function [fractionMaps, patterns, stats] = DTpatternmatching(RawData, patternsIn, config, fig, irf_custom)
% DTPATTERNMATCHING - Linear Decomposition using reference patterns
% Based on the principle described in Niehörster et al., Nature Methods 2016.
%
% Inputs:
%   RawData: (nY, nX, nGates) matrix of photon counts
%   patternsIn: Either:
%       - Vector of reference lifetimes (e.g. [1.0, 3.0]) -> Patterns generated
%       - Matrix (nGates, K) of explicit reference decay patterns
%   config: Configuration struct (dt, T, IRF, etc.)
%   fig: (Optional) figure handle for progress bar
%   irf_custom: (Optional) Custom IRF vector
%
% Outputs:
%   fractionMaps: (nY, nX, K) maps of pattern contributions
%   patterns: (nGates, K) matrix of reference patterns used
%   stats: Basic statistics

if nargin < 5, irf_custom = []; end

[nY, nX, nGates] = size(RawData);
M = nY * nX;

% 1. Determine Patterns Source
if isvector(patternsIn) && length(patternsIn) < nGates
    % Treat as Tau References
    tau_refs = patternsIn;
    K = length(tau_refs);

    % Setup Time and Gate Functions
    dt = config.dt; T = config.T; t = 0:dt:T;
    gate_profiles = DTgates(t, config.r, config.gate_edges);
    gate_interp_fns = cell(nGates, 1);
    for i = 1:nGates
        gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
    end

    % Generate Reference Patterns
    patterns = DTpmod(nGates, tau_refs, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma, 0, false, 0, irf_custom);
else
    % Treat as Explicit Patterns
    patterns = patternsIn;
    [pGates, K] = size(patterns);
    if pGates ~= nGates
        error('Pattern gate count (%d) does not match data gate count (%d)', pGates, nGates);
    end
end

% 2. Normalize patterns (sum to 1)
% Critical for interpreting weights as photon contributions
for k = 1:K
    s = sum(patterns(:, k));
    if s > 0
        patterns(:, k) = patterns(:, k) / s;
    end
end

% 3. Linear Decomposition
% We solve Y = Patterns * Weights
% Using Pseudo-inverse for speed (Ordinary Least Squares)
% A more robust approach would be Non-Negative Least Squares (NNLS) to avoid negative contributions
% But pinv is much faster for interactive use.

flatData = double(reshape(permute(RawData, [3, 1, 2]), nGates, M)); % (nGates, M)

% Solver: Weighted or Ordinary?
pinvP = pinv(patterns);
weights = pinvP * flatData; % (K, M)

% Reshape results
fractionMaps = reshape(weights', nY, nX, K);

% 4. Stats
stats.mean_weights = mean(weights, 2);
if exist('tau_refs', 'var')
    stats.tau_refs = tau_refs;
end
end
