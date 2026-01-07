function DigitalTwin_Manual
% HILIGHT FLIM Digital Twin - Comprehensive User Manual
%
% 1. PROJECT OVERVIEW
% The HILIGHT FLIM Digital Twin is an advanced modeling environment designed
% to simulate the entire FLIM acquisition and analysis pipeline.
%
% 2. KEY MODULES & ARCHITECTURE
%
% --- Forward Model (Physics of Fluorescence) ---
% * DTpdf.m, DTexcitation.m, DTgates.m, DTpmod.m
%
% --- Inverse Problem (Statistical Analysis) ---
% * DTmle.m, DTiterative.m
%
% --- Optimization & Evaluation ---
% * DTcomputeFisherInfo, DToptimizeGates
%
% 3. SIMULATION MODES (MockData_GUI)
%
% * Lifetime Gradient:
%   Simulates a linear gradient of lifetimes across the image X-axis.
%   Each column contains repeats of the same ground-truth lifetime.
%
% * Lifetime Mix:
%   Simulates a two-species mixture where lifetimes remain constant
%   (Lifetime 1 and Lifetime 2), but their relative fractional
%   contribution varies linearly from 0% to 100% across the X-axis.
%
% 4. STATISTICAL PERFORMANCE METRICS
%
% * Background (Dark Counts):
%   A constant offset added to all gates to simulate detector noise.
%   High background values typically increase the 1/Efficiency score.
%
% * Z-Score Residuals:
%   Z = (Tau_est - Tau_true) / Sigma_crlb.
%   In 'Lifetime Mix' mode, Tau_true is the intensity-weighted mean lifetime.
%
% * 1 / Efficiency:
%   Represents how close the estimator comes to the theoretical
%   best-possible precision (CRLB).
%
% See also: MockData_GUI, FLIM_GUI, DigitalTwin_Manual

help('DigitalTwin_Manual');
end
