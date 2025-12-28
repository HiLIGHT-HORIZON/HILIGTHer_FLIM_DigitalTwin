% DigitalTwin.m - Reconstructed GUI layout for parameter sweeping

function DigitalTwin()
% Add AppProperties to path to ensure shared utilities are available
addpath(fullfile(fileparts(mfilename('fullpath')), 'AppProperties'));


gui_line    = 30;
gui_header  = 30;
panel_width = 400;
fig_height  = 1120;
fig_width   = 1400;

fig = uifigure('Name', 'HILIGHT FLIM Digital Twin', 'Position', [100 100 fig_width fig_height]);

% === App Properties & Theme ===
setupAppProperties(fig);


% === Excitation Panel ===
panel_height    = 270;
panel_bottom    = 800;
excitationPanel = uipanel(fig, 'Title', 'Excitation', 'FontWeight', 'bold', 'Position', [20 panel_bottom panel_width panel_height]);

new_line = panel_height-gui_header-gui_line;
uilabel(excitationPanel, 'Text', 'Period (T)',                  'Position', [10  new_line 100 22]);
TField = uieditfield(excitationPanel, 'numeric', 'Value', 50,   'Position', [120 new_line 100 22], 'Tag', 'TField');
uilabel(excitationPanel, 'Text', 'ns',                          'Position', [230 new_line  30 22]);

new_line = new_line-gui_line;
uilabel(excitationPanel, 'Text', 'Excitation FWHM',             'Position', [ 10 new_line 100 22]);
fwhmField = uieditfield(excitationPanel, 'text', 'Value', '5',  'Position', [120 new_line 100 22], 'Tooltip', 'Full Width at Half Maximum', 'Tag', 'fwhmField');
sweepAlphaCheck = uicheckbox(excitationPanel, 'Text', 'Sweep α','Position', [250 new_line 100 22], 'Tag', 'sweepAlphaCheck');
uilabel(excitationPanel, 'Text', 'ns',                          'Position', [230 new_line  30 22]);

new_line = new_line-gui_line;
uilabel(excitationPanel, 'Text', 'Profile type',                'Position', [ 10 new_line 100 22]);
profileDropdown = uidropdown(excitationPanel, ...
    'Items', {'Rectangular','Gaussian'},'Value', 'Rectangular', 'Position', [120 new_line 140 22], 'Tag', 'profileDropdown');

new_line = new_line-gui_line;
uilabel(excitationPanel, 'Text', 'Last gate edge (toff)',           'Position', [ 10 new_line 120 22]);
toffField = uieditfield(excitationPanel, 'numeric', 'Value', 18,    'Position', [140 new_line  80 22], 'Tag', 'toffField');
uilabel(excitationPanel, 'Text', 'ns',                              'Position', [230 new_line  30 22]);

new_line = new_line-gui_line;
uilabel(excitationPanel, 'Text', 'Rise time',                       'Position', [ 10 new_line 100 22]);
riseField = uieditfield(excitationPanel, 'text', 'Value', '0',      'Position', [120 new_line  60 22], 'Tag', 'riseField');
uilabel(excitationPanel, 'Text', 'ns',                              'Position', [190 new_line  30 22]);
sweepRiseCheck = uicheckbox(excitationPanel, 'Text', 'Sweep rise',  'Position', [210 new_line 100 22], 'Tag', 'sweepRiseCheck');

new_line = new_line-gui_line;
uilabel(excitationPanel, 'Text', 'Fall time',                   'Position', [ 10 new_line 100 22]);
fallField = uieditfield(excitationPanel, 'numeric', 'Value', 0, 'Position', [120 new_line  60 22], 'Tag', 'fallField');
uilabel(excitationPanel, 'Text', 'ns',                          'Position', [190 new_line  30 22]);

% Enable/disable rise/fall fields based on profile
profileDropdown.ValueChangedFcn = @(dd, event) toggleRiseFall(dd, riseField, fallField);
toggleRiseFall(profileDropdown, riseField, fallField);  % set initial state

new_line = new_line-gui_line;
PTCheck = uicheckbox(excitationPanel, 'Text', 'Pulse Train',        'Position', [ 10 new_line 100 22], 'Tag', 'PTCheck');
uilabel(excitationPanel, 'Text', 'T',                               'Position', [110 new_line 100 22]);
PTTField = uieditfield(excitationPanel, 'numeric', 'Value', 0.1,    'Position', [120 new_line  60 22], 'Tag', 'PTTField');
uilabel(excitationPanel, 'Text', 'ns',                              'Position', [190 new_line  30 22]);
uilabel(excitationPanel, 'Text', '\sigma',                          'Position', [210 new_line 100 22]);
PTSField = uieditfield(excitationPanel, 'numeric', 'Value', 0.05,   'Position', [220 new_line  60 22], 'Tag', 'PTSField');
uilabel(excitationPanel, 'Text', 'ns',                              'Position', [290 new_line  30 22]);

% Enable/disable rise/fall fields based on profile
PTCheck.ValueChangedFcn = @(dd, event) togglePT(dd, PTTField, PTSField);
togglePT(PTCheck, PTTField, PTSField);  % set initial state


% === Gate Settings Panel ===

panel_height    = 230;
panel_bottom    = panel_bottom - panel_height - gui_line/2;
gatePanel = uipanel(fig, 'Title', 'Gate Settings', 'FontWeight', 'bold', 'Position', [20 panel_bottom panel_width panel_height]);

new_line = panel_height-gui_header-gui_line;
uilabel(gatePanel, 'Text', 'Gating type',                 'Position', [ 10 new_line 100 22]);
gateDropdown = uidropdown(gatePanel, ...
    'Items', {'Equal','Custom (max 8)'}, ...
    'Value',  'Equal',               'Position', [120 new_line 140 22], 'Tag', 'gateDropdown');

new_line = new_line-gui_line;
uilabel(gatePanel, 'Text', 'Number of gates',                       'Position', [ 10 new_line 120 22]);
NGateField = uieditfield(gatePanel, 'text', 'Value', '4',           'Position', [140 new_line 100 22], 'Tooltip', 'Can be scalar or vector', 'Tag', 'NGateField');
sweepNGateCheck = uicheckbox(gatePanel, 'Text', 'Sweep #gates',     'Position', [280 new_line 120 22], 'Tag', 'sweepNGateCheck');

new_line = new_line-gui_line;
uilabel(gatePanel, 'Text', 'Rise/decay time (r)',           'Position', [ 10 new_line 120 22]);
rField = uieditfield(gatePanel, 'text', 'Value', '0.001',   'Position', [140 new_line 100 22], 'Tooltip', 'Can be scalar or vector', 'Tag', 'rField');
sweepRCheck = uicheckbox(gatePanel, 'Text', 'Sweep r',      'Position', [280 new_line 100 22], 'Tag', 'sweepRCheck');
uilabel(gatePanel, 'Text', 'ns',                            'Position', [250 new_line  30 22]);

% custom gates
new_line = new_line-gui_line;
gFields = gobjects(1, 8); % Preallocate for speed
for i=1:8
    uilabel(gatePanel, 'Text', ['Width' num2str(i)],            'Position', [ 10+(i-1)*panel_width/9 new_line    40 22]);
    gFields(i) = uieditfield(gatePanel, 'numeric', 'Value', 2,  'Position', [ 10+(i-1)*panel_width/9 new_line-20 40 22], 'Tooltip', 'Gate width in nanoseconds', 'Tag', sprintf('gField%d', i));
end
uilabel(gatePanel, 'Text', 'ns',                                'Position', [ 10+8*panel_width/9 new_line-20 40 22]);

% Enable/disable gate inputs based on drop down selection
gateDropdown.ValueChangedFcn = @(dd, event) toggleGate(dd, gFields,NGateField);
toggleGate(gateDropdown, gFields,NGateField);  % set initial state


% Make sweep checkboxes mutually exclusive
sweepAlphaCheck.ValueChangedFcn = @(src, event) set([sweepNGateCheck, sweepRCheck, sweepRiseCheck], 'Value', false);
sweepNGateCheck.ValueChangedFcn = @(src, event) set([sweepAlphaCheck, sweepRCheck, sweepRiseCheck], 'Value', false);
sweepRCheck.ValueChangedFcn = @(src, event) set([sweepAlphaCheck, sweepNGateCheck, sweepRiseCheck], 'Value', false);
sweepRiseCheck.ValueChangedFcn = @(src, event) set([sweepAlphaCheck, sweepNGateCheck, sweepRCheck], 'Value', false);



% === Lifetime Panel ===
panel_height    = 90;
panel_bottom    = panel_bottom - panel_height - gui_line/2;
lifetimePanel = uipanel(fig, 'Title', 'Lifetime (τ) sweep', 'FontWeight', 'bold', 'Position', [20 panel_bottom panel_width panel_height]);

new_line = panel_height-gui_header-gui_line;
uilabel(lifetimePanel, 'Text', 'Min',                               'Position', [  10 new_line 30 22]);
tauMinField = uieditfield(lifetimePanel, 'numeric', 'Value', 0.5,   'Position', [  40 new_line 60 22]);
uilabel(lifetimePanel, 'Text', 'ns',                                'Position', [ 105 new_line 20 22]);

uilabel(lifetimePanel, 'Text', 'Max',                               'Position', [ 130 new_line 30 22]);
tauMaxField = uieditfield(lifetimePanel, 'numeric', 'Value', 10,    'Position', [ 160 new_line 60 22]);
uilabel(lifetimePanel, 'Text', 'ns',                                'Position', [ 225 new_line 20 22]);

uilabel(lifetimePanel, 'Text', '#steps',                            'Position', [255 new_line 50 22]);
tauStpField = uieditfield(lifetimePanel, 'numeric', 'Value', 20,    'Position', [300 new_line 60 22]);

% === Monte Carlo Panel ===
panel_height    = 130;
panel_bottom    = panel_bottom - panel_height - gui_line/2;
montePanel = uipanel(fig, 'Title', 'Monte Carlo', 'FontWeight', 'bold', 'Position', [20 panel_bottom panel_width panel_height]);

new_line = panel_height-gui_header-gui_line;
uilabel(montePanel, 'Text', 'Photons/run',                          'Position', [ 10 new_line 100 22]);
NPhotonsField = uieditfield(montePanel, 'numeric', 'Value', 1e4,    'Position', [120 new_line 100 22]);

new_line = new_line-gui_line;
uilabel(montePanel, 'Text', 'MC samples (M)',                       'Position', [ 10 new_line 100 22]);
MField = uieditfield(montePanel, 'numeric', 'Value', 400,           'Position', [120 new_line 100 22]);

new_line = new_line-gui_line;
uilabel(montePanel, 'Text', 'dt (time step)',                       'Position', [ 10 new_line 100 22]);
dtField = uieditfield(montePanel, 'numeric', 'Value', 0.01,         'Position', [120 new_line 100 22]);
uilabel(montePanel, 'Text', 'ns',                                   'Position', [225 new_line 20 22]);

% === Estimation Grid Panel ===
panel_height    = 90;
panel_bottom    = panel_bottom - panel_height - gui_line/2;
gridPanel = uipanel(fig, 'Title', 'Estimation Grid (τ)', 'FontWeight', 'bold', 'Position', [20 panel_bottom panel_width panel_height]);

new_line = panel_height-gui_header-gui_line;
uilabel(gridPanel, 'Text', 'Min',                                   'Position', [ 10 new_line 30 22]);
tauEMinField = uieditfield(gridPanel, 'numeric', 'Value', 0.03,     'Position', [ 40 new_line 60 22]);
uilabel(lifetimePanel, 'Text', 'ns',                                'Position', [105 new_line 20 22]);

uilabel(gridPanel, 'Text', 'Max',                                   'Position', [130 new_line 30 22]);
tauEMaxField = uieditfield(gridPanel, 'numeric', 'Value', 30,       'Position', [160 new_line 60 22]);
uilabel(lifetimePanel, 'Text', 'ns',                                'Position', [225 new_line 20 22]);

uilabel(gridPanel, 'Text', '#steps',                                'Position', [255 new_line 50 22]);
tauEStpField = uieditfield(gridPanel, 'numeric', 'Value', 2000,     'Position', [300 new_line 60 22]);

% === Flow Control Panel ===
panel_height    = 160;
panel_bottom    = panel_bottom - panel_height - gui_line/2;
controlPanel    = uipanel(fig, 'Title', 'Control', 'FontWeight', 'bold', 'Position', [20 panel_bottom panel_width panel_height]);

new_line        = panel_height-gui_header-gui_line;
elapsedLabel    = uilabel(controlPanel, 'Text', 'Elapsed time: 0.0 s', 'Position', [ 30 new_line 150 22]);
remainingLabel  = uilabel(controlPanel, 'Text', 'Remaining time: N/A', 'Position', [200 new_line 150 22]);

new_line    = new_line-gui_line;
soundCheck  = uicheckbox(controlPanel, 'Text', 'Play sound when done', 'Position', [30 new_line 200 22], 'Value', true);

% === Shared axes for results ===
axF   = uiaxes(fig, 'Position', [880 750 480 250]);
title(axF, 'F-value vs τ'); xlabel(axF, 'τ (ns)'); ylabel(axF, 'F'); grid(axF, 'on'); box(axF, 'on')

axEff = uiaxes(fig, 'Position', [880 500 480 250]);
title(axEff, 'Photon Efficiency'); xlabel(axEff, 'τ (ns)'); ylabel(axEff, '1/F²'); grid(axEff, 'on'); box(axEff, 'on')

axTau = uiaxes(fig, 'Position', [880 200 480 250]);
title(axTau, 'Estimated τ ± std'); xlabel(axTau, 'Simulated τ'); ylabel(axTau, 'Estimated τ'); grid(axTau, 'on'); box(axTau, 'on')
% ===


% === Run button ===
new_line    = new_line-1.2*gui_line;
uibutton(controlPanel, 'Text', 'Run Simulation', 'Position', [30 new_line panel_width-60 20], 'ButtonPushedFcn', ...
    @(btn,event) onRunButton(TField, fwhmField, profileDropdown, toffField, ...
    tauMinField, tauMaxField, tauStpField, rField, NGateField, NPhotonsField, MField, dtField, ...
    tauEMinField, tauEMaxField, tauEStpField, sweepAlphaCheck, sweepNGateCheck, sweepRCheck, ...
    axF, axEff, axTau, elapsedLabel, remainingLabel, fig, soundCheck, riseField, fallField, ...
    sweepRiseCheck, PTCheck, PTSField, PTTField, gFields, gateDropdown));

% === HILIGHTer Button ===
new_line = new_line - 30;
uibutton(controlPanel, 'Text', 'HILIGHTer', 'Position', [30 new_line panel_width-60 20], ...
    'ButtonPushedFcn', @(btn, event) launchHILIGHTer(TField, fwhmField, profileDropdown, toffField, rField, NGateField, ...
    NPhotonsField, MField, dtField, riseField, fallField, ...
    PTCheck, PTSField, PTTField, gFields, gateDropdown));

% === Optimize Gates Button (Create late to ensure all fields exist) ===
% Position manually relative to Gate Panel
% We need to find the gate panel or just hardcode if we know the layout.
% The gate Panel creation code was around lines 70-110.
% To place it cleanly, we can find the Gate Settings panel object or just assume it exists.
% However, 'gatePanel' variable is still in scope since this is a nested function or same scope.
% Yes, it is same scope.

% Find position: earlier we used 'new_line' inside gate panel logic.
% Gate Panel height is 230.
% Let's place it at bottom: 10px from bottom.

uibutton(gatePanel, 'Text', 'Optimize Gates...', 'Position', [10 10 140 20], ...
    'FontSize', 10, 'BackgroundColor', [0.9 0.9 1.0], ...
    'ButtonPushedFcn', @(btn, event) launchOptimizer(TField, fwhmField, profileDropdown, riseField, fallField, PTCheck, PTTField, PTSField, gFields, NGateField, gateDropdown, tauMinField, tauMaxField, tauStpField, rField));

end

function toggleRiseFall(profileDropdown, riseField, fallField)
if strcmp(profileDropdown.Value, 'Rectangular')
    riseField.Enable = 'on';
    fallField.Enable = 'on';
else
    riseField.Enable = 'off';
    fallField.Enable = 'off';
end
end

function togglePT(checkbox, field_id1,field_id2)
if checkbox.Value
    field_id1.Enable = 'on';
    field_id2.Enable = 'on';
else
    field_id1.Enable = 'off';
    field_id2.Enable = 'off';

end
end

function toggleGate(gateDropdown,field_ids, NGateField)
if strcmp(gateDropdown.Value, 'Equal')
    set(field_ids,'Enable','off');
else
    set(field_ids(1:str2double(NGateField.Value)),'Enable','on');
end
end

function launchOptimizer(TField, fwhmField, profileDropdown, riseField, fallField, PTCheck, PTTField, PTSField, gFields, NGateField, gateDropdown, tauMinField, tauMaxField, tauStpField, rField)
% Extract current IRF parameters to pass to optimizer
irf.fwhm = str2double(fwhmField.Value);
irf.profile = profileDropdown.Value;
irf.rise_time = str2double(riseField.Value);
irf.fall_time = fallField.Value;
irf.bPulseTrain = PTCheck.Value;
irf.PT_Trep = PTTField.Value;
irf.PT_sigma = PTSField.Value;

T_max = TField.Value;

tau_params.min = tauMinField.Value;
tau_params.max = tauMaxField.Value;
tau_params.steps = tauStpField.Value;

gate_params.rise_time = str2double(rField.Value);

% Launch the optimizer GUI with callback
updateGatesCallback = @(edges) updateMainGuiGates(edges, gFields, NGateField, gateDropdown);
GateOptimizer_GUI(irf, T_max, tau_params, updateGatesCallback, gate_params);
end



function updateMainGuiGates(edges, gFields, NGateField, gateDropdown)
% Update the main GUI fields with the optimized edges
widths = diff(edges);
N = length(widths);

% Update N Gates if changed (though optimizer uses fixed N)
NGateField.Value = num2str(N);

% Set Dropdown to Custom
gateDropdown.Value = 'Custom (max 8)';
% Enable fields
toggleGate(gateDropdown, gFields, NGateField);

% Update width fields
for i = 1:min(N, 8)
    gFields(i).Value = widths(i);
end

% If there are more gates than fields, we can't show them all,
% but the text output in optimizer preserves them.
fprintf('Updated Main GUI with optimized gate widths.\n');
end

function toggleModality(dropdown, lifetimePanel, fretPanel)
if strcmp(dropdown.Value, 'Lifetime Sweep')
    lifetimePanel.Visible = 'on';
    fretPanel.Visible = 'off';
else
    lifetimePanel.Visible = 'off';
    fretPanel.Visible = 'on';
end
end
