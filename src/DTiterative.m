function [Results, stats] = DTiterative(RawData, config, fig, start_gate_idx, end_gate_idx, num_components, irf_custom)
% DTITERATIVE - Iterative Reconvolution (LSQ) for FLIM Data
% Fits lifetime tau using Weighted Least Squares (Chi-Squared minimization).
%
% Inputs:
%   RawData: (nY, nX, nGates) matrix of photon counts
%   config: Configuration struct
%   fig: (Optional) Figure handle for progress bar
%   start_gate_idx, end_gate_idx: (Optional) Fit range
%   num_components: (Optional) Number of exponential components (1, 2, or 3). Default 1.
%   irf_custom: (Optional) Custom IRF vector
%
% Outputs:
%   Results: Struct containing maps:
%       .Tau1, .Frac1 (if N>=1)
%       .Tau2, .Frac2 (if N>=2)
%       .Tau3, .Frac3 (if N>=3)
%   stats: Struct with basic stats

if nargin < 6 || isempty(num_components), num_components = 1; end
if nargin < 7, irf_custom = []; end

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
if ~isempty(irf_custom)
    excitation = irf_custom(:)';
    if numel(excitation) ~= Nt
        excitation = interp1(linspace(0, T, numel(excitation)), excitation, t, 'linear', 0);
    end
else
    excitation = DTexcitation(t, config.fwhm, config.profile, ...
        config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);
end
IRF = excitation / sum(excitation); % Sum=1

% 3. Convolution Matrix W
% ExpectedSignal = W * DecayVector
% W(g, j) represents the contribution of Decay(j) to Gate g
col = IRF(:);
row = zeros(1, Nt); row(1) = col(1);
T_IRF = toeplitz(col, row);
W = gate_profiles * T_IRF; % (N_gates x Nt)

% 4. Prepare Data
[nY, nX, nGates] = size(RawData);

% Handle Start/End Gates
if nargin < 4 || isempty(start_gate_idx), start_gate_idx = 1; end
if nargin < 5 || isempty(end_gate_idx), end_gate_idx = nGates; end
if start_gate_idx < 1, start_gate_idx = 1; end
if end_gate_idx > nGates, end_gate_idx = nGates; end
if end_gate_idx <= start_gate_idx, end_gate_idx = start_gate_idx + 1; end

gates_to_fit = start_gate_idx:end_gate_idx;
nFitGates = length(gates_to_fit);

M = nY * nX;
flatData = reshape(RawData, M, nGates)'; % (nGates, M)

% Initialize Output Maps
Results = struct();
Results.Tau1 = nan(nY, nX);
Results.Frac1 = nan(nY, nX);
if num_components >= 2
    Results.Tau2 = nan(nY, nX);
    Results.Frac2 = nan(nY, nX);
end
if num_components >= 3
    Results.Tau3 = nan(nY, nX);
    Results.Frac3 = nan(nY, nX);
end

% Flattened arrays for parallel/loop access
tau1_flat = nan(1, M);
frac1_flat = nan(1, M);
tau2_flat = nan(1, M);
frac2_flat = nan(1, M);
tau3_flat = nan(1, M);
frac3_flat = nan(1, M);

% Optimization Setup
options = optimset('Display', 'off', 'TolX', 1e-3);

% 5. Progress Bar
d = [];
if nargin >= 3 && ~isempty(fig)
    d = uiprogressdlg(fig, 'Title', 'Iterative Fitting', 'Message', 'Initializing...', 'Cancelable', true);
    d.Value = 0;
end

% 6. Fitting Loop
update_interval = floor(M / 100);
if update_interval < 1, update_interval = 1; end

% Pre-allocate t vector for speed
t_vec = t(:);

for k = 1:M
    if ~isempty(d) && d.CancelRequested, break; end

    pixel_counts = flatData(gates_to_fit, k);
    total_counts = sum(pixel_counts); % We use sum logic inside obj fun, strictly

    if sum(pixel_counts) < 10, continue; end

    try
        if num_components == 1
            % --- Mono-Exponential ---
            % x = tau
            search_range = [0.1, 10];
            tau_est = fminbnd(@(x) obj_mono(x, pixel_counts, W, gates_to_fit, t_vec), ...
                search_range(1), search_range(2), options);

            tau1_flat(k) = tau_est;
            frac1_flat(k) = 100;

        elseif num_components == 2
            % --- Bi-Exponential ---
            % x = [tau1, tau2, frac1]
            % Constraints: tau > 0, 0 <= frac1 <= 1
            % Initial Guess: [0.5, 2.5, 0.5]
            x0 = [0.5, 2.5, 0.5];

            % Using fminsearch (unconstrained) with penalties or transforms
            % Transform: tau = exp(u), frac = sigmoid(v)
            % Or simple absolute values / clamping inside objective

            [x_opt, ~] = fminsearch(@(x) obj_bi(x, pixel_counts, W, gates_to_fit, t_vec), x0, options);

            % Extract results (clamped)
            t1 = abs(x_opt(1));
            t2 = abs(x_opt(2));
            f1 = max(0, min(1, x_opt(3)));

            % Re-order so Tau1 < Tau2 for consistency?
            % Or Tau1 is the 'fast' one?
            % Usually ordered by size.
            if t1 > t2
                tmp = t1; t1 = t2; t2 = tmp;
                f1 = 1 - f1;
            end

            tau1_flat(k) = t1;
            tau2_flat(k) = t2;
            frac1_flat(k) = f1 * 100;
            frac2_flat(k) = (1 - f1) * 100;

        elseif num_components == 3
            % --- Tri-Exponential ---
            % x = [t1, t2, t3, f1, f2]
            x0 = [0.4, 1.5, 4.0, 0.33, 0.33];
            [x_opt, ~] = fminsearch(@(x) obj_tri(x, pixel_counts, W, gates_to_fit, t_vec), x0, options);

            t1 = abs(x_opt(1)); t2 = abs(x_opt(2)); t3 = abs(x_opt(3));
            f1 = max(0, min(1, x_opt(4)));
            f2 = max(0, min(1 - f1, x_opt(5)));
            f3 = 1 - f1 - f2;

            % Sort
            vars = [t1, f1; t2, f2; t3, f3];
            [~, idx] = sort(vars(:,1));
            vars = vars(idx, :);

            tau1_flat(k) = vars(1,1); frac1_flat(k) = vars(1,2) * 100;
            tau2_flat(k) = vars(2,1); frac2_flat(k) = vars(2,2) * 100;
            tau3_flat(k) = vars(3,1); frac3_flat(k) = vars(3,2) * 100;
        end

    catch
        % Failed fit stays NaN
    end

    if ~isempty(d) && mod(k, update_interval) == 0
        d.Value = k / M;
        d.Message = sprintf('Fitting pixel %d / %d', k, M);
    end
end

if ~isempty(d), close(d); end

% 7. Populate Output Maps
Results.Tau1 = reshape(tau1_flat, nY, nX);
Results.Frac1 = reshape(frac1_flat, nY, nX);

if num_components >= 2
    Results.Tau2 = reshape(tau2_flat, nY, nX);
    Results.Frac2 = reshape(frac2_flat, nY, nX);
end
if num_components >= 3
    Results.Tau3 = reshape(tau3_flat, nY, nX);
    Results.Frac3 = reshape(frac3_flat, nY, nX);
end

stats.mean = mean(tau1_flat, 'omitnan');
stats.std = std(tau1_flat, 'omitnan');
end

% --- Objective Functions ---

function ssq = obj_mono(tau, obs, W, gates, t)
if tau <= 0, ssq=1e9; return; end
d = exp(-t ./ tau);
pred = W * d;
p = pred(gates);

s = sum(p); if s>0, p=p/s; end
exp_counts = p * sum(obs);

w = 1 ./ max(exp_counts, 1e-9);
ssq = sum(((obs - exp_counts).^2) .* w);
end

function ssq = obj_bi(x, obs, W, gates, t)
t1 = abs(x(1)); t2 = abs(x(2));
f1 = x(3);
% Soft constraint on f1
if f1 < 0 || f1 > 1, ssq = 1e9 + abs(f1)*1000; return; end

d1 = exp(-t ./ t1);
d2 = exp(-t ./ t2);

% Linear combo of decays
d = f1*d1 + (1-f1)*d2;

pred = W * d;
p = pred(gates);
s = sum(p); if s>0, p=p/s; end
exp_counts = p * sum(obs);
w = 1 ./ max(exp_counts, 1e-9);
ssq = sum(((obs - exp_counts).^2) .* w);
end

function ssq = obj_tri(x, obs, W, gates, t)
t1 = abs(x(1)); t2 = abs(x(2)); t3 = abs(x(3));
f1 = x(4); f2 = x(5);
if f1 < 0 || f2 < 0 || (f1+f2) > 1, ssq = 1e9; return; end

d = f1*exp(-t./t1) + f2*exp(-t./t2) + (1-f1-f2)*exp(-t./t3);

pred = W * d;
p = pred(gates);
s = sum(p); if s>0, p=p/s; end
exp_counts = p * sum(obs);
w = 1 ./ max(exp_counts, 1e-9);
ssq = sum(((obs - exp_counts).^2) .* w);
end
