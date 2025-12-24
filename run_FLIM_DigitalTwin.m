
function [tau_true, F, p_eff, mean_tau, std_tau] = run_FLIM_DigitalTwin( ...
    T, fwhm, profile, toff, tau_min, tau_max, tau_stp, r, ...
    N_gates, N_photons, M, dt, tauE_min, tauE_max, tauE_stp, ...
    updateProgress, updateTime, ax, axF, axEff, axTau,...
    rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, gate_edges)

startTime = tic;

% Time and lifetime setup
t = 0:dt:T;
tau_true = linspace(tau_min, tau_max, tau_stp);
tau_grid = linspace(tauE_min, tauE_max, tauE_stp);

% Allocate result arrays
F = zeros(1, tau_stp);
p_eff = zeros(1, tau_stp);
mean_tau = zeros(1, tau_stp);
std_tau = zeros(1, tau_stp);

startTime = tic;
colors = lines(max(tau_stp, N_gates));


gate_profiles = DTgates(t, r, gate_edges);
gate_interp_fns = cell(N_gates, 1);
for i = 1:N_gates
    gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
end



% Draw gate layout once
cla(ax); hold(ax, 'on');
gate_colors = lines(N_gates);
for i = 1:N_gates
    plot(ax,t,gate_interp_fns{i}.Values,'Color',gate_colors(i,:),'LineWidth',3)
end

for tau_i = 1:tau_stp
    [pdf, cdf] = DTpdf(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma,  tau_true(tau_i));

    gate_hist_all = zeros(N_gates, M);
    N_detections = zeros(1, M);

    %PAR
    parfor m = 1:M
        photon_times = randsample(t, N_photons, true, pdf);

        counts = zeros(N_gates, 1);
        for i = 1:N_gates
            gate_vals = gate_interp_fns{i}(photon_times);
            detected = rand(1,N_photons) < gate_vals;
            counts(i) = sum(detected);
        end

        N_detections(m) = sum(counts);
        gate_hist_all(:, m) = counts;
    end

    P_model_grid = DTpmod(N_gates, tau_grid, t, gate_interp_fns, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma);

    % Maximum likelihood estimation


    [~, stats] = DTmle(N_detections, gate_hist_all, tau_grid, P_model_grid);

    % Store outputs
    F(tau_i) = stats.F;
    p_eff(tau_i) = stats.p_eff;
    mean_tau(tau_i) = stats.mean;
    std_tau(tau_i) = stats.std;

    % Optional PDF plot
    if isa(ax, 'matlab.ui.control.UIAxes')
        updatePlotPDF(ax, gate_edges, N_gates, T, t, pdf, tau_true(tau_i), tau_i, tau_stp, [0 0 0]);
    end

    % GUI updates
    if isa(updateProgress, 'function_handle')
        updateProgress(tau_i, tau_stp);
    end
    if isa(updateTime, 'function_handle')
        elapsed = toc(startTime);
        updateTime(tau_i, tau_stp, elapsed);
    end


    

end

% === Post-simulation stats and plots ===
    
    % F-value plot
    if isa(axF, 'matlab.ui.control.UIAxes')
        %cla(axF); hold(axF, 'on');
        plot(axF, tau_true, F, '-', 'Color', colors(i,:), 'LineWidth', 2);
        %plot(axF, [0, max(tau_true)], [1 1], 'k--');
        title(axF, 'F-value vs τ'); xlabel(axF, 'Simulated τ (ns)'); ylabel(axF, 'F-value');
        grid(axF, 'on');
    end
    
    % Efficiency plot
    if isa(axEff, 'matlab.ui.control.UIAxes')
        %cla(axEff);
        plot(axEff, tau_true, p_eff, '-','Color', colors(i,:), 'LineWidth', 2);
        title(axEff, 'Photon Efficiency vs τ');
        xlabel(axEff, 'Simulated τ (ns)'); ylabel(axEff, 'Efficiency (1/F²)');
        ylim(axEff, [0 1.05]);
        grid(axEff, 'on');
    end
    
    % τ estimation plot
    if isa(axTau, 'matlab.ui.control.UIAxes')
        %cla(axTau); hold(axTau, 'on');
        errorbar(axTau, tau_true, mean_tau, std_tau, 'Color', colors(i,:), 'LineWidth', 1.5);
        plot(axTau, tau_true, tau_true, 'k--');
        title(axTau, 'Estimated τ ± std vs Simulated τ');
        xlabel(axTau, 'Simulated τ (ns)'); ylabel(axTau, 'Estimated τ (ns)');
        grid(axTau, 'on');
    end
    
    % Finalize PDF panel
    title(ax, 'All Emission PDFs with Gate Layout');
    xlim(ax, [-0.5 T+0.5]); ylim(ax, [-0.05 1.05]); 
end


function updatePlotPDF(ax, gate_edges, N_gates, T, t, pdf, tau_val, tau_idx, tau_stp, color)
    if isempty(ax) || ~isvalid(ax), return; end
    plot(ax, t, pdf / max(pdf), 'Color', color, 'LineWidth', 1.5);
    title(ax, sprintf('τ = %.2f ns (%d of %d)', tau_val, tau_idx, tau_stp));
    xlabel(ax, 'Time (ns)'); ylabel(ax, 'Amplitude');
    xlim(ax, [-0.5 T+0.5]); ylim(ax, [-0.05 1.05]);
    drawnow limitrate;
end