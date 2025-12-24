function [tau_est, stats] = DTmle(N_detections, gate_hist_all, tau_grid, P_model_grid, fig)
% Inputs:
% - N_detections: number of photons per measurement
% - gate_hist_all: N_gates x M matrix of normalized counts
% - tau_grid: candidate lifetimes
% - P_model_grid: N_gates x length(tau_grid) model probabilities
% - fig: (Optional) figure handle for progress dialog

M = size(gate_hist_all, 2);  % number of repetitions

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

    counts = gate_hist_all(:, m);
    counts = counts / sum(counts);

    % Compute log-likelihood for each candidate tau
    logL = zeros(1, length(tau_grid));
    for k = 1:length(tau_grid)
        Pk = P_model_grid(:, k); Pk = Pk / sum(Pk);
        if all(Pk > 0)
            logL(k) = sum(counts .* log(Pk));
        else
            logL(k) = -inf;  % Invalid candidate
        end
    end

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
