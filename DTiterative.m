function [tau_est_map, stats] = DTiterative(RawData, config, fig)
% DTITERATIVE - Iterative Reconvolution (LSQ) for FLIM Data
% Fits lifetime tau using Weighted Least Squares (Chi-Squared minimization).
% Uses Matrix Method for fast convolution and integration.
%
% Inputs:
%   RawData: (nY, nX, nGates) matrix of photon counts
%   config: Configuration struct containing time/gate/IRF info
%   fig: (Optional) Figure handle for uiprogressdlg. If empty, no progress bar.
%
% Outputs:
%   tau_est_map: (nY, nX) matrix of estimated lifetimes
%   stats: Struct with basic stats (mean, std)

% 1. Setup Time vector
dt = config.dt;
T = config.T;
t = 0:dt:T;
Nt = length(t);

% Gates
if isempty(config.gate_edges)
    actual_gate_edges = linspace(0, T - config.toff, config.N_gates + 1);
else
    actual_gate_edges = config.gate_edges;
end
gate_profiles = DTgates(t, config.r, actual_gate_edges); % (N_gates x Nt)

% 2. IRF (Normalized)
excitation = DTexcitation(t, config.fwhm, config.profile, ...
    config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);
IRF = excitation / sum(excitation); % Sum=1

% 3. Pre-Calculate Convolution Matrix or Effective Sensitivity Matrix
% Method: ExpectedSignal = Gates * (IRF * Decay)
% We want Matrix W such that ExpectedSignal = W * DecayVector
% W(g, j) represents the contribution of Decay(j) to Gate g
% W = GateMatrix * ConvolutionMatrix(IRF)

% Construct Convolution Matrix T_IRF (Lower Toeplitz)
% C(i, j) = IRF(i - j + 1)
% Since dimension is small (~256-1000), we can build it explicitly.
% Or use loops to build W directly to save memory.

W = zeros(config.N_gates, Nt);

% It is faster to build T_IRF if Nt is small.
col = IRF(:);
row = zeros(1, Nt); row(1) = col(1);
T_IRF = toeplitz(col, row);
% T_IRF is lower triangular. Matches filter(IRF, 1, Decay)

% The convolution matrix T_IRF does not account for 'dt' in integral.
% But we are working with discrete sums.
% Gate integration: trapz or sum?
% DTgates assumes continuous profiles.
% Let's use simple sum for matrix ops: Proj = GateMatrix * (T_IRF * Decay)
% To match trapz scaling roughly we can multiply by dt later if needed,
% but since we normalize the resulting profile, constant factors cancel.

W = gate_profiles * T_IRF; % (N_gates x Nt)

% 4. Prepare Data
[nY, nX, nGates] = size(RawData);
M = nY * nX;
flatData = reshape(RawData, M, nGates)'; % (nGates, M)
tau_est_flat = nan(1, M);

% Optimization Setup
search_range = [0.1, 10];
options = optimset('Display', 'off', 'TolX', 1e-3);

% 5. Progress Bar
d = [];
if nargin >= 3 && ~isempty(fig)
    d = uiprogressdlg(fig, 'Title', 'Iterative Fitting', 'Message', 'Initializing...', 'Cancelable', true);
    d.Value = 0;
end

% 6. Loop over pixels
% We define objective function here to use W

% Nested Objective Function
    function ssq = fast_objective(tau, observed_counts)
        % Decay Vector
        d_vec = exp(-t(:) ./ tau);

        % Predicted Gate Counts (Unscaled)
        pred = W * d_vec; % (N_gates x 1)

        % Normalize pattern
        s = sum(pred);
        if s > 0
            pred = pred / s;
        end

        % Scale to Observation (Minimize Shape Error + Poisson Weight)
        total_counts = sum(observed_counts);
        expected = pred * total_counts;

        % Weights (Poisson: 1/N)
        w = 1 ./ max(expected, 1e-9);

        diff = observed_counts - expected;
        ssq = sum((diff.^2) .* w);
    end

% Batch processed? No, fminbnd is scalar.
% Loop
update_interval = floor(M / 100);
if update_interval < 1, update_interval = 1; end

for k = 1:M
    % Check Cancel
    if ~isempty(d) && d.CancelRequested
        break;
    end

    pixel_counts = flatData(:, k);
    if sum(pixel_counts) < 10
        continue;
    end

    try
        tau_est_flat(k) = fminbnd(@(tau) fast_objective(tau, pixel_counts), ...
            search_range(1), search_range(2), options);
    catch ME
        % Report error to command window so user can see what's happening
        fprintf('Error fitting pixel %d: %s\n', k, ME.message);
        tau_est_flat(k) = NaN;
    end

    % Progress
    if ~isempty(d) && mod(k, update_interval) == 0
        d.Value = k / M;
        d.Message = sprintf('Fitting pixel %d / %d', k, M);
    end
end

if ~isempty(d)
    close(d);
end

% 7. Reshape and Stats
tau_est_map = reshape(tau_est_flat, nY, nX);
stats.mean = mean(tau_est_flat, 'omitnan');
stats.std = std(tau_est_flat, 'omitnan');
stats.F = NaN;
stats.p_eff = NaN;

end
