function [fisher_info, f_value, t] = DTcomputeFisherInfo(gate_edges, irf_params, gate_r, T_max, tau_grid, n_photons)
% DTCOMPUTEFISHERINFO - Calculate Fisher Information and F-value for given gates
%
% Inputs:
%   gate_edges : Vector of gate edges (ns)
%   irf_params : Struct with IRF parameters
%   gate_r     : Gate rise time (ns)
%   T_max      : Max time (ns)
%   tau_grid   : Vector of lifetimes to evaluate (ns)
%   n_photons  : Number of photons (scaling factor)
%
% Outputs:
%   fisher_info : Vector of Fisher Information values corresponding to tau_grid
%   f_value     : Vector of F-values (sqrt(N)/F) or (std/mean * sqrt(N))
%                 F-value usually defined as F = (sigma_tau / tau) * sqrt(N).
%                 CRLB variance = 1/FI. sigma_tau = 1/sqrt(FI).
%                 So F = (1/sqrt(FI) / tau) * sqrt(N) = sqrt(N/FI) / tau * sqrt(N) ?
%                 Wait. F = normalized standard deviation = (std(tau)/tau) * sqrt(N).
%                 std(tau) = 1/sqrt(I).
%                 So F = (1/sqrt(I) / tau) * sqrt(N) = sqrt(N / (I * tau^2)).
%                 Note: I includes n_photons factor?
%                 If Input n_photons is N, then I ~ N.
%                 Then F = sqrt(N / (N * i_1 * tau^2)) = 1 / (tau * sqrt(i_1)).
%                 Let's calculate based on I provided.
%   t           : Time vector used

if nargin < 6, n_photons = 1; end

dt = 0.01;
t = 0:dt:T_max;
epsilon = 1e-4;

% Prepare Gate Profiles
gate_profiles = DTgates(t, gate_r, gate_edges);

% Prepare Probabilities and Derivatives
N_tau = length(tau_grid);
fisher_info = zeros(1, N_tau);

for k = 1:N_tau
    tau_val = tau_grid(k);

    % We need derivatives dP/dtau. Use central difference.
    taus = [tau_val, tau_val*exp(epsilon), tau_val*exp(-epsilon)];

    % Compute PDFs
    P_gates = zeros(size(gate_profiles, 1), 3);

    for j = 1:3
        [pdf, ~] = DTpdf(t, irf_params.fwhm, irf_params.profile, ...
            irf_params.rise_time, irf_params.fall_time, ...
            irf_params.bPulseTrain, irf_params.PT_Trep, ...
            irf_params.PT_sigma, taus(j));

        % Integrate against gates
        % P_i = sum(pdf * gate_i * dt)
        % pdf is density, sum(pdf * dt) ~ 1
        % gate_profiles is [Ng x Nt]
        % pdf is [1 x Nt] (or column?)
        pdf = pdf(:)';

        % Batch multiply
        % P_gates(:, j) = (gate_profiles * pdf'); % Matrix: [Ng x Nt] * [Nt x 1] -> [Ng x 1]
        % Remove * dt because pdf is already discrete probability mass (sum=1)
        P_gates(:, j) = (gate_profiles * pdf');
    end

    P_cen = P_gates(:, 1);
    P_plus = P_gates(:, 2);
    P_minus = P_gates(:, 3);

    % Derivative dP/dtau
    dP_dtau = (P_plus - P_minus) / (2 * epsilon * tau_val);

    % Fisher Info = n * sum( (dP/dtau)^2 / P )
    P_floor = 1e-12;
    P_safe = max(P_cen, P_floor);

    fi_elem = (dP_dtau.^2) ./ P_safe;
    fisher_info(k) = n_photons * sum(fi_elem);
end

% F-value
% F = (sigma_tau / tau) * sqrt(N)
% CRLB sigma_tau = 1 / sqrt(I)
% F = (1/sqrt(I) / tau) * sqrt(N) = sqrt(N/I) / tau
% Note: I scales with N. So I = N * i_1.
% F = sqrt(N / (N * i_1)) / tau = 1 / (tau * sqrt(i_1))
% This is independent of N.
% So we can compute it directly.

sigma_tau = 1 ./ sqrt(fisher_info);
f_value = (sigma_tau ./ tau_grid) * sqrt(n_photons);

end
