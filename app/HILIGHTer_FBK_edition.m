classdef HILIGHTer_FBK_edition < matlab.apps.AppBase

    % Properties target components
    properties (Access = public)
        UIFigure      matlab.ui.Figure
        GridLayout    matlab.ui.container.GridLayout
        LeftPanel     matlab.ui.container.Panel
        RightPanel    matlab.ui.container.Panel
        TabGroup      matlab.ui.container.TabGroup
        GatesTab      matlab.ui.container.Tab
        DataTab       matlab.ui.container.Tab

        % Left Panel Components
        btnImportGates      matlab.ui.control.Button
        btnImportExactGates matlab.ui.control.Button
        btnImportLaser      matlab.ui.control.Button
        btnImportData  matlab.ui.control.Button
        ddGateMethod   matlab.ui.control.DropDown
        ddBgOption     matlab.ui.control.DropDown
        btnImportBg    matlab.ui.control.Button
        spnThreshold   matlab.ui.control.NumericEditField
        btnRunFit      matlab.ui.control.Button
        btnSaveResults matlab.ui.control.Button
        chkUseEIRF     matlab.ui.control.CheckBox
        btnDistillGates matlab.ui.control.Button
        spnEdges       (1, 5) matlab.ui.control.NumericEditField

        % Right Panel Components (Tab: Gate Characterization)
        axSweep        matlab.ui.control.UIAxes
        axLaser        matlab.ui.control.UIAxes
        axIdeal        matlab.ui.control.UIAxes
        axExpGates     matlab.ui.control.UIAxes
        axSynthGates   matlab.ui.control.UIAxes

        % Skewness and Method
        spnSkewness    matlab.ui.control.Spinner

        % Simulation Inputs
        spnSimA        matlab.ui.control.NumericEditField
        spnSimTau1     matlab.ui.control.NumericEditField
        spnSimTau2     matlab.ui.control.NumericEditField
        spnSimB        matlab.ui.control.NumericEditField
        spnSimRes      matlab.ui.control.Spinner
        btnSimulate    matlab.ui.control.Button

        % Right Panel Components (Tab: DATA)
        glData         matlab.ui.container.GridLayout
        axTotal        matlab.ui.control.UIAxes
        axGate1        matlab.ui.control.UIAxes
        axGate2        matlab.ui.control.UIAxes
        axGate3        matlab.ui.control.UIAxes
        axGate4        matlab.ui.control.UIAxes
        axGateSumBar   matlab.ui.control.UIAxes
        axMapA         matlab.ui.control.UIAxes
        axMapTau       matlab.ui.control.UIAxes
        axMapB         matlab.ui.control.UIAxes
        axMapChi2      matlab.ui.control.UIAxes
        axResiduals    matlab.ui.control.UIAxes

        % Row 3: Histograms
        axHistA        matlab.ui.control.UIAxes
        axHistTau      matlab.ui.control.UIAxes
        axHistB        matlab.ui.control.UIAxes
        axHistChi2     matlab.ui.control.UIAxes

        % Histogram Settings
        spnHistRes     matlab.ui.control.Spinner

        % Interactive Selection
        SelectedPixel  (1,2) double = [1, 1]
        hCrossH        matlab.graphics.chart.primitive.Line
        hCrossV        matlab.graphics.chart.primitive.Line

    end

    properties (Access = private)
        Model         FBK_Model % MVC: Model handle
        LastSimRes    double = 64 % State for power-of-two increments
        LastHistRes   double = 64 % State for power-of-two increments
        IsUpdateBusy  logical = false % Guard for UI re-entry
    end

    methods (Access = private)

        function createComponents(app)
            % CREATECOMPONENTS - Initialize UI layout
            app.UIFigure = uifigure('Name', 'HILIGHTer FBK Edition', ...
                'Position', [100 100 1400 850], ...
                'CloseRequestFcn', @(~,~) app.onAppClose());
            app.GridLayout = uigridlayout(app.UIFigure, [1, 2]);
            app.GridLayout.ColumnWidth = {280, '1x'};

            % Left Panel: Controls
            app.LeftPanel = uipanel(app.GridLayout, 'Title', 'Settings & Controls');
            glLeft = uigridlayout(app.LeftPanel, [6, 1]);
            glLeft.RowHeight = {35, 280, 155, 205, 35, '1x'};
            glLeft.RowSpacing = 10;
            glLeft.Padding = [10 10 10 10];

            % 1. Import Data
            app.btnImportData = uibutton(glLeft, 'Text', '1. Import Sample Data', 'ButtonPushedFcn', @(~,~) app.importDataCallback(), ...
                'Tooltip', 'Load experimental multi-gate data from .sdt or .mat files. Data should be a 3D matrix (Y, X, Gates).');
            app.btnImportData.Layout.Row = 1;

            % 2. IRF & Characterization Section
            pIRF = uipanel(glLeft, 'Title', '2. IRF & Characterization');
            pIRF.Layout.Row = 2;
            glIRF = uigridlayout(pIRF, [6, 3]);
            glIRF.Padding = [5 5 5 5];
            glIRF.RowHeight = {25, 22, 25, 35, 50, 35};
            glIRF.ColumnWidth = {'1x', '1x', '1x'};

            app.btnImportGates = uibutton(glIRF, 'Text', 'Import Gate Sweep', 'FontSize', 9, 'ButtonPushedFcn', @(~,~) app.importSweepCallback(), ...
                'Tooltip', 'Import hardware gate measurements (Experimental Sweep) from a CSV file to characterize gate kinetics.');
            app.btnImportGates.Layout.Row = 1; app.btnImportGates.Layout.Column = 1;

            app.btnImportExactGates = uibutton(glIRF, 'Text', 'Import Gates', 'FontSize', 9, 'ButtonPushedFcn', @(~,~) app.importExactGatesCallback(), ...
                'Tooltip', 'Import exactly measured profiles for the 4 experimental gates.');
            app.btnImportExactGates.Layout.Row = 1; app.btnImportExactGates.Layout.Column = 2;

            app.btnImportLaser = uibutton(glIRF, 'Text', 'Import Laser', 'FontSize', 9, 'ButtonPushedFcn', @(~,~) app.importLaserCallback(), ...
                'Tooltip', 'Load the laser impulse response (IRF) measurement.');
            app.btnImportLaser.Layout.Row = 1; app.btnImportLaser.Layout.Column = 3;

            app.chkUseEIRF = uicheckbox(glIRF, 'Text', 'Use eIRF', 'Value', true, 'Enable', 'off', 'ValueChangedFcn', @(~,~) app.updateUseEIRF(), ...
                'Tooltip', 'Enable to convolve the theoretical decay model with the experimental laser pulse during fitting.');
            app.chkUseEIRF.Layout.Row = 2; app.chkUseEIRF.Layout.Column = [1 3];

            app.btnDistillGates = uibutton(glIRF, 'Text', 'Distill Gate Shapes', 'ButtonPushedFcn', @(~,~) app.distillGatesCallback(), ...
                'Tooltip', 'Trigger the hardware characterization workflow: Fits global kinetics from the gate sweep.');
            app.btnDistillGates.Layout.Row = 3; app.btnDistillGates.Layout.Column = [1 3];

            % Gate Method (inside IRF)
            uilabel(glIRF, 'Text', 'Method:', 'FontSize', 10);
            app.ddGateMethod = uidropdown(glIRF, 'Items', {'Ideal', 'Experimental', 'Synthetic'}, 'ValueChangedFcn', @(~,~) app.updateGateMethod(), ...
                'Tooltip', 'Select gate representation.');
            app.ddGateMethod.Layout.Row = 4; app.ddGateMethod.Layout.Column = [2 3];
            % Method label needs its own layout too or it will overlap
            lblM = uilabel(glIRF, 'Text', 'Method:', 'FontSize', 10);
            lblM.Layout.Row = 4; lblM.Layout.Column = 1;

            % Gate Edges (inside IRF)
            glE = uigridlayout(glIRF, [2, 1]);
            glE.Padding = [0 0 0 0]; glE.RowSpacing = 1;
            glE.Layout.Row = 5; glE.Layout.Column = [1 3];
            uilabel(glE, 'Text', 'Gate Edges [ns]:', 'FontSize', 10);
            glEdges = uigridlayout(glE, [1, 5]);
            glEdges.Padding = [0 0 0 0]; glEdges.ColumnSpacing = 2;
            app.spnEdges = [uieditfield(glEdges, 'numeric', 'FontSize', 9), ...
                uieditfield(glEdges, 'numeric', 'FontSize', 9), ...
                uieditfield(glEdges, 'numeric', 'FontSize', 9), ...
                uieditfield(glEdges, 'numeric', 'FontSize', 9), ...
                uieditfield(glEdges, 'numeric', 'FontSize', 9)];
            for i = 1:5
                app.spnEdges(i).ValueChangedFcn = @(~,~) app.updateEdges();
                app.spnEdges(i).Tooltip = sprintf('Position of Gate Edge %d [ns]', i);
            end

            % Skewness (inside IRF)
            lblS = uilabel(glIRF, 'Text', 'Skewness [ps]:', 'FontSize', 10);
            lblS.Layout.Row = 6; lblS.Layout.Column = 1;
            app.spnSkewness = uispinner(glIRF, 'Value', 0, 'Step', 50, 'ValueDisplayFormat', '%d', 'LowerLimit', 0, ...
                'ValueChangedFcn', @(~,~) app.updateSkewness(), 'Tooltip', 'Std of Gaussian used to smooth ideal gates.');
            app.spnSkewness.Layout.Row = 6; app.spnSkewness.Layout.Column = [2 3];

            % 3. Simulation Section
            pSim = uipanel(glLeft, 'Title', '3. Simulation Params');
            pSim.Layout.Row = 3;
            glSim = uigridlayout(pSim, [4, 4]);
            glSim.Padding = [5 5 5 5];
            glSim.RowHeight = {20, 20, 20, 28};
            glSim.ColumnWidth = {'fit', '1x', 'fit', '1x'};

            uilabel(glSim, 'Text', 'A:');
            app.spnSimA = uieditfield(glSim, 'numeric', 'Value', 1000, 'ValueChangedFcn', @(~,~) app.updateSimA(), 'Tooltip', 'Amplitude (photon counts).');
            uilabel(glSim, 'Text', 'B:');
            app.spnSimB = uieditfield(glSim, 'numeric', 'Value', 10, 'ValueChangedFcn', @(~,~) app.updateSimB(), 'Tooltip', 'Background level.');

            uilabel(glSim, 'Text', 'Tau 1:');
            app.spnSimTau1 = uieditfield(glSim, 'numeric', 'Value', 1.0, 'ValueChangedFcn', @(~,~) app.updateSimTau1(), 'Tooltip', 'Start lifetime [ns].');
            uilabel(glSim, 'Text', 'Tau 2:');
            app.spnSimTau2 = uieditfield(glSim, 'numeric', 'Value', 5.0, 'ValueChangedFcn', @(~,~) app.updateSimTau2(), 'Tooltip', 'End lifetime [ns].');

            uilabel(glSim, 'Text', 'Pixel Res:');
            app.spnSimRes = uispinner(glSim, 'Value', 64, 'ValueChangedFcn', @(~,~) app.updateSimRes(), 'Tooltip', 'Spatial Res.');
            app.spnSimRes.Layout.Column = [2 4];

            app.btnSimulate = uibutton(glSim, 'Text', 'Generate Simulated Data', 'ButtonPushedFcn', @(~,~) app.simulateCallback(), ...
                'Tooltip', 'Generate synthetic data with current parameters.', 'BackgroundColor', [0.9 0.9 1.0]);
            app.btnSimulate.Layout.Row = 4; app.btnSimulate.Layout.Column = [1 4];

            % 4. Data Fitting Section
            pFitting = uipanel(glLeft, 'Title', '4. Data Fitting');
            pFitting.Layout.Row = 4;
            glFit = uigridlayout(pFitting, [4, 1]);
            glFit.Padding = [5 5 5 5];
            glFit.RowHeight = {42, 38, 35, 25};
            glFit.RowSpacing = 5;

            % Bg
            glB = uigridlayout(glFit, [2, 1]); glB.Padding = [0 0 0 0]; glB.RowSpacing = 1;
            uilabel(glB, 'Text', 'Background Mode:', 'FontSize', 10);
            glB2 = uigridlayout(glB, [1, 2]); glB2.Padding = [0 0 0 0]; glB2.ColumnWidth = {'1x', 30};
            app.ddBgOption = uidropdown(glB2, 'Items', {'Fit', 'Fix to 0', 'Measurement'}, 'ValueChangedFcn', @(~,~) app.updateBgOption(), ...
                'Tooltip', 'Choose how to handle background: Fit (pixel-wise estimate), Fix to 0, or Measurement (uses imported background file).');
            app.btnImportBg = uibutton(glB2, 'Text', '📁', 'Tooltip', 'Import Background Map', 'Enable', 'off', 'ButtonPushedFcn', @(~,~) app.importBgCallback());

            % Threshold
            glT = uigridlayout(glFit, [1, 2]); glT.Padding = [0 0 0 0];
            uilabel(glT, 'Text', 'Threshold:', 'FontSize', 10);
            app.spnThreshold = uieditfield(glT, 'numeric', 'Value', 10, 'ValueChangedFcn', @(~,~) app.updateThreshold(), ...
                'Tooltip', 'Minimum total photon count required to perform a fit on a pixel. Areas below this are ignored.');

            % Fit Button
            app.btnRunFit = uibutton(glFit, 'Text', 'Run Iterative Fit', 'BackgroundColor', [0.8 1.0 0.8], 'ButtonPushedFcn', @(~,~) app.runFitCallback(), ...
                'Tooltip', 'Execute the iterative reconvolution fitting algorithm across all valid pixels to extract A, Tau, and B maps.');

            % Hist Res
            glH = uigridlayout(glFit, [1, 2]); glH.Padding = [0 0 0 0];
            uilabel(glH, 'Text', 'Hist Res:', 'FontSize', 10);
            app.spnHistRes = uispinner(glH, 'Value', 64, 'ValueChangedFcn', @(~,~) app.updateHistRes(), ...
                'Tooltip', 'Number of bins used for the analysis maps histograms.');

            % 5. Save Results
            app.btnSaveResults = uibutton(glLeft, 'Text', 'Save Results (.mat)', 'ButtonPushedFcn', @(~,~) app.saveResultsCallback(), ...
                'Tooltip', 'Export current fitting results (Tau, A, B, Chi2 maps) to a MATLAB .mat file.');
            app.btnSaveResults.Layout.Row = 5;

            % Right Panel: Visualization
            app.RightPanel = uipanel(app.GridLayout, 'Title', 'Analysis & Results');
            glRight = uigridlayout(app.RightPanel, [1, 1]);
            app.TabGroup = uitabgroup(glRight);

            % Tab 1: Gate Characterization Dashboard
            app.GatesTab = uitab(app.TabGroup, 'Title', 'Gate Characterization');
            glGates = uigridlayout(app.GatesTab, [2, 3]);
            glGates.RowHeight = {'1x', '1x'};

            % Row 1
            app.axSweep = uiaxes(glGates); title(app.axSweep, 'Experimental Sweep (Raw)');
            app.axLaser = uiaxes(glGates); title(app.axLaser, 'Laser Pulse (IRF)');
            app.axIdeal = uiaxes(glGates); title(app.axIdeal, 'Ideal Gates');

            % Row 2
            app.axExpGates = uiaxes(glGates); title(app.axExpGates, 'Experimental Gates');
            app.axSynthGates = uiaxes(glGates); title(app.axSynthGates, 'Synthetic Gates');
            uipanel(glGates, 'Visible', 'off'); % Future content

            % Tab 2: Result Maps -> DATA
            app.DataTab = uitab(app.TabGroup, 'Title', 'DATA');
            app.glData = uigridlayout(app.DataTab, [3, 5]);
            app.glData.RowHeight = {'1x', '1x', '0.5x'}; % Histograms are half height

            % Row 1: Experimental Data
            app.axTotal = uiaxes(app.glData); title(app.axTotal, 'Total Counts');
            app.axTotal.ButtonDownFcn = @(src, event) app.selectPixelCallback(event);
            app.axGate1 = uiaxes(app.glData); title(app.axGate1, 'Gate 1');
            app.axGate2 = uiaxes(app.glData); title(app.axGate2, 'Gate 2');
            app.axGate3 = uiaxes(app.glData); title(app.axGate3, 'Gate 3');
            app.axGate4 = uiaxes(app.glData); title(app.axGate4, 'Gate 4');

            % Row 2: Analysis Maps
            app.axGateSumBar = uiaxes(app.glData); title(app.axGateSumBar, 'Gate Sums');
            app.axMapA   = uiaxes(app.glData); title(app.axMapA, 'Amplitudes (A)');
            app.axMapTau = uiaxes(app.glData); title(app.axMapTau, 'Lifetime (Tau)');
            app.axMapB   = uiaxes(app.glData); title(app.axMapB, 'Background (B)');
            app.axMapChi2 = uiaxes(app.glData); title(app.axMapChi2, 'Reduced Chi2');

            % Row 3: Residuals and Histograms
            app.axResiduals = uiaxes(app.glData); title(app.axResiduals, 'Standardized Residuals');
            app.axHistA    = uiaxes(app.glData); title(app.axHistA, 'A Histogram');
            app.axHistTau  = uiaxes(app.glData); title(app.axHistTau, 'Tau Histogram');
            app.axHistB    = uiaxes(app.glData); title(app.axHistB, 'B Histogram');
            app.axHistChi2 = uiaxes(app.glData); title(app.axHistChi2, 'Chi2 Histogram');
        end

        function updateSimRes(app)
            val = app.spnSimRes.Value;
            if val > app.LastSimRes
                app.spnSimRes.Value = app.LastSimRes * 2;
            elseif val < app.LastSimRes && app.LastSimRes > 2
                app.spnSimRes.Value = app.LastSimRes / 2;
            else
                app.spnSimRes.Value = 2^max(0, round(log2(val)));
            end
            app.LastSimRes = app.spnSimRes.Value;
            app.Model.SimRes = app.LastSimRes;
        end

        function updateSimA(app), app.Model.SimA = app.spnSimA.Value; end
        function updateSimB(app), app.Model.SimB = app.spnSimB.Value; end
        function updateSimTau1(app), app.Model.SimTau1 = app.spnSimTau1.Value; end
        function updateSimTau2(app), app.Model.SimTau2 = app.spnSimTau2.Value; end

        function updateHistRes(app)
            val = app.spnHistRes.Value;
            if val > app.LastHistRes
                app.spnHistRes.Value = app.LastHistRes * 2;
            elseif val < app.LastHistRes && app.LastHistRes > 2
                app.spnHistRes.Value = app.LastHistRes / 2;
            else
                app.spnHistRes.Value = 2^max(0, round(log2(val)));
            end
            app.LastHistRes = app.spnHistRes.Value;
            app.updateDataTab(); % Refresh histograms
        end

        function simulateCallback(app)
            try
                % Ensure we have gates before simulating
                if isempty(app.Model.GateShapes)
                    app.Model.distillGates();
                end

                if isempty(app.Model.GateShapes)
                    error('Gate shapes are not defined. Please check settings or load a gate measurement file.');
                end

                res = app.spnSimRes.Value;
                app.Model.simulateData(app.Model.SimA, app.Model.SimTau1, app.Model.SimTau2, app.Model.SimB, res, res);
                app.updateDataTab();
                app.TabGroup.SelectedTab = app.DataTab; % Auto-switch to see results
                uialert(app.UIFigure, 'Simulated data generated.', 'Success', 'Icon', 'info');
            catch ME
                uialert(app.UIFigure, ME.message, 'Simulation Error');
            end
        end

        function importSweepCallback(app)
            [file, path] = uigetfile('*.csv', 'Select Gate Sweep CSV');
            if isequal(file, 0), return; end
            try
                app.Model.importSweepCSV(fullfile(path, file));
                app.Model.distillGates();
                app.plotGates();
            catch ME
                uialert(app.UIFigure, ME.message, 'Import Error');
            end
        end

        function importExactGatesCallback(app)
            [file, path] = uigetfile('*.csv', 'Select Exact Gates CSV');
            if isequal(file, 0), return; end
            try
                app.Model.importExactGatesCSV(fullfile(path, file));
                app.ddGateMethod.Value = 'Experimental';
                app.Model.GateMethod = 'experimental';
                app.Model.distillGates();
                app.plotGates();
            catch ME
                uialert(app.UIFigure, ME.message, 'Import Error');
            end
        end

        function saveResultsCallback(app)
            if isempty(app.Model.TauMap)
                uialert(app.UIFigure, 'No results to save. Run fit first.', 'Warning');
                return;
            end
            [file, path] = uiputfile('*.mat', 'Save Fitting Results', 'FBK_Results.mat');
            if isequal(file, 0), return; end
            try
                app.Model.exportResults(fullfile(path, file));
                uialert(app.UIFigure, 'Results exported successfully.', 'Success', 'Icon', 'info');
            catch ME
                uialert(app.UIFigure, ME.message, 'Export Error');
            end
        end

        function importLaserCallback(app)
            [file, path] = uigetfile('*.csv', 'Select Laser Pulse CSV');
            if isequal(file, 0), return; end
            try
                app.Model.importLaserCSV(fullfile(path, file));
                app.chkUseEIRF.Enable = 'on'; % Enable toggle once IRF is available
                app.Model.distillGates();
                app.plotGates();
            catch ME
                uialert(app.UIFigure, ME.message, 'Import Error');
            end
        end

        function distillGatesCallback(app)
            % Warn if laser not loaded but proceed with geometric fit
            if isempty(app.Model.LaserPulse)
                uialert(app.UIFigure, 'No laser pulse (IRF) loaded. Distillation will skip deconvolution step.', 'Warning', 'Icon', 'warning');
            end

            app.UIFigure.Pointer = 'watch';
            drawnow;
            try
                app.Model.characterizeHardware();
                app.plotGates();
                uialert(app.UIFigure, 'Gates distilled successfully.', 'Success', 'Icon', 'info');
            catch ME
                uialert(app.UIFigure, ME.message, 'Distillation Error');
            end
            app.UIFigure.Pointer = 'arrow';
        end

        function updateUseEIRF(app)
            app.Model.UseEIRF = app.chkUseEIRF.Value;
        end

        function importDataCallback(app)
            [file, path] = uigetfile({'*.sdt;*.mat', 'Sample Data Files'}, 'Select Sample Data');
            if isequal(file, 0), return; end
            try
                % Assuming a generic loader that populates Model.RawData
                % For now, support .mat with 'RawData' variable or .sdt
                [~, ~, ext] = fileparts(file);
                if strcmpi(ext, '.mat')
                    s = load(fullfile(path, file));
                    if isfield(s, 'RawData'), app.Model.RawData = s.RawData;
                    else, error('MAT file must contain "RawData" variable.'); end
                else
                    app.Model.RawData = read_SDT(fullfile(path, file)); % Reuses HILIGHTer tool
                end
                uialert(app.UIFigure, 'Data loaded successfully.', 'Success', 'Icon', 'info');
            catch ME
                uialert(app.UIFigure, ME.message, 'Import Error');
            end
        end

        function updateGateMethod(app)
            if app.IsUpdateBusy, return; end
            app.IsUpdateBusy = true;
            c = onCleanup(@() setUpdateBusy(app, false));

            app.Model.GateMethod = lower(app.ddGateMethod.Value);
            app.Model.distillGates();
            app.plotGates();
        end

        function setUpdateBusy(app, val), app.IsUpdateBusy = val; end

        function updateBgOption(app)
            val = app.ddBgOption.Value;
            if strcmpi(val, 'Fit')
                app.Model.BgOption = 'fit';
                app.btnImportBg.Enable = 'off';
            elseif strcmpi(val, 'Fix to 0')
                app.Model.BgOption = 'fix0';
                app.btnImportBg.Enable = 'off';
            else
                app.Model.BgOption = 'measurement';
                app.btnImportBg.Enable = 'on';
            end
        end

        function importBgCallback(app)
            [file, path] = uigetfile({'*.sdt;*.mat;*.csv', 'Background Files'}, 'Select Background Measurement');
            if isequal(file, 0), return; end
            try
                [~, ~, ext] = fileparts(file);
                if strcmpi(ext, '.mat')
                    s = load(fullfile(path, file));
                    if isfield(s, 'BgData'), app.Model.BgData = s.BgData;
                    else, error('MAT file must contain "BgData" variable (2D image).'); end
                elseif strcmpi(ext, '.csv')
                    % Load CSV as mean background per gate
                    data = readmatrix(fullfile(path, file));
                    app.Model.BgData = mean(data(:));
                else
                    % Placeholder for SDT background loading
                    error('SDT Background loading placeholder.');
                end
                uialert(app.UIFigure, 'Background measurement loaded.', 'Success', 'Icon', 'info');
            catch ME
                uialert(app.UIFigure, ME.message, 'Import Error');
            end
        end

        function updateThreshold(app)
            app.Model.Threshold = app.spnThreshold.Value;
        end

        function updateEdges(app)
            if app.IsUpdateBusy, return; end
            app.IsUpdateBusy = true;
            c = onCleanup(@() setUpdateBusy(app, false));

            newEdges = zeros(1, 5);
            for i = 1:5
                newEdges(i) = app.spnEdges(i).Value;
            end
            app.Model.GateEdges = newEdges;
            app.Model.distillGates();
            app.plotGates();
        end

        function updateSkewness(app)
            if app.IsUpdateBusy, return; end
            app.IsUpdateBusy = true;
            c = onCleanup(@() setUpdateBusy(app, false));

            app.Model.Skewness = app.spnSkewness.Value;
            app.Model.distillGates();
            app.plotGates();
        end

        function runFitCallback(app)
            if isempty(app.Model.RawData)
                uialert(app.UIFigure, 'Please load sample data first.', 'Error');
                return;
            end

            % Indicate busy status
            app.UIFigure.Pointer = 'watch';
            drawnow;

            try
                app.Model.runFit();
                app.updateDataTab();
                uialert(app.UIFigure, 'Fitting complete.', 'Success', 'Icon', 'info');
            catch ME
                uialert(app.UIFigure, ME.message, 'Fit Error');
            end

            app.UIFigure.Pointer = 'arrow';
        end

        function plotGates(app)
            % View-Only Refresh: Assumes model is already distilled
            app.Model.IsAborted = false;

            % 1. Plot Raw Sweep Data (Mirrored and Normalized for validation)
            cla(app.axSweep);
            if ~isempty(app.Model.MinGateData)
                hold(app.axSweep, 'on');
                % Use the same mirroring logic as in characterization
                t_orig = app.Model.MinGateData.LaserDelay;
                t_mirrored = (max(t_orig) + min(t_orig)) - t_orig;
                widths = unique(app.Model.MinGateData.GateWidth);
                for i = 1:length(widths)
                    if app.Model.IsAborted, return; end
                    w = widths(i);
                    rows = app.Model.MinGateData.GateWidth == w;
                    td = t_mirrored(rows); [td, idx] = sort(td);
                    cd = app.Model.MinGateData.Counts(rows); cd = cd(idx);
                    plot(app.axSweep, td, cd / max(cd + 1e-10), '.-', 'DisplayName', sprintf('%d ps', w));
                end
                xlabel(app.axSweep, 'Delay (Mirrored) [ns]'); ylabel(app.axSweep, 'Norm. Counts');
                title(app.axSweep, sprintf('Gate Sweep Characterization (\\sigma_{fit} = %.1f ps)', app.Model.SweepFittedSigma * 1000));
                grid(app.axSweep, 'on'); box(app.axSweep, 'on');
                ylim(app.axSweep, [-0.05, 1.1]);
                hold(app.axSweep, 'off');
            end

            % 2. Plot Laser Pulse
            cla(app.axLaser);
            if ~isempty(app.Model.LaserPulse)
                plot(app.axLaser, app.Model.LaserPulse.t, app.Model.LaserPulse.p, 'LineWidth', 1.5);
                xlabel(app.axLaser, 'Time [ns]'); ylabel(app.axLaser, 'Normalized Intensity');
                title(app.axLaser, 'Laser Pulse'); grid(app.axLaser, 'on'); box(app.axLaser, 'on');
            end

            % 3. Plot Comparison Dashboard
            cla(app.axIdeal); cla(app.axExpGates); cla(app.axSynthGates);
            t = app.Model.TimeVector;
            if isempty(t), return; end
            xlims = [app.Model.GateEdges(1)-1, app.Model.GateEdges(end)+1];

            % Save active state to restore later
            backup = app.Model.GateShapes;

            % --- Ideal ---
            app.Model.calculateIdealGates(true);
            if ~isempty(app.Model.GateShapes)
                hold(app.axIdeal, 'on');
                for i = 1:size(app.Model.GateShapes, 1)
                    plot(app.axIdeal, t, app.Model.GateShapes(i, :), 'LineWidth', 1.5);
                end
                grid(app.axIdeal, 'on'); box(app.axIdeal, 'on');
                title(app.axIdeal, sprintf('Ideal (Rect + Skew: %.1f ps)', app.Model.Skewness));
                xlim(app.axIdeal, xlims); ylim(app.axIdeal, [-0.05, 1.1]);
            end

            % --- Experimental (Exact) ---
            if ~isempty(app.Model.ExperimentalExactGates)
                hold(app.axExpGates, 'on');
                tex = app.Model.ExperimentalExactTime;
                for i = 1:size(app.Model.ExperimentalExactGates, 1)
                    plot(app.axExpGates, tex, app.Model.ExperimentalExactGates(i, :), 'LineWidth', 1.5);
                end
                grid(app.axExpGates, 'on'); box(app.axExpGates, 'on');
                title(app.axExpGates, 'Experimental (Exact Profiles)');
                xlim(app.axExpGates, xlims); ylim(app.axExpGates, [-0.05, 1.1]);
            end

            % --- Synthetic (Fitted) ---
            app.Model.calculateSyntheticGates();
            if ~isempty(app.Model.GateShapes)
                hold(app.axSynthGates, 'on');
                for i = 1:size(app.Model.GateShapes, 1)
                    plot(app.axSynthGates, t, app.Model.GateShapes(i, :), 'LineWidth', 1.5);
                end
                grid(app.axSynthGates, 'on'); box(app.axSynthGates, 'on');
                title(app.axSynthGates, sprintf('Synthetic (\\sigma_{fit} = %.1f ps)', app.Model.SweepFittedSigma * 1000));
                xlim(app.axSynthGates, xlims); ylim(app.axSynthGates, [-0.05, 1.1]);
            end

            % Restore the active model state
            app.Model.GateShapes = backup;
            app.Model.distillGates();
        end

        function updateDataTab(app)
            if isempty(app.Model.RawData)
                % Show zeros if no data is loaded
                res = app.spnSimRes.Value;
                data = zeros(res, res, 4);
            else
                data = app.Model.RawData;
            end

            % Scaling Logic
            % 1. Total counts has its own scale
            totalData = sum(data, 3);
            totalScale = [0, max(max(totalData(:)), 1)];

            % 2. Gate 1 has its own scale and sets the scale for Gates 2-4
            gate1Data = data(:,:,1);
            gateScale = [0, max(max(gate1Data(:)), 1)];

            % Row 1: Images of Raw Data (using 'gray' colormap)
            app.plotData(app.axTotal, totalData, 'Total Counts', true, totalScale, 'gray');
            app.plotData(app.axGate1, data(:,:,1), 'Gate 1', true, gateScale, 'gray');
            app.plotData(app.axGate2, data(:,:,2), 'Gate 2', true, gateScale, 'gray');
            if size(data, 3) >= 3, app.plotData(app.axGate3, data(:,:,3), 'Gate 3', true, gateScale, 'gray'); end
            if size(data, 3) >= 4, app.plotData(app.axGate4, data(:,:,4), 'Gate 4', true, gateScale, 'gray'); end

            % Row 2, Col 1: Mixed Decay Plot (YYAXIS) + Selection Update
            app.updatePixelSelection();

            % Row 2, Col 2-5: Results (Horizontal colorbars, 'turbo' colormap)
            if ~isempty(app.Model.TauMap)
                app.plotData(app.axMapA, app.Model.AMap, 'Amplitudes (A)', true, [], 'turbo');
                app.plotData(app.axMapTau, app.Model.TauMap, 'Lifetime [ns]', true, [], 'turbo');
                app.plotData(app.axMapB, app.Model.BMap, 'Background (B)', true, [], 'turbo');
                app.plotData(app.axMapChi2, app.Model.Chi2Map, 'Reduced Chi2', true, [], 'turbo');

                % Get selected pixel values for markers
                y = app.SelectedPixel(1); x = app.SelectedPixel(2);
                selA = app.Model.AMap(y,x);
                selTau = app.Model.TauMap(y,x);
                selB = app.Model.BMap(y,x);
                selChi2 = app.Model.Chi2Map(y,x);

                app.plotHistogramWithStats(app.axHistA, app.Model.AMap, 'A', selA);
                app.plotHistogramWithStats(app.axHistTau, app.Model.TauMap, 'Tau', selTau);
                app.plotHistogramWithStats(app.axHistB, app.Model.BMap, 'B', selB);
                app.plotHistogramWithStats(app.axHistChi2, app.Model.Chi2Map, 'Chi2', selChi2);
            else
                % Reset result axes to blank/zero if fitting results are missing
                res = app.spnSimRes.Value;
                blank = zeros(res, res);
                app.plotData(app.axMapA, blank, 'Amplitudes (A)', true, [0 1], 'turbo');
                app.plotData(app.axMapTau, blank, 'Lifetime [ns]', true, [0 1], 'turbo');
                app.plotData(app.axMapB, blank, 'Background (B)', true, [0 1], 'turbo');
                app.plotData(app.axMapChi2, blank, 'Reduced Chi2', true, [0 1], 'turbo');
                cla(app.axHistA);
                cla(app.axHistTau);
                cla(app.axHistB);
                cla(app.axHistChi2);
                cla(app.axResiduals);
            end
        end


        function plotHistogramWithStats(app, ax, data, lbl, selVal)
            if isempty(data), return; end
            vals = data(:);
            vals = vals(~isnan(vals) & ~isinf(vals));
            if isempty(vals), return; end

            cla(ax);
            numBins = app.spnHistRes.Value;
            histogram(ax, vals, numBins, 'FaceColor', [0.4 0.4 0.6], 'EdgeColor', 'w', 'Normalization', 'probability');
            hold(ax, 'on');

            % Outlier-resistant limits (1st to 99th percentile)
            q = quantile(vals, [0.01, 0.99]);
            if q(1) < q(2)
                xlim(ax, [q(1), q(2)]);
            else
                xlim(ax, 'auto');
            end

            mu = mean(vals);
            sd = std(vals);

            % Plot mean and std vertical lines
            yl = ylim(ax);
            plot(ax, [mu mu], yl, 'r-', 'LineWidth', 2, 'DisplayName', 'Mean');
            plot(ax, [mu-sd mu-sd], yl, 'r--', 'LineWidth', 1, 'DisplayName', 'Std');
            plot(ax, [mu+sd mu+sd], yl, 'r--', 'LineWidth', 1);

            % Plot Selected Pixel Marker (Blue Circle)
            if nargin > 4 && ~isempty(selVal) && ~isnan(selVal)
                yMarker = yl(2) * 0.1;
                plot(ax, selVal, yMarker, 'bo', 'MarkerSize', 10, 'LineWidth', 2, 'MarkerFaceColor', 'c', 'DisplayName', 'Selected', 'Tag', 'selMarker');
                text(ax, selVal, yMarker * 1.8, sprintf('%.2f', selVal), 'Color', 'b', 'FontWeight', 'bold', 'HorizontalAlignment', 'center', 'Tag', 'selLabel');
            end

            hold(ax, 'off');
            title(ax, sprintf('%s: \\mu=%.2f, \\sigma=%.2f', lbl, mu, sd));
            grid(ax, 'on');
        end

        function plotData(~, ax, data, lbl, showColorbar, cRange, cm)
            img = imagesc(ax, data);
            img.HitTest = 'off'; % Crucial for axes ButtonDownFcn

            % Apply colormap
            if nargin > 6 && ~isempty(cm)
                colormap(ax, cm);
            end

            % Apply color limits
            if nargin > 5 && ~isempty(cRange)
                clim(ax, cRange);
            else
                clim(ax, 'auto');
            end

            % Configure Colorbar
            if nargin > 4 && showColorbar
                colorbar(ax, 'southoutside'); % Horizontal below the axes
            else
                colorbar(ax, 'off');
            end

            axis(ax, 'image');
            axis(ax, 'tight');
            box(ax, 'on');
            ax.LineWidth = 2;

            % Remove Labels
            ax.XTick = [];
            ax.YTick = [];
            title(ax, lbl);
        end

        function selectPixelCallback(app, event)
            % Select pixel from click on axTotal
            pt = event.IntersectionPoint;
            x = round(pt(1));
            y = round(pt(2));

            % Clamp to image bounds
            [nY, nX, ~] = size(app.Model.RawData);
            x = max(1, min(x, nX));
            y = max(1, min(y, nY));

            app.SelectedPixel = [y, x];
            app.updatePixelSelection();
        end

        function updatePixelSelection(app)
            % Draw/Update crosshair and trigger plot refresh
            if isempty(app.Model.RawData), return; end

            y = app.SelectedPixel(1);
            x = app.SelectedPixel(2);
            [nY, nX, ~] = size(app.Model.RawData);

            % Initial Selection if defaulted to 1,1
            if y == 1 && x == 1 && isempty(app.hCrossH)
                app.SelectedPixel = [round(nY/2), round(nX/2)];
                y = app.SelectedPixel(1);
                x = app.SelectedPixel(2);
            end

            % Update Crosshair on axTotal (Ensure red marker is drawn and valid)
            if isempty(app.hCrossH) || ~isvalid(app.hCrossH) || isempty(app.hCrossH.Parent)
                hold(app.axTotal, 'on');
                app.hCrossH = plot(app.axTotal, [1 nX], [y y], 'r-', 'LineWidth', 1.2, 'HitTest', 'off');
                app.hCrossV = plot(app.axTotal, [x x], [1 nY], 'r-', 'LineWidth', 1.2, 'HitTest', 'off');
                hold(app.axTotal, 'off');
            else
                % Use actual axes limits in case of resize/zoom
                app.hCrossH.YData = [y y];
                app.hCrossH.XData = [0.5 nX+0.5];
                app.hCrossV.XData = [x x];
                app.hCrossV.YData = [0.5 nY+0.5];
            end

            app.updateMixedDecayPlot();

            % Update Histogram Markers on Selection Change
            if ~isempty(app.Model.TauMap) && all(size(app.Model.TauMap) == [nY, nX])
                app.plotHistogramWithStats(app.axHistA, app.Model.AMap, 'A', app.Model.AMap(y,x));
                app.plotHistogramWithStats(app.axHistTau, app.Model.TauMap, 'Tau', app.Model.TauMap(y,x));
                app.plotHistogramWithStats(app.axHistB, app.Model.BMap, 'B', app.Model.BMap(y,x));
                app.plotHistogramWithStats(app.axHistChi2, app.Model.Chi2Map, 'Chi2', app.Model.Chi2Map(y,x));
            end
        end

        function updateMixedDecayPlot(app)
            % UPDATE MIXED DECAY PLOT on axGateSumBar

            % Robustly clear both sides of the dual-axis plot
            yyaxis(app.axGateSumBar, 'left'); cla(app.axGateSumBar);
            yyaxis(app.axGateSumBar, 'right'); cla(app.axGateSumBar);

            if isempty(app.Model.RawData)
                title(app.axGateSumBar, 'Decay');
                return;
            end

            % Global Integrated Counts
            sums = squeeze(sum(sum(app.Model.RawData, 1), 2));
            nGates = length(sums);

            % Gate centers and widths for physical axis
            edges = app.Model.GateEdges;
            centers = (edges(1:end-1) + edges(2:end)) / 2;

            % Switch to Left Axis: Global Integrated Bins
            yyaxis(app.axGateSumBar, 'left');
            hold(app.axGateSumBar, 'on');

            % Draw bins as patches to respect variable physical widths
            for i = 1:nGates
                x_box = [edges(i) edges(i+1) edges(i+1) edges(i)];
                y_box = [0 0 sums(i) sums(i)];
                patch(app.axGateSumBar, x_box, y_box, [0.8 0.8 0.8], 'FaceAlpha', 0.4, ...
                    'EdgeColor', [0.6 0.6 0.6], 'DisplayName', 'Global Sum', 'HandleVisibility', 'off');
            end
            % Dummy plot for legend (patches don't always show up well in legends)
            plot(app.axGateSumBar, nan, nan, 's', 'MarkerFaceColor', [0.8 0.8 0.8], ...
                'MarkerEdgeColor', [0.6 0.6 0.6], 'DisplayName', 'Global Sum');

            ylabel(app.axGateSumBar, 'Integrated Counts');
            app.axGateSumBar.YColor = [0.4 0.4 0.4];

            % Switch to Right Axis: Specific Pixel Decay
            yyaxis(app.axGateSumBar, 'right');
            cla(app.axGateSumBar);
            y = app.SelectedPixel(1);
            x = app.SelectedPixel(2);
            pixelObs = squeeze(app.Model.RawData(y, x, :));

            hold(app.axGateSumBar, 'on');
            stem(app.axGateSumBar, centers, pixelObs, 'filled', 'Color', 'r', 'LineWidth', 1.2, 'DisplayName', 'Pixel Obs');

            % 3. Standardized Residuals and Predicted fit
            if ~isempty(app.Model.TauMap) && ~isnan(app.Model.TauMap(y,x))
                tau = app.Model.TauMap(y,x);
                a = app.Model.AMap(y,x);
                b = app.Model.BMap(y,x);

                t = app.Model.TimeVector;
                decay = exp(-t(:) / tau);
                if app.Model.UseEIRF && ~isempty(app.Model.LaserPulse)
                    L = interp1(app.Model.LaserPulse.t, app.Model.LaserPulse.p, t, 'linear', 0);
                    L = L / sum(L);
                    decay = conv(decay, L, 'same');
                end

                termA = app.Model.GateShapes * decay;
                termA = termA / sum(termA);
                termB = sum(app.Model.GateShapes, 2);
                pixelPred = a * termA(:) + b * termB(:);

                % Plot pred on right axis
                plot(app.axGateSumBar, centers, pixelPred, 'b-o', 'LineWidth', 1.5, 'DisplayName', 'Pixel Fit');

                % Standardized Residuals: (Obs - Fit) / sqrt(Fit)
                res = (pixelObs(:) - pixelPred(:)) ./ sqrt(max(pixelPred(:), 1));
                stem(app.axResiduals, centers, res, 'filled', 'Color', [0.6 0.2 0.2]);
                yline(app.axResiduals, 0, 'k--', 'HandleVisibility', 'off');
                title(app.axResiduals, 'Standardized Residuals');
                xlabel(app.axResiduals, 'Time [ns]');
                ylabel(app.axResiduals, 'Z-Score');
                grid(app.axResiduals, 'on');
                box(app.axResiduals, 'on');
                % Dynamic Y Limits (min +/- 5)
                maxRes = max(abs(res));
                limVal = max(5, ceil(maxRes * 1.2));
                ylim(app.axResiduals, [-limVal, limVal]);
                xlim(app.axResiduals, [edges(1) edges(end)]);

                % Randomness Test (Runs Test)
                s_pix = sign(res); s_pix(s_pix==0) = 1;
                r_pix = 1 + sum(diff(s_pix)~=0);
                n1 = sum(s_pix>0); n2 = sum(s_pix<0);
                if n1==0 || n2==0
                    rndText = 'Randomness: NO (Bias)';
                    rndColor = [0.8 0 0];
                else
                    mu_r = 1 + (2*n1*n2)/(n1+n2);
                    s_r = sqrt((2*n1*n2*(2*n1*n2-n1-n2))/((n1+n2)^2 * (n1+n2-1)));
                    z_rnd = (r_pix - mu_r)/s_r;
                    if z_rnd < -1.645
                        rndText = sprintf('Randomness: NO (Z=%.1f)', z_rnd);
                        rndColor = [0.8 0 0];
                    else
                        rndText = sprintf('Randomness: YES (Z=%.1f)', z_rnd);
                        rndColor = [0 0.6 0];
                    end
                end
                text(app.axResiduals, 0.05, 0.9, rndText, 'Units', 'normalized', ...
                    'Color', rndColor, 'FontWeight', 'bold', 'BackgroundColor', 'w', 'EdgeColor', rndColor);
            end
            hold(app.axGateSumBar, 'off');

            ylabel(app.axGateSumBar, 'Pixel Counts');
            app.axGateSumBar.YColor = 'r';
            xlabel(app.axGateSumBar, 'Time [ns]');
            xlim(app.axGateSumBar, [edges(1) edges(end)]);

            title(app.axGateSumBar, 'Decay');
            grid(app.axGateSumBar, 'on'); box(app.axGateSumBar, 'on');
            legend(app.axGateSumBar, 'Location', 'northoutside', 'FontSize', 8, 'Orientation', 'horizontal');
        end
    end

    methods (Access = public)
        function onAppClose(app)
            % Signal abort for any loops and save settings
            app.Model.IsAborted = true;
            try
                app.Model.saveSettings();
            catch
                % Silently fail to ensure the app closes
            end
            delete(app.UIFigure);
        end

        function app = HILIGHTer_FBK_edition()
            app.Model = FBK_Model();
            app.createComponents();
            app.loadInitialSettings();
        end

        function loadInitialSettings(app)
            % Gate Method
            items = app.ddGateMethod.Items;
            idx = find(strcmpi(items, app.Model.GateMethod), 1);
            if ~isempty(idx)
                app.ddGateMethod.Value = items{idx};
            end

            % Bg Option
            items = app.ddBgOption.Items;
            modelVal = app.Model.BgOption;
            if strcmpi(modelVal, 'fit')
                mapVal = 'Fit';
            elseif strcmpi(modelVal, 'fix0')
                mapVal = 'Fix to 0';
            else
                mapVal = 'Measurement';
            end

            idx = find(strcmpi(items, mapVal), 1);
            if ~isempty(idx)
                app.ddBgOption.Value = items{idx};
            end
            app.updateBgOption(); % Sync button state

            app.spnThreshold.Value = app.Model.Threshold;

            % Gate Edges
            for i = 1:5
                app.spnEdges(i).Value = app.Model.GateEdges(i);
            end

            app.chkUseEIRF.Value = app.Model.UseEIRF;
            if ~isempty(app.Model.LaserPulse)
                app.chkUseEIRF.Enable = 'on';
            end

            app.spnSkewness.Value = app.Model.Skewness;

            % Simulation Params
            app.spnSimA.Value = app.Model.SimA;
            app.spnSimB.Value = app.Model.SimB;
            app.spnSimTau1.Value = app.Model.SimTau1;
            app.spnSimTau2.Value = app.Model.SimTau2;
            app.spnSimRes.Value = app.Model.SimRes;
            app.LastSimRes = app.Model.SimRes;

            % Ensure model is ready (distills and plots gates)
            app.updateGateMethod();
            app.updateDataTab();
        end
    end
end
