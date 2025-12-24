function GateOptimizer_GUI(initial_irf_params, initial_T_max, initial_tau_params, updateCallback, initial_gate_params)
% GATEOPTIMIZER_GUI - GUI for optimizing detection gates
    
    if nargin < 1 || isempty(initial_irf_params)
        % Default IRF logic...
        initial_irf_params.fwhm = 5;
        % ...
    end
    if nargin < 2 || isempty(initial_T_max)
        initial_T_max = 50;
    end
    if nargin < 3 || isempty(initial_tau_params)
        initial_tau_params.min = 0.5;
        initial_tau_params.max = 5.0;
        initial_tau_params.steps = 50;
    end
    if nargin < 4
        updateCallback = [];
    end
    if nargin < 5 || isempty(initial_gate_params)
        initial_gate_params.rise_time = 0.001; 
    end

    fig = uifigure('Name', 'HILIGHT Detection Gate Optimizer', 'Position', [150 150 1000 700]);
    
    % Store current params
    irf_params = initial_irf_params;

    % Layout: Left Control Panel (300px), Right Plots
    % Layout: Left Control Panel (300px), Right Plots
    mainGrid = uigridlayout(fig, [1, 2]);
    mainGrid.ColumnWidth = {300, '1x'};
    
    % Control Panel
    % Control Panel
    panelControl = uipanel(mainGrid, 'Title', 'Optimization Settings');
    
    layout = uigridlayout(panelControl, [14, 2]);
    layout.RowHeight = {25, 25, 25, 25, 25, 25, 25, 25, 25, 25, 40, 30, '1x', 25};
    layout.ColumnWidth = {'1x', '1x'};
    
    % Inputs
    uilabel(layout, 'Text', 'Number of Gates:');
    nGateField = uieditfield(layout, 'numeric', 'Value', 4);
    
    uilabel(layout, 'Text', 'Max Time (T, ns):');
    maxTimeField = uieditfield(layout, 'numeric', 'Value', initial_T_max);
    
    uilabel(layout, 'Text', 'Tau Min (ns):');
    tauMinField = uieditfield(layout, 'numeric', 'Value', initial_tau_params.min);
    
    uilabel(layout, 'Text', 'Tau Max (ns):');
    tauMaxField = uieditfield(layout, 'numeric', 'Value', initial_tau_params.max);
    
    uilabel(layout, 'Text', 'Tau Steps:');
    tauStepsField = uieditfield(layout, 'numeric', 'Value', initial_tau_params.steps);
    
    uilabel(layout, 'Text', 'Gate Rise Time (ns):');
    riseTimeField = uieditfield(layout, 'numeric', 'Value', initial_gate_params.rise_time);
    
    uilabel(layout, 'Text', 'Restarts:');
    restartsField = uieditfield(layout, 'numeric', 'Value', 20);
    
    % Separator or Label
    lbl = uilabel(layout, 'Text', 'Current IRF:');
    lbl.FontWeight = 'bold';
    lbl.Layout.Column = 1;
    
    irfDescLabel = uilabel(layout, 'Text', sprintf('%s\nFWHM: %.2g ns', irf_params.profile, irf_params.fwhm));
    irfDescLabel.Layout.Column = 2;
    irfDescLabel.Layout.Row = [8 9];
    irfDescLabel.VerticalAlignment = 'top';

    % Run Button
    btnOptimize = uibutton(layout, 'Text', 'OPTIMIZE', 'FontWeight', 'bold', 'BackgroundColor', [0.2 0.8 0.2]);
    btnOptimize.Layout.Column = [1 2];
    btnOptimize.Layout.Row = 11;
    
    % Export Button
    btnExport = uibutton(layout, 'Text', 'Export to Main GUI', 'BackgroundColor', [0.8 0.9 1.0]);
    btnExport.Layout.Column = [1 2];
    btnExport.Layout.Row = 12;
     
    % Status Label
    statusLabel = uilabel(layout, 'Text', 'Ready');
    statusLabel.Layout.Column = [1 2];
    statusLabel.Layout.Row = 14;

    % Right Panel: Plots and Results
    % Right Panel: Plots and Results
    panelResults = uipanel(mainGrid, 'Title', 'Results');
    resultsLayout = uigridlayout(panelResults, [4, 1]);
    resultsLayout.RowHeight = {'1x', '1x', 45, '0.5x'};
    
    axGates = uiaxes(resultsLayout);
    title(axGates, 'Optimized Gates & Excitation');
    xlabel(axGates, 'Time (ns)');
    ylabel(axGates, 'Amplitude');
    
    axFisher = uiaxes(resultsLayout);
    title(axFisher, 'Fisher Information vs Tau');
    xlabel(axFisher, 'Tau (ns)');
    ylabel(axFisher, 'Fisher Info (a.u.)');
    axFisher.XScale = 'log';
    axFisher.YScale = 'log';
    
    % Controls Row
    ctrlGrid = uigridlayout(resultsLayout, [1, 4]);
    ctrlGrid.ColumnWidth = {'1x', '1x', '1x', '1x'};
    
    lblScale = uilabel(ctrlGrid, 'Text', 'Scale:', 'HorizontalAlignment', 'right');
    swScale = uiswitch(ctrlGrid, 'Items', {'Log', 'Linear'}, 'Value', 'Log');
    
    lblMetric = uilabel(ctrlGrid, 'Text', 'Metric:', 'HorizontalAlignment', 'right');
    swMetric = uiswitch(ctrlGrid, 'Items', {'Fisher Info', 'F-value'}, 'Value', 'Fisher Info');
    
    % Text output area
    txtResults = uitextarea(resultsLayout);
    txtResults.Editable = 'on'; % Allow copying
    
    % State variables
    currentResults = [];
    
    % Initialize (simulate a run with equal gates to populate plots)
    initializePlots();

    % Callbacks
    swScale.ValueChangedFcn = @(btn, event) updatePlots();
    swMetric.ValueChangedFcn = @(btn, event) updatePlots();
    btnOptimize.ButtonPushedFcn = @(btn, event) runOptimization();
    btnExport.ButtonPushedFcn = @(btn, event) exportGates();

    function exportGates()
        if isempty(currentResults) || isempty(updateCallback)
            statusLabel.Text = 'Nothing to export.';
            return;
        end
        try
            updateCallback(currentResults.opt.edges);
            statusLabel.Text = 'Gates exported to Main GUI.';
        catch err
            statusLabel.Text = 'Export failed.';
            fprintf('Export error: %s\n', err.message);
        end
    end
    
    function initializePlots()
        % Perform a 'fake' optimization run (0 restarts) just to get baseline and initial layout
        % Or better: just compute baseline and show it.
        
        N_gates_init = nGateField.Value;
        T_max_init = maxTimeField.Value;
        tau_range_init = [tauMinField.Value, tauMaxField.Value];
        N_tau_init = tauStepsField.Value;
        
        % Time vector
        dt = 0.01;
        t = 0:dt:T_max_init;
        
        % Baseline Edges
        base_edges = linspace(0, T_max_init, N_gates_init + 1);
        
        % Current Gates (initially equal) used as 'optimized'
        gate_profiles = DTgates(t, riseTimeField.Value, base_edges);
        
        % Excitation
        excitation = DTexcitation(t, irf_params.fwhm, irf_params.profile, ...
                irf_params.rise_time, irf_params.fall_time, irf_params.bPulseTrain, irf_params.PT_Trep, irf_params.PT_sigma);
                
        % Compute Metrics
        tau_grid_log = linspace(log(tau_range_init(1)), log(tau_range_init(2)), N_tau_init);
        tau_grid = exp(tau_grid_log);
        
        [base_FI, base_F, ~] = DTcomputeFisherInfo(base_edges, irf_params, riseTimeField.Value, T_max_init, tau_grid, 1e4);
        
        % Store initial state
        currentResults.opt.edges = base_edges;
        currentResults.opt.gate_profiles = gate_profiles;
        currentResults.opt.FI = base_FI;
        currentResults.opt.F = base_F;
        
        currentResults.base = currentResults.opt; % Baseline is same as current initially
        
        currentResults.t = t;
        currentResults.tau_grid = tau_grid;
        currentResults.excitation = excitation;
        currentResults.tau_range = tau_range_init; % Store range for plotting decays
        
        updatePlots();
    end

    function runOptimization()
        try
            % Reset plots / state
            cla(axGates); legend(axGates, 'off');
            cla(axFisher); legend(axFisher, 'off');
            currentResults = []; % Clear previous state
            
            % Disable button
            btnOptimize.Enable = 'off';
            statusLabel.Text = 'Optimizing... (this may take a moment)';
            drawnow;
            
            % Gather params
            N_gates = nGateField.Value;
            T_max = maxTimeField.Value;
            tau_range = [tauMinField.Value, tauMaxField.Value];
            
            gate_params.rise_time = riseTimeField.Value;
            
            optim_params.n_restarts = restartsField.Value;
            optim_params.n_photons = 1e4; 
            optim_params.N_tau = tauStepsField.Value;
            
            % 1. Run Optimization
            [best_edges, best_J, info] = DToptimizeGates(N_gates, T_max, tau_range, irf_params, gate_params, optim_params);
            
            % 2. Calculate Baseline (Equal Gates)
            % Equal spacing filling [0, T_max] or [0, last_edge]? 
            % Usually T_max.
            base_edges = linspace(0, T_max, N_gates + 1);
            
            [base_FI, base_F, ~] = DTcomputeFisherInfo(base_edges, irf_params, gate_params.rise_time, T_max, info.tau_grid, optim_params.n_photons);
            
            % 3. Calculate Optimized F-value
            sigma_tau = 1 ./ sqrt(info.fisher_info);
            opt_F = (sigma_tau ./ info.tau_grid) * sqrt(optim_params.n_photons);

            % 4. Get Excitation Profile for plotting
            excitation = DTexcitation(info.t, irf_params.fwhm, irf_params.profile, ...
                irf_params.rise_time, irf_params.fall_time, irf_params.bPulseTrain, irf_params.PT_Trep, irf_params.PT_sigma);
            
            % Store Results
            currentResults.opt.edges = best_edges;
            currentResults.opt.gate_profiles = info.gate_profiles;
            currentResults.opt.FI = info.fisher_info;
            currentResults.opt.F = opt_F;
            
            currentResults.base.edges = base_edges;
            currentResults.base.gate_profiles = DTgates(info.t, gate_params.rise_time, base_edges);
            currentResults.base.FI = base_FI;
            currentResults.base.F = base_F;
            
            currentResults.t = info.t;
            currentResults.tau_grid = info.tau_grid;
            currentResults.excitation = excitation;
            currentResults.best_J = best_J;
            currentResults.tau_range = tau_range;
            
            % Update UI
            updatePlots();
            
            % TODO: Sync back to main GUI? 
            % The user asked: "When the optimization stops, I would like to gates to be adjusted to the new optimized position"
            % This implies we might need a handle to the calling GUI or output argument, or just print them.
            % Since this is a separate window, maybe we can copy to clipboard or display boldly.
            % However, if started from FLIM_GUI, we cannot easily reach back without a callback or handle.
            % For now, let's make it very clear in the text output.
            
            str = sprintf('Optimization Complete.\nObjective (J): %.4e\n\nOptimized Edges (ns):\n%s\n\nBaseline Edges (ns):\n%s', ...
                          best_J, ...
                          mat2str(best_edges, 4), ...
                          mat2str(base_edges, 4));
            % Automatic sync removed as per user request. Use Export button.

            
            txtResults.Value = str;
            
            statusLabel.Text = 'Done.';
            
        catch ME
            statusLabel.Text = 'Error occurred.';
            report = getReport(ME, 'extended', 'hyperlinks', 'off');
            uialert(fig, report, 'Optimization Error');
            fprintf('Error in Optimization: %s\n', report);
        end
        % Re-enable
        btnOptimize.Enable = 'on';
    end

    function updatePlots()
        if isempty(currentResults), return; end
        
        % Plot Gates & Excitation
        cla(axGates);
        hold(axGates, 'on');
        
        % Normalize Excitation for visibility (scale to 0.8 max gate?)
        max_gate = 1; 
        if max(currentResults.excitation) > 0
            % Plot Excitation
            exc_scaled = currentResults.excitation / max(currentResults.excitation) * 0.8 * max_gate;
            plot(axGates, currentResults.t, exc_scaled, 'Color', [0.7 0.7 0.7], 'LineWidth', 1, 'DisplayName', 'Excitation');
        end

        % Plot Gates
        plot(axGates, currentResults.t, currentResults.opt.gate_profiles, 'LineWidth', 1.5, 'DisplayName', 'Gates');
        
        % Plot Decays (All tau grid used in optimization)
        % Reduce density if too many for visualization (e.g. max 10 curves)
        taus_to_plot = currentResults.tau_grid;
        if length(taus_to_plot) > 10
            indices = round(linspace(1, length(taus_to_plot), 10));
            taus_to_plot = taus_to_plot(indices);
        end
        
        % Plot them as thin gray lines to show the "envelope"
        for i = 1:length(taus_to_plot)
            [pdf_val, ~] = DTpdf(currentResults.t, irf_params.fwhm, irf_params.profile, irf_params.rise_time, irf_params.fall_time, ...
                                 irf_params.bPulseTrain, irf_params.PT_Trep, irf_params.PT_sigma, taus_to_plot(i));
            if max(pdf_val) > 0
                 pdf_scaled = pdf_val / max(pdf_val); % Normalize to 1
                 % Only label min and max for legend clarity
                 if i == 1
                    dn = sprintf('Decay %.1fns (Min)', taus_to_plot(i));
                    ls = '--';
                 elseif i == length(taus_to_plot)
                    dn = sprintf('Decay %.1fns (Max)', taus_to_plot(i));
                    ls = '-';
                 else
                     dn = ''; % hidden from legend
                     ls = '-';
                 end
                 
                 p = plot(axGates, currentResults.t, pdf_scaled, 'Color', [0.2 0.2 0.2 0.3], 'LineWidth', 0.5, 'LineStyle', ls);
                 if ~isempty(dn)
                     p.DisplayName = dn;
                 else
                     p.Annotation.LegendInformation.IconDisplayStyle = 'off';
                 end
            end
        end

        legend(axGates, 'show', 'Location', 'northeast');
        hold(axGates, 'off');
        title(axGates, 'Optimized Gates & Fluorescence Profile');
        
        % Plot Metric
        cla(axFisher);
        hold(axFisher, 'on');
        
        isFI = strcmp(swMetric.Value, 'Fisher Info');
        isLog = strcmp(swScale.Value, 'Log');
        
        if isFI
            y_opt = currentResults.opt.FI;
            y_base = currentResults.base.FI;
            y_lab = 'Fisher Information';
        else
            y_opt = currentResults.opt.F;
            y_base = currentResults.base.F;
            y_lab = 'F-value (Photon Efficiency)';
        end
        
        if isLog
            plot_fun = @loglog;
            axFisher.XScale = 'log';
            axFisher.YScale = 'log';
        else
            plot_fun = @plot;
            axFisher.XScale = 'linear';
            axFisher.YScale = 'linear';
        end
        
        plot_fun(axFisher, currentResults.tau_grid, y_opt, 'b-', 'LineWidth', 2, 'DisplayName', 'Optimized');
        plot_fun(axFisher, currentResults.tau_grid, y_base, 'r--', 'LineWidth', 2, 'DisplayName', 'Baseline (Equal)');
        
        ylabel(axFisher, y_lab);
        xlabel(axFisher, 'Lifetime \tau (ns)');
        legend(axFisher, 'show');
        grid(axFisher, 'on'); % Just use grid function, should work now as variable is renamed
        % Or use safe assignments if paranoid
        axFisher.XGrid = 'on';
        axFisher.YGrid = 'on';
        
        hold(axFisher, 'off');
    end

end
