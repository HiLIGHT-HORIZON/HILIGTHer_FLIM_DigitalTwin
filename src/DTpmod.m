function P_model_grid = DTpmod(N_gates, tau_grid, t, gate_interp_fns, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, irf_shift, bWrap, dead_time, irf_custom)
if nargin < 12, irf_shift = 0; end
if nargin < 13, bWrap = false; end
if nargin < 14, dead_time = 0; end
if nargin < 15, irf_custom = []; end

% Preallocate result
P_model_grid = zeros(N_gates, length(tau_grid));

% Loop over lifetimes and gates
for k = 1:length(tau_grid)
    [pdf_k, ~] = DTpdf(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, tau_grid(k), irf_shift, bWrap, dead_time, irf_custom);

    for j = 1:N_gates
        gate_interp = gate_interp_fns{j};
        P_model_grid(j,k) = trapz(t, pdf_k .* gate_interp(t));
    end
end
end
