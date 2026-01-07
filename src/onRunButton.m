

function onRunButton(TField, fwhmField, profileDropdown, toffField, tauMinField, tauMaxField, tauStpField, ...
    rField, NGateField, NPhotonsField, MField, dtField, ...
    tauEMinField, tauEMaxField, tauEStpField, ...
    sweepAlphaCheck, sweepNGateCheck, sweepRCheck, ...
    axF, axEff, axTau, elapsedLabel, remainingLabel, fig, soundCheck, riseField, fallField, sweepRiseCheck, ...
    PTCheck, PTSField, PTTField, gFields, gateDropdown)


% Extract excitation profile
profile = profileDropdown.Value;


% Determine active sweep
if sweepAlphaCheck.Value
    sweepParam = 'alpha';
    sweepValues = str2num(fwhmField.Value);
elseif sweepNGateCheck.Value
    sweepParam = 'N_gates';
    sweepValues = str2num(NGateField.Value);
elseif sweepRCheck.Value
    sweepParam = 'r';
    sweepValues = str2num(rField.Value);
elseif sweepRiseCheck.Value
    sweepParam = 'rise time';
    sweepValues = str2num(riseField.Value);
else
    sweepParam = 'none';
    sweepValues = 1;
end

% Validate sweep input
if isempty(sweepValues)
    uialert(fig, 'Sweep values must be numeric.', 'Input Error');
    return;
end

% Extract fixed parameters
T           = TField.Value;
toff        = toffField.Value;
tau_min     = tauMinField.Value;
tau_max     = tauMaxField.Value;
tau_stp     = tauStpField.Value;
N_photons   = NPhotonsField.Value;
M           = MField.Value;
dt          = dtField.Value;
tauE_min    = tauEMinField.Value;
tauE_max    = tauEMaxField.Value;
tauE_stp    = tauEStpField.Value;
fall_time   = fallField.Value;
bPulseTrain = PTCheck.Value;
PT_Trep     = PTTField.Value;
PT_sigma    = PTSField.Value;

% Init plots
cla(axF); cla(axEff); cla(axTau);
hold(axF, 'on'); hold(axEff, 'on'); hold(axTau, 'on');
legends = cell(numel(sweepValues), 1);
colors = lines(numel(sweepValues));
progressBar = uiprogressdlg(fig, 'Title', 'Running Simulation', 'Indeterminate', 'off');
totalSteps = numel(sweepValues) * tau_stp;
startTime = tic;


fig_pos = get(fig,'Position')
baseY       = 50;  % distance from top and bottom
max_height  = 300; % max height of pdf plots
space       = 20;  % spacing of the plots
height      = min([max_height (fig_pos(4)-2*baseY-numel(sweepValues)*space)/numel(sweepValues)])

axesHandles = findall(fig, 'Type', 'axes','Tag','itisme');
if ~isempty(axesHandles)
    delete(axesHandles)
end

pdfAxes = gobjects(1, numel(sweepValues)); % Preallocate for speed
for i = 1:numel(sweepValues)
    pdfAxes(i) = uiaxes(fig, ...
        'Position', [440, baseY + (i - 1) * (height + 30), 420, height], ...
        'Box', 'on','Tag','itisme');
    title(pdfAxes(i), sprintf('Gate + PDF (%s = %.3f)', sweepParam, sweepValues(i)));
    grid(pdfAxes(i), 'on');

    switch sweepParam
        case 'alpha'
            fwhm = sweepValues(i);
            N_gates = str2double(NGateField.Value);
            r = str2double(rField.Value);
            rise_time = str2double(riseField.Value);

        case 'N_gates'
            fwhm = str2double(fwhmField.Value);
            N_gates = sweepValues(i);
            r = str2double(rField.Value);
            rise_time = str2double(riseField.Value);

        case 'r'
            fwhm = str2double(fwhmField.Value);
            N_gates = str2double(NGateField.Value);
            r = sweepValues(i);
            rise_time = str2double(riseField.Value);

        case 'rise time'
            fwhm = str2double(fwhmField.Value);
            N_gates = str2double(NGateField.Value);
            r = str2double(rField.Value);
            rise_time = sweepValues(i);

        otherwise
            fwhm = str2double(fwhmField.Value);
            N_gates = str2double(NGateField.Value);
            r = str2double(rField.Value);
            rise_time = str2double(riseField.Value);
    end


    switch lower(gateDropdown.Value)
        case 'equal'
            gate_edges  = linspace(0, T - toff, N_gates + 1);
        otherwise
            gate_edges = zeros(1, N_gates + 1); % Preallocate for speed
            for gi = 1 : N_gates
                gate_edges(gi+1) = gate_edges(gi) + gFields(gi).Value;
            end
    end

    updateProgress = @(curr, total) set(progressBar, ...
        'Value', ((i - 1) + curr / total) / numel(sweepValues), ...
        'Message', sprintf('%s %.3f (%d/%d)', sweepParam, sweepValues(i), i, numel(sweepValues)));
    updateTime = @(curr, total, ~) setElapsedAndRemaining(elapsedLabel, remainingLabel, ...
        (i - 1) * tau_stp + curr, totalSteps, toc(startTime));

    % Call simulation
    [tau, F, pEff, tauEst, tauStd] = run_FLIM_DigitalTwin( ...
        T, fwhm, profile, toff, tau_min, tau_max, tau_stp, r, ...
        N_gates, N_photons, M, dt, tauE_min, tauE_max, tauE_stp, ...
        updateProgress, updateTime, pdfAxes(i), axF, axEff, axTau,...
        rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, gate_edges);

    plot(axF, tau, F, 'Color', colors(i,:), 'LineWidth', 1.5);
    plot(axEff, tau, pEff, 'Color', colors(i,:), 'LineWidth', 1.5);
    errorbar(axTau, tau, tauEst, tauStd, 'Color', colors(i,:), 'LineWidth', 1.5);
    legends{i} = sprintf('%s = %.3f', sweepParam, sweepValues(i));
end

xlabel(axF, 'τ (ns)'); ylabel(axF, 'F'); title(axF, 'F-value vs τ');
xlabel(axEff, 'τ (ns)'); ylabel(axEff, '1/F²'); title(axEff, 'Photon Efficiency');
xlabel(axTau, 'Simulated τ'); ylabel(axTau, 'Estimated τ'); title(axTau, 'τ ± Std');
legend(axF, legends); legend(axEff, legends); legend(axTau, legends);
close(progressBar);

if soundCheck.Value, beep; end
end
