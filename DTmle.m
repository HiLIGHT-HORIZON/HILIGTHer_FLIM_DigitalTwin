function [tau_est, stats] = DTmle(N_detections, gate_hist_all, tau_grid, P_model_grid, fig, start_gate_idx, end_gate_idx)
% Outputs:
%   tau_est - (1 x M) estimated lifetimes
%   stats   - Struct containing stats

M = size(gate_hist_all, 2);  % number of repetitions
nGates = size(gate_hist_all, 1);

% Handle Start/End
if nargin < 6 || isempty(start_gate_idx), start_gate_idx = 1; end
if nargin < 7 || isempty(end_gate_idx), end_gate_idx = nGates; end

% Ensure range
if start_gate_idx < 1, start_gate_idx = 1; end
if end_gate_idx > nGates, end_gate_idx = nGates; end
if end_gate_idx <= start_gate_idx, end_gate_idx = start_gate_idx + 1; end

fit_gates = start_gate_idx:end_gate_idx;

% Pre-slice and normalize Model Grid
P_model_sub = P_model_grid(fit_gates, :);
% Normalize columns to sum to 1 (conditional probability)
colSums = sum(P_model_sub, 1);
colSums(colSums == 0) = 1;
P_model_sub = P_model_sub ./ colSums;

% Progress Bar
d = [];
if nargin >= 5 && ~isempty(fig)
    d = uiprogressdlg(fig, 'Title', 'MLE Fitting', 'Message', 'Initializing...', 'Cancelable', true);
    d.Value = 0;
end

tau_est = zeros(1, M);
update_interval = floor(M / 100);
if update_interval < 1, update_interval = 1; end

for m = 1:M
    % Check Cancel
    if ~isempty(d) && d.CancelRequested
        break;
    end

    counts = gate_hist_all(fit_gates, m);
    if sum(counts) == 0
        tau_est(m) = NaN;
        continue;
    end
    counts = counts / sum(counts);

    % Compute log-likelihood for each candidate tau
    % We can vectorize this: logL = counts' * log(P_model_sub)
    % counts is [G x 1], P is [G x K].
    % logL is [1 x K].

    % Safe Log
    logP = log(P_model_sub);
    logP(isinf(logP)) = -1e9; % Handle log(0)

    logL = counts' * logP;

    % Pick tau with maximum likelihood
    [~, idx] = max(logL);
    tau_est(m) = tau_grid(idx);

    % Progress
    if ~isempty(d) && mod(m, update_interval) == 0
        d.Value = m / M;
        d.Message = sprintf('Fitting pixel %d / %d', m, M);
    end
end

if ~isempty(d)
    close(d);
end

% Stats
stats.mean = mean(tau_est);
stats.std = std(tau_est);
stats.F = (stats.std / stats.mean) * sqrt(mean(N_detections));
stats.p_eff = 1 / stats.F^2;
end
