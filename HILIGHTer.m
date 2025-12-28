function HILIGHTer(configStruct)
% Add AppProperties to path to ensure shared utilities are available
addpath(fullfile(fileparts(mfilename('fullpath')), 'AppProperties'));

% MOCKDATA_GUI - renamed to HILIGHTer
% ConfigStruct contains settings imported from the main FLIM_GUI

% Handle empty input for direct calls
if nargin < 1 || isempty(configStruct)
    % Provide defaults for direct calls
    configStruct.T = 12.5;
    configStruct.fwhm = 0.2;
    configStruct.profile = 'Gaussian';
    configStruct.toff = 12.5;
    configStruct.r = 0.5;
    configStruct.N_gates = 32;
    configStruct.N_photons = 1000;
    configStruct.M = 1;
    configStruct.dt = 0.05;
    configStruct.rise_time = 0.1;
    configStruct.fall_time = 0.1;
    configStruct.bPulseTrain = false;
    configStruct.PT_sigma = 0.2;
    configStruct.PT_Trep = 12.5;
    configStruct.gate_type = 'Equal';
    configStruct.gate_edges = linspace(0, 12.5, 33);
    initialMode = 'Analyser';
else
    initialMode = 'Simulator';
end

% === Main Figure ===
figWidth = 1800;
figHeight = 1050;
fig = uifigure('Name', 'HILIGHTer', 'Position', [50 50 figWidth figHeight]);

% === App Properties & Theme ===
setupAppProperties(fig);


% Store config and data in a struct
dataStruct.config = configStruct;
dataStruct.RawData = [];
dataStruct.TauMap = [];
dataStruct.projXY = [];  % Store for ROI colorization
dataStruct.G_vals = [];  % Store phasor coordinates
dataStruct.S_vals = [];
dataStruct.vizMode = 'Default'; % 'Default' or 'ROI Overlay'
dataStruct.runCount = 0;
fig.UserData = dataStruct;

% === Layout Constants ===
margin = 15;

% --- Column 1: Controls ---
col1W = 280;
col1X = margin;

% Remaining width for cols 2 and 3
col2X = col1X + col1W + margin;

% === Top Switches (Top Left) ===
% We position these on two different lines as requested
toggleY = figHeight - 45;
labelW = 85;

% First Line: App Mode
uilabel(fig, 'Text', 'App Mode', 'Position', [col1X, toggleY, labelW, 25], 'FontWeight', 'bold');
swMode = uiswitch(fig, 'slider', 'Items', {'', ''}, 'ItemsData', {'Simulator', 'Analyser'}, ...
    'Position', [col1X + labelW, toggleY, 45, 20], ...
    'Tag', 'swMode', ...
    'ValueChangedFcn', @(src, ev) toggleAppMode(fig, src.Value));
swMode.Value = initialMode;
uilabel(fig, 'Text', swMode.Value, 'Position', [col1X + labelW + 60, toggleY, 100, 25], ...
    'Tag', 'lblAppStatus', 'FontWeight', 'bold', 'FontColor', [0 0.45 0.74]);

% Second Line: Expert Mode
toggleY2 = toggleY - 35;
uilabel(fig, 'Text', 'Expert Mode', 'Position', [col1X, toggleY2, labelW, 25], 'FontWeight', 'bold');
swExpert = uiswitch(fig, 'slider', 'Items', {'', ''}, 'ItemsData', {'Basic', 'Expert'}, ...
    'Position', [col1X + labelW, toggleY2, 45, 20], ...
    'Tag', 'swExpert', ...
    'ValueChangedFcn', @(src, ev) toggleExpertMode(fig, src.Value));
swExpert.Value = 'Basic';
uilabel(fig, 'Text', swExpert.Value, 'Position', [col1X + labelW + 60, toggleY2, 100, 25], ...
    'Tag', 'lblExpertStatus', 'FontWeight', 'bold', 'FontColor', [0.5 0.5 0.5]);

% === Configuration Panel (Top Left) ===
% === Configuration Panel (Top Left) ===
configPanelH = 450;
configPanel = uipanel(fig, 'Title', 'Simulation Configuration', 'Tag', 'pnlConfig', ...
    'Position', [col1X, figHeight - configPanelH - margin - 90, col1W, configPanelH]);

% === Analyzer Panel (Alternative to Config) ===
analyzerPanel = uipanel(fig, 'Title', 'Analysis Controls', 'Tag', 'pnlAnalyzer', ...
    'Position', configPanel.Position, 'Visible', 'off');

% -- Analyzer Panel Contents --
currYa = configPanelH - 50;
uilabel(analyzerPanel, 'Text', 'Modality:', 'Position', [10 currYa 70 22]);
uidropdown(analyzerPanel, 'Items', {'Import Single File'}, ...
    'Position', [80 currYa 180 22], 'Tag', 'ddModality');

currYa = currYa - 45;
uibutton(analyzerPanel, 'Text', 'LOAD FILE', 'FontWeight', 'bold', ...
    'Position', [20 currYa 120 20], 'Tag', 'btnLoadFile', ...
    'BackgroundColor', [0 0.4470 0.7410], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(btn, event) onLoadFile(fig));

% -- Enhanced Drag and Drop Area --
dropZone = uipanel(analyzerPanel, 'Title', '', ...
    'Position', [20, 30, 240, 110], ...
    'BackgroundColor', [0.94 0.96 1.0], ... % Very light blue
    'BorderType', 'line', ...
    'HighlightColor', [0 0.45 0.74]); % MATLAB Blue border

uilabel(dropZone, 'Text', '[ + ]', 'FontSize', 24, ...
    'FontWeight', 'bold', 'FontColor', [0 0.45 0.74], ...
    'HorizontalAlignment', 'center', 'Position', [0 60 240 40]);

% --- Sidebar (Left) ---

uilabel(dropZone, 'Text', 'DRAG & DROP FILE', 'FontSize', 10, ...
    'FontWeight', 'bold', 'FontColor', [0.2 0.4 0.6], ...
    'HorizontalAlignment', 'center', 'Position', [0 35 240 20]);

uilabel(dropZone, 'Text', '(or click LOAD above)', 'FontSize', 8, ...
    'FontColor', [0.5 0.5 0.5], ...
    'HorizontalAlignment', 'center', 'Position', [0 15 240 20]);

% Enable figure-wide drag and drop logic
if isprop(fig, 'WindowFileDroppedFcn')
    fig.WindowFileDroppedFcn = @(src, event) onFileDropped(fig, event);
else
    % If version is < R2020b, keep visible but update text to reflect status
    dropZone.BackgroundColor = [0.9 0.9 0.9]; % Grayed out
    lbl1 = findobj(dropZone, 'Text', 'DRAG & DROP FILE');
    if ~isempty(lbl1), lbl1.Text = 'DRAG & DROP (Not active)'; end
    lbl2 = findobj(dropZone, 'Text', '(or click LOAD above)');
    if ~isempty(lbl2), lbl2.Text = 'Upgrade to R2020b+ for this feature'; end
end

% Apply initial mode visibility
if strcmp(initialMode, 'Analyser')
    configPanel.Visible = 'off';
    analyzerPanel.Visible = 'on';
end

inputH = 22;

% === Configuration Panel (Top Left) ===
% Config Panel already created above
% configPanelH = 450;
% configPanel construction removed to avoid duplicate

% ... (Analyzer Panel skipped, unrelated) ...

% Apply initial mode visibility: Handled later or above?
% The replace block skips 105-159. Adjust StartLine to be specific to the block.

% -- Mode Selection --
currY = configPanelH - 50;
lblMode = uilabel(configPanel, 'Text', 'Mode:', 'Position', [10 currY 50 inputH]);
modeDropdown = uidropdown(configPanel, ...
    'Items', {'Lifetime Gradient', 'Lifetime Mix', 'FRET'}, ...
    'Value', 'Lifetime Gradient', ...
    'Tooltip', 'Select simulation scenario', ...
    'Position', [70 currY 200 inputH]); % Use full width

currY = currY - 35;
% -- Image Dimensions (Line 1) --
uilabel(configPanel, 'Text', 'Size:', 'Position', [10 currY 40 inputH]);
dimXField = uieditfield(configPanel, 'numeric', 'Value', 64, 'Position', [50 currY 40 inputH], 'Tooltip', 'Width');
uilabel(configPanel, 'Text', 'x', 'Position', [92 currY 10 inputH]);
dimYField = uieditfield(configPanel, 'numeric', 'Value', 64, 'Position', [105 currY 40 inputH], 'Tooltip', 'Height');

uibutton(configPanel, 'Text', 'x2', 'Position', [160 currY 30 inputH], 'Tooltip', 'Double size', ...
    'ButtonPushedFcn', @(btn, event) adjustSize(dimXField, dimYField, 2));
uibutton(configPanel, 'Text', '/2', 'Position', [195 currY 30 inputH], 'Tooltip', 'Halve size', ...
    'ButtonPushedFcn', @(btn, event) adjustSize(dimXField, dimYField, 0.5));

currY = currY - 35;
% -- Photons & Background (Line 2) --
uilabel(configPanel, 'Text', 'Photons:', 'Position', [10 currY 55 inputH]);
photonsField = uieditfield(configPanel, 'numeric', 'Value', dataStruct.config.N_photons, 'Position', [70 currY 60 inputH], 'Tooltip', 'Photons/pixel');
uilabel(configPanel, 'Text', 'Bkg:', 'Position', [140 currY 30 inputH]);
darkCountsField = uieditfield(configPanel, 'numeric', 'Value', 0, 'Position', [175 currY 50 inputH], 'Tooltip', 'Background counts');

currY = currY - 45;
% -- Generate Button Placeholder --
btnY = currY;

% -- Mode Specific Inputs (Below Generate) --
currY = currY - 20; % Reduced spacing
paramStartY = currY;

% 1. FRET Fields
fretY = paramStartY;
lblFretTau = uilabel(configPanel, 'Text', 'Tau (ps):', 'Position', [10 fretY 60 inputH], 'Visible', 'off');
fretTauField = uieditfield(configPanel, 'numeric', 'Value', 3000, 'Position', [70 fretY 60 inputH], ...
    'Tag', 'fretTauField', 'Visible', 'off');

fretY = fretY - 35;
lblMinFRET = uilabel(configPanel, 'Text', 'Min FRET%:', 'Position', [10 fretY 70 inputH], 'Visible', 'off');
minFRETField = uieditfield(configPanel, 'numeric', 'Value', 0, 'Position', [80 fretY 40 inputH], ...
    'Tag', 'minFRETField', 'Visible', 'off');
lblMaxFRET = uilabel(configPanel, 'Text', 'Max:', 'Position', [130 fretY 40 inputH], 'Visible', 'off');
maxFRETField = uieditfield(configPanel, 'numeric', 'Value', 100, 'Position', [170 fretY 40 inputH], ...
    'Tag', 'maxFRETField', 'Visible', 'off');

fretY = fretY - 35;
lblMinFrac = uilabel(configPanel, 'Text', 'Min Frac%:', 'Position', [10 fretY 70 inputH], 'Visible', 'off');
minFracField = uieditfield(configPanel, 'numeric', 'Value', 0, 'Position', [80 fretY 40 inputH], ...
    'Tag', 'minFracField', 'Visible', 'off');
lblMaxFrac = uilabel(configPanel, 'Text', 'Max:', 'Position', [130 fretY 40 inputH], 'Visible', 'off');
maxFracField = uieditfield(configPanel, 'numeric', 'Value', 100, 'Position', [170 fretY 40 inputH], ...
    'Tag', 'maxFracField', 'Visible', 'off');

% 2. Lifetime Fields
lifeY = paramStartY;
lblTau1 = uilabel(configPanel, 'Text', 'Lifetime 1 (ps):', 'Position', [10 lifeY 90 inputH]);
tau1Field = uieditfield(configPanel, 'numeric', 'Value', 1000, 'Position', [100 lifeY 80 inputH], ...
    'Tooltip', 'Base lifetime 1', 'Tag', 'tau1Field');

lifeY = lifeY - 35;
lblTau2 = uilabel(configPanel, 'Text', 'Lifetime 2 (ps):', 'Position', [10 lifeY 90 inputH]);
tau2Field = uieditfield(configPanel, 'numeric', 'Value', 2000, 'Position', [100 lifeY 80 inputH], ...
    'Tooltip', 'Base lifetime 2', 'Tag', 'tau2Field');

% Callbacks for instant updating of Instrument Plot
tau1Field.ValueChangedFcn = @(src, event) updateInstrumentPlot(fig, tau1Field, tau2Field);
tau2Field.ValueChangedFcn = @(src, event) updateInstrumentPlot(fig, tau1Field, tau2Field);

% -- Generate Button (Created Last) --
uibutton(configPanel, 'Text', 'GENERATE', 'FontWeight','bold', 'Tooltip', 'Create mock data', ...
    'Position', [20 btnY 240 18], ... % Narrower vertically
    'ButtonPushedFcn', @(btn, event) onGenerate(fig, modeDropdown, dimXField, dimYField, tau1Field, tau2Field, photonsField, darkCountsField, ...
    fretTauField, minFRETField, maxFRETField, minFracField, maxFracField));


% Callbacks for Modality Toggle
% Group Lifetime (Only Lifetime Params)
lifetimeGroup = [lblTau1, tau1Field, lblTau2, tau2Field];
% Group FRET
fretGroup = [lblFretTau, fretTauField, lblMinFRET, minFRETField, lblMaxFRET, maxFRETField, ...
    lblMinFrac, minFracField, lblMaxFrac, maxFracField];

modeDropdown.ValueChangedFcn = @(dd, ~) toggleHILIGHTerModality(dd, lifetimeGroup, fretGroup);
toggleHILIGHTerModality(modeDropdown, lifetimeGroup, fretGroup); % Initial


% === Instrument Parameters Panel (Below Config) ===
% Fill the remaining vertical space in Column 1
instPanelH = configPanel.Position(2) - 2*margin;
instPanel = uipanel(fig, 'Title', 'Instrument Parameters', ...
    'Position', [col1X, margin, col1W, instPanelH]);

% Initialization of vizMode
% (vizSwitch removed from sidebar, will be in tabs)

% Plot Ax
% Move slightly down and right to avoid clipping titles/labels
axInst = uiaxes(instPanel, 'Position', [45 45 col1W-65 instPanelH-90]);
axInst.Tag = 'axInst';
title(axInst, 'IRF & Gates', 'FontSize', 11, 'FontWeight', 'bold');
xlabel(axInst, 'Time (ns)'); ylabel(axInst, 'Counts (norm)');
grid(axInst, 'on'); axInst.GridAlpha = 0.3;


% === Column 2: Data Projections (Center) ===
% We now use a Tabbed interface to support multiple channels
% === Column 2: Data Projections (Center) ===
% We now use a Tabbed interface to support multiple channels
plotH = 375;
xyY = figHeight - margin - plotH;
xtH = 100; % Fixed height for XT
xtY = xyY - margin - xtH;
% Adjusted layout for 50% larger histogram
histH = 120; % Increased from 80
histY = xtY - margin - histH;
ctrlH = 35;
ctrlY = histY - margin - ctrlH;
threshY = ctrlY - margin - ctrlH; % New row for threshold controls
ytW = plotH * 0.3;
ytX = col2X + plotH + margin;
tabDataWidth = col2X + plotH + margin + ytW - col2X + 50;

dataTabGroup = uitabgroup(fig, 'Position', [col2X, margin, tabDataWidth, figHeight - 2*margin], 'Tag', 'dataTabGroup');
dataTabGroup.SelectionChangedFcn = @(~,~) refreshXYProjection(fig);

% Store layout constants for tab creation
dataStruct.plotH = plotH;
dataStruct.xtH = xtH;
dataStruct.ytW = ytW;
dataStruct.col2X = col2X;
dataStruct.xyY = xyY;
dataStruct.xtY = xtY;
dataStruct.histY = histY;
dataStruct.threshY = ctrlY - 30; % Explicit position for threshold row
dataStruct.ctrlY = ctrlY;
dataStruct.histH = histH;
dataStruct.ctrlH = ctrlH;
dataStruct.ytX = ytX;
fig.UserData = dataStruct;

% Create initial Channel 1 tab
createDataTab(dataTabGroup, 1, dataStruct);

% === Column 3: Analysis Results Tabs ===
col3X = col2X + tabDataWidth + margin;
tabGroup = uitabgroup(fig, 'Position', [col3X, margin, figWidth - col3X - margin, figHeight - 2*margin]);
tabGroup.Tag = 'analysisTabs';
tabGroup.SelectionChangedFcn = @(src, event) refreshXYProjection(fig);

% Initial Analysis tabs (now permanent)
tabMLE = uitab(tabGroup, 'Title', 'Grid MLE');
uibutton(tabMLE, 'Text', 'ANALYSE using Grid MLE', 'Position', [10, 960, 180, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'Grid MLE'));
uibutton(tabMLE, 'Text', 'Clear', 'Position', [200, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

tabIter = uitab(tabGroup, 'Title', 'Iterative Reconvolution');
uibutton(tabIter, 'Text', 'ANALYSE using Iterative Reconv.', 'Position', [10, 960, 180, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'Iterative Reconvolution'));
uibutton(tabIter, 'Text', 'Clear', 'Position', [200, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

tabTail = uitab(tabGroup, 'Title', 'Tail Fitting');
uibutton(tabTail, 'Text', 'ANALYSE using Tail Fitting', 'Position', [10, 960, 180, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'Tail Fitting'));
uibutton(tabTail, 'Text', 'Clear', 'Position', [200, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

tabPhasor = uitab(tabGroup, 'Title', 'Phasor Analysis');
uibutton(tabPhasor, 'Text', 'ANALYSE using Phasor Plot', 'Position', [10, 960, 180, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'Phasor Analysis'));
uibutton(tabPhasor, 'Text', 'Clear', 'Position', [200, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

tabPM = uitab(tabGroup, 'Title', 'Pattern Matching');
uibutton(tabPM, 'Text', 'ANALYSE using Pattern Matching', 'Position', [10, 960, 180, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'Pattern Matching'));
uibutton(tabPM, 'Text', 'Clear', 'Position', [200, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

tabLima = uitab(tabGroup, 'Title', 'LiMA');
uibutton(tabLima, 'Text', 'ANALYSE using LiMA', 'Position', [10, 960, 180, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'LiMA'));
uibutton(tabLima, 'Text', 'Clear', 'Position', [200, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

tabFisher = uitab(tabGroup, 'Title', 'Fisher Analysis');
uibutton(tabFisher, 'Text', 'ANALYSE using Fisher Analysis', 'Position', [10, 960, 220, 20], ...
    'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [1 0 0], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(~,~) onAnalyze(fig, 'Fisher Analysis'));
uibutton(tabFisher, 'Text', 'Clear', 'Position', [240, 960, 60, 20], ...
    'ButtonPushedFcn', @(~,~) onClearTab(fig));

% Relative alignment constants for use inside tabs
dataStruct.axL = 70;
dataStruct.axW = 400;
dataStruct.metX = 650;
dataStruct.xyY_top = 530; % Slightly lowered to make room for button
dataStruct.xtH = xtH;
fig.UserData = dataStruct;

% Initial Instrument Update
% Initial Instrument Update
updateInstrumentPlot(fig, tau1Field, tau2Field);

% Theme is now handled by setupAppProperties(fig)


end


function onGenerate(fig, modeDropdown, dimXField, dimYField, tau1Field, tau2Field, photonsField, darkCountsField, ...
    fretTauField, minFRETField, maxFRETField, minFracField, maxFracField)
try
    fprintf('Starting Generate Data...\n');
    % Retrieve config and params
    data = fig.UserData;
    config = data.config;

    Mode = modeDropdown.Value;
    isFRET = strcmp(Mode, 'FRET');

    nX = dimXField.Value;
    nY = dimYField.Value;
    tau1_ns = tau1Field.Value / 1000; % convert ps to ns
    tau2_ns = tau2Field.Value / 1000;
    N_generated = photonsField.Value;
    N_dark = darkCountsField.Value;

    % Setup Time and Gates (Reuse logic)
    dt = config.dt;
    T = config.T;
    t = 0:dt:T;

    % Reconstruct Gate Interp Functions
    actual_gate_edges = config.gate_edges;
    gate_profiles = DTgates(t, config.r, actual_gate_edges);
    gate_interp_fns = cell(config.N_gates, 1);
    for i = 1:config.N_gates
        gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
    end

    % === 1. Create Model Probabilities ===
    if isFRET
        % --- FRET Modality ---
        tau_D_ps = fretTauField.Value;
        tau_D_ns = tau_D_ps / 1000;

        E_min = minFRETField.Value / 100;
        E_max = maxFRETField.Value / 100;

        Frac_min = minFracField.Value / 100;
        Frac_max = maxFracField.Value / 100;

        % FRET Gradient (X-axis)
        grad_E = linspace(E_min, E_max, nX);
        % Fraction Gradient (Y-axis)
        grad_f = linspace(Frac_min, Frac_max, nY)';

        % Map for Ground Truth
        [Map_E, Map_f] = meshgrid(grad_E, grad_f); % YxX

        % Calculate Decays Efficiently
        % Component 1: Donor Only (Lifetime = tau_D)
        % P_tau1 is constant for all pixels.
        P_tau1_basis = DTpmod(config.N_gates, tau_D_ns, t, gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma); % [Gate x 1]

        % Component 2: FRET species (Lifetime = tau_D * (1-E))
        % Lifetime varies only with X (E varies with X).
        unique_tau2 = tau_D_ns * (1 - grad_E); % 1xX vector

        P_tau2_basis_set = DTpmod(config.N_gates, unique_tau2, t, gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma); % [Gates x X]

        % Reconstruct Full Probability Image P_model(y,x,g)
        % Pixel(y,x) = (1-f(y))*P1 + f(y)*P2(x)

        % Reshape for Compatibility
        % P1: [1, 1, G]
        P1_shape = reshape(P_tau1_basis, 1, 1, config.N_gates);

        % P2: [1, X, G]
        % P_tau2_basis_set is [G x X]. Reshape to [1, X, G] requires permute?
        % reshape(P_tau2_basis_set, G, X) -> permute to (3, 2, 1) -> (1, X, G)
        P2_shape = permute(reshape(P_tau2_basis_set, config.N_gates, nX), [3 2 1]);

        % f: [Y, 1, 1]
        f_vec = grad_f; % [Y x 1]

        % Calculate Terms (using implicit expansion)
        % Term1: (1-f) * P1
        Term1 = (1 - f_vec) .* P1_shape; % [Y, 1, G]

        % Term2: f * P2
        Term2 = f_vec .* P2_shape;       % [Y, X, G]

        % Combine
        P_model_3D = Term1 + Term2; % [Y, X, Gates]

        % Normalize
        P_sum = sum(P_model_3D, 3);
        P_sum(P_sum == 0) = 1;
        P_model_norm = P_model_3D ./ P_sum;

        ExpCounts_Full = P_model_norm * N_generated;

        % Add Background
        ExpCounts_Full = ExpCounts_Full + N_dark;

        % Poisson Noise
        RawData = poissrnd(ExpCounts_Full);

        % Store Data
        data.RawData = reshape(RawData, [nY, nX, config.N_gates, 1]);
        data.GroundTruthE = Map_E;
        data.GroundTruthFrac = Map_f;
        fig.UserData = data;

        refreshAllPlots(fig);
        return;
    end

    % === Existing Lifetime Logic ===

    if strcmp(Mode, 'Lifetime Gradient')
        unique_taus = linspace(tau1_ns, tau2_ns, nX);
        P_model = DTpmod(config.N_gates, unique_taus, t, gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma);
    else
        % Lifetime Mix Mode
        taus_base = [tau1_ns, tau2_ns];
        P_base = DTpmod(config.N_gates, taus_base, t, gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma);
        P_tau1 = P_base(:, 1);
        P_tau2 = P_base(:, 2);
        alpha = linspace(0, 1, nX);
        P_model = P_tau1 * (1 - alpha) + P_tau2 * alpha;

        % Intensity-weighted average lifetime for residuals reference
        unique_taus = tau1_ns * (1 - alpha) + tau2_ns * alpha;
    end

    % Normalize P_model so that specificed N_generated is the DETECTED sum (Expected)
    P_sum = sum(P_model, 1);
    P_sum(P_sum == 0) = 1;
    P_model_norm = P_model ./ P_sum;

    ExpCounts_1Row = P_model_norm * N_generated;

    % 4. Expand to full image AND ADD Background
    ExpCounts_Full = repmat(reshape(ExpCounts_1Row', 1, nX, config.N_gates), nY, 1, 1);
    ExpCounts_Full = ExpCounts_Full + N_dark;

    RawData = poissrnd(ExpCounts_Full);

    % Store Data for Analysis (with 4th dimension for Channel)
    data.RawData = reshape(RawData, [nY, nX, config.N_gates, 1]);
    data.GroundTruthTaus = unique_taus;
    fig.UserData = data;

    % 6. Refresh Plotting
    refreshAllPlots(fig);

    % Note: Analysis results (tabs) are preserved as history.
    % To clear them, one would interact with the tab group.
    fprintf('Data generation complete.\n');

catch ME
    fprintf(2, 'Error in onGenerate: %s\n', ME.message);
    disp(ME.stack);
    % uialert(fig, ['Generate Failed: ' ME.message], 'Error'); % Optional UI feedback
end
end

function refreshAllPlots(fig)
try
    data = fig.UserData;
    RawData = data.RawData;
    if isempty(RawData)
        fprintf('refreshAllPlots: RawData empty.\n');
        return;
    end

    % Ensure data is [Y, X, T, C]
    [~, ~, ~, nC] = size(RawData);

    % Find Channel Tabs
    dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
    if isempty(dataTabGroup), return; end

    % If number of tabs doesn't match nC, recreate them
    if numel(dataTabGroup.Children) ~= nC
        setupDataTabs(fig, nC);
    end

    % Update each channel
    for c = 1:nC
        cData = squeeze(RawData(:, :, :, c)); % [Y, X, T]

        % Projections for this channel
        projXY = sum(cData, 3);
        projXT = squeeze(sum(cData, 1))'; % [T, X]
        projYT = squeeze(sum(cData, 2));  % [Y, T]

        % Find axes globally by unique tag
        axXY = findobj(fig, 'Tag', sprintf('axXY_Ch%d', c));
        axXT = findobj(fig, 'Tag', sprintf('axXT_Ch%d', c));
        axYT = findobj(fig, 'Tag', sprintf('axYT_Ch%d', c));

        % Update XY
        if ~isempty(axXY)
            imagesc(axXY, projXY);
            colormap(axXY, 'gray');
            axis(axXY, 'image');
            cb = colorbar(axXY, 'Location', 'westoutside');
            cb.Label.String = 'Photons';
            maxCounts = max(projXY(:));
            title(axXY, sprintf('XY Channel %d | Max: %g', c, maxCounts));
            set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');
            % CLim will be set later by spinners to avoid redundancy/beeps
        end

        % Update XT
        if ~isempty(axXT)
            imagesc(axXT, projXT);
            colormap(axXT, 'gray');
            cb = colorbar(axXT, 'Location', 'westoutside');
            cb.Label.String = 'Photons';
            xlabel(axXT, 'XT Projection', 'Visible', 'on', 'FontWeight', 'bold');
            axis(axXT, 'tight');
            set(axXT, 'XTick', [], 'YTick', [], 'Box', 'on');
        end

        % Update YT
        if ~isempty(axYT)
            imagesc(axYT, projYT);
            colormap(axYT, 'gray');
            cb = colorbar(axYT, 'Location', 'eastoutside');
            cb.Label.String = 'Photons';
            title(axYT, 'YT Proj');
            axis(axYT, 'tight');
            set(axYT, 'XTick', [], 'YTick', [], 'Box', 'on');
        end

        % Update Histogram & Contrast
        axHist = findobj(fig, 'Tag', sprintf('axHist_Ch%d', c));
        if ~isempty(axHist)
            cla(axHist);
            % Linear Y-axis histogram
            hData = projXY(:); if isempty(hData), hData=0; end

            histogram(axHist, hData, 'FaceColor', [0.3 0.3 0.3], 'EdgeColor', 'none');

            set(axHist, 'YScale', 'linear', 'Box', 'on', 'Color', 'w', 'YTickMode', 'auto');
            title(axHist, 'Intensity histogram', 'Color', 'k', 'FontSize', 9);
            axHist.XColor = 'k'; axHist.YColor = 'k';
            axHist.YAxis.Visible = 'on';

            % Set labels explicitly so there is something to click
            ylabel(axHist, 'Count');
            xlabel(axHist, 'Photons');

            % Bind toggle callbacks specifically to the labels
            axHist.YLabel.ButtonDownFcn = @toggleHistYScale;
            axHist.XLabel.ButtonDownFcn = @toggleHistXScale;

            disableDefaultInteractivity(axHist); % Lock axes

            % Add background threshold patch (initially 0 width)
            hold(axHist, 'on');
            pThresh = patch(axHist, [0 0 0 0], [0 0 1 1], 'r', ...
                'FaceAlpha', 0.2, 'EdgeColor', 'none', 'Tag', 'pThresh');
            % Send to back so histogram bars are on top
            uistack(pThresh, 'bottom');

            maxC = max(projXY(:)); if maxC <= 0, maxC = 1; end
            xPad = 0.1 * maxC;
            axHist.XLim = [-xPad, maxC + xPad];

            spnMin = findobj(fig, 'Tag', sprintf('spnMin_Ch%d', c));
            spnMax = findobj(fig, 'Tag', sprintf('spnMax_Ch%d', c));
            spnThresh = findobj(fig, 'Tag', sprintf('spnThresh_Ch%d', c));

            if ~isempty(spnMin) && ~isempty(spnMax) && ~isempty(spnThresh)
                % Temporarily expand limits to avoid beeps when setting values
                % Use broad limits first
                spnMin.Limits = [-Inf Inf];
                spnMax.Limits = [-Inf Inf];
                spnThresh.Limits = [-Inf Inf];

                % Calculate valid values bounded by actual data range
                vMin = min(max(0, spnMin.Value), maxC);
                vMax = min(max(0, spnMax.Value), maxC);
                vTh  = min(max(0, spnThresh.Value), maxC);

                % Ensure Logic: Max >= Min (optional but good UI)
                if vMax < vMin, vMax = vMin; end

                % Apply Values
                spnMin.Value = vMin;
                spnMax.Value = vMax;
                spnThresh.Value = vTh;

                % Set Final Limits (Ensure Max > Min for limits to be valid if ever strictly checked,
                % but [0 maxC] is standard. Ensure maxC > 0 to avoid [0 0] if that's an issue)
                finalMax = max(1, maxC);
                spnMin.Limits = [0 finalMax];
                spnMax.Limits = [0 finalMax];
                spnThresh.Limits = [0 finalMax];

                if ~isempty(axXY) && (vMax > vMin)
                    set(axXY, 'CLim', [vMin, vMax]);

                    % Add/Update red background mask overlay
                    hold(axXY, 'on');
                    % Check if mask exists
                    hMask = findobj(axXY, 'Tag', 'BackgroundMask');
                    if isempty(hMask)
                        % Create a solid red image
                        sz = size(projXY);
                        redImg = cat(3, ones(sz), zeros(sz), zeros(sz));
                        hMask = image(axXY, redImg, 'Tag', 'BackgroundMask');
                        % Ensure mask is on top of data but below grid/lines if any
                    end

                    % Update alpha: 1 where data <= threshold, 0 otherwise
                    % Use current threshold value OR custom mask
                    thisTab = dataTabGroup.Children(c);
                    if isfield(thisTab.UserData, 'CustomMask') && ~isempty(thisTab.UserData.CustomMask)
                        alphaMap = double(thisTab.UserData.CustomMask);
                        % Update Threshold line label to indicate mode? Optional.
                    else
                        tVal = spnThresh.Value;
                        alphaMap = double(projXY <= tVal);
                    end
                    % Make it semi-transparent red (e.g. 0.5) or solid (1.0)?
                    % Request saying "distinctive colour red", usually implies overlay
                    % "Background... displayed with a distinctive colour red"
                    % Let's use 1.0 (solid) as requested, or maybe 0.7 for context?
                    % User said "red patch in background" for hist, "distinctive colour" for XY
                    hMask.AlphaData = alphaMap;
                end
                % Draw draggable lines (moved inside axHist check)
                lMin = drawline(axHist, 'Position', [spnMin.Value 0.1; spnMin.Value 1e9], ...
                    'Color', 'y', 'Label', 'Min', 'InteractionsAllowed', 'translate');
                lMax = drawline(axHist, 'Position', [spnMax.Value 0.1; spnMax.Value 1e9], ...
                    'Color', [1 0.5 0], 'Label', 'Max', 'InteractionsAllowed', 'translate');
                lThresh = drawline(axHist, 'Position', [spnThresh.Value 0.1; spnThresh.Value 1e9], ...
                    'Color', [0.5 0.5 0.5], 'Label', 'Thresh', 'InteractionsAllowed', 'translate');

                % Add listeners for interactive dragging
                % PASS TAB explicitly as 'ancestor' on ROI can be flaky
                addlistener(lMin, 'MovingROI', @(src, ev) onContrastLineMoving(axHist.Parent, c, 'Min', src));
                addlistener(lMax, 'MovingROI', @(src, ev) onContrastLineMoving(axHist.Parent, c, 'Max', src));
                addlistener(lThresh, 'MovingROI', @(src, ev) onContrastLineMoving(axHist.Parent, c, 'Thresh', src));
                % Also listen for when moving is finished to update plot
                addlistener(lMin, 'ROIMoved', @(src, ev) onContrastControlChange(axHist.Parent, c, 'line', []));
                addlistener(lMax, 'ROIMoved', @(src, ev) onContrastControlChange(axHist.Parent, c, 'line', []));
                addlistener(lThresh, 'ROIMoved', @(src, ev) onContrastControlChange(axHist.Parent, c, 'line', []));
            end
        end
    end

    updateInstrumentPlot(fig);
    drawnow;
catch ME
    fprintf(2, 'Error in refreshAllPlots: %s\n', ME.message);
    disp(ME.stack);
end
end

function adjustSize(dimXField, dimYField, factor)
dimXField.Value = round(dimXField.Value * factor);

dimYField.Value = round(dimYField.Value * factor);
end

function onAnalyze(fig, algo)
try

    data = fig.UserData;
    if isempty(data.RawData)
        uialert(fig, 'No data generated. Click GENERATE first.', 'Error');
        return;
    end

    tabGroup = findobj(fig, 'Tag', 'analysisTabs');
    allTabs = tabGroup.Children;
    destTab = [];
    for i = 1:numel(allTabs)
        if strcmpi(strtrim(allTabs(i).Title), strtrim(algo))
            destTab = allTabs(i);
            break;
        end
    end

    if isempty(destTab)
        destTab = uitab(tabGroup, 'Title', algo);
    end
    tabGroup.SelectedTab = destTab;

    % Identify active data channel
    dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
    activeChanIdx = 1;
    if ~isempty(dataTabGroup) && ~isempty(dataTabGroup.SelectedTab)
        % Robustly extract channel index from Title "Channel %d"
        tokens = regexp(dataTabGroup.SelectedTab.Title, 'Channel (\d+)', 'tokens');
        if ~isempty(tokens)
            activeChanIdx = str2double(tokens{1}{1});
        end
    end

    if strcmpi(algo, 'Phasor Analysis')
        createNewPhasorTab(fig, destTab, activeChanIdx);
    elseif strcmpi(algo, 'Pattern Matching')
        createNewPatternTab(fig, destTab, activeChanIdx);
    elseif strcmpi(algo, 'LiMA')
        createNewLimaTab(fig, destTab, activeChanIdx);
    elseif strcmpi(algo, 'Fisher Analysis')
        createNewFisherTab(fig, destTab, activeChanIdx);
    elseif strcmpi(algo, 'Tail Fitting')
        createNewFitTab(fig, destTab, algo, activeChanIdx);
    else
        createNewFitTab(fig, destTab, algo, activeChanIdx);
    end

catch ME
    fprintf('Error in onAnalyze: %s\n', ME.message);
    uialert(fig, ['Analysis failed: ' ME.message], 'Error');
end
end


function addPhasorROI(fig, idx)
tabGroup = findobj(fig, 'Tag', 'analysisTabs');

if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
if isempty(tab.UserData), return; end
meta = tab.UserData;

% Determine axes (Phasor or LiMA)
if isfield(meta, 'axPhasor')
    ax = meta.axPhasor;
elseif isfield(meta, 'axGraph')
    ax = meta.axGraph;
else
    return;
end

% Colors: 1=Red, 2=Green, 3=Blue
colors = {[1 0 0], [0 0.8 0], [0 0 1]};

% Remove existing if present in this tab
if ~isempty(meta.ROIs(idx).handle) && isvalid(meta.ROIs(idx).handle)
    delete(meta.ROIs(idx).handle);
end

% Draw new circle at center
h = drawcircle(ax, 'Center', [0.5, 0.3], 'Radius', 0.05, ...
    'Color', colors{idx}, 'Label', sprintf('ROI %d', idx));

% Add listener for movement
addlistener(h, 'ROIMoved', @(src, event) refreshXYProjection(fig));

meta.ROIs(idx).handle = h;
meta.ROIs(idx).active = true;
tab.UserData = meta;

refreshXYProjection(fig);
end

function clearPhasorROI(fig, idxOrAll)
tabGroup = findobj(fig, 'Tag', 'analysisTabs');

if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
if isempty(tab.UserData) || ~isfield(tab.UserData, 'ROIs'), return; end
meta = tab.UserData;

if ischar(idxOrAll) && strcmpi(idxOrAll, 'all')
    for i = 1:3
        if ~isempty(meta.ROIs(i).handle) && isvalid(meta.ROIs(i).handle)
            delete(meta.ROIs(i).handle);
        end
        meta.ROIs(i).handle = [];
        meta.ROIs(i).active = false;
    end
else
    idx = idxOrAll;
    if ~isempty(meta.ROIs(idx).handle) && isvalid(meta.ROIs(idx).handle)
        delete(meta.ROIs(idx).handle);
    end
    meta.ROIs(idx).handle = [];
    meta.ROIs(idx).active = false;
end
tab.UserData = meta;
refreshXYProjection(fig);
end

function toggleVizMode(fig, mode)
data = fig.UserData;

data.vizMode = mode;
fig.UserData = data;
refreshXYProjection(fig);
end

function refreshXYProjection(fig)
data = fig.UserData;

if isempty(data.RawData), return; end

% Find the currently selected Channel Tab
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
if isempty(dataTabGroup), return; end
activeTab = dataTabGroup.SelectedTab;
if isempty(activeTab), return; end

% Robustly extract channel index from Title "Channel %d"
tokens = regexp(activeTab.Title, 'Channel (\d+)', 'tokens');
if ~isempty(tokens)
    chanIdx = str2double(tokens{1}{1});
else
    chanIdx = 1; % Fallback
end

% Get axes for this channel
axXY = findobj(activeTab, 'Tag', sprintf('axXY_Ch%d', chanIdx));
if isempty(axXY), return; end

% Get data for this channel
cData = squeeze(data.RawData(:, :, :, chanIdx));
projXY = sum(cData, 3);

% Capture current crosshair positions if they exist
hV_old = findobj(activeTab, 'Tag', 'crossV');
hH_old = findobj(activeTab, 'Tag', 'crossH');
lastX = 1; lastY = 1; vVisible = 'off';
if ~isempty(hV_old) && isvalid(hV_old(1))
    lastX = hV_old(1).Value;
    vVisible = hV_old(1).Visible;
end
if ~isempty(hH_old) && isvalid(hH_old(1))
    lastY = hH_old(1).Value;
end

cla(axXY);

if strcmpi(data.vizMode, 'Default')
    % Standard Photons Map
    hImg = imagesc(axXY, projXY);
    colormap(axXY, 'gray');
    cb = colorbar(axXY, 'Location', 'westoutside');
    cb.Label.String = 'Photons';
    title(axXY, sprintf('XY (Channel %d)', chanIdx));
else
    % ROI Overlay mode
    tabGroup = findobj(fig, 'Tag', 'analysisTabs');
    tab = tabGroup.SelectedTab;
    tabMeta = [];
    if ~isempty(tab), tabMeta = tab.UserData; end

    % We need coordinates to compute masks.
    % Phasor: G_vals / S_vals
    % LiMA: mu_vals / I2_vals
    X_coord = []; Y_coord = []; rois = [];

    if ~isempty(tabMeta)
        if isfield(tabMeta, 'G_vals') && ~isempty(tabMeta.G_vals)
            X_coord = tabMeta.G_vals;
            Y_coord = tabMeta.S_vals;
            rois = tabMeta.ROIs;
        elseif isfield(tabMeta, 'mu_vals') && ~isempty(tabMeta.mu_vals)
            X_coord = tabMeta.mu_vals;
            Y_coord = tabMeta.I2_vals;
            rois = tabMeta.ROIs;
        end
    end

    if isempty(X_coord)
        % Fallback: If no tab or no mapping data, we can't show overlay
        hImg = imagesc(axXY, projXY);
    else
        [nY, nX] = size(projXY);
        I = double(projXY);
        I_norm = (I - min(I(:))) / (max(I(:)) - min(I(:)) + 1e-10);

        % Background: Full brightness grayscale
        % For each pixel, determine which ROIs it's in
        % 1=Red, 2=Green, 3=Blue
        pixelMasks = false(3, length(X_coord));
        % Defensively check if rois is a struct array
        if isstruct(rois) && numel(rois) >= 3
            for i = 1:3
                if rois(i).active && isvalid(rois(i).handle)
                    roi = rois(i).handle;
                    if isa(roi, 'images.roi.Polygon')
                        pixelMasks(i, :) = inpolygon(X_coord, Y_coord, roi.Position(:,1), roi.Position(:,2));
                    else
                        distSq = (X_coord - roi.Center(1)).^2 + (Y_coord - roi.Center(2)).^2;
                        pixelMasks(i, :) = distSq <= roi.Radius^2;
                    end
                end
            end
        end

        % Construct RGB image: Highlight ROI pixels
        isAnyROI = any(pixelMasks, 1);
        RGB = repmat(I_norm * 0.5, [1, 1, 3]);

        if any(isAnyROI)
            maskAny = reshape(isAnyROI, nY, nX);
            % Zero out ROI pixels to start fresh modulation
            for c = 1:3
                temp = RGB(:,:,c); temp(maskAny) = 0; RGB(:,:,c) = temp;
            end

            for i = 1:3
                mask = reshape(pixelMasks(i, :), nY, nX);
                if any(mask(:))
                    chan = RGB(:,:,i); chan(mask) = I_norm(mask); RGB(:,:,i) = chan;
                end
            end
        end
        hImg = imagesc(axXY, RGB);
        title(axXY, 'XY (ROI Overlay)');
        colorbar(axXY, 'off');
    end
end

axis(axXY, 'image');
set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');
if exist('hImg','var') && isvalid(hImg)
    hImg.ButtonDownFcn = @(src, event) updatePixelAnalysis(fig, event.IntersectionPoint);
end

% Restore crosshair
hold(axXY, 'on');
xline(axXY, lastX, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossV', 'Visible', vVisible);
yline(axXY, lastY, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossH', 'Visible', vVisible);
hold(axXY, 'off');
end

function createNewPhasorTab(fig, t, activeChanIdx)
data = fig.UserData;


% If UI already exists in this tab, just refresh and return
if ~isempty(t.UserData) && isfield(t.UserData, 'axPhasor')
    refreshPhasorPlot(fig, t.UserData.axPhasor);
    return;
end

% Local settings for this run
tabMeta.activeChanIdx = activeChanIdx;
tabMeta.harmonic = 1;
tabMeta.plotAllHarmonics = true;
tabMeta.phasorZoomMode = 'Full';
tabMeta.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});
tabMeta.G_vals = []; tabMeta.S_vals = [];

% Dimensions
fullW = t.Parent.Position(3);
fullH = t.Parent.Position(4);
panelW = 220;
axW = fullW - panelW - 80;

% Main Phasor Axes
axP = uiaxes(t, 'Position', [40, 50, axW, fullH - 120]);
axP.Tag = 'axPhasorRun';
title(axP, t.Title);
xlabel(axP, 'G'); ylabel(axP, 'S');
axP.Box = 'on'; grid(axP, 'on');
axis(axP, 'equal');
tabMeta.axPhasor = axP;
t.UserData = tabMeta;

% ROI & Controls Panel (Inside Tab)
ctrlPanel = uipanel(t, 'Title', 'ROI & Phasor Settings', ...
    'Position', [axW + 60, 50, panelW, fullH - 120]);

currY = ctrlPanel.Position(4) - 45;
uibutton(ctrlPanel, 'Text', 'Add ROI (Red)', 'FontColor', [0.8 0 0], 'Position', [10 currY 120 25], ...
    'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 1));
uibutton(ctrlPanel, 'Text', 'Clear R', 'Position', [140 currY 60 25], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 1));

currY = currY - 30;
uibutton(ctrlPanel, 'Text', 'Add ROI (Green)', 'FontColor', [0 0.6 0], 'Position', [10 currY 120 25], ...
    'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 2));
uibutton(ctrlPanel, 'Text', 'Clear G', 'Position', [140 currY 60 25], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 2));

currY = currY - 30;
uibutton(ctrlPanel, 'Text', 'Add ROI (Blue)', 'FontColor', [0 0 0.8], 'Position', [10 currY 120 25], ...
    'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 3));
uibutton(ctrlPanel, 'Text', 'Clear B', 'Position', [140 currY 60 25], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 3));

currY = currY - 40;
uibutton(ctrlPanel, 'Text', 'CLEAR ALL ROIs', 'FontWeight', 'bold', 'Position', [10 currY 190 30], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 'all'));

currY = currY - 45;
uilabel(ctrlPanel, 'Text', 'Visualization:', 'Position', [10 currY 80 20]);
uiswitch(ctrlPanel, 'toggle', 'Items', {'Default', 'Overlay'}, 'Value', data.vizMode, ...
    'Position', [100 currY + 10 50 20], ...
    'ValueChangedFcn', @(sw, event) toggleVizMode(fig, sw.Value));

currY = currY - 45;
uilabel(ctrlPanel, 'Text', 'Harmonic:', 'Position', [10 currY 70 20]);
uispinner(ctrlPanel, 'Limits', [1 3], 'Value', tabMeta.harmonic, ...
    'Position', [80 currY 50 22], ...
    'ValueChangedFcn', @(sp, event) updateHarmonic(fig, sp.Value, []));

uicheckbox(ctrlPanel, 'Text', 'All', 'Value', tabMeta.plotAllHarmonics, ...
    'Position', [135 currY 45 22], ...
    'Tooltip', 'Show all harmonics up to selected', ...
    'ValueChangedFcn', @(cb, event) updateHarmonic(fig, [], cb.Value));

currY = currY - 40;
uibutton(ctrlPanel, 'Text', '', 'Position', [30 currY 32 32], 'Tooltip', 'Zoom to Data only', ...
    'Icon', 'C:/Users/ae275/.gemini/antigravity/brain/eb553d2f-4539-4e9a-94c9-4c463a29c28a/zoom_in_icon_1766743622031.png', ...
    'ButtonPushedFcn', @(btn, event) setPhasorZoom(fig, 'Data'));
uibutton(ctrlPanel, 'Text', '', 'Position', [70 currY 32 32], 'Tooltip', 'Zoom to Full (Data + Curves)', ...
    'Icon', 'C:/Users/ae275/.gemini/antigravity/brain/eb553d2f-4539-4e9a-94c9-4c463a29c28a/zoom_out_icon_1766743633452.png', ...
    'ButtonPushedFcn', @(btn, event) setPhasorZoom(fig, 'Full'));

refreshPhasorPlot(fig, axP);
end

function createNewFitTab(fig, tab, algo, activeChanIdx)
data = fig.UserData;

config = data.config;

axL = data.axL; axW = data.axW; metX = data.metX; xyY_top = data.xyY_top;

% If UI already exists, retrieval
if isempty(tab.UserData) || ~isfield(tab.UserData, 'axTau')
    axTau = uiaxes(tab, 'PositionConstraint', 'innerposition');
    axTau.InnerPosition = [axL, xyY_top, axW, axW]; axTau.Tag = 'axTauLocal';
    % Customize for tight display
    set(axTau, 'XTick', [], 'YTick', [], 'Box', 'on', 'LineWidth', 2);

    % Colorbar Spinners (Right of Axes)
    cbX = axL + axW + 10; % Align with colorbar left edge
    cbY_mid = xyY_top + axW/2;

    % Max Spinner (Top of half-bar)
    spnCMax = uispinner(tab, 'Position', [cbX, cbY_mid + axW/4 + 10, 60, 22], ...
        'Tag', 'spnCMax', 'Value', 10, 'Step', 0.1, ...
        'ValueChangedFcn', @(src,ev) updateCLimFit(tab, 'Max', src.Value));

    % Min Spinner (Bottom of half-bar)
    spnCMin = uispinner(tab, 'Position', [cbX, cbY_mid - axW/4 - 30, 60, 22], ...
        'Tag', 'spnCMin', 'Value', 0, 'Step', 0.1, ...
        'ValueChangedFcn', @(src,ev) updateCLimFit(tab, 'Min', src.Value));


    statsY = xyY_top - 15 - data.xtH;
    axStats = uiaxes(tab, 'PositionConstraint', 'innerposition');
    axStats.InnerPosition = [axL, statsY, axW, data.xtH];

    zH = data.xtH * 0.45;
    resY = statsY - 2 - zH;
    axRes = uiaxes(tab, 'PositionConstraint', 'innerposition');
    axRes.InnerPosition = [axL, resY, axW, zH];

    uChi = uilabel(tab, 'Text', 'Chi2: --', 'FontWeight', 'bold', 'Position', [metX, resY + zH - 20, 150, 20]);
    uRE = uilabel(tab, 'Text', 'R.E.: --%', 'FontWeight', 'bold', 'Position', [metX, resY + zH - 40, 150, 20]);
    uRND = uilabel(tab, 'Text', 'RND: --', 'FontWeight', 'bold', 'Position', [metX, resY + zH - 60, 150, 20]);

    pixelH = 150; pixelY = resY - 60 - pixelH;
    axPix = uiaxes(tab, 'PositionConstraint', 'innerposition');
    axPix.InnerPosition = [axL, pixelY, axW, pixelH];
    axPixRes = uiaxes(tab, 'PositionConstraint', 'innerposition');
    axPixRes.InnerPosition = [axL, pixelY - 5 - zH, axW, zH];

    uPixPos = uilabel(tab, 'Text', 'Pos: --', 'FontWeight', 'bold', 'Position', [metX, pixelY + pixelH - 20, 150, 20]);
    uPixTau = uilabel(tab, 'Text', 'Tau: --', 'FontWeight', 'bold', 'Position', [metX, pixelY + pixelH - 40, 150, 20]);
    uPixChi = uilabel(tab, 'Text', 'Chi2: --', 'FontWeight', 'bold', 'Position', [metX, pixelY + pixelH - 60, 150, 20]);
    uPixRE = uilabel(tab, 'Text', 'R.E.: --%', 'FontWeight', 'bold', 'Position', [metX, pixelY + pixelH - 80, 150, 20]);
    uPixRND = uilabel(tab, 'Text', 'RND: --', 'FontWeight', 'bold', 'Position', [metX, pixelY + pixelH - 100, 150, 20]);

    % Analysis Parameters Panel (Inside Fit Tab)
    paramPanel = uipanel(tab, 'Title', 'Analysis Parameters', 'Tag', 'paramPanel', ...
        'Position', [metX, xyY_top + axW - 160, 230, 160]);
    uilabel(paramPanel, 'Text', 'Algorithm: --', 'Tag', 'uAlgo', 'Position', [10, 110, 200, 20]);
    uilabel(paramPanel, 'Text', 'Gates: --', 'Tag', 'uGates', 'Position', [10, 90, 200, 20]);
    uilabel(paramPanel, 'Text', 'FWHM: --', 'Tag', 'uFWHM', 'Position', [10, 70, 200, 20]);

    % Checkbox Anscombe
    chkAns = uicheckbox(paramPanel, 'Text', 'Anscombe Transform', ...
        'Position', [10, 40, 200, 22], ...
        'Tooltip', 'Apply 2*sqrt(x + 3/8) to stabilize variance before fitting.', ...
        'Tag', 'chkAnscombe');

    % Run Button
    uibutton(paramPanel, 'Text', 'Re-Run Analysis', 'FontWeight', 'bold', ...
        'Position', [10, 10, 200, 25], ...
        'ButtonPushedFcn', @(btn, ev) runFitAnalysis(fig, tab));

    tabMeta.activeChanIdx = activeChanIdx;
    tabMeta.axTau = axTau; tabMeta.axStats = axStats; tabMeta.axRes = axRes;
    tabMeta.axPix = axPix; tabMeta.axPixRes = axPixRes;
    tabMeta.uChi = uChi; tabMeta.uRE = uRE; tabMeta.uRND = uRND;
    tabMeta.uPixPos = uPixPos; tabMeta.uPixTau = uPixTau;
    tabMeta.uPixChi = uPixChi; tabMeta.uPixRE = uPixRE; tabMeta.uPixRND = uPixRND;
    tabMeta.chkAnscombe = chkAns;
    tabMeta.spnCMin = spnCMin; tabMeta.spnCMax = spnCMax;
    tabMeta.algo = algo;
    tab.UserData = tabMeta;
else
    % Refresh references if needed
    tabMeta = tab.UserData;
    % If we re-opened same tab for same channel, activeChanIdx matches.
    % If channel changed, we should probably update it.
    tabMeta.activeChanIdx = activeChanIdx;
    tabMeta.algo = algo;
    tab.UserData = tabMeta;
end

% Update Parameters Panel text
pnl = findobj(tab, 'Tag', 'paramPanel');
if ~isempty(pnl)
    uAlgo = findobj(pnl, 'Tag', 'uAlgo'); uAlgo.Text = sprintf('Algorithm: %s', algo);
    uGates = findobj(pnl, 'Tag', 'uGates'); uGates.Text = sprintf('Gates: %d', config.N_gates);
    uFWHM = findobj(pnl, 'Tag', 'uFWHM'); uFWHM.Text = sprintf('FWHM: %.1f ps', config.fwhm*1000);
end

% Run Initial Analysis
runFitAnalysis(fig, tab);
end

function runFitAnalysis(fig, tab)
% Extract Data & Config

data = fig.UserData;
config = data.config;
meta = tab.UserData;
activeChanIdx = meta.activeChanIdx;

RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [nY, nX, nGates] = size(RawData);
    mask3D = repmat(mask, 1, 1, nGates);
    RawData(mask3D) = 0;
else
    [nY, nX, nGates] = size(RawData);
end

% Check Anscombe
isAnscombe = false;
if isfield(meta, 'chkAnscombe') && isvalid(meta.chkAnscombe) && meta.chkAnscombe.Value
    isAnscombe = true;
    RawData = 2 * sqrt(RawData + 3/8);
end

dt = config.dt; T = config.T; t = 0:dt:T;
gate_profiles = DTgates(t, config.r, config.gate_edges);
gate_interp_fns = cell(config.N_gates, 1);
for i = 1:config.N_gates
    gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
end

M = nY * nX; flatData = double(reshape(permute(RawData, [3, 1, 2]), nGates, M));
N_detections = sum(flatData, 1); % If Anscombe, this sums transformed values!

algo = meta.algo;
if strcmpi(algo, 'Grid MLE')
    tau_grid = linspace(0.1, 10, 100);
    P_model_grid = DTpmod(config.N_gates, tau_grid, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);

    % We proceed passing transformed data as requested.
    [tau_est_flat, ~] = DTmle(N_detections, flatData, tau_grid, P_model_grid, fig);
elseif strcmpi(algo, 'Tail Fitting')
    % Tail Fit
    % Pass RawData directly.
    [TauMap_Tail, ~] = DTtailfit(RawData, config);
    tau_est_flat = reshape(TauMap_Tail, 1, []);
else
    % Iterative
    % DTiterative usually takes RawData (3D).
    [TauMap_Iter, ~] = DTiterative(RawData, config, fig);
    tau_est_flat = reshape(TauMap_Iter, 1, []);
end
TauMap = reshape(tau_est_flat, nY, nX);

% Update Plots
axTau = meta.axTau; axStats = meta.axStats; axRes = meta.axRes;

hImg = imagesc(axTau, TauMap); colormap(axTau, 'jet');
hImg.ButtonDownFcn = @(src, event) updatePixelAnalysis(fig, event.IntersectionPoint);
axis(axTau, 'image'); % Fix aspect ratio
set(axTau, 'XTick', [], 'YTick', [], 'Box', 'on', 'LineWidth', 2); % Re-apply style

% --- Colorbar Logic ---
% 1. Create or Get Colorbar
cb = colorbar(axTau);
cb.Ticks = [];
cb.Location = 'eastoutside';
cb.Units = 'pixels'; % Ensure units match for positioning

% 2. Manual Resize to Half Height
% We must use 'Position' property of colorbar which requires manual mode
% AXIS InnerPosition: [x,y,w,h]
axPos = axTau.InnerPosition;
cbW = 20;
cbH = axPos(4) * 0.5; % Half height
cbX = axPos(1) + axPos(3) + 10; % 10px padding
cbY = axPos(2) + (axPos(4) - cbH)/2; % Centered vertically

% Wait for layout reflow or force position
drawnow limitrate;
cb.Position = [cbX, cbY, cbW, cbH];
cb.Label.String = 'Lifetime (ns)';

% Update Spinners
cMin = min(TauMap(:)); cMax = max(TauMap(:));
if isempty(cMin), cMin = 0; end
if isempty(cMax) || cMax <= cMin, cMax = cMin + 1e-3; end

% Update Spinner Values & Position
meta = tab.UserData;
if ~isempty(meta.spnCMin) && isvalid(meta.spnCMin)
    meta.spnCMin.Value = cMin;
    % Align left edge to colorbar left edge
    meta.spnCMin.Position(1) = cbX;
    meta.spnCMin.Position(2) = cbY - 25;
end
if ~isempty(meta.spnCMax) && isvalid(meta.spnCMax)
    meta.spnCMax.Value = cMax;
    % Align left edge to colorbar left edge
    meta.spnCMax.Position(1) = cbX;
    meta.spnCMax.Position(2) = cbY + cbH + 5;
end

% Set CLim
set(axTau, 'CLim', [cMin cMax]);

if isAnscombe
    title(axTau, [tab.Title ' [Anscombe]']);
else
    title(axTau, tab.Title);
end

meta.TauMap = TauMap; meta.gate_interp_fns = gate_interp_fns;
meta.nX = nX; meta.nY = nY;
tab.UserData = meta;

% Update Stats
meanTau = mean(TauMap, 1, 'omitnan'); stdTau = std(TauMap, 0, 1, 'omitnan');
xVec = 1:nX;
cla(axStats);
fill(axStats, [xVec, fliplr(xVec)], [meanTau+1.96*stdTau, fliplr(meanTau-1.96*stdTau)], ...
    [0.6 0.8 1], 'EdgeColor', 'none', 'FaceAlpha', 0.5);
hold(axStats, 'on'); plot(axStats, xVec, meanTau, 'b-', 'LineWidth', 1.5);
grid(axStats, 'on');

% Update Residuals (Global)
% Note: Ground Truth might not align if user did transform.
% We compute residual vs Ground Truth if available.

if isfield(data, 'GroundTruthTaus') && ~isempty(data.GroundTruthTaus)
    tau_true = data.GroundTruthTaus(:)';
    % Handle mismatch if user changed resolution (e.g. from 64x64 to something else)
    % or if GT is 1D (gradient) but TauMap is 2D.
    if numel(tau_true) ~= numel(tau_est_flat)
        % Try to reshape GT to match X dimension
        if length(tau_true) == nX
            tau_true = repmat(tau_true, nY, 1);
        elseif length(tau_true) == nY
            tau_true = repmat(tau_true', 1, nX);
        end
    end

    % Re-check after potential expansion
    if numel(tau_true) == numel(TauMap)
        % Ensure shapes match
        if size(tau_true, 1) == 1 && size(tau_true, 2) > 1
            % 1D vector -> expand to 2D
            tau_true = repmat(tau_true, nY, 1);
        end
    end

    if numel(tau_true) == numel(TauMap)
        tau_true = reshape(tau_true, nY, nX); % Ensure exact shape match

        irf_params = struct('fwhm',config.fwhm,'profile',config.profile,'rise_time',config.rise_time,'fall_time',config.fall_time,...
            'bPulseTrain',config.bPulseTrain,'PT_Trep',config.PT_Trep,'PT_sigma',config.PT_sigma);

        % Use original photon count for CRLB, but we might only have transformed data here.
        n_ph_px_est = sum(N_detections) / M;

        [~, f_vals_true] = DTcomputeFisherInfo(config.gate_edges, irf_params, config.r, config.T, tau_true(:)', n_ph_px_est);
        f_vals_true = reshape(f_vals_true, nY, nX);

        sigma_crlb = (f_vals_true .* tau_true) / sqrt(n_ph_px_est);
        z_map = (TauMap - tau_true) ./ sigma_crlb;

        stem(axRes, 1:nX, mean(z_map, 1, 'omitnan'), 'Marker', 'none');
        yline(axRes, [2, -2], 'r--'); grid(axRes, 'on');

        chi2_val = mean(z_map(:).^2, 'omitnan');
        meta.uChi.Text = sprintf('Chi2: %.3f', chi2_val);
        meta.uRE.Text = sprintf('R.E.: %.1f%%', (1/chi2_val)*100);
        meta.uRND.Text = sprintf('RND: %.2f', 1/chi2_val);
    else
        cla(axRes); title(axRes, 'Dimension Mismatch with GT');
        % Warning: Ground Truth size does not match Tau Map size
    end
else
    cla(axRes); title(axRes, 'No Ground Truth');
end

updatePixelAnalysis(fig, [nX/2, nY/2]);
end


function createNewPatternTab(fig, t, activeChanIdx)
data = fig.UserData;

if ~isfield(data, 'RawData') || isempty(data.RawData)
    error('RawData is missing from fig.UserData. Please generate data first.');
end
if ~isfield(data, 'config') || isempty(data.config)
    error('Config is missing from fig.UserData.');
end

RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [nY, nX, nGates] = size(RawData);
    mask3D = repmat(mask, 1, 1, nGates);
    RawData(mask3D) = 0;
else
    [nY, nX, nGates] = size(RawData);
end

[nY, nX, ~] = size(RawData);
axL = data.axL;
% We use a local higher top Y for this tab to fit two rows
xyY_top = 920;

if isempty(t.UserData) || ~isfield(t.UserData, 'axDDM')
    % --- Layout ---
    % Top Left: Decay Diversity Map (DDM)
    ddmW = 420; ddmH = 380;
    axDDM = uiaxes(t, 'Position', [axL, xyY_top - ddmH, ddmW, ddmH]);
    axDDM.Tag = 'axDDM'; title(axDDM, 'Decay Diversity Map');
    xlabel(axDDM, 'Mean Lifetime \tau_m (ns)'); ylabel(axDDM, 'Heterogeneity \sigma (ns)');
    grid(axDDM, 'on'); box(axDDM, 'on');

    % Top Right: Pattern Management Panel
    pnlX = axL + ddmW + 30;
    pnlW = 340;
    pnlH = ddmH;
    pnl = uipanel(t, 'Title', 'Pattern Management', 'Position', [pnlX, xyY_top - ddmH, pnlW, pnlH]);

    % Listbox for patterns
    lbPatterns = uilistbox(pnl, 'Position', [10, 150, pnlW-20, pnlH-180], 'Items', {});
    lbPatterns.Tag = 'lbPatterns';

    % Buttons
    uibutton(pnl, 'Text', 'Draw ROI & Add Pattern', 'Position', [10, 110, pnlW-20, 25], ...
        'ButtonPushedFcn', @(btn, event) addPatternROI(fig, 'poly'));

    uibutton(pnl, 'Text', 'Delete Selected', 'Position', [10, 75, 100, 25], ...
        'ButtonPushedFcn', @(btn, event) deletePattern(fig));

    % Checkbox Anscombe
    chkAns = uicheckbox(pnl, 'Text', 'Anscombe Transform', ...
        'Position', [120, 75, 150, 25], ...
        'Tooltip', 'Apply 2*sqrt(x + 3/8) to stabilize variance before fitting.', ...
        'Tag', 'chkAnscombe');

    uibutton(pnl, 'Text', 'RUN FIT', 'FontWeight', 'bold', 'BackgroundColor', [0.8 0 0], 'FontColor', [1 1 1], ...
        'Position', [10, 10, pnlW-20, 40], ...
        'ButtonPushedFcn', @(btn, event) runPatternFit(fig));

    % Bottom: Results Maps (RGB and Individual)
    resY = xyY_top - ddmH - 425;
    axFit = uiaxes(t, 'Position', [axL, resY, 420, 380]);
    axFit.Tag = 'axFit'; title(axFit, 'Reference Pattern Fit (RGB)');
    axis(axFit, 'image'); set(axFit, 'XTick', [], 'YTick', []);

    % Patterns Plot (Show the actual decays)
    axPats = uiaxes(t, 'Position', [axL + 450, resY, 340, 380]);
    axPats.Tag = 'axPats'; title(axPats, 'Pattern Decays');
    xlabel(axPats, 'Gate Time (ns)'); ylabel(axPats, 'Prob');
    grid(axPats, 'on');

    meta.axDDM = axDDM;
    meta.lbPatterns = lbPatterns;
    meta.axFit = axFit;
    meta.axPats = axPats;
    meta.patterns = struct('name', {}, 'color', {}, 'decay', {}, 'roi', {});
    meta.ddm_scatter = [];
    meta.activeChanIdx = activeChanIdx;
    meta.chkAnscombe = chkAns;
    t.UserData = meta;

    % -- Initialize DDM Data (One time calc) --
    % We interpret this as LiMA moments: Mean Tau vs Sigma
    % Use the data for the active channel extracted at the beginning of the function
    [limaResults, ~] = DTlima(RawData, data.config, 1, []); % Call with empty fig to suppress waiting

    if isstruct(limaResults) && isfield(limaResults, 'mu_tau') && isfield(limaResults, 'sigma_tau')
        meta.mu_flat = limaResults.mu_tau(:);
        meta.sig_flat = limaResults.sigma_tau(:);
    else
        error('DTlima failed to return valid results struct for DDM.');
    end
    meta.nX = nX; meta.nY = nY;

    t.UserData = meta;

    % Initial Plot
    plotDDM(fig);
end
end

function plotDDM(fig)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;

meta = t.UserData;
ax = meta.axDDM;
cla(ax); hold(ax, 'on');

% Plot density scatter
% Downsample for performance if needed
mu = meta.mu_flat; sig = meta.sig_flat;
if length(mu) > 20000; idx = randperm(length(mu), 20000); else; idx = 1:length(mu); end

scatter(ax, mu(idx), sig(idx), 4, 'filled', 'MarkerFaceAlpha', 0.2, 'MarkerEdgeColor', 'none', 'MarkerFaceColor', [0.2 0.2 0.8]);

% Re-plot ROI shapes if they exist
for i = 1:length(meta.patterns)
    p = meta.patterns(i);
    if ~isempty(p.roi) && isvalid(p.roi)
        % Roi is handle to drawn shape, might be deleted.
        % We don't persist ROI shapes on redraw usually unless we stored coordinates.
        % For now, just show the DDM.
    end
end
end

function addPatternROI(fig, ~)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;

meta = t.UserData;
data = fig.UserData;
ax = meta.axDDM; % Get ax from meta
btnDraw = findobj(t, 'Text', 'Draw ROI & Add Pattern');
if ~isempty(btnDraw), btnDraw.Enable = 'off'; end

% Add a temporary label for instructions
% Position it just above the DDM axes
lblHint = uilabel(t, 'Text', 'Draw Polygon then DOUBLE-CLICK TO CONFIRM', ...
    'FontSize', 14, 'FontWeight', 'bold', 'FontColor', [1 0 1], ...
    'Position', [ax.Position(1), ax.Position(2) + ax.Position(4) + 5, 400, 25]);

hROI = drawpolygon(ax, 'Color', 'm');

% 2. Wait for user to finish drawing
% hROI.wait() blocks execution until double-click on the ROI
wait(hROI);
delete(lblHint); % Remove instruction
if ~isempty(btnDraw), btnDraw.Enable = 'on'; end

if ~isvalid(hROI)
    return; % User might have deleted it during wait
end

% 3. Refresh metadata to avoid race conditions after the blocking wait
meta = t.UserData;
if isempty(meta), return; end % Should not happen if initialized

% 2. Extract Mask in Mu/Sigma space
% No, createMask works on images. scatter is not image.
% We need inpolygon.
polyPos = hROI.Position;
in_mask = inpolygon(meta.mu_flat, meta.sig_flat, polyPos(:,1), polyPos(:,2));

if ~any(in_mask)
    uialert(fig, 'ROI contains no pixels!', 'Warning');
    delete(hROI);
    return;
end

% 3. Extract Average Decay
% We need to access RawData linear indices.
% We identify the active channel data.
activeChanIdx = meta.activeChanIdx;
RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [nY, nX, nGates] = size(RawData);
    mask3D = repmat(mask, 1, 1, nGates);
    RawData(mask3D) = 0;
else
    [nY, nX, nGates] = size(RawData);
end
flatData = reshape(permute(RawData, [3, 1, 2]), nGates, []); % (Gates, M)

ref_decay = sum(flatData(:, in_mask), 2);
ref_decay = ref_decay / sum(ref_decay); % Normalize

% 4. Ask for Name
idx = length(meta.patterns) + 1;
defaultName = sprintf('Pattern %d', idx);

% Use inputdlg to ask for pattern name
answer = inputdlg('Enter Pattern Name:', 'New Pattern', [1 50], {defaultName});
if isempty(answer)
    name = defaultName;
else
    name = answer{1};
end
% Assign color
colors = [1 0 0; 0 1 0; 0 0 1; 1 0 1; 0 1 1; 1 1 0];
col = colors(mod(idx-1, 6)+1, :);
hROI.Color = col; % Update ROI color

meta.patterns(idx).name = name;
meta.patterns(idx).color = col;
meta.patterns(idx).decay = ref_decay;
meta.patterns(idx).roi = hROI; % Store handle to allowing deleting/hiding later

t.UserData = meta;
updatePatternList(t);
updatePatternPlot(t);
end

function deletePattern(fig)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;

meta = t.UserData;
lb = meta.lbPatterns;

sel = lb.Value; % Name of selected
if isempty(sel), return; end

% Find index
idx = find(strcmp({meta.patterns.name}, sel));
if isempty(idx), return; end

% Remove ROI
if isvalid(meta.patterns(idx).roi)
    delete(meta.patterns(idx).roi);
end

meta.patterns(idx) = [];
t.UserData = meta;
updatePatternList(t);
updatePatternPlot(t);
end

function updatePatternList(t)
meta = t.UserData;

items = {meta.patterns.name};
meta.lbPatterns.Items = items;
if ~isempty(items)
    meta.lbPatterns.Value = items{end};
end
drawnow;
end

function updatePatternPlot(t)
meta = t.UserData;

ax = meta.axPats;
cla(ax); hold(ax, 'on');
config = t.Parent.Parent.UserData.config;
% Decay is gates, not time bins?
% Patterns are N_gates.
gate_centers = (config.gate_edges(1:end-1) + config.gate_edges(2:end))/2;

for i = 1:length(meta.patterns)
    p = meta.patterns(i);
    plot(ax, gate_centers, p.decay, '.-', 'Color', p.color, 'LineWidth', 2, 'DisplayName', p.name);
end
legend(ax, 'Location', 'best');
drawnow;
end

function runPatternFit(fig)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;

meta = t.UserData;
data = fig.UserData;

if isempty(meta.patterns)
    uialert(fig, 'No patterns defined!', 'Error');
    return;
end

% 1. Build Matrix
K = length(meta.patterns);
activeChanIdx = meta.activeChanIdx;
RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [nY, nX, nGates] = size(RawData);
    mask3D = repmat(mask, 1, 1, nGates);
    RawData(mask3D) = 0;
else
    [nY, nX, nGates] = size(RawData);
end

% Check Anscombe
if isfield(meta, 'chkAnscombe') && isvalid(meta.chkAnscombe) && meta.chkAnscombe.Value
    RawData = 2 * sqrt(RawData + 3/8);
end

patMat = zeros(nGates, K);
for i = 1:K
    patMat(:, i) = meta.patterns(i).decay;
end

% 2. Run Fit
[fractionMaps, ~, ~] = DTpatternmatching(RawData, patMat, data.config, fig);

% 3. Visualize RGB
% Only use first 3 patterns for R, G, B
RGB = zeros(nY, nX, 3);
for k = 1:min(K, 3)
    map = fractionMaps(:,:,k);
    % Normalize for display brightness?
    % Weights are photon counts roughly.
    % We want to show relative contribution?
    % Or absolute intensity of that component?

    % Option A: Absolute Intensity Scaled
    % RGB(:,:,k) = map / max(map(:));

    % Option B: Relative contribution (Alpha mixing)
    % This is tricky.

    % Let's use simple normalization by max of ALL maps to preserve relative intensities
    maxVal = max(fractionMaps(:));
    if maxVal > 0
        RGB(:,:,k) = map / maxVal;
    end
end

% Enhance brightness
RGB = RGB * 2; % simple gain
RGB(RGB>1) = 1;

image(meta.axFit, RGB);
title(meta.axFit, 'RGB Composition (P1=R, P2=G, P3=B)');
axis(meta.axFit, 'image'); set(meta.axFit, 'XTick', [], 'YTick', []);

end

function createNewLimaTab(fig, t, activeChanIdx)
debugInfo = 'Start';

try
    data = fig.UserData;
    debugInfo = 'Retrieved data';

    if ~isfield(data, 'config') || ~isstruct(data.config)
        error('Configuration data (data.config) is missing or not a struct.');
    end
    config = data.config;

    if ~isfield(data, 'RawData')
        error('RawData is missing.');
    end
    % Extract data for this channel
    RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

    % Apply Mask
    mask = getChannelMask(fig, activeChanIdx);
    if ~isempty(mask)
        [nY, nX, nGates] = size(RawData);
        mask3D = repmat(mask, 1, 1, nGates);
        RawData(mask3D) = 0;
    end

    axL = data.axL; xyY_top = data.xyY_top;
    debugInfo = 'Layout vars set';

    % Initialize UI if needed - check for a key component like axMu
    if isempty(findobj(t, 'Tag', 'axMu'))
        debugInfo = 'Initializing UI';
        % Two maps: Mu and Sigma
        paxW = 280;
        axMu = uiaxes(t, 'Position', [axL, xyY_top - 60, paxW, paxW]);
        axMu.Tag = 'axMu'; title(axMu, 'Mean Lifetime \mu (ns)'); colormap(axMu, 'jet');

        axSig = uiaxes(t, 'Position', [axL + paxW + 40, xyY_top - 60, paxW, paxW]);
        axSig.Tag = 'axSig'; title(axSig, 'Heterogeneity \sigma (ns)'); colormap(axSig, 'hot');

        % Plot for Mu vs I2
        axGraph = uiaxes(t, 'Position', [axL, xyY_top - 460, paxW*2 + 40, 350]);
        axGraph.Tag = 'axGraph'; title(axGraph, 'LiMA Analysis: \mu vs I_2');
        xlabel(axGraph, '\mu (reduced)'); ylabel(axGraph, 'I_2 (reduced)');

        grid(axGraph, 'on');

        % LiMA Controls Panel
        ctrlPanel = uipanel(t, 'Title', 'LiMA Controls', 'Position', [axL + paxW*2 + 60, xyY_top - 460, 200, 350]);

        currY = 300;
        uibutton(ctrlPanel, 'Text', 'Add ROI (Red)', 'FontColor', [0.8 0 0], 'Position', [10 currY 110 25], ...
            'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 1));
        uibutton(ctrlPanel, 'Text', 'Clear R', 'Position', [130 currY 60 25], ...
            'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 1));

        currY = currY - 30;
        uibutton(ctrlPanel, 'Text', 'Add ROI (Green)', 'FontColor', [0 0.6 0], 'Position', [10 currY 110 25], ...
            'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 2));
        uibutton(ctrlPanel, 'Text', 'Clear G', 'Position', [130 currY 60 25], ...
            'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 2));

        currY = currY - 30;
        uibutton(ctrlPanel, 'Text', 'Add ROI (Blue)', 'FontColor', [0 0 0.8], 'Position', [10 currY 110 25], ...
            'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 3));
        uibutton(ctrlPanel, 'Text', 'Clear B', 'Position', [130 currY 60 25], ...
            'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 3));

        currY = currY - 40;
        uibutton(ctrlPanel, 'Text', 'CLEAR ALL', 'FontWeight', 'bold', 'Position', [10 currY 180 30], ...
            'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 'all'));

        currY = currY - 45;
        uilabel(ctrlPanel, 'Text', 'Visualization:', 'Position', [10 currY 80 20]);
        uiswitch(ctrlPanel, 'toggle', 'Items', {'Default', 'Overlay'}, 'Value', data.vizMode, ...
            'Position', [100 currY + 10 50 20], ...
            'ValueChangedFcn', @(sw, event) toggleVizMode(fig, sw.Value));

        currY = currY - 40;
        uibutton(ctrlPanel, 'Text', '', 'Position', [30 currY 32 32], 'Tooltip', 'Zoom Data', ...
            'Icon', 'C:/Users/ae275/.gemini/antigravity/brain/eb553d2f-4539-4e9a-94c9-4c463a29c28a/zoom_in_icon_1766743622031.png', ...
            'ButtonPushedFcn', @(btn, event) setPhasorZoom(fig, 'Data'));
        uibutton(ctrlPanel, 'Text', '', 'Position', [70 currY 32 32], 'Tooltip', 'Zoom Full', ...
            'Icon', 'C:/Users/ae275/.gemini/antigravity/brain/eb553d2f-4539-4e9a-94c9-4c463a29c28a/zoom_out_icon_1766743633452.png', ...
            'ButtonPushedFcn', @(btn, event) setPhasorZoom(fig, 'Full'));

        % Anscombe Checkbox
        currY = currY - 35;
        chkAns = uicheckbox(ctrlPanel, 'Text', 'Anscombe Transform', ...
            'Position', [10, currY, 180, 22], ...
            'Tooltip', 'Apply 2*sqrt(x + 3/8) to stabilize variance (LiMA moments).', ...
            'Tag', 'chkAnscombe');

        % Run Button
        currY = currY - 35;
        uibutton(ctrlPanel, 'Text', 'Recalculate', 'FontWeight', 'bold', ...
            'Position', [10, currY, 180, 30], ...
            'ButtonPushedFcn', @(btn, event) runLimaAnalysis(fig));

        meta = struct();
        meta.axMu = axMu; meta.axSig = axSig; meta.axGraph = axGraph;
        meta.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});
        meta.phasorZoomMode = 'Full';
        meta.harmonic = 1;
        meta.activeChanIdx = activeChanIdx;
        meta.chkAnscombe = chkAns;
        t.UserData = meta;
        debugInfo = 'UI Initialized and UserData set';
    end

    runLimaAnalysis(fig);

catch ME
    uialert(fig, ['LiMA Analysis Failed (' debugInfo '): ' ME.message], 'Error');
end
end

function runLimaAnalysis(fig)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;

meta = t.UserData;
data = fig.UserData;
config = data.config;

% Validate meta
if isempty(meta) || ~isstruct(meta)
    % Try to recover handles if UI exists but meta lost (rare)
    % For now just return or error
    return;
end

% Check Anscombe
activeChanIdx = meta.activeChanIdx;
RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [nY, nX, nGates] = size(RawData);
    mask3D = repmat(mask, 1, 1, nGates);
    RawData(mask3D) = 0;
end

if isfield(meta, 'chkAnscombe') && isvalid(meta.chkAnscombe) && meta.chkAnscombe.Value
    RawData = 2 * sqrt(RawData + 3/8);
end

harmonic = 1;
if isfield(meta, 'harmonic'), harmonic = meta.harmonic; end

% Run LiMA
[limaResults, stats] = DTlima(RawData, config, harmonic, fig);

% Validate stats
if ~isstruct(stats) || ~isfield(stats, 'S') || ~isfield(stats, 'G')
    error('DTlima returned invalid stats structure.');
end

% Store Results
meta.mu_vals = stats.S(:) ./ max(stats.G(:), 1e-9);

M_val_tmp = sqrt(stats.G(:).^2 + stats.S(:).^2);
meta.I2_vals = 0.5 * (max(M_val_tmp.^-2 - 1, 0) + meta.mu_vals.^2);

if ~isstruct(limaResults) || ~isfield(limaResults, 'mu_tau')
    error('DTlima returned invalid results structure (not a struct or missing mu_tau).');
end

if ~isempty(meta.axMu) && isvalid(meta.axMu)
    imagesc(meta.axMu, limaResults.mu_tau); colorbar(meta.axMu); axis(meta.axMu, 'image');
end
if ~isempty(meta.axSig) && isvalid(meta.axSig)
    imagesc(meta.axSig, limaResults.sigma_tau); colorbar(meta.axSig); axis(meta.axSig, 'image');
end

% Relationship plot
if ~isempty(meta.axGraph) && isvalid(meta.axGraph)
    cla(meta.axGraph); hold(meta.axGraph, 'on');

    mu_theoretical = linspace(0, 1.5, 100);
    plot(meta.axGraph, mu_theoretical, mu_theoretical.^2, 'r--', 'LineWidth', 1.5);
end

G = stats.G(:); S = stats.S(:);
x_phi = S ./ max(G, 1e-9);
M_val = sqrt(G.^2 + S.^2);
x_m = sqrt(max(M_val.^-2 - 1, 0));
mu_red = x_phi;
I2_red = 0.5 * (x_m.^2 + x_phi.^2);

% Decimate for plot performance
if ~isempty(meta.axGraph) && isvalid(meta.axGraph)
    if numel(mu_red) > 10000
        idx = randperm(numel(mu_red), 10000);
        plot(meta.axGraph, mu_red(idx), I2_red(idx), 'k.', 'MarkerSize', 2);
    else
        plot(meta.axGraph, mu_red, I2_red, 'k.', 'MarkerSize', 2);
    end
end

% System Locus (Mono-exp given IRF/Gates)
dt = config.dt; T = config.T; t_vec = 0:dt:T;
irf = DTexcitation(t_vec, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);
irf = irf / sum(irf);

omega = harmonic * (2*pi / T);
g_irf = sum(irf .* cos(omega * t_vec));
s_irf = sum(irf .* sin(omega * t_vec));
m_irf = sqrt(g_irf^2 + s_irf^2);
phi_irf = atan2(s_irf, g_irf);

tau_locus = logspace(log10(0.1), log10(50), 100);

% Generate Model Decays
gate_profiles = DTgates(t_vec, config.r, config.gate_edges);
gate_interp_fns = cell(config.N_gates, 1);
for i = 1:config.N_gates
    gate_interp_fns{i} = griddedInterpolant(t_vec, gate_profiles(i, :), 'linear', 'nearest');
end
meta.gate_interp_fns = gate_interp_fns;

P_locus_raw = DTpmod(config.N_gates, tau_locus, t_vec, gate_interp_fns, ...
    config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);

gate_centers = (config.gate_edges(1:end-1) + config.gate_edges(2:end)) / 2;
gc = cos(omega * gate_centers);
gs = sin(omega * gate_centers);

sumP = sum(P_locus_raw, 1); sumP(sumP==0) = 1;
G_raw = (gc * P_locus_raw) ./ sumP;
S_raw = (gs * P_locus_raw) ./ sumP;

m_raw = sqrt(G_raw.^2 + S_raw.^2);
phi_raw = atan2(S_raw, G_raw);

m_corr = m_raw ./ m_irf;
phi_corr = phi_raw - phi_irf;
G_sys = m_corr .* cos(phi_corr);
S_sys = m_corr .* sin(phi_corr);

G_safe = G_sys; G_safe(abs(G_sys) < 1e-9) = 1e-9;
x_phi = S_sys ./ G_safe;
M_val_sys = sqrt(G_sys.^2 + S_sys.^2);
x_m = sqrt(max(M_val_sys.^-2 - 1, 0));

mu_sys = x_phi;
I2_sys = 0.5 * (x_m.^2 + x_phi.^2);

if ~isempty(meta.axGraph) && isvalid(meta.axGraph)
    plot(meta.axGraph, mu_sys, I2_sys, 'b-', 'LineWidth', 2);
end

% Update meta with results
t.UserData = meta;

if ~isempty(meta.axGraph) && isvalid(meta.axGraph)
    plot(meta.axGraph, mu_sys, I2_sys, 'b--', 'LineWidth', 1.5);

    try
        legend(meta.axGraph, {'Universal Mono-exp', 'Pixels', 'System Mono-exp'}, 'Location', 'eastoutside');
    catch
    end
end

t.UserData = meta;
if isfield(meta, 'phasorZoomMode')
    try
        setPhasorZoom(fig, meta.phasorZoomMode);
    catch
    end
else
    setPhasorZoom(fig, 'Full');
end
end

function updateInstrumentPlot(fig, tau1Field, tau2Field)
% UPDATEINSTRUMENTPLOT - Refresh the instrument settings plot
axInstrument = findobj(fig, 'Tag', 'axInst');
if isempty(axInstrument), return; end

data = fig.UserData;
if ~isfield(data, 'config'), return; end
config = data.config;

% Time vector
if ~isfield(config, 'dt') || isempty(config.dt), config.dt = 0.05; end
if ~isfield(config, 'T') || isempty(config.T), config.T = 12.5; end
dt = config.dt;
t = 0:dt:config.T;

% Helper for DTexcitation access (local path should be set)
% Calculate IRF
irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);

% Shift IRF by toff
toff = 0;
if isfield(config, 'toff'), toff = config.toff; end

if toff ~= 0
    irf = interp1(t, irf, t - toff, 'linear', 0);
end

% Normalize
if max(irf) > 0, irf = irf / max(irf); end

% Setup Plot
% Clear and Reset to Single Axis
cla(axInstrument, 'reset');
axInstrument.Tag = 'axInst'; % Restore Tag
hold(axInstrument, 'on');
grid(axInstrument, 'on');
box(axInstrument, 'on');
xlabel(axInstrument, 'Time (ns)'); ylabel(axInstrument, 'Norm. Amp');
title(axInstrument, 'Instrument & Decays', 'FontWeight', 'bold');

% Plot IRF
plot(axInstrument, t, irf, 'r-', 'LineWidth', 2, 'DisplayName', 'IRF');

% Plot Decays if fields provided (Visualization of settings)
if nargin >= 3 && ~isempty(tau1Field) && ~isempty(tau2Field)
    try
        % Handle potentially empty or non-numeric values
        if isnumeric(tau1Field), v1=tau1Field; else, v1=tau1Field.Value; end
        if isnumeric(tau2Field), v2=tau2Field; else, v2=tau2Field.Value; end

        tau1 = v1 / 1000; % ps to ns
        tau2 = v2 / 1000;

        % Simple exponential decay for viz
        d1 = exp(-t/tau1); d1 = d1/max(d1);
        d2 = exp(-t/tau2); d2 = d2/max(d2);

        plot(axInstrument, t, d1, 'b--', 'LineWidth', 1, 'DisplayName', sprintf('\\tau_1=%.1gns', tau1));
        plot(axInstrument, t, d2, 'g:', 'LineWidth', 1.5, 'DisplayName', sprintf('\\tau_2=%.1gns', tau2));
    catch
    end
end

% Plot Gates (Smart Density)
edges = config.gate_edges;
ylim(axInstrument, [0 1.1]);
if numel(edges) > 32
    xRegion = [edges(1), edges(end), edges(end), edges(1)];
    yRegion = [0 0 1.1 1.1];
    patch(axInstrument, xRegion, yRegion, [0.5 0.5 0.5], 'FaceAlpha', 0.1, 'EdgeColor', 'none', 'DisplayName', 'Gates');
    if exist('xline', 'file')
        xline(axInstrument, edges(1), 'k-', 'HandleVisibility', 'off');
        xline(axInstrument, edges(end), 'k-', 'HandleVisibility', 'off');
    else
        plot(axInstrument, [edges(1) edges(1)], [0 1.1], 'k-', 'HandleVisibility', 'off');
        plot(axInstrument, [edges(end) edges(end)], [0 1.1], 'k-', 'HandleVisibility', 'off');
    end
else
    for i = 1:numel(edges)
        if exist('xline', 'file')
            xline(axInstrument, edges(i), 'k:', 'Color', [0.5 0.5 0.5], 'HandleVisibility', 'off');
        else
            plot(axInstrument, [edges(i) edges(i)], [0 1.1], 'k:', 'Color', [0.5 0.5 0.5], 'HandleVisibility', 'off');
        end
    end
end

legend(axInstrument, 'Location', 'northeast');
drawnow;
end

function updatePixelAnalysis(fig, point)
data = fig.UserData;
tabGroup = findobj(fig, 'Tag', 'analysisTabs');
if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
if isempty(tab.UserData) || ~isfield(tab.UserData, 'TauMap'), return; end
meta = tab.UserData;

px = round(point(1)); py = round(point(2));
% Use tab-local dimensions if available, else fallback to current data
chanIdx = 1;
if isfield(meta, 'activeChanIdx'), chanIdx = meta.activeChanIdx; end

cData = squeeze(data.RawData(:, :, :, chanIdx));
[nY, nX, ~] = size(cData);

if px < 1 || px > nX || py < 1 || py > nY, return; end

% Update Crosshair
hV = findobj(fig, 'Tag', 'crossV');
hH = findobj(fig, 'Tag', 'crossH');
if ~isempty(hV), set(hV, 'Value', px, 'Visible', 'on'); end
if ~isempty(hH), set(hH, 'Value', py, 'Visible', 'on'); end

% Extract Pixel Data (Note: RawData is now handled per channel)
pixelCounts = squeeze(cData(py, px, :));
estTau = meta.TauMap(py, px);
config = data.config;

% 1. Clean up axes immediately for visual feedback
axPixel = meta.axPix;
axPixelRes = meta.axPixRes;

% Reset axes
cla(axPixel, 'reset');
set(axPixel, 'Box', 'on', 'XTickLabel', []);
ylabel(axPixel, 'Counts', 'FontWeight', 'bold');
grid(axPixel, 'on');
hold(axPixel, 'on');

cla(axPixelRes, 'reset');
set(axPixelRes, 'Box', 'on');
ylabel(axPixelRes, 'Z-score', 'FontWeight', 'bold');
xlabel(axPixelRes, 'Time (ns)', 'FontWeight', 'bold');
grid(axPixelRes, 'on');
hold(axPixelRes, 'on');

drawnow; % Ensure old traces are definitively deleted

% 2. Time Vector and Gate Centers
t = 0:config.dt:config.T;
gate_edges = config.gate_edges;
gate_centers = 0.5 * (gate_edges(1:end-1) + gate_edges(2:end));

% 2. Calculate Fitted Model Gate Counts
% Need to match scaling of the original photon count
n_det = sum(pixelCounts);
P_pixel = DTpmod(config.N_gates, estTau, t, meta.gate_interp_fns, ...
    config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);
P_pixel = P_pixel ./ sum(P_pixel); % Normalize
fittedCounts = P_pixel * n_det;

% 3. Calculate Smooth Decay Curve for Visualization
[decay_smooth, ~] = DTpdf(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma, estTau);
decay_smooth = decay_smooth * (sum(fittedCounts) / sum(decay_smooth));

% IRF for background
irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);

% 4. Plot
title(axPixel, '(In-pixel fitting)');
% IRF (Normalized and scaled - Red Line)
plot(axPixel, t, (irf/max(irf)) * max(pixelCounts) * 0.5, 'r-', 'LineWidth', 1, 'DisplayName', 'IRF');

% Fitted Curve (Smooth - Solid Black Line)
plot(axPixel, t, decay_smooth, 'k-', 'LineWidth', 1.5, 'DisplayName', sprintf('Fit (%.2fns)', estTau));

% Discrete Fitted Gate Counts (Line connecting)
plot(axPixel, gate_centers(:), fittedCounts(:), 'k--', 'LineWidth', 0.5, 'HandleVisibility', 'off');

% Experimental Data (Blue Circles)
plot(axPixel, gate_centers(:), pixelCounts(:), 'bo', 'MarkerSize', 6, 'LineWidth', 1.5, 'DisplayName', 'Data');
hold(axPixel, 'off');
legend(axPixel, 'Location', 'northeast', 'FontSize', 8);
grid(axPixel, 'on');
set(axPixel, 'XTickLabel', []); % Remove time ticks here

% Update Pixel Info Labels
meta.uPixPos.Text = sprintf('Pos: %d, %d', px, py);
meta.uPixTau.Text = sprintf('%c: %.2f ns', 964, estTau);

% == Update Pixel Residuals Plot ==
% (axPixelRes already cleared at top)

% Standardized residuals for Poisson data: (Data - Model) / sqrt(Model)
z_pixel = (pixelCounts(:) - fittedCounts(:)) ./ sqrt(fittedCounts(:) + 1e-10);

% Plot against gate_centers for same horizontal scale as axPixel
stem(axPixelRes, gate_centers(:), z_pixel, 'Marker', 'o', 'MarkerSize', 4, 'LineWidth', 1.5, 'Color', [0.4 0.4 0.4]);
yline(axPixelRes, 0, 'k-');
yline(axPixelRes, [1.96, -1.96], 'r--'); % 95% confidence bounds

grid(axPixelRes, 'on');
xlim(axPixelRes, [min(t) max(t)]); % Synchronize X-axis with decay plot
xlabel(axPixelRes, 'Time (ns)', 'FontWeight', 'bold');
set(axPixelRes, 'XTickLabelMode', 'auto');

% == Update Pixel-Level Metrics ==
pix_chi2 = mean(z_pixel.^2);
meta.uPixChi.Text = sprintf('%c%c%c: %.3f', 967, 178, 7523, pix_chi2);
meta.uPixRE.Text = sprintf('R.E.: %.1f%%', (1/pix_chi2)*100);

% Runs test on the decay residuals for this pixel
s_pix = sign(z_pixel);
s_pix(s_pix==0) = 1;
r_pix = 1 + sum(diff(s_pix)~=0);
n1 = sum(s_pix>0); n2 = sum(s_pix<0);
if n1==0 || n2==0
    meta.uPixRND.Text = 'RND: NO (Bias)';
    meta.uPixRND.FontColor = [0.8 0 0];
else
    mu_r = 1 + (2*n1*n2)/(n1+n2);
    s_r = sqrt((2*n1*n2*(2*n1*n2-n1-n2))/((n1+n2)^2 * (n1+n2-1)));
    z_r = (r_pix - mu_r)/s_r;
    if z_r < -1.645
        meta.uPixRND.Text = sprintf('RND: NO (Z=%.1f)', z_r);
        meta.uPixRND.FontColor = [0.8 0 0];
    else
        meta.uPixRND.Text = sprintf('RND: YES (Z=%.1f)', z_r);
        meta.uPixRND.FontColor = [0 0.6 0];
    end
end
end

function setPhasorZoom(fig, mode)
tabGroup = findobj(fig, 'Tag', 'analysisTabs');
if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;

meta = tab.UserData;
% Defensively initialize if missing or not a struct
if isempty(meta) || ~isstruct(meta)
    meta = struct('phasorZoomMode', mode);
else
    meta.phasorZoomMode = mode;
end
tab.UserData = meta;

% Check if Phasor or LiMA
if isfield(meta, 'axPhasor') && isvalid(meta.axPhasor)
    refreshPhasorPlot(fig, meta.axPhasor);
elseif isfield(meta, 'axGraph') && isvalid(meta.axGraph)
    applyZoom(meta.axGraph, mode);
end
end

function applyZoom(ax, mode)
% Zoom and Layout Logic
all_children = ax.Children;
if strcmpi(mode, 'Data')
    minX = inf; maxX = -inf; minY = inf; maxY = -inf;
    for i = 1:numel(all_children)
        if matches(all_children(i).Type, 'line') && strcmp(all_children(i).Marker, '.')
            if isempty(all_children(i).XData), continue; end
            minX = min(minX, min(all_children(i).XData(:)));
            maxX = max(maxX, max(all_children(i).XData(:)));
            minY = min(minY, min(all_children(i).YData(:)));
            maxY = max(maxY, max(all_children(i).YData(:)));
        end
    end
    if isinf(minX), minX=0; maxX=1; minY=0; maxY=0.5; end
    padding = 0.10;
else
    % For Phasor and LiMA (Mu vs I2), 0-1 and 0-0.5 is standard
    % But LiMA Mu is 0-1, I2 is 0-1? No I2 is mu^2 so 0 - 1.
    % Phasor S is 0 - 0.5.
    % Let's use auto-range of all items (inc curves)
    minX = 0; maxX = 1; minY = 0; maxY = 0.5;
    for i = 1:numel(all_children)
        if isprop(all_children(i), 'XData') && ~isempty(all_children(i).XData)
            minX = min(minX, min(all_children(i).XData(:)));
            maxX = max(maxX, max(all_children(i).XData(:)));
            minY = min(minY, min(all_children(i).YData(:)));
            maxY = max(maxY, max(all_children(i).YData(:)));
        end
    end
    padding = 0.05;
end

w = maxX - minX; h = maxY - minY;
if w == 0, w = 1; end
if h == 0, h = 1; end
xlim(ax, [minX - padding*w, maxX + padding*w]);
ylim(ax, [minY - padding*h, maxY + padding*h]);

grid(ax, 'on');
% axis(ax, 'equal'); % LiMA mu vs I2 might not need equal aspect, but Phasor does.
% Let's check tag
if contains(ax.Tag, 'Phasor'), axis(ax, 'equal'); end
end

function updateHarmonic(fig, spinVal, cbVal)
tabGroup = findobj(fig, 'Tag', 'analysisTabs');
if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
if isempty(tab.UserData) || ~isfield(tab.UserData, 'axPhasor'), return; end
meta = tab.UserData;
if ~isempty(spinVal), meta.harmonic = spinVal; end
if ~isempty(cbVal), meta.plotAllHarmonics = cbVal; end
tab.UserData = meta;
refreshPhasorPlot(fig);
refreshXYProjection(fig);
end

function refreshPhasorPlot(fig, axIn)
data = fig.UserData;
if isempty(data.RawData), return; end

if nargin < 2 || isempty(axIn)
    tabGroup = findobj(fig, 'Tag', 'analysisTabs');
    if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
    tab = tabGroup.SelectedTab;
    if isempty(tab.UserData) || ~isfield(tab.UserData, 'axPhasor'), return; end
    meta = tab.UserData;
    axPhasor = meta.axPhasor;
else
    axPhasor = axIn;
    % If axIn is provided, we might be calling from createNewPhasorTab before meta is set
    % but createNewPhasorTab usually sets meta before calling.
    % Let's be safe and assume meta exists if axIn is from a tab.
    meta = [];
    if isprop(axPhasor, 'Parent') && isprop(axPhasor.Parent, 'UserData')
        meta = axPhasor.Parent.UserData;
    end
end

if isempty(meta)
    % Fallback to global or defaults if no meta found
    harmonic = 1; plotAllHarmonics = true; zoomMode = 'Full'; chanIdx = 1;
else
    harmonic = meta.harmonic;
    plotAllHarmonics = meta.plotAllHarmonics;
    zoomMode = meta.phasorZoomMode;
    chanIdx = 1;
    if isfield(meta, 'activeChanIdx'), chanIdx = meta.activeChanIdx; end
end

config = data.config;
cData = squeeze(data.RawData(:, :, :, chanIdx));

% Apply Mask
mask = getChannelMask(fig, chanIdx);
if ~isempty(mask)
    [nY, nX, nGates] = size(cData);
    mask3D = repmat(mask, 1, 1, nGates);
    cData(mask3D) = 0;
else
    [nY, nX, nGates] = size(cData);
end

[nY, nX, nGates] = size(cData);
M = nX * nY;
flatData = double(reshape(permute(cData, [3, 1, 2]), nGates, M));
sumIntensity = sum(flatData, 1);
sumIntensity(sumIntensity == 0) = 1e-10;

dt = config.dt; T = config.T; t = 0:dt:T;
gate_profiles = DTgates(t, config.r, config.gate_edges);
gate_interp_fns = cell(config.N_gates, 1);
for i = 1:config.N_gates
    gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
end
tau_locus = logspace(log10(0.05), log10(50), 100);

max_h = harmonic;
h_range = 1:max_h; if ~plotAllHarmonics, h_range = max_h; end

cla(axPhasor); hold(axPhasor, 'on');
gArc = linspace(0, 1, 100); sArc = sqrt(gArc .* (1 - gArc));
plot(axPhasor, gArc, sArc, 'k-', 'LineWidth', 1, 'HandleVisibility', 'off');

hColors = {[0 0 1], [0 0.7 0], [1 0 0]};
hPlots = gobjects(1, length(h_range));
names = cell(1, length(h_range));
counter = 1;

f_base = 1/config.T; if config.bPulseTrain && isfield(config, 'PT_Trep'), f_base = 1/config.PT_Trep; end
gate_centers = 0.5 * (config.gate_edges(1:end-1) + config.gate_edges(2:end));

for h = h_range
    f_h = h * f_base;
    cosT = cos(2 * pi * f_h * gate_centers(:)); sinT = sin(2 * pi * f_h * gate_centers(:));
    Gh = (cosT' * flatData) ./ sumIntensity; Sh = (sinT' * flatData) ./ sumIntensity;

    if h == max_h, meta.G_vals = Gh; meta.S_vals = Sh; end

    if M > 5000
        idx = round(linspace(1, M, 5000));
        hp = plot(axPhasor, Gh(idx), Sh(idx), '.', 'Color', hColors{h}, 'MarkerSize', 2);
    else
        hp = plot(axPhasor, Gh, Sh, '.', 'Color', hColors{h}, 'MarkerSize', 2);
    end
    hPlots(counter) = hp;
    names{counter} = sprintf('H%d', h);
    counter = counter + 1;

    P_locus = DTpmod(config.N_gates, tau_locus, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);
    sumP = sum(P_locus, 1); sumP(sumP == 0) = 1e-10;
    plot(axPhasor, (cosT' * P_locus)./sumP, (sinT' * P_locus)./sumP, '--', 'Color', [0.4 0.4 0.4]);
end

if ~isempty(meta)
    meta.G_vals = Gh; % Ensure tab has latest for overlay
    tabGroup = findobj(fig, 'Tag', 'analysisTabs');
    if ~isempty(tabGroup) && ~isempty(tabGroup.SelectedTab)
        tabGroup.SelectedTab.UserData = meta;
    end
end

% Zoom and Layout
all_children = axPhasor.Children;
if strcmpi(zoomMode, 'Data')
    minG = inf; maxG = -inf; minS = inf; maxS = -inf;
    for i = 1:numel(all_children)
        if matches(all_children(i).Type, 'line') && strcmp(all_children(i).Marker, '.')
            minG = min(minG, min(all_children(i).XData(:)));
            maxG = max(maxG, max(all_children(i).XData(:)));
            minS = min(minS, min(all_children(i).YData(:)));
            maxS = max(maxS, max(all_children(i).YData(:)));
        end
    end
    if isinf(minG), minG=0; maxG=1; minS=0; maxS=0.5; end
    padding = 0.10;
else
    minG = 0; maxG = 1; minS = 0; maxS = 0.5;
    for i = 1:numel(all_children)
        if isprop(all_children(i), 'XData') && ~isempty(all_children(i).XData)
            minG = min(minG, min(all_children(i).XData(:)));
            maxG = max(maxG, max(all_children(i).XData(:)));
            minS = min(minS, min(all_children(i).YData(:)));
            maxS = max(maxS, max(all_children(i).YData(:)));
        end
    end
    padding = 0.05;
end
gw = maxG - minG; sh = maxS - minS;
if gw == 0, gw = 1; end
if sh == 0, sh = 1; end
xlim(axPhasor, [minG - padding*gw, maxG + padding*gw]);
ylim(axPhasor, [minS - padding*sh, maxS + padding*sh]);

grid(axPhasor, 'on'); axis(axPhasor, 'equal');
legend(axPhasor, hPlots, names, 'Location', 'eastoutside');
end

function onClearTab(fig)
tabGroup = findobj(fig, 'Tag', 'analysisTabs');
if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
% Clean up any persistent ROIs (e.g. Fisher ROIs)
if ~isempty(tab.UserData) && isstruct(tab.UserData) && isfield(tab.UserData, 'refROIs')
    rois = tab.UserData.refROIs;
    for i = 1:numel(rois)
        if ~isempty(rois{i}) && isvalid(rois{i})
            delete(rois{i});
        end
    end
end

tab.UserData = [];
kids = tab.Children;
for i = numel(kids):-1:1
    if isa(kids(i), 'matlab.ui.control.Button'), continue; end
    delete(kids(i));
end
end

function createNewFisherTab(fig, t, activeChanIdx)

if isempty(t.UserData)
    meta = struct(); % Initialize meta
    meta.activeChanIdx = activeChanIdx;
    % === Layout Configuration ===
    leftCol = 40;
    mapSize = 350;
    fppSize = 450;

    mapY = 40;
    topY = mapY + mapSize + 80;

    % 1. Fisher Projective Plane (Top Left)
    axFPP = uiaxes(t, 'Position', [leftCol, topY, fppSize, fppSize]);
    axFPP.Tag = 'axFPP';
    title(axFPP, 'Fisher Projective Plane');
    xlabel(axFPP, 'Fisher Mixing Component (\alpha)');
    ylabel(axFPP, 'Fisher Orthogonal Residual (\delta)');
    grid(axFPP, 'on'); box(axFPP, 'on');

    % 2. Controls Panel (Top Right)
    ctrlX = leftCol + fppSize + 40;
    ctrlW = 320;
    ctrlH = 300;
    ctrlY = (topY + fppSize) - ctrlH;

    ctrlPanel = uipanel(t, 'Title', 'Fisher Analysis Controls', ...
        'Position', [ctrlX, ctrlY, ctrlW, ctrlH], ...
        'FontSize', 12, 'FontWeight', 'bold', 'Tag', 'pnlFisherCtrl');

    % -- Panel Contents --
    cY = ctrlH - 60;
    uilabel(ctrlPanel, 'Text', '1. Define References', 'FontWeight', 'bold', 'Position', [15, cY, 200, 22]);

    cY = cY - 35;
    uibutton(ctrlPanel, 'Text', 'Set Ref 1 (Red)', 'FontColor', [0.8 0 0], 'Position', [15, cY, 125, 30], ...
        'Tag', 'btnRef1', 'ButtonPushedFcn', @(btn, event) addFisherROI(fig, 1));

    uibutton(ctrlPanel, 'Text', 'Set Ref 2 (Blue)', 'FontColor', [0 0 0.8], 'Position', [150, cY, 125, 30], ...
        'Tag', 'btnRef2', 'ButtonPushedFcn', @(btn, event) addFisherROI(fig, 2));

    cY = cY - 50;
    uilabel(ctrlPanel, 'Text', '2. Run Analysis', 'FontWeight', 'bold', 'Position', [15, cY, 200, 22]);

    cY = cY - 25;
    % Checkbox Anscombe
    chkAns = uicheckbox(ctrlPanel, 'Text', 'Anscombe Transform', ...
        'Position', [15, cY, 200, 22], ...
        'Tooltip', 'Apply 2*sqrt(x + 3/8) to stabilize variance before fitting.', ...
        'Tag', 'chkAnscombe');

    cY = cY - 45;
    uibutton(ctrlPanel, 'Text', 'Calculate Transforms', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.2 0.2 0.2], 'FontColor', [1 1 1], ...
        'Position', [15, cY, 260, 40], ...
        'ButtonPushedFcn', @(btn, event) runFisherAnalysis(fig));

    % 3. Maps (Bottom Row)
    axAlpha = uiaxes(t, 'Position', [leftCol, mapY, mapSize, mapSize]);
    title(axAlpha, 'Mixing Map (\alpha)');
    axis(axAlpha, 'image'); colorbar(axAlpha);
    axAlpha.Tag = 'axAlpha';

    axDelta = uiaxes(t, 'Position', [leftCol + mapSize + 60, mapY, mapSize, mapSize]);
    title(axDelta, 'Residual Map (\delta)');
    axis(axDelta, 'image'); colorbar(axDelta);
    axDelta.Tag = 'axDelta';

    % Store handles in UserData
    meta.axFPP = axFPP;
    meta.axAlpha = axAlpha;
    meta.axDelta = axDelta;
    meta.ref1 = [];
    meta.ref2 = [];
    meta.refROIs = {[], []}; % Store handles
    meta.chkAnscombe = chkAns;
    t.UserData = meta;
end
end

function addFisherROI(fig, refIdx)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;
meta = t.UserData;
data = fig.UserData;

% Find the active channel tab's XY axis
chanIdx = meta.activeChanIdx;
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
chanTab = dataTabGroup.Children(chanIdx);
axXY = findobj(chanTab, 'Tag', sprintf('axXY_Ch%d', chanIdx));

if isempty(axXY), return; end

% Disable control buttons to avoid concurrent ROI creation
pnl = findobj(t, 'Tag', 'pnlFisherCtrl');
btns = findall(pnl, 'Type', 'uibutton');
if ~isempty(btns), set(btns, 'Enable', 'off'); end

% Prepare Colors
if refIdx == 1
    col = [1 0 0];
    tagName = 'btnRef1';
else
    col = [0 0 1];
    tagName = 'btnRef2';
end

% Clean old ROI handle if valid
if isfield(meta, 'refROIs') && numel(meta.refROIs) >= refIdx
    oldROI = meta.refROIs{refIdx};
    if ~isempty(oldROI) && isvalid(oldROI)
        delete(oldROI);
    end
else
    meta.refROIs = {[], []};
end

try
    % Create new ROI
    hROI = drawpolygon(axXY, 'Color', col, 'LineWidth', 2, 'Label', sprintf('Ref %d', refIdx));

    % Wait for user to finish
    wait(hROI);
    if ~isempty(btns), set(btns, 'Enable', 'on'); end

    if ~isvalid(hROI)
        % User deleted it?
        return;
    end

    % Refresh meta to get latest state (might have changed during wait)
    meta = t.UserData;

    % Extract Mask
    mask = hROI.createMask();
    if ~any(mask(:))
        uialert(fig, 'Selected ROI describes no pixels.', 'Warning');
        delete(hROI);
        return;
    end

    % Compute Decay
    [~, ~, nGates] = size(data.RawData);
    flatData = reshape(permute(data.RawData, [3, 1, 2]), nGates, []);

    decay = sum(flatData(:, mask(:)), 2);
    decaySum = sum(decay);
    if decaySum == 0
        uialert(fig, 'Selected region has 0 photons.', 'Warning');
        delete(hROI);
        return;
    end

    decay = decay / decaySum;

    % Persist Data
    if refIdx == 1
        meta.ref1 = decay;
        lbl = 'Ref 1 Set (Ready)';
    else
        meta.ref2 = decay;
        lbl = 'Ref 2 Set (Ready)';
    end

    meta.refROIs{refIdx} = hROI;
    t.UserData = meta; % Save to Tab

    % Update UI
    pnl = findobj(t, 'Tag', 'pnlFisherCtrl');
    btn = findobj(pnl, 'Tag', tagName);
    if ~isempty(btn)
        btn.Text = lbl;
        btn.FontWeight = 'bold';
    end

catch ME
    uialert(fig, ['Error setting ROI: ' ME.message], 'Error');
    if exist('hROI','var') && isvalid(hROI), delete(hROI); end
end
end

function runFisherAnalysis(fig)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;
meta = t.UserData;
data = fig.UserData;

% Defensive check
if isempty(meta) || ~isfield(meta, 'ref1') || ~isfield(meta, 'ref2')
    uialert(fig, 'Fisher analysis state is invalid. Please reset.', 'Error');
    return;
end

if isempty(meta.ref1) || isempty(meta.ref2)
    uialert(fig, 'Please set both Reference 1 and Reference 2 ROIs.', 'Error');
    return;
end

try
    P1 = meta.ref1(:);
    P2 = meta.ref2(:);

    activeChanIdx = meta.activeChanIdx;
    RawData = squeeze(data.RawData(:, :, :, activeChanIdx));

    % Apply Mask
    mask = getChannelMask(fig, activeChanIdx);
    if ~isempty(mask)
        % mask is logical 1 for Background.
        % We set RawData to 0 where mask is 1.
        % RawData is [Y, X, T]. Mask is [Y, X].
        % Expand mask to 3D
        [nY, nX, nGates] = size(RawData);
        mask3D = repmat(mask, 1, 1, nGates);
        RawData(mask3D) = 0;
    else
        [nY, nX, nGates] = size(RawData);
    end

    % Check Anscombe
    if isfield(meta, 'chkAnscombe') && isvalid(meta.chkAnscombe) && meta.chkAnscombe.Value
        RawData = 2 * sqrt(RawData + 3/8);
    end

    flatData = reshape(permute(RawData, [3, 1, 2]), nGates, []);

    % 1. Fisher Mixing Component (FMC)
    A = [(P1 - P2)'; P2'];
    % Weighting D (Inverse Variance ~ 1/Counts)
    % Approximate variance by mean expected counts of a mix
    p_ref = 0.5 * P1 + 0.5 * P2;
    D_inv = diag(1 ./ (p_ref + 1e-9));

    % Solve Generalized Least Squares
    % beta = (A D^-1 A')^-1 (A D^-1 y)  <-- Standard?
    % Target: Minimize (y - Ax)'D(y - Ax) subject to ...
    % Here we follow the logic: Project into Fisher Discriminant Direction

    % FMC vector f_FMC is the direction that maximizes separation relative to variance
    % For 2-component: f ~ D^-1 (P1 - P2)

    % Let's use the efficient projection implementation
    % f = D_inv * (P1 - P2);
    % But we want normalized outputs. The previous implementation used a constrained solve
    % Let's stick to the previous linear algebra which seemed intended for this:

    b = [1; 0];
    M_mat = A * D_inv * A';
    beta = M_mat \ b;
    f_FMC = D_inv * A' * beta;

    Alpha_est = f_FMC' * flatData;

    % 2. Fisher Orthogonal Residual (FOR)
    % Project out Model Space
    [U_S, ~] = qr([P1, P2], 0);
    Proj_S = U_S * U_S';
    Residuals = flatData - Proj_S * flatData;

    % PCA on Residuals
    [u_res, ~, ~] = svds(Residuals, 1);

    % Align sign for consistency (arbitrary but stable)
    if sum(u_res) < 0, u_res = -u_res; end

    f_FOR = u_res;
    Delta_est = f_FOR' * flatData;

    % 3. Visualization

    % Scatter Plot (Downsampled)
    if numel(Alpha_est) > 5000
        idx = randperm(numel(Alpha_est), 5000);
        a_plt = Alpha_est(idx);
        d_plt = Delta_est(idx);
    else
        a_plt = Alpha_est;
        d_plt = Delta_est;
    end

    plot(meta.axFPP, a_plt, d_plt, '.', 'MarkerSize', 4, 'Color', [0.3 0.3 0.3]);
    title(meta.axFPP, 'Fisher Projective Plane');
    xlabel(meta.axFPP, 'FMC (\alpha)'); ylabel(meta.axFPP, 'FOR (\delta)');
    grid(meta.axFPP, 'on'); box(meta.axFPP, 'on');

    % Overlay Reference Points on Scatter
    hold(meta.axFPP, 'on');
    % Ref 1 is theoretically Alpha=1, Delta=0
    plot(meta.axFPP, 1, 0, 'ro', 'MarkerSize', 10, 'LineWidth', 2, 'DisplayName', 'Ref 1');
    % Ref 2 is theoretically Alpha=0, Delta=0
    plot(meta.axFPP, 0, 0, 'bo', 'MarkerSize', 10, 'LineWidth', 2, 'DisplayName', 'Ref 2');
    hold(meta.axFPP, 'off');

    % Maps
    imagesc(meta.axAlpha, reshape(Alpha_est, nY, nX));
    title(meta.axAlpha, 'Mixing Map (\alpha)'); axis(meta.axAlpha, 'image'); colorbar(meta.axAlpha);
    colormap(meta.axAlpha, 'parula');

    imagesc(meta.axDelta, reshape(Delta_est, nY, nX));
    title(meta.axDelta, 'Residual Map (\delta)'); axis(meta.axDelta, 'image'); colorbar(meta.axDelta);
    colormap(meta.axDelta, 'jet');

    meta.AlphaMap = reshape(Alpha_est, nY, nX);
    meta.DeltaMap = reshape(Delta_est, nY, nX);
    t.UserData = meta;

catch ME
    uialert(fig, ['Analysis Failed: ' ME.message], 'Error');
end
end

function toggleAppMode(fig, mode)
lbl = findobj(fig, 'Tag', 'lblAppStatus');
if ~isempty(lbl), lbl.Text = mode; end

pConfig = findobj(fig, 'Tag', 'pnlConfig');
pAnalyzer = findobj(fig, 'Tag', 'pnlAnalyzer');

if isempty(pConfig) || isempty(pAnalyzer)
    % Debug fallback if handles missing
    fprintf('Error: config or analyzer panel not found for toggle.\n');
    return;
end

if strcmpi(mode, 'Simulator')
    pConfig.Visible = 'on';
    pAnalyzer.Visible = 'off';
else
    pConfig.Visible = 'off';
    pAnalyzer.Visible = 'on';
end
end

function toggleExpertMode(fig, mode)
lbl = findobj(fig, 'Tag', 'lblExpertStatus');
if ~isempty(lbl), lbl.Text = mode; end

% Logic for Expert Mode can be expanded here
if strcmpi(mode, 'Expert')
    lbl.FontColor = [0.8 0 0]; % Red for Expert
else
    lbl.FontColor = [0.5 0.5 0.5]; % Gray for Basic
end
end

function onFileDropped(fig, event)
% Capture the path of the dropped file
files = event.Files;
if isempty(files), return; end
filePath = files{1}; % Take the first file
processImportedFile(fig, filePath);
end

function onLoadFile(fig)
[file, path] = uigetfile({'*.sdt', 'Becker & Hickl SDT Files (*.sdt)'}, 'Select SDT File');
if isequal(file, 0)
    return;
end
processImportedFile(fig, fullfile(path, file));
end

function processImportedFile(fig, filePath)
[~, ~, ext] = fileparts(filePath);
if ~strcmpi(ext, '.sdt')
    uialert(fig, 'Only .sdt files are supported currently.', 'Unsupported Format');
    return;
end

try
    % Visual feedback
    [~, name, ext] = fileparts(filePath);
    fprintf('Processing file: %s%s\n', name, ext);

    waitMsg = uiprogressdlg(fig, 'Title', 'Importing SDT...', 'Message', 'Opening file...');

    % read_SDT is a helper function to be implemented
    [data, config] = read_SDT(filePath);

    % Check if data is empty (Dimension Hunter failed)
    if isempty(data) || sum(data(:)) == 0
        % Try to extract debug log from warnings or use generic message
        uialert(fig, sprintf('Import failed. No valid dimensions found.\nCheck command window for debug details.'), 'Import Failed', 'Icon', 'error');
        return;
    end

    % Update figure UserData
    userData = fig.UserData;
    userData.RawData = data;
    userData.config = config;
    userData.runCount = userData.runCount + 1;
    fig.UserData = userData;

    % Update all visual components
    if exist('waitMsg', 'var') && isvalid(waitMsg)
        waitMsg.Value = 1;
        waitMsg.Message = 'Finalizing plots...';
    end

    refreshAllPlots(fig);
    if exist('waitMsg', 'var') && isvalid(waitMsg), close(waitMsg); end

    msg = sprintf('SDT loaded successfully.\nChannels Found: %d\nSelected Dims: %dx%dx%d\nMax Proj Count: %g', ...
        size(userData.RawData, 4), size(userData.RawData, 1), size(userData.RawData, 2), size(userData.RawData, 3), max(sum(userData.RawData(:,:,:,1), 3), [], 'all'));
    uialert(fig, msg, 'Import Success', 'Icon', 'success');
catch ME
    if exist('waitMsg', 'var') && isvalid(waitMsg), close(waitMsg); end
    uialert(fig, ['Failed to load SDT: ' ME.message], 'Import Error', 'Icon', 'error');
end
end

function setupDataTabs(fig, nC)
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
% Clear existing tabs
delete(dataTabGroup.Children);

userData = fig.UserData;
% UserData should contain layout constants
dataStruct.plotH = userData.plotH;
dataStruct.xtH = userData.xtH;
dataStruct.ytW = userData.ytW;
dataStruct.col2X = userData.col2X;
dataStruct.xyY = userData.xyY;
dataStruct.xtY = userData.xtY;
dataStruct.histY = userData.histY;
dataStruct.threshY = userData.threshY; % New row below histogram
dataStruct.ctrlY = userData.ctrlY;
dataStruct.histH = userData.histH;
dataStruct.ctrlH = userData.ctrlH;
dataStruct.ytX = userData.ytX;

for c = 1:nC
    createDataTab(dataTabGroup, c, dataStruct);
end
end

function createDataTab(tabGroup, chanIdx, dataStruct)
tab = uitab(tabGroup, 'Title', sprintf('Channel %d', chanIdx));

% Pack everything into the tab relative to it
% We use uiaxes inside the tab. The Position is relative to the Tab container.
% However, the Tab container is the size of the TabGroup.

plotH = dataStruct.plotH;
xtH = dataStruct.xtH;
ytW = dataStruct.ytW;

% XY Projection (Top)
axXY = uiaxes(tab, 'Position', [10, dataStruct.xyY - (tabGroup.Position(2)), plotH, plotH]);
axXY.Tag = sprintf('axXY_Ch%d', chanIdx);
title(axXY, sprintf('XY Channel %d', chanIdx));
set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');

% XT Projection (Middle)
axXT = uiaxes(tab, 'Position', [10, dataStruct.xtY - (tabGroup.Position(2)), plotH, xtH]);
axXT.Tag = sprintf('axXT_Ch%d', chanIdx);
set(axXT, 'XTick', [], 'YTick', [], 'Box', 'on');

% YT Projection (Right)
axYT = uiaxes(tab, 'Position', [10 + plotH + 15, dataStruct.xyY - (tabGroup.Position(2)), ytW, plotH]);
axYT.Tag = sprintf('axYT_Ch%d', chanIdx);
set(axYT, 'XTick', [], 'YTick', [], 'Box', 'on');

% === Histogram ===
histY_local = dataStruct.histY - (tabGroup.Position(2));
histW = plotH * 0.75; % Reduce width to make room for contrast on right
axHist = uiaxes(tab, 'Position', [10, histY_local, histW, dataStruct.histH]);
axHist.Tag = sprintf('axHist_Ch%d', chanIdx);
axHist.BackgroundColor = 'w';
axHist.XColor = 'k'; axHist.YColor = 'k';
% Set click-to-toggle labels
ylabel(axHist, 'Count'); xlabel(axHist, 'Photons');
axHist.YLabel.ButtonDownFcn = @toggleHistYScale;
axHist.XLabel.ButtonDownFcn = @toggleHistXScale;
set(axHist, 'Box', 'on');

disableDefaultInteractivity(axHist);
hold(axHist, 'on');
pThresh = patch(axHist, [0 0 0 0], [0 0 1 1], 'r', ...
    'FaceAlpha', 0.2, 'EdgeColor', 'none', 'Tag', 'pThresh');
uistack(pThresh, 'bottom');

% === Contrast Controls (Right of Histogram) ===
ctrlX = 10 + histW + 10;
ctrlY_local = histY_local + dataStruct.histH - 22; % Start from top

uilabel(tab, 'Text', 'Contrast:', 'FontWeight', 'bold', 'Position', [ctrlX, ctrlY_local, 60, 22]);

% Min
uilabel(tab, 'Text', 'Min', 'Position', [ctrlX, ctrlY_local - 25, 30, 22]);
uispinner(tab, 'Limits', [0 1e6], 'Value', 0, 'Position', [ctrlX + 35, ctrlY_local - 25, 65, 22], ...
    'Tag', sprintf('spnMin_Ch%d', chanIdx), ...
    'ValueChangedFcn', @(src, ev) onContrastControlChange(tab, chanIdx, 'spnMin', src.Value));

% Max
uilabel(tab, 'Text', 'Max', 'Position', [ctrlX, ctrlY_local - 50, 30, 22]);
uispinner(tab, 'Limits', [0 1e6], 'Value', 1000, 'Position', [ctrlX + 35, ctrlY_local - 50, 65, 22], ...
    'Tag', sprintf('spnMax_Ch%d', chanIdx), ...
    'ValueChangedFcn', @(src, ev) onContrastControlChange(tab, chanIdx, 'spnMax', src.Value));

% === Threshold Controls (Below Histogram) ===
threshY_local = histY_local - 30;

uilabel(tab, 'Text', 'Threshold', 'Position', [10, threshY_local + 5, 55, 22]);
uispinner(tab, 'Limits', [0 1e6], 'Value', 10, 'Position', [70, threshY_local + 5, 60, 22], ...
    'Tag', sprintf('spnThresh_Ch%d', chanIdx), ...
    'ValueChangedFcn', @(src, ev) onContrastControlChange(tab, chanIdx, 'spnThresh', src.Value));

uibutton(tab, 'Text', 'Set', 'Position', [140, threshY_local + 5, 40, 22], ...
    'Tag', sprintf('btnThreshSet_Ch%d', chanIdx), ...
    'ButtonPushedFcn', @(btn, ev) onThresholdAction(tab, chanIdx, 'Set'));

uibutton(tab, 'Text', 'Auto', 'Position', [185, threshY_local + 5, 40, 22], ...
    'Tag', sprintf('btnThreshAuto_Ch%d', chanIdx), ...
    'ButtonPushedFcn', @(btn, ev) onThresholdAction(tab, chanIdx, 'Auto'));

uibutton(tab, 'Text', 'Reset', 'Position', [230, threshY_local + 5, 45, 22], ...
    'Tag', sprintf('btnThreshReset_Ch%d', chanIdx), ...
    'ButtonPushedFcn', @(btn, ev) onThresholdAction(tab, chanIdx, 'Reset'));

% Edit Mask Button (Disabled - See FUTURE_TASKS.md)
uibutton(tab, 'Text', 'Edit Mask', 'Position', [285, threshY_local + 5, 70, 22], ...
    'Enable', 'off', ...
    'Tag', sprintf('btnEditMask_Ch%d', chanIdx), ...
    'Tooltip', 'Manually edit mask (Coming Soon)');

% Store ROI handles in tab? (Not strictly necessary if we use findobj)

% Store ROI handles in tab? (Not strictly necessary if we use findobj)
tab.UserData = struct();
end

function onContrastControlChange(tab, chanIdx, source, ~)
spnMin = findobj(tab, 'Tag', sprintf('spnMin_Ch%d', chanIdx));
spnMax = findobj(tab, 'Tag', sprintf('spnMax_Ch%d', chanIdx));
axXY = findobj(tab, 'Tag', sprintf('axXY_Ch%d', chanIdx));

if ~isempty(axXY)
    vMin_v = spnMin.Value; vMax_v = spnMax.Value;
    % Ensure valid range silently
    if vMin_v >= vMax_v
        vMax_v = vMin_v + 1;
        spnMax.Value = vMax_v;
    end
    set(axXY, 'CLim', [vMin_v vMax_v]);
end

% If triggered by spinner, update lines
if strcmp(source, 'spnMin') || strcmp(source, 'spnMax') || strcmp(source, 'spnThresh')
    axHist = findobj(tab, 'Tag', sprintf('axHist_Ch%d', chanIdx));
    % Find images.roi.Line types
    rois = findobj(axHist, '-property', 'Label');
    for i = 1:numel(rois)
        if strcmp(rois(i).Label, 'Min')
            rois(i).Position = [spnMin.Value 0.1; spnMin.Value 1e9];
        elseif strcmp(rois(i).Label, 'Max')
            rois(i).Position = [spnMax.Value 0.1; spnMax.Value 1e9];
        elseif strcmp(rois(i).Label, 'Thresh')
            spnTh = findobj(tab, 'Tag', sprintf('spnThresh_Ch%d', chanIdx));
            tv = spnTh.Value;
            rois(i).Position = [tv 0.1; tv 1e9];

            % Clear CustomMask if threshold changed manually
            if isfield(tab.UserData, 'CustomMask')
                tab.UserData = rmfield(tab.UserData, 'CustomMask');
            end

            % Update Histogram Red Patch
            pThresh = findobj(axHist, 'Tag', 'pThresh');
            if ~isempty(pThresh)
                yl = ylim(axHist);
                pThresh.XData = [0 tv tv 0];
                pThresh.YData = [yl(1) yl(1) yl(2) yl(2)];
            end

            % Update XY Projection Red Mask
            axXY = findobj(tab, 'Tag', sprintf('axXY_Ch%d', chanIdx));
            if ~isempty(axXY)
                hMask = findobj(axXY, 'Tag', 'BackgroundMask');
                if ~isempty(hMask)
                    % Need image data to compute mask.
                    % Find the main image (not the mask itself)
                    imgs = findobj(axXY, 'Type', 'image');
                    % The mask has Tag='BackgroundMask', the main data doesn't (or diff tag)
                    dImg = [];
                    for k=1:numel(imgs)
                        if ~strcmp(imgs(k).Tag, 'BackgroundMask')
                            dImg = imgs(k); break;
                        end
                    end

                    if ~isempty(dImg)
                        % Update Alpha based on new threshold
                        hMask.AlphaData = double(dImg.CData <= tv);
                    end
                end
            end
        end
    end
end
end

function onContrastLineMoving(tab, chanIdx, type, roi)
% Direct Tab handle passed - no lookup needed
if isempty(tab) || ~isvalid(tab), return; end

val = round(roi.Position(1,1));

% Update the numeric spinner Value property
spn = findobj(tab, 'Tag', sprintf('spn%s_Ch%d', type, chanIdx));
if ~isempty(spn)
    v = max(val, spn.Limits(1));
    v = min(v, spn.Limits(2));
    spn.Value = v;
    % Crucial: force the UI to repaint the spinner text during the move
    drawnow limitrate;
end

% Also live-update the Main XY Projection if we are moving contrast lines
if strcmp(type, 'Min') || strcmp(type, 'Max')
    axXY = findobj(tab, 'Tag', sprintf('axXY_Ch%d', chanIdx));
    if ~isempty(axXY)
        spnMin = findobj(tab, 'Tag', sprintf('spnMin_Ch%d', chanIdx));
        spnMax = findobj(tab, 'Tag', sprintf('spnMax_Ch%d', chanIdx));
        if ~isempty(spnMin) && ~isempty(spnMax)
            vMin = spnMin.Value; vMax = spnMax.Value;
            % Basic overlapping safety check (push logic)
            if vMin >= vMax
                if strcmp(type, 'Min')
                    vMin = max(0, vMax - 1);
                    spnMin.Value = vMin;
                else
                    vMax = vMin + 1;
                    spnMax.Value = vMax;
                end
            end
            set(axXY, 'CLim', [vMin vMax]);
        end
    end
end
end

function onThresholdAction(tab, chanIdx, action)
try
    % Helper to handle Set, Auto, Reset for threshold
    spnTh = findobj(tab, 'Tag', sprintf('spnThresh_Ch%d', chanIdx));
    if isempty(spnTh), return; end

    switch action
        case 'Set'
            % Store threshold in persistent UserData for analysis usage
            fig = ancestor(tab, 'figure');
            if ~isfield(fig.UserData, 'Thresholds')
                data = fig.UserData;
                data.Thresholds = containers.Map('KeyType', 'double', 'ValueType', 'double');
                fig.UserData = data;
            end
            fig.UserData.Thresholds(chanIdx) = spnTh.Value;

            % If user explicitly sets threshold, do we clear custom mask? Usually yes.
            % However, 'Set' here implies "Saving Value" rather than "Changing Value".
            % But 'Auto' and 'Reset' definitely change the mask state.

            fprintf('Channel %d Threshold stored: %.2f\n', chanIdx, spnTh.Value);

        case 'Auto'
            % Clear Custom Override
            if isfield(tab.UserData, 'CustomMask')
                tab.UserData = rmfield(tab.UserData, 'CustomMask');
            end

            % Robust auto-threshold: Triangle Method (Zack algorithm)
            axXY = findobj(tab, 'Tag', sprintf('axXY_Ch%d', chanIdx));
            if ~isempty(axXY) && ~isempty(axXY.Children)
                img = findobj(axXY.Children, 'Type', 'image');
                if ~isempty(img)
                    data = double(img.CData);
                    validData = data(~isnan(data));

                    if isempty(validData)
                        spnTh.Value = 0;
                    else
                        % 1. Compute Histogram
                        nbins = 256;
                        [counts, edges] = histcounts(validData, nbins);
                        centers = edges(1:end-1) + diff(edges)/2;

                        % 2. Find Peak (Background Mode) and Extreme (Max Signal)
                        [maxCount, idxPeak] = max(counts);
                        idxLast = find(counts > 0, 1, 'last');

                        tAuto = 0;
                        if idxPeak < idxLast
                            % 3. Triangle Geometry
                            x1 = idxPeak; y1 = maxCount;
                            x2 = idxLast; y2 = counts(idxLast);

                            xVec = x1:x2; yVec = counts(x1:x2);
                            A = y2 - y1; B = -(x2 - x1); C = x2*y1 - y2*x1;

                            dists = abs(A.*xVec + B.*yVec + C) ./ sqrt(A^2 + B^2);
                            [~, idxSplit] = max(dists);

                            % Safety check for empty distance max
                            if isempty(idxSplit), idxSplit = 1; end

                            splitBinIndex = xVec(idxSplit);
                            tAuto = centers(splitBinIndex);
                        else
                            tAuto = centers(idxPeak);
                        end

                        valAuto = round(tAuto);
                        if isnan(valAuto) || isinf(valAuto), valAuto = 0; end

                        % Temporarily expand limits to avoid beep if auto value > current limit
                        spnTh.Limits = [0 max(spnTh.Limits(2), valAuto + 1000)];
                        spnTh.Value = valAuto;
                        fprintf('Auto-Threshold (Triangle) calc: %d\n', valAuto);
                    end
                end
            end

        case 'Reset'
            % Clear Custom Override
            if isfield(tab.UserData, 'CustomMask')
                tab.UserData = rmfield(tab.UserData, 'CustomMask');
            end
            spnTh.Value = 0;
    end

    % Synchronize line on histogram
    onContrastControlChange(tab, chanIdx, 'spnThresh', spnTh.Value);

catch ME
    fprintf(2, 'Error in onThresholdAction: %s\n', ME.message);
    disp(ME.stack);
end
end

function toggleHistYScale(src, ~)
% Toggle Y-axis Log/Lin
try
    ax = ancestor(src, 'axes');
    if isempty(ax), return; end

    if strcmp(ax.YScale, 'linear')
        ax.YScale = 'log';
        src.String = 'Count (Log)';
    else
        ax.YScale = 'linear';
        src.String = 'Count';
    end
catch
end
end

function toggleHistXScale(src, ~)
% Toggle X-axis Log/Lin
try
    ax = ancestor(src, 'axes');
    if isempty(ax), return; end

    if strcmp(ax.XScale, 'linear')
        ax.XScale = 'log';
        src.String = 'Photons (Log)';
    else
        ax.XScale = 'linear';
        src.String = 'Photons';
    end
catch
end
end



function onEditMask(fig, chanIdx)
% 1. Get Data
fprintf('onEditMask triggered for channel %d\n', chanIdx);
data = fig.UserData;
if isempty(data.RawData)
    fprintf('RawData is empty, returning.\n');
    return;
end

% Access correct channel
[~, ~, ~, nC] = size(data.RawData);
if chanIdx > nC, return; end

cData = squeeze(data.RawData(:, :, :, chanIdx));
projXY = sum(cData, 3);

% 2. Get Current Mask (Same logic as refreshAllPlots)
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
if isempty(dataTabGroup), return; end
thisTab = dataTabGroup.Children(chanIdx);
meta = thisTab.UserData;

if isfield(meta, 'CustomMask') && ~isempty(meta.CustomMask)
    currentMask = meta.CustomMask;
else
    % Calc from threshold
    spnThresh = findobj(thisTab, 'Tag', sprintf('spnThresh_Ch%d', chanIdx));
    tVal = spnThresh.Value;
    currentMask = (projXY <= tVal); % Background Mask
end

% 3. Call Editor
try
    if exist('MaskEditor', 'file')==2
        [newMask, cancelled] = MaskEditor(projXY, currentMask);

        if ~cancelled
            % 4. Save
            meta.CustomMask = newMask;
            thisTab.UserData = meta;

            % 5. Update Display
            refreshXYProjection(fig);
            refreshAllPlots(fig);
        end
    else
        uialert(fig, 'MaskEditor.m not found. Please ensure it is in the path.', 'Missing File');
    end
catch ME
    uialert(fig, ['MaskEditor Error: ' ME.message], 'Error');
end
end

function mask = getChannelMask(fig, chanIdx)
% Helper to retrieve the current mask (Custom or Threshold)
% Returns logical matrix where 1 = Background (masked out), 0 = Signal (valid)
mask = [];
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
if isempty(dataTabGroup), return; end
if chanIdx > numel(dataTabGroup.Children), return; end

thisTab = dataTabGroup.Children(chanIdx);
meta = thisTab.UserData;

if isfield(meta, 'CustomMask') && ~isempty(meta.CustomMask)
    mask = logical(meta.CustomMask);
else
    % Threshold calculation
    spnThresh = findobj(thisTab, 'Tag', sprintf('spnThresh_Ch%d', chanIdx));
    if ~isempty(spnThresh)
        val = spnThresh.Value;
        guiData = fig.UserData;
        if ~isempty(guiData.RawData)
            cData = squeeze(guiData.RawData(:, :, :, chanIdx));
            projXY = sum(cData, 3);
            mask = (projXY <= val);
        else
            mask = [];
        end
    else
        mask = [];
    end
end
end


function toggleHILIGHTerModality(dropdown, lifetimeGroup, fretGroup)
if strcmp(dropdown.Value, 'FRET')
    set(lifetimeGroup, 'Visible', 'off');
    set(fretGroup, 'Visible', 'on');
else
    set(lifetimeGroup, 'Visible', 'on');
    set(fretGroup, 'Visible', 'off');
end
end

function updateCLimFit(tab, type, val)
meta = tab.UserData;
if ~isfield(meta, 'axTau') || isempty(meta.axTau), return; end

currentLim = meta.axTau.CLim;
if strcmp(type, 'Min')
    % Ensure Min < Max
    if val >= currentLim(2)
        val = currentLim(2) - 0.001;
        meta.spnCMin.Value = val;
        return; % Stop recursion or redundant updates
    end
    meta.axTau.CLim = [val, currentLim(2)];
else
    % Ensure Max > Min
    if val <= currentLim(1)
        val = currentLim(1) + 0.001;
        meta.spnCMax.Value = val;
        return;
    end
    meta.axTau.CLim = [currentLim(1), val];
end
end
