function [limaResults, stats] = DTlima(RawData, config, harmonic, ~)
% DTLIMA - Lifetime Moments Analysis (LiMA)
% Based on Esposito et al., Biophysical Journal 2005.
%
% This implementation converts gated TD data to FD-like coordinates (G, S)
% and computes the moments and heterogeneity index.

[nY, nX, nGates] = size(RawData);
if nargin < 3 || isempty(harmonic), harmonic = 1; end

% 1. Setup Time and IRF
dt = config.dt; T = config.T; t = 0:dt:T;
irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);
irf = irf / sum(irf);

% Fundamental frequency adjusted by harmonic
omega = harmonic * (2*pi / T);

% Fourier coefficients of IRF
g_irf = sum(irf .* cos(omega * t));
s_irf = sum(irf .* sin(omega * t));
m_irf = sqrt(g_irf^2 + s_irf^2);
phi_irf = atan2(s_irf, g_irf);

% Gate centers
gate_edges = config.gate_edges;
gate_centers = (gate_edges(1:end-1) + gate_edges(2:end)) / 2;

% Cos/Sin weights for gates
gc = cos(omega * gate_centers);
gs = sin(omega * gate_centers);

% Compute per pixel
flatData = double(reshape(RawData, [], nGates));
sums = sum(flatData, 2);
sums(sums == 0) = 1;

G_raw = (flatData * gc') ./ sums;
S_raw = (flatData * gs') ./ sums;

% Deconvolution (Frequency Domain)
m_raw = sqrt(G_raw.^2 + S_raw.^2);
phi_raw = atan2(S_raw, G_raw);

m_corr = m_raw ./ m_irf;
phi_corr = phi_raw - phi_irf;

G = m_corr .* cos(phi_corr);
S = m_corr .* sin(phi_corr);

% 2. LiMA Moments
% Reduced units (dimensionless)
% x_phi = tan(phi) = S/G
% x_m = sqrt(M^-2 - 1)

% Clip to avoid singularities
G_safe = G; G_safe(abs(G) < 1e-9) = 1e-9;
x_phi = S ./ G_safe;

M_val = sqrt(G.^2 + S.^2); % Corrected element-wise power
M_safe = min(max(M_val, 1e-6), 1.0);
x_m = sqrt(1./(M_safe.^2) - 1);

% Moments
% First moment (Mean) = x_phi
% Second moment (I2) = 1/2 (x_m^2 + x_phi^2)
mu = x_phi;
I2 = 0.5 * (x_m.^2 + x_phi.^2);

% Heterogeneity (Standard deviation sigma)
% sigma^2 = 1/2 (x_m^2 - x_phi^2)
sigma_sq = 0.5 * (x_m.^2 - x_phi.^2);
sigma = sqrt(max(sigma_sq, 0));

% Convert to time units (ns)
limaResults.mu_tau = reshape(mu / omega, nY, nX);
limaResults.I2 = reshape(I2, nY, nX);
limaResults.sigma_tau = reshape(sigma / omega, nY, nX);

% Extra stats
stats.omega = omega;
stats.mean_mu = mean(limaResults.mu_tau(:), 'omitnan');
stats.mean_sigma = mean(limaResults.sigma_tau(:), 'omitnan');
stats.G = reshape(G, nY, nX);
stats.S = reshape(S, nY, nX);
end
