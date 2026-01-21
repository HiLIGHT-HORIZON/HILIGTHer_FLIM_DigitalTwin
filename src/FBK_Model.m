classdef FBK_Model < handle
    % FBK_MODEL - Domain model for the FBK HILIGHTer Edition.
    % Handles data importing, gate shape distillation, and iterative reconvolution.
    % Physical Units: Time [ns], Counts [photons], Lifetime [ns]

    properties
        RawData       % (nY, nX, nGates) matrix of photon counts [counts] (Current Working Data)
        RawDataOriginal % (nY, nX, nGates) matrix of photon counts [counts] (Backup)
        LaserDelay    % Vector of laser delay values from sweep [ns]
        MinGateData   % Table containing laser delay, gate width, and counts
        LaserPulse    % Struct with .t and .p for laser impulse response

        GateShapes    % (nGates x nTime) Matrix of time-domain gate profiles
        TimeVector    % High-resolution time vector for reconvolution [ns]

        ExperimentalExactGates % [nGates x nTime] Loaded from CSV
        ExperimentalExactTime  % [1 x nTime] Time axis for exact gates

        SweepFittedSigma = 0.1 % [ns] Globally fitted smoothing from sweep
        SweepFittedWidths      % [1 x nSwept] Fitted widths from sweep

        % Fitting Results
        TauMap        % Map of fitted lifetimes [ns]
        AMap          % Map of correlated amplitudes [counts]
        BMap          % Map of background levels [counts]
        Chi2Map       % Map of reduced chi-squared values

        % Settings
        ThresholdMin = 10 % [counts] Minimum photon count per pixel
        ThresholdMax = Inf % [counts] Maximum photon count per pixel
        ThresholdSource = 'Total' % 'Total' or 'Gate1'
        DtInput = 0.05 % [ns] Interpolation step for gate distillation
        BgOption = 'fit' % 'fit', 'fix_manual', 'gate4' or 'measurement'
        BgData          % (nY, nX) matrix of background counts
        FixedBgValue = 0 % [counts] Manual background level per pixel (for 'fix_manual')
        BgMeanMeasurement = 0 % mean background per unit gate area
        GateMethod = 'ideal' % 'experimental', 'synthetic', or 'ideal'
        GateEdges = [0, 1.1, 3.4, 9.0, 25.0] % [ns] Default edges
        Skewness = 0 % [ps] Gaussian smoothing for ideal gates
        UseEIRF = true % Use experimental IRF for reconvolution
        MedianFilterSize = 0 % [pixels] Kernel size for median filtering (0 = off)

        % Simulation Parameters
        SimA = 1000
        SimB = 0
        SimTau1 = 1.5
        SimTau2 = 4.5
        SimRes = 64

        % Distilled synthetic kinetics
        SyntheticRise = NaN % [ns]
        SyntheticFall = NaN % [ns]

        % Legacy settings for memory
        LastSettingsFile = 'AppProperties/fbk_settings.mat'

        IsAborted = false % Flag to interrupt long-running loops
    end

    methods
        function obj = FBK_Model()
            % Constructor - initialize empty state
            obj.RawData = [];
            obj.RawDataOriginal = [];
            obj.GateShapes = [];
            obj.loadSettings();
        end

        function importSweepCSV(obj, filePath)
            % IMPORTSWEEPCSV - Imports the gate sweep characterization CSV.
            opts = detectImportOptions(filePath);
            obj.MinGateData = readtable(filePath, opts);
        end

        function importExactGatesCSV(obj, filePath)
            % IMPORTEXACTGATESCSV - Imports the 4 exact experimental gates.
            % Expected format: [Time_ns, G1, G2, G3, G4]
            data = readmatrix(filePath);
            obj.ExperimentalExactTime = data(:,1)';
            obj.ExperimentalExactGates = data(:, 2:end)'; % (nGates x nTime)
        end

        function importLaserCSV(obj, filePath)
            % IMPORTLASERCSV - Imports the laser_236mW.csv file.
            arguments
                obj
                filePath (1,1) string
            end
            data = readmatrix(filePath);
            % Sort by time [ns]
            [~, idx] = sort(data(:,1));
            obj.LaserPulse.t = data(idx, 1) * 1e-9; % If original is ns, convert?
            % Based on Jupyter: tl = arr[:,0]*1e-9; t_interp = np.arange(0.5,2.5,dt)*1e-9
            % Actually the Jupyter script converts to seconds for some reason then works with ns?
            % Let's stick to ns internally to avoid confusion.
            obj.LaserPulse.t = data(idx, 1); % [ns]
            obj.LaserPulse.p = data(idx, 2);
        end

        function importFBKDataFolder(obj, folderPath)
            % IMPORTFBKDATAFOLDER - Imports 4-gate binary data from a legacy FBK folder.
            % Expects files: image2D_G0.bin, ... G3.bin inside the folder.
            % Performs cumulative subtraction and orientation correction.

            arguments
                obj
                folderPath (1,1) string
            end

            % Define filenames
            files = ["image2D_G0.bin", "image2D_G1.bin", "image2D_G2.bin", "image2D_G3.bin"];
            rawCells = cell(1, 4);

            % 1. Read Raw Binary Data (uint32)
            for i = 1:4
                fullPath = fullfile(folderPath, files(i));
                if ~exist(fullPath, 'file')
                    error('FBK Data file missing: %s', fullPath);
                end
                fid = fopen(fullPath, 'r');
                cleaner = onCleanup(@() fclose(fid));
                rawCells{i} = fread(fid, 'uint32');
                % File closes automatically due to onCleanup
            end

            % 2. Decode Cumulative Gates
            % Logic from displayFLIM.m:
            % G0vec = G0raw;
            % G1vec = G1raw - G0raw; ...
            g0 = rawCells{1};
            g1 = rawCells{2} - rawCells{1};
            g2 = rawCells{3} - rawCells{2};
            g3 = rawCells{4} - rawCells{3};

            gateVecs = {g0, g1, g2, g3};

            % 3. Reshape and Orient
            % displayFLIM.m: fliplr(rot90(rot90(rot90(reshape(..., 100, 100)))))
            % rot90 x 3 is equivalent to rot90(x, -1) (clockwise) or rot90(x, 3).

            % Check size - assume 100x100 based on legacy, but should be dynamic if possible?
            % displayFLIM hardcodes 100x100. Length is 10000.
            nPixels = length(g0);
            dim = sqrt(nPixels);
            if floor(dim) ~= dim
                error('Data length %d is not a perfect square. Cannot reshape.', nPixels);
            end

            data = zeros(dim, dim, 4);

            for k = 1:4
                mat = reshape(gateVecs{k}, dim, dim);
                % Apply orientation transform: Rotated 270 deg (or -90) then flipped LR
                % rot90(A, 3) is 270 counter-clockwise.
                mat = rot90(mat, 3);
                mat = fliplr(mat);
                data(:, :, k) = mat;
            end
            obj.setRawData(data);
        end

        function distillGates(obj)
            % DISTILLGATES - Infers gate shapes based on current method.
            switch lower(obj.GateMethod)
                case 'experimental'
                    obj.calculateExperimentalGates();
                case 'synthetic'
                    obj.calculateSyntheticGates();
                case 'ideal'
                    obj.calculateIdealGates(true); % Use manual skewness
            end
        end

        function runFit(obj, pixelData)
            % RUNFIT - Main iterative reconvolution fitting loop.
            % pixelData: (nY, nX, nGates) matrix
            arguments
                obj
                pixelData (:,:,:) double = obj.RawData
            end

            if isempty(pixelData) || isempty(obj.GateShapes)
                error('Data or GateShapes missing. Cannot fit.');
            end

            [nY, nX, nGates] = size(pixelData);
            obj.TauMap = nan(nY, nX);
            obj.AMap = nan(nY, nX);
            obj.BMap = nan(nY, nX);
            obj.Chi2Map = nan(nY, nX);

            % Flatten and Threshold
            M = nY * nX;
            flatData = reshape(pixelData, M, nGates)'; % (nGates x M)

            if strcmpi(obj.ThresholdSource, 'Gate1')
                metric = flatData(1, :);
            else
                metric = sum(flatData, 1);
            end

            validIdx = find(metric > obj.ThresholdMin & metric < obj.ThresholdMax);

            options = optimset('Display', 'off', 'TolX', 1e-4);

            % Pre-calculate Global Background if using 'gate4'
            globalBgVal = 0;
            if strcmpi(obj.BgOption, 'gate4') && nGates >= 4
                % 1. Calculate Mean Counts in Gate 4 (using valid pixels to avoid masking artifacts)
                % Only use pixels that have passed the threshold to avoid skewing by empty areas
                if ~isempty(validIdx)
                    g4_counts = flatData(4, validIdx);
                    mean_g4 = mean(g4_counts);

                    % 2. Scaling Factor (Wtotal / W4)
                    Wj = sum(obj.GateShapes, 2);
                    if Wj(4) > 0
                        ratio = sum(Wj) / Wj(4);
                        globalBgVal = mean_g4 * ratio;
                    end
                end
            end

            % Loop over valid pixels
            obj.IsAborted = false;
            for i = validIdx
                if obj.IsAborted, return; end

                % Periodically allow UI events (like Close) to be processed
                if mod(i, 50) == 0, drawnow limitrate; end

                obs = flatData(:, i);

                % Determine pixel-specific fixed background if needed
                pixelBg = 0;
                if strcmpi(obj.BgOption, 'measurement') && ~isempty(obj.BgData)
                    pixelBg = obj.BgData(i);
                elseif strcmpi(obj.BgOption, 'gate4')
                    pixelBg = globalBgVal;
                end

                % Fit with initial values (A=photoncount, Tau=3ns, B=0)
                % We use fminsearch for Tau starting at 3.0 ns.
                % A and B are computed analytically starting from the requested levels.
                tau0 = 3.0;
                tau_est = fminsearch(@(t) obj.objFunc(t, obs, pixelBg), tau0, options);

                % Final solve for A and B at optimal Tau
                [chi2, a, b] = obj.objFunc(tau_est, obs, pixelBg);

                obj.TauMap(i) = tau_est;
                obj.AMap(i) = a;
                obj.BMap(i) = b;
                obj.Chi2Map(i) = chi2 / max(1, nGates - 2); % Reduced Chi2
            end
        end

        function saveSettings(obj)
            % Persistent settings and gate characterization
            s.BgOption = obj.BgOption;
            s.FixedBgValue = obj.FixedBgValue;
            s.ThresholdSource = obj.ThresholdSource;
            s.GateMethod = obj.GateMethod;
            s.ThresholdMin = obj.ThresholdMin;
            s.ThresholdMax = obj.ThresholdMax;
            s.GateEdges = obj.GateEdges;
            s.GateEdges = obj.GateEdges;
            s.GateShapes = obj.GateShapes;
            s.TimeVector = obj.TimeVector;
            s.MedianFilterSize = obj.MedianFilterSize;

            % Save characterization data if available
            s.MinGateData = obj.MinGateData;
            s.LaserPulse = obj.LaserPulse;
            s.LaserDelay = obj.LaserDelay;
            s.Skewness = obj.Skewness;
            s.UseEIRF = obj.UseEIRF;

            % Simulation Params
            s.SimA = obj.SimA;
            s.SimB = obj.SimB;
            s.SimTau1 = obj.SimTau1;
            s.SimTau2 = obj.SimTau2;
            s.SimRes = obj.SimRes;

            if ~exist(fileparts(obj.LastSettingsFile), 'dir')
                mkdir(fileparts(obj.LastSettingsFile));
            end
            save(obj.LastSettingsFile, '-struct', 's');
        end

        function loadSettings(obj)
            if exist(obj.LastSettingsFile, 'file')
                s = load(obj.LastSettingsFile);
                obj.BgOption = s.BgOption;
                obj.GateMethod = s.GateMethod;

                if isfield(s, 'FixedBgValue'), obj.FixedBgValue = s.FixedBgValue; end

                % Migration: Map 'fix0' to 'fix_manual' with value 0
                if strcmpi(obj.BgOption, 'fix0')
                    obj.BgOption = 'fix_manual';
                    obj.FixedBgValue = 0;
                end

                % Backward compatibility for single threshold
                if isfield(s, 'Threshold')
                    obj.ThresholdMin = s.Threshold;
                elseif isfield(s, 'ThresholdMin')
                    obj.ThresholdMin = s.ThresholdMin;
                end

                if isfield(s, 'ThresholdSource')
                    obj.ThresholdSource = s.ThresholdSource;
                else
                    obj.ThresholdSource = 'Total';
                end

                if isfield(s, 'ThresholdMax'), obj.ThresholdMax = s.ThresholdMax; end

                if isfield(s, 'GateEdges')
                    % Migration: If legacy default edges are found, upgrade them to new defaults
                    legacyEdges = [0.5, 1.5, 2.5, 3.5, 4.5];
                    if isequal(s.GateEdges, legacyEdges)
                        obj.GateEdges = [0, 1.1, 3.4, 9.0, 25.0];
                    else
                        obj.GateEdges = s.GateEdges;
                    end
                end
                if isfield(s, 'GateShapes'), obj.GateShapes = s.GateShapes; end
                if isfield(s, 'TimeVector'), obj.TimeVector = s.TimeVector; end
                if isfield(s, 'MedianFilterSize'), obj.MedianFilterSize = s.MedianFilterSize; end

                % Load characterization data
                if isfield(s, 'MinGateData'), obj.MinGateData = s.MinGateData; end
                if isfield(s, 'LaserPulse'), obj.LaserPulse = s.LaserPulse; end
                if isfield(s, 'LaserDelay'), obj.LaserDelay = s.LaserDelay; end
                if isfield(s, 'Skewness'), obj.Skewness = s.Skewness; end
                if isfield(s, 'UseEIRF'), obj.UseEIRF = s.UseEIRF; end

                % Sim Params
                if isfield(s, 'SimA'), obj.SimA = s.SimA; end
                if isfield(s, 'SimB'), obj.SimB = s.SimB; end
                if isfield(s, 'SimTau1'), obj.SimTau1 = s.SimTau1; end
                if isfield(s, 'SimTau2'), obj.SimTau2 = s.SimTau2; end
                if isfield(s, 'SimRes'), obj.SimRes = s.SimRes; end
            end
        end

        function simulateData(obj, A, tau1, tau2, B, nY, nX)
            % SIMULATEDATA - Generates a synthetic dataset [nY, nX, nGates] with a tau gradient
            arguments
                obj
                A (1,1) double = 1000
                tau1 (1,1) double = 1.0
                tau2 (1,1) double = 5.0
                B (1,1) double = 10
                nY (1,1) double = 64
                nX (1,1) double = 64
            end

            if isempty(obj.GateShapes)
                error('GateShapes must be defined before simulation.');
            end

            nGates = size(obj.GateShapes, 1);
            synData = zeros(nY, nX, nGates);

            % Reset fitting results
            obj.TauMap = [];
            obj.AMap = [];
            obj.BMap = [];
            obj.Chi2Map = [];

            tVec = obj.TimeVector(:);

            % Lifetime gradient from left to right along X
            tauValues = linspace(tau1, tau2, nX);
            termB = sum(obj.GateShapes, 2);

            obj.IsAborted = false;
            for x = 1:nX
                if obj.IsAborted, return; end
                if mod(x, 10) == 0, drawnow limitrate; end

                tau = tauValues(x);
                % Decay D(t) = exp(-t/tau) for this column
                decay = exp(-tVec / tau);

                % Model counts per gate
                termA = obj.GateShapes * decay;

                % RENORMALIZATION: Scale termA so sum(termA) = 1
                % This makes 'A' the total fluorescence photons per pixel
                termA = termA / sum(termA);

                pixelCounts = A * termA + B * termB;

                % Add Poisson noise and expand to column
                for g = 1:nGates
                    synData(:, x, g) = poissrnd(pixelCounts(g), [nY, 1]);
                end
            end
            obj.setRawData(synData);
        end

        function exportResults(obj, filePath)
            % EXPORTRESULTS - Saves fitting maps to a .mat file.
            results.TauMap = obj.TauMap;
            results.AMap = obj.AMap;
            results.BMap = obj.BMap;
            results.Chi2Map = obj.Chi2Map;
            results.Timestamp = char(datetime('now'));
            save(filePath, '-struct', 'results');
        end
    end

    methods
        function characterizeHardware(obj)
            % Scientific workflow: Mirror Sweep -> Global Fit (Gaussian Rect)
            if isempty(obj.MinGateData), return; end

            % 1. Extract and Mirror Sweep Data
            t_orig = obj.MinGateData.LaserDelay;
            % Mirroring curves as requested (assume time axis inversion)
            t_sweep = (max(t_orig) + min(t_orig)) - t_orig;

            widths_labels = unique(obj.MinGateData.GateWidth);
            nSwept = length(widths_labels);
            sweep_data = cell(nSwept, 1);

            for i = 1:nSwept
                rows = obj.MinGateData.GateWidth == widths_labels(i);
                td = t_sweep(rows);
                cd = obj.MinGateData.Counts(rows);
                [td, idx] = sort(td);
                sweep_data{i} = [td(:), cd(idx)];
            end

            % 2. Global Fit: Sigma (global) and Widths (individual)
            % Model: Rect(w) * Gaussian(sigma) * Laser(opt)
            init_sigma = 0.2;
            init_widths = widths_labels; % Use labels as first guess
            params0 = [init_sigma; init_widths(:)];

            options = optimset('Display', 'off', 'TolX', 1e-3);
            % Objective: minimize total RMSE across all swept gates
            fit_obj = @(p) obj.sweepGlobalFunc(p, sweep_data);

            params_opt = fminsearch(fit_obj, params0, options);

            obj.SweepFittedSigma = abs(params_opt(1));
            obj.SweepFittedWidths = abs(params_opt(2:end));

            % 3. Update Synthetic State
            if strcmpi(obj.GateMethod, 'synthetic')
                obj.calculateSyntheticGates();
            end
        end

        function err = sweepGlobalFunc(obj, params, dataCells)
            sigma = abs(params(1));
            widths = abs(params(2:end));
            nS = length(dataCells);
            err = 0;

            for i = 1:nS
                t = dataCells{i}(:,1);
                obs = dataCells{i}(:,2);
                obs = obs / max(obs(:) + 1e-10);

                % Model: Rect * Gaussian * Laser
                % Approximation: Evaluating analytical response or numerical conv
                w = widths(i);
                % Ideal Rect centered at roughly middle of t
                mid = mean(t);
                rect = (t >= (mid - w/2)) & (t <= (mid + w/2));

                % Gaussian Kernel
                dt = mean(diff(t));
                t_k = -4*sigma : dt : 4*sigma;
                kern = exp(-t_k.^2 / (2*sigma^2));

                % Convolve with Laser if present
                if ~isempty(obj.LaserPulse)
                    L = interp1(obj.LaserPulse.t, obj.LaserPulse.p, t_k, 'linear', 0);
                    kern = conv(kern, L, 'same');
                end

                kern = kern / sum(kern);
                pred = conv(double(rect), kern, 'same');
                pred = pred / max(pred(:) + 1e-10);

                err = err + sum((obs - pred(:)).^2);
            end
        end

        function calculateExperimentalGates(obj)
            % Use loaded exact profiles if available
            if ~isempty(obj.ExperimentalExactGates)
                obj.GateShapes = obj.ExperimentalExactGates;
                obj.TimeVector = obj.ExperimentalExactTime;
                return;
            end
        end

        function calculateSyntheticGates(obj)
            % Synthetic gates = Ideal geometry + Sweep-fitted Sigma
            backup_skew = obj.Skewness;
            obj.Skewness = obj.SweepFittedSigma * 1000; % [ps]
            obj.calculateIdealGates(false); % Don't use manual skewness
            obj.Skewness = backup_skew;
        end

        function calculateIdealGates(obj, useManualSkewness)
            if nargin < 2, useManualSkewness = true; end

            % Ensure TimeVector contains the edges
            if isempty(obj.TimeVector) || obj.TimeVector(1) > obj.GateEdges(1) || obj.TimeVector(end) < obj.GateEdges(end)
                obj.TimeVector = (obj.GateEdges(1)-2) : obj.DtInput : (obj.GateEdges(end)+2);
            end

            nGates = length(obj.GateEdges) - 1;
            obj.GateShapes = zeros(nGates, length(obj.TimeVector));
            for i = 1:nGates
                mask = (obj.TimeVector >= obj.GateEdges(i)) & (obj.TimeVector < obj.GateEdges(i+1));
                obj.GateShapes(i, :) = mask(:)';
            end

            % Apply Skewness
            sig_val = obj.Skewness;
            if ~useManualSkewness
                sig_val = obj.SweepFittedSigma * 1000;
            end

            if sig_val > 0
                sigma = sig_val / 1000; % [ns]
                t_k = (-4*sigma) : obj.DtInput : (4*sigma);
                kernel = exp(-t_k.^2 / (2 * sigma^2));

                % Convolve with Laser if EIRF requested and present
                if obj.UseEIRF && ~isempty(obj.LaserPulse)
                    L = interp1(obj.LaserPulse.t, obj.LaserPulse.p, t_k, 'linear', 0);
                    kernel = conv(kernel, L, 'same');
                end

                kernel = kernel / sum(kernel);
                obj.GateShapes = conv2(obj.GateShapes, kernel, 'same');
            end
        end
    end

    methods
        function setRawData(obj, data)
            % SETRAWDATA - Populates RawData and RawDataOriginal
            obj.RawDataOriginal = data;
            obj.RawData = data;

            % Re-apply filters if necessary
            obj.applyMedianFilter();
        end

        function applyMedianFilter(obj)
            if isempty(obj.RawDataOriginal), return; end

            k = obj.MedianFilterSize;
            if k <= 1
                obj.RawData = obj.RawDataOriginal;
            else
                % Apply medfilt2 to each gate channel
                [nY, nX, nG] = size(obj.RawDataOriginal);
                filtered = zeros(nY, nX, nG);
                for g = 1:nG
                    filtered(:,:,g) = medfilt2(obj.RawDataOriginal(:,:,g), [k k]);
                end
                obj.RawData = filtered;
            end
        end
    end

    methods (Access = private)
        function [ssq, a, b] = objFunc(obj, tau, obs, fixedBg)
            % Penalty for invalid tau (used by fminsearch)
            if tau <= 0, ssq = 1e15; a = 0; b = 0; return; end

            % 1. Build Signal Profile Pj(tau)
            t = obj.TimeVector(:);
            decay = exp(-t / tau);
            if obj.UseEIRF && ~isempty(obj.LaserPulse)
                % Interp laser to current time vector
                L = interp1(obj.LaserPulse.t, obj.LaserPulse.p, t, 'linear', 0);
                L = L / sum(L);
                if length(t) > 1, decay = conv(decay, L, 'same'); end
            end
            Pj = obj.GateShapes * decay;
            Pj = Pj / sum(Pj); % Normalize signal profile (sum=1)

            % 2. Build Background Profile Qj
            Wj = sum(obj.GateShapes, 2); % Gate areas
            Wtotal = sum(Wj);
            Qj = Wj / Wtotal; % Normalize background profile (sum=1)

            Dtotal = sum(obs);

            % 3. Determine Background Fraction 'k'
            if strcmpi(obj.BgOption, 'fix_manual')
                % Use manually fixed background value
                % k = FixedBg / TotalCounts
                k = min(1, obj.FixedBgValue / max(Dtotal, 1));
            elseif strcmpi(obj.BgOption, 'gate4')
                % Use provided total background for this pixel
                k = min(1, fixedBg / max(Dtotal, 1));


                k = max(0, min(1, k));
            else % 'fit' mode
                % Find k that minimizes WLS: sum (wj * (obs - F(k))^2)
                % F(k) = Dtotal * (Pj + k*(Qj - Pj))
                % Let Vj = Qj - Pj. Then F(k) = Dtotal*Pj + k*Dtotal*Vj
                % This is a linear fit for k: (obs - offset) = k * slope
                Vj = Qj - Pj;
                offset = Dtotal * Pj;
                slope  = Dtotal * Vj;

                % Analytical WLS for k (one iteration using Poisson weights from offset)
                % To be precise, we solve: sum( wj * (obs - offset - k*slope) * slope ) = 0
                weights = 1 ./ max(offset, 1);
                k = (sum(weights .* (obs - offset) .* slope)) / (sum(weights .* slope.^2) + 1e-10);

                % Physical constraint: k in [0, 1]
                k = max(0, min(1, k));
            end

            % 4. Final Amplitudes
            a = Dtotal * (1 - k);               % Signal Photons
            b = (Dtotal * k) / max(Wtotal, 1e-10); % Backgd counts per unit area

            pred = a * Pj + b * Wj;
            residuals = (obs - pred);
            weights = 1 ./ max(pred, 1);
            ssq = sum(residuals.^2 .* weights);
        end

    end
end
