function [best_edges, best_J, info] = DToptimizeGates(N_gates, T_max, tau_range, irf_params, gate_params, optim_params)
% DTOPTIMIZEGATES - Optimize detection gates for robust Fisher Information
%
% Inputs:
%   N_gates      : number of gates
%   T_max        : maximum time (ns)
%   tau_range    : [min, max] lifetime to optimize over
%   irf_params   : struct with fields: fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma
%   gate_params  : struct with fields: rise_time (r)
%   optim_params : struct with fields: n_restarts (default 20), n_photons (default 1)
%
% Outputs:
%   best_edges : (N_gates+1) vector of optimized gate edges
%   best_J     : final objective value (log-integrated FI)
%   info       : struct with detailed results (FI_curve, tau_grid, etc.)

    % Default optimization parameters
    if nargin < 6 || isempty(optim_params)
        optim_params.n_restarts = 20;
        optim_params.n_photons = 1; 
        optim_params.N_tau = 50;
    end
    if ~isfield(optim_params, 'n_restarts'), optim_params.n_restarts = 20; end
    if ~isfield(optim_params, 'n_photons'), optim_params.n_photons = 1; end
    if ~isfield(optim_params, 'N_tau'), optim_params.N_tau = 50; end
    
    % Simulation parameters
    dt = 0.01; % Time step for PDF generation (ns)
    t = 0:dt:T_max;
    
    
    % Prepare PDF grid
    % We need PDFs for tau and tau*(1 +/- eps) to compute derivatives
    epsilon = 1e-4;
    
    % Define the target tau grid for the objective function (log-spaced)
    % Use exact number of steps requested by user
    N_tau = optim_params.N_tau; 
    tau_grid_log = linspace(log(tau_range(1)), log(tau_range(2)), N_tau);
    tau_grid = exp(tau_grid_log);
    
    % Precompute ALL PDFs needed:
    % For each tau in tau_grid, we need P(tau), P(tau*exp(eps)), P(tau*exp(-eps))
    % Actually simpler: compute dP/dtau numerically.
    % To vectorize, let's precompute the emission PDFs s(t|tau) for all required taus.
    
    taus_central = tau_grid;
    taus_plus    = tau_grid * exp(epsilon);
    taus_minus   = tau_grid * exp(-epsilon);
    
    % Combine to batch generate
    all_taus = [taus_central, taus_plus, taus_minus];
    unique_taus = unique(all_taus);
    
    % Generate emission profiles s(t|tau)
    % s_matrix: [length(t) x length(unique_taus)]
    s_matrix = zeros(length(t), length(unique_taus));
    
    for k = 1:length(unique_taus)
        tau_val = unique_taus(k);
        % Call DTpdf
        % function [pdf, cdf] = DTpdf(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, tau)
        [pdf_val, ~] = DTpdf(t, irf_params.fwhm, irf_params.profile, ...
                             irf_params.rise_time, irf_params.fall_time, ...
                             irf_params.bPulseTrain, irf_params.PT_Trep, ...
                             irf_params.PT_sigma, tau_val);
                             
        % Ensure normalization just in case, though DTpdf does it
        s_matrix(:, k) = pdf_val(:) * dt; % Probabilities per bin (approx)
        % Actually, strictly DTpdf returns pdf density. * dt makes it probability mass if summed.
        % We will do integration against gates later.
        s_matrix(:, k) = pdf_val(:);
    end
    
    % Helper to look up s(t) for a specific tau vector
    function s_cols = get_s_cols(query_taus)
       [~, idxs] = ismember(query_taus, unique_taus);
       s_cols = s_matrix(:, idxs); 
    end

    s_central = get_s_cols(taus_central);
    s_plus    = get_s_cols(taus_plus);
    s_minus   = get_s_cols(taus_minus);

    % Optimization variables:
    % N_gates items. We need N_gates relative widths (u), 1 total duration (v), 1 start offset (z).
    % Dim = N_gates + 2.
    % Wait, mapping says: u_1...u_N for widths.
    n_vars = N_gates + 2;
    
    % Objective function wrapper
    obj_fun = @(params) -compute_objective(params, N_gates, T_max, gate_params.rise_time, ...
                                           t, dt, s_central, s_plus, s_minus, ...
                                           optim_params.n_photons, tau_grid, epsilon);
    
    % Multi-start optimization
    best_opt_val = inf; % we are minimizing negative J
    best_params = [];
    
    for i = 1:optim_params.n_restarts
        % Random initialization
        % u: random normal around 0 (equal widths initially)
        u_init = randn(1, N_gates) * 0.5;
        % v: total duration, want it usually large, so v > 0
        v_init = 2 + randn; 
        % z: offset, around 0 (centered in allowable range?)
        z_init = randn;
        
        initial_params = [u_init, v_init, z_init];
        
        options = optimset('Display','off', 'MaxIter', 500);
        [params_opt, val_opt] = fminsearch(obj_fun, initial_params, options);
        
        if val_opt < best_opt_val
            best_opt_val = val_opt;
            best_params = params_opt;
        end
    end
    
    % Decode best solution
    [best_edges, ~] = decode_params(best_params, N_gates, T_max);
    
    % Compute final statistics
    best_J = -best_opt_val;
    [~, I_tau] = compute_objective(best_params, N_gates, T_max, gate_params.rise_time, ...
                                   t, dt, s_central, s_plus, s_minus, ...
                                   optim_params.n_photons, tau_grid, epsilon);
                                   
    info.tau_grid = tau_grid;
    info.fisher_info = I_tau;
    info.gate_edges = best_edges;
    info.t = t;
    info.gate_profiles = DTgates(t, gate_params.rise_time, best_edges);
    
end

function [J, I_tau] = compute_objective(params, N_gates, T_max, r, t, dt, s_cen, s_pus, s_mus, n_photons, tau_grid, eps_val)
    % 1. Decode parameters to physical gate edges
    [gate_edges, ~] = decode_params(params, N_gates, T_max);
    
    % 2. Build gate functions g_i(t)
    % gate_profiles: [N_gates x length(t)]
    gate_profiles = DTgates(t, r, gate_edges);
    
    % 3. Compute Gate Probabilities P_i(tau)
    % P_i = integral s(t|tau) * g_i(t) dt
    % s_cen has sum(s_cen) = 1 (discrete probability mass).
    % So integral becomes sum. Multiplying by dt is incorrect if s_cen is already normalized to sum=1.
    
    P_central = (gate_profiles * s_cen);
    P_plus    = (gate_profiles * s_pus);
    P_minus   = (gate_profiles * s_mus);    
    % 4. Compute Derivatives dPi/dtau
    % dPi/dtau approx (Pi(tau*e^e) - Pi(tau*e^-e)) / (2*e*tau)
    % Note: The denominator is 2*epsilon*tau. 
    % Wait, the user specified: stable log-space central difference
    % dPi/dtau approx ( P(tau*e^eps) - P(tau*e^-eps) ) / (2 * eps * tau)
    
    dP_dtau = (P_plus - P_minus) ./ (2 * eps_val * tau_grid);
    
    % 5. Compute Fisher Information I(tau)
    % I(tau) = n * sum_i ( (dPi/dtau)^2 / Pi )
    P_floor = 1e-12;
    P_safe = max(P_central, P_floor);
    
    fisher_elem = (dP_dtau.^2) ./ P_safe;
    I_tau = n_photons * sum(fisher_elem, 1); % sum over gates (rows) -> [1 x Ntau]
    
    % 6. Compute Robust Objective J
    % J = integral w(tau) log(I(tau)) dtau
    % w(tau) propto 1/tau.
    % The user suggests trapezoidal quadrature on log(tau).
    % J = integral_{log_tmin}^{log_tmax} log(I(tau)) d(log_tau)
    % Since we have tau_grid log-spaced, log(tau) is uniform.
    % So we can just sum log(I(tau)) or use trapz on log(I(tau)).
    
    I_floor = 1e-12;
    log_I = log(max(I_tau, I_floor));
    
    % Integrate over log(tau)
    % tau_grid_log was linear, so dx is constant.
    log_tau = log(tau_grid);
    J = trapz(log_tau, log_I);
    
    % We maximize J, so minimize -J
end

function [gate_edges, D] = decode_params(params, N_gates, T_max)
    u = params(1:N_gates);
    v = params(N_gates+1);
    z = params(N_gates+2);
    
    % 1. Total duration D
    % D = T_max * sigma(v)
    D = T_max * (1 ./ (1 + exp(-v)));
    
    % 2. Gate widths Delta_i
    % softmax(u)
    expu = exp(u - max(u)); % stability
    soft_u = expu / sum(expu);
    widths = D * soft_u;
    
    % 3. Start offset t0
    % t0 range? Users says: t0 = t0_min + (t0_max - t0_min) * sigma(z)
    % Need to define min/max.
    % Max possible start is T_max - D. Min is 0.
    t0_min = 0;
    t0_max = max(0, T_max - D); 
    
    t0 = t0_min + (t0_max - t0_min) * (1 ./ (1 + exp(-z)));
    
    % 4. Edges
    % t1 = t0, t2 = t1+w1, ...
    gate_edges = zeros(1, N_gates+1);
    gate_edges(1) = t0;
    current_t = t0;
    for i = 1:N_gates
        current_t = current_t + widths(i);
        gate_edges(i+1) = current_t;
    end
end
