function [TauMap, Info] = DTtailfit(RawData, config, start_gate_idx, end_gate_idx)
% DTTAILFIT - Performs tail fitting on FLIM data
%
% Syntax:
%   [TauMap, Info] = DTtailfit(RawData, config, start_gate_idx, end_gate_idx)
%
% Inputs:
%   RawData        - 3D array [Y, X, Gates] of photon counts
%   config         - Structure containing configuration (needs .dt for time step)
%   start_gate_idx - (Optional) Integer index of the gate to start fitting from.
%                    If omitted, the function will attempt to auto-detect the peak.
%
% Outputs:
%   TauMap         - 2D array [Y, X] of fitted lifetimes (ns)
%   Info           - Struct containing additional info (residuals, etc.)

% 1. Extract Dimensions
[nY, nX, nGates] = size(RawData);
dt = config.dt;

% Prepare Output
TauMap = zeros(nY, nX);
Info = struct();

% 2. Determine Start/End Gates
if nargin < 3 || isempty(start_gate_idx)
    sumDecay = squeeze(sum(sum(RawData, 1), 2));
    [~, peakIdx] = max(sumDecay);
    % Default: start 2 gates after peak to avoid IRF convolution effects
    start_gate_idx = min(peakIdx + 2, nGates - 2);
end

if nargin < 4 || isempty(end_gate_idx)
    end_gate_idx = nGates;
end

% Ensure valid range
if start_gate_idx < 1, start_gate_idx = 1; end
if start_gate_idx > nGates - 2
    % warning('Start gate too late for fitting.');
    start_gate_idx = max(1, nGates - 3);
end
if end_gate_idx > nGates, end_gate_idx = nGates; end
if end_gate_idx <= start_gate_idx, end_gate_idx = start_gate_idx + 1; end

% 3. Extract Tail Data
% We will fit data from start_gate_idx to end_gate_idx
% Time vector relative to start of tail (t=0 at start_gate_idx)
gates_to_fit = start_gate_idx:end_gate_idx;
nFit = length(gates_to_fit);
t_tail = (0:(nFit-1))' * dt; % Column vector

% Reshape Data for Vectorized Fitting
% Pixels as columns: [nFit x M]
M = nY * nX;
flatData = reshape(RawData, M, nGates)'; % [Gates x M]
fitData = double(flatData(gates_to_fit, :)); % [nFit x M]

% 4. Rapid Linearized Fit (Log-Linear)
% This is faster and robust for single exponential tails.
% Model: I(t) = A * exp(-t/tau) + C (background usually subtracted or assumed small in tail)
% Linearized: ln(I) = ln(A) - (1/tau)*t
% We ignore pixels with too few photons in tail to avoid errors

threshold_photons = 10; % Minimum photons in tail to attempt fit
valid_pixels = sum(fitData, 1) > threshold_photons;

% Pre-calculate sums for linear regression (y = mx + c)
% detection of valid points (I > 0) is needed for log
% We mask invalid data in the loop or use robust methods.
% For speed, we'll do correct matrix math on valid pixels only.

% Only process valid pixels
data_subset = fitData(:, valid_pixels);
% Handle zeros for log: shift small amount or ignore?
% Standard is to ignore or add 1 (if C=0).
% Let's use weights w = I (Poisson approximation for linear fit) or just normal log.
% Simple unweighted log-linear fit:
% ln(I) = -k*t + C
% We must handle 0 counts in tail.
% Strategy: Smooth slightly or mask.
% Simple: Replace 0 with 0.1 for stability (bias risk, but tail fit is approx)
data_subset(data_subset <= 0) = 0.1;

y = log(data_subset); % [nFit x Sum(valid)]
X = [ones(nFit, 1), -t_tail]; % Design matrix: Intercept, Slope (-1/tau coefficient)

% Solve normal equations: beta = (X'X)^-1 X'y
% Since X is constant for all pixels, precompute pseudoinverse
pinvX = (X' * X) \ X';
beta = pinvX * y; % [2 x Sum(valid)]

% Extract Tau
% Slope m corresponds to beta(2, :) which approximates 1/tau (since we used -t)
% actually: ln(I) = ln(A) - t/tau.
% So if X = [1, -t], then beta2 is 1/tau.
inv_tau = beta(2, :);

% Filter crazy results
tau_vals = 1 ./ inv_tau;
tau_vals(tau_vals < 0 | tau_vals > 50) = NaN; % Typical biological range check

% Map back to full image
TauMap_flat = nan(1, M);
TauMap_flat(valid_pixels) = tau_vals;
TauMap = reshape(TauMap_flat, nY, nX);

Info.start_gate = start_gate_idx;

end
