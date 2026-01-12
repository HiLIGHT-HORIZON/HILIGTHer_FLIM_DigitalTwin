function HILIGHTer(configStruct)
% Add AppProperties to path to ensure shared utilities are available


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
fig = uifigure('Name', 'HILIGHTer', 'Position', [50 50 figWidth figHeight], ...
    'CloseRequestFcn', @(src, ev) manageSession(src, 'HILIGHTer', 'closing'));

% === App Properties & Theme ===
setupAppProperties(fig);

% --- Loading Progress Bar ---
d = uiprogressdlg(fig, 'Title', 'Please Wait', ...
    'Message', 'Initializing HILIGHTer Application...', 'Indeterminate', 'off');
drawnow;
d.Value = 0.05;

try


    % Store config and data in a struct
    dataStruct.config = configStruct;
    dataStruct.RawData = [];
    dataStruct.TauMap = [];
    dataStruct.projXY = [];  % Store for ROI colorization
    dataStruct.G_vals = [];  % Store phasor coordinates
    dataStruct.S_vals = [];
    dataStruct.vizMode = 'Default'; % 'Default' or 'ROI Overlay'
    dataStruct.runCount = 0;
    dataStruct.irf_source = 'Simulated';
    dataStruct.irf_data = []; % For experimental/estimated IRF
    dataStruct.functions.refreshAllPlots = @refreshAllPlots;
    dataStruct.functions.syncAnalysisTabsWithConfig = @syncAnalysisTabsWithConfig;
    dataStruct.functions.syncAnalysisMethods = @syncAnalysisMethods;
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
    % First Line: App Mode
    % App Mode Group
    % User Request: Left aligned to the analysis control tab (col1X).
    swX = col1X;
    swMode = uiswitch(fig, 'slider', 'Items', {'', ''}, 'ItemsData', {'Simulator', 'Analyser'}, ...
        'Position', [swX, toggleY, 45, 20], ...
        'Tag', 'swMode', ...
        'ValueChangedFcn', @(src, ev) toggleAppMode(fig, src.Value));
    swMode.Value = initialMode;
    uilabel(fig, 'Text', swMode.Value, 'Position', [swX + 50, toggleY, 100, 25], ...
        'Tag', 'lblAppStatus', 'FontWeight', 'bold', 'FontColor', [0 0.45 0.74]);

    % Expert Mode (Moved to same line, to the right)
    % Restored to previous position to ensure App Mode visibility
    offsetX = col1X + 55; % User Request: Move right by 20px (35 + 20)

    % uilabel(fig, 'Text', 'Expert Mode', 'Position', [offsetX, toggleY, labelW, 25], 'FontWeight', 'bold'); % Removed Title
    swExpert = uiswitch(fig, 'slider', 'Items', {'', ''}, 'ItemsData', {'Basic', 'Expert'}, ...
        'Position', [offsetX + labelW, toggleY, 45, 20], ...
        'Tag', 'swExpert', ...
        'ValueChangedFcn', @(src, ev) toggleExpertMode(fig, src.Value));
    swExpert.Value = 'Basic';
    uilabel(fig, 'Text', swExpert.Value, 'Position', [offsetX + labelW + 60, toggleY, 100, 25], ...
        'Tag', 'lblExpertStatus', 'FontWeight', 'bold', 'FontColor', [0.5 0.5 0.5]);

    % Debug Mode Switch (Hidden by default, revealed in Expert Mode)
    debugOffX = offsetX + labelW + 110;
    uiswitch(fig, 'slider', 'Items', {'', ''}, 'ItemsData', {'Off', 'On'}, ...
        'Position', [debugOffX, toggleY, 45, 20], ...
        'Tag', 'swDebug', 'Visible', 'off', ...
        'ValueChangedFcn', @(src, ev) toggleDebugMode(fig, src.Value));
    uilabel(fig, 'Text', 'Debug Info', 'Position', [debugOffX + 50, toggleY, 100, 25], ...
        'Tag', 'lblDebugStatus', 'FontColor', [0.8 0.4 0], 'Visible', 'off');

    % === Configuration Panel (Top Left) ===
    % === Configuration Panel (Top Left) ===
    % === Configuration Panel ===
    configPanelH = 650; % Reduced from 850 (approx 25% shorter)
    configPanel = uipanel(fig, 'Title', 'Simulation Configuration', 'Tag', 'pnlConfig', ...
        'Position', [col1X, figHeight - configPanelH - margin - 50, col1W, configPanelH]);

    inputH = 22;
    currY = configPanelH - 40 - 15; % Moved 15px lower

    % 1. Mode Selector
    uilabel(configPanel, 'Text', 'Mode:', 'Position', [10 currY 40 inputH]);
    uidropdown(configPanel, ...
        'Items', {'Single Lifetime', 'Lifetime Mix', 'FRET (Donor FLIM)', 'seFRET (Donor/Acceptor FLIM)', 'Time resolved anisotropy'}, ...
        'Value', 'Single Lifetime', ...
        'Position', [55 currY 210 inputH], 'Tag', 'modeDropdown', ...
        'ValueChangedFcn', @(src, ev) toggleHILIGHTerModality(fig));

    % 2. Configuration Manager
    currY = currY - 30;
    uilabel(configPanel, 'Text', 'Config:', 'Position', [10 currY 45 inputH]);
    uidropdown(configPanel, 'Items', {'Default', 'Load...', 'Save Current...'}, ...
        'Position', [55 currY 210 inputH], 'Tag', 'ddConfigMgr', ...
        'ValueChangedFcn', @(src, ev) manageSimulationConfig(fig, src));
    % Placeholder for analyzer panel (keep hidden)
    analyzerPanel = uipanel(fig, 'Title', 'Analysis Controls', 'Tag', 'pnlAnalyzer', ...
        'Position', configPanel.Position, 'Visible', 'off');

    % --- Ported Flows GUI Layout ---
    % Main Grid for Flows
    flGrid = uigridlayout(analyzerPanel, [4 1]);
    flGrid.RowHeight = {'1.5x', '1.5x', 90, 50}; % Adapted relative heights
    flGrid.Padding = [5 5 5 5];
    flGrid.RowSpacing = 5;

    % 1. Conditions Panel
    condPanel = uipanel(flGrid, 'Title', 'CONDITIONS', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.18 0.18 0.20], 'ForegroundColor', [0.9 0.9 0.9]);

    cpGrid = uigridlayout(condPanel, [3 1]);
    cpGrid.RowHeight = {30, '1x', 30};
    cpGrid.Padding = [2 2 2 2]; cpGrid.RowSpacing = 2;

    % New Buttons
    btnGrid = uigridlayout(cpGrid, [1 2]);
    btnGrid.Padding = [0 0 0 0];
    uibutton(btnGrid, 'Text', 'Files 📄', 'ButtonPushedFcn', @(s,e) flows_createFromFiles(fig), ...
        'Tooltip', 'Create a new Experimental Condition group by selecting files.');
    uibutton(btnGrid, 'Text', 'Folder 📁', 'ButtonPushedFcn', @(s,e) flows_createFromFolder(fig), ...
        'Tooltip', 'Create a new Experimental Condition group by importing a folder.');

    % List
    uilistbox(cpGrid, 'Tag', 'condListBox', 'BackgroundColor', [0.12 0.12 0.14], ...
        'FontColor', [0.9 0.9 0.9], 'ValueChangedFcn', @(s,e) flows_updateFileDisplay(fig), 'Items', {});

    % Tools
    toolGrid = uigridlayout(cpGrid, [1 5]);
    toolGrid.Padding = [0 0 0 0]; toolGrid.ColumnSpacing = 1;
    uibutton(toolGrid, 'Text', '✎', 'ButtonPushedFcn', @(s,e) flows_renameCondition(fig), ...
        'Tooltip', 'Rename: Change the name of the selected condition group.');
    uibutton(toolGrid, 'Text', '±', 'ButtonPushedFcn', @(s,e) flows_flagCondition(fig), ...
        'Tooltip', 'Set Type: Cycle this condition between Experimental, Positive Control, and Negative Control.');
    uibutton(toolGrid, 'Text', '🗑', 'FontColor', [0.8 0.3 0.3], 'ButtonPushedFcn', @(s,e) flows_deleteCondition(fig), ...
        'Tooltip', 'Delete: Permanently remove the selected condition group.');
    uibutton(toolGrid, 'Text', '🔗', 'ButtonPushedFcn', @(s,e) flows_mergeConditions(fig), ...
        'Tooltip', 'Merge: Combine two or more selected conditions into a single group.');
    uibutton(toolGrid, 'Text', '❐', 'ButtonPushedFcn', @(s,e) flows_duplicateCondition(fig), ...
        'Tooltip', 'Duplicate: Create a copy of the selected condition group.');

    % 2. Files Panel
    filePanel = uipanel(flGrid, 'Title', 'FILES', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.18 0.18 0.20], 'ForegroundColor', [0.9 0.9 0.9]);
    fpGrid = uigridlayout(filePanel, [2 1]);
    fpGrid.RowHeight = {'1x', 30};
    fpGrid.Padding = [2 2 2 2];

    uilistbox(fpGrid, 'Tag', 'fileListBox', 'Multiselect', 'on', ...
        'BackgroundColor', [0.12 0.12 0.14], 'FontColor', [0.9 0.9 0.9], 'Items', {});

    fTools = uigridlayout(fpGrid, [1 3]);
    fTools.Padding = [0 0 0 0];
    uibutton(fTools, 'Text', 'Add...', 'ButtonPushedFcn', @(s,e) flows_addFiles(fig), ...
        'Tooltip', 'Add more files or content directly to the selected condition.');
    uibutton(fTools, 'Text', '🗑', 'FontColor', [0.8 0.3 0.3], 'ButtonPushedFcn', @(s,e) flows_removeFiles(fig), ...
        'Tooltip', 'Remove Files: Delete selected file(s) from this condition list.');
    uibutton(fTools, 'Text', '➡', 'ButtonPushedFcn', @(s,e) flows_moveFiles(fig), ...
        'Tooltip', 'Move: Move selected files to a different condition group.');

    % 3. Pre-Processing
    prePanel = uipanel(flGrid, 'Title', 'PRE-PROCESS', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.18 0.18 0.20], 'ForegroundColor', [0.9 0.9 0.9]);
    ppGrid = uigridlayout(prePanel, [2 3]);
    ppGrid.RowHeight = {25, 25};
    ppGrid.ColumnWidth = {'fit', '1x', 60};
    ppGrid.Padding = [2 2 2 2];

    % Row 1: Binning
    uilabel(ppGrid, 'Text', 'Binning:');
    uidropdown(ppGrid, 'Items', {'None', 'Simple Binning', 'Gaussian Filter'}, ...
        'Tag', 'flowsBinType', 'ValueChangedFcn', @(s,e) flows_onBinTypeChange(fig, s));
    uispinner(ppGrid, 'Enable', 'off', 'Tag', 'flowsBinSpinner', ...
        'Tooltip', 'Parameter (Bin Size or Sigma)');

    % Row 2: Channels
    uilabel(ppGrid, 'Text', 'Channels:');
    uidropdown(ppGrid, 'Items', {'Keep All Channels', 'Sum All Channels', 'Force Single Channel'}, ...
        'Tag', 'flowsChannelMode', 'Tooltip', 'How to handle multi-channel data', ...
        'ValueChangedFcn', @(s,e) flows_onChannelModeChange(fig, s));
    uispinner(ppGrid, 'Limits', [1 4], 'Value', 1, 'Enable', 'off', ...
        'Tag', 'flowsChannelSpinner', 'Tooltip', 'Select Channel Index');

    % 4. Run
    uibutton(flGrid, 'Text', 'Load Data 🚀', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.2 0.6 0.3], 'FontColor', [1 1 1], 'FontSize', 16, ...
        'ButtonPushedFcn', @(s,e) flows_runAnalysis(fig), ...
        'Tooltip', 'Proceed to the Analysis Step');

    % 3. Generate Button
    currY = currY - 40;
    uibutton(configPanel, 'Text', 'GENERATE DATA', 'FontWeight', 'bold', ...
        'Position', [30 currY 220 30], 'Tag', 'btnGenerate', ...
        'BackgroundColor', [0 0.4470 0.7410], 'FontColor', [1 1 1], ...
        'ButtonPushedFcn', @(btn, event) onGenerate(fig));

    % === Tab Group for Settings ===
    % === Tab Group for Settings ===
    % Moved down 20px and made shorter (shorter by ~25%)
    tabGroupTop = currY - 30;
    tabGroupHeight = 435; % Increased from 400 (+35px)
    simTabGroup = uitabgroup(configPanel, 'Position', [5, tabGroupTop - tabGroupHeight, col1W - 10, tabGroupHeight], 'Tag', 'simTabGroup');

    configPanelBottom = tabGroupTop - tabGroupHeight;

    % --- Tab 1: Acquisition (Size, Inst, Photons) ---
    tabAcq = uitab(simTabGroup, 'Title', 'Acquisition');

    % Dimensions
    yPos = 350; % Moved up by 30 (was 320) to avoid bottom clipping
    uilabel(tabAcq, 'Text', 'Dimensions:', 'Position', [10 yPos 80 22], 'FontWeight', 'bold');
    yPos = yPos - 25;
    uilabel(tabAcq, 'Text', 'X:', 'Position', [10 yPos 20 22]);
    uispinner(tabAcq, 'Limits', [1 4096], 'Value', 64, 'Step', 1, ...
        'Position', [30 yPos 60 22], 'Tag', 'dimXField', 'UserData', 64, ...
        'ValueChangedFcn', @(src,ev) onDimChange(fig, 'X'));

    uilabel(tabAcq, 'Text', 'Y:', 'Position', [100 yPos 20 22]);
    uispinner(tabAcq, 'Limits', [1 4096], 'Value', 64, 'Step', 1, ...
        'Position', [120 yPos 60 22], 'Tag', 'dimYField', 'Enable', 'off', 'UserData', 64, ...
        'ValueChangedFcn', @(src,ev) onDimChange(fig, 'Y'));

    uicheckbox(tabAcq, 'Text', '1:1', 'Position', [190 yPos 50 22], ...
        'Value', 1, 'Tag', 'chkAspect', 'ValueChangedFcn', @(src,ev) onDimChange(fig, 'Aspect'));

    % Instrument Settings
    yPos = yPos - 30;
    uilabel(tabAcq, 'Text', 'Instrument:', 'Position', [10 yPos 80 22], 'FontWeight', 'bold');

    yPos = yPos - 25;
    uilabel(tabAcq, 'Text', 'Channels:', 'Position', [10 yPos 60 22]);
    uispinner(tabAcq, 'Limits', [1 4], 'Value', 1, 'Position', [80 yPos 50 22], 'Tag', 'numChannelsField');

    yPos = yPos - 25;
    uilabel(tabAcq, 'Text', 'Dwell (us):', 'Position', [10 yPos 60 22]);
    uispinner(tabAcq, 'Limits', [0.1 1e6], 'Value', 1000, 'Position', [80 yPos 70 22], 'Tag', 'dwellField', ...
        'ValueChangedFcn', @(src,ev) updateRateDisplay(fig));

    uilabel(tabAcq, 'Text', 'Dead (ns):', 'Position', [160 yPos 60 22]);
    uispinner(tabAcq, 'Limits', [0 1e5], 'Value', 0, 'Position', [220 yPos 50 22], 'Tag', 'deadTimeField', ...
        'ValueChangedFcn', @(src,ev) updateRateDisplay(fig));

    % Photons & Rate
    yPos = yPos - 30;
    uilabel(tabAcq, 'Text', 'Photons / Pixel:', 'Position', [10 yPos 100 22]);
    uispinner(tabAcq, 'Limits', [1 1e9], 'Value', 1000, 'Step', 1, ...
        'Position', [120 yPos 80 22], 'Tag', 'photonsField', 'UserData', 1000, ...
        'ValueChangedFcn', @(src,ev) onPhotonChange(fig));

    yPos = yPos - 25;
    uicheckbox(tabAcq, 'Text', 'Multihit (Ideal)', 'Position', [10 yPos 120 22], 'Value', 1, 'Tag', 'chkMultihit', ...
        'Tooltip', 'Count all photons (ideal) or simulate pile-up loss');

    yPos = yPos - 20;
    uilabel(tabAcq, 'Text', 'Rate: -- MHz', 'Position', [10 yPos 150 22], 'Tag', 'lblRate', 'FontColor', [0.3 0.3 0.3]);
    yPos = yPos - 15;
    uilabel(tabAcq, 'Text', 'Lost: -- %', 'Position', [10 yPos 150 22], 'Tag', 'lblPileUp', 'FontColor', [0.8 0 0]);

    % IRF & Wrap
    yPos = yPos - 30;
    uilabel(tabAcq, 'Text', 'IRF & Correction:', 'Position', [10 yPos 120 22], 'FontWeight', 'bold');

    yPos = yPos - 25;
    uicheckbox(tabAcq, 'Text', 'Wrap Decays', 'Position', [10 yPos 100 22], 'Value', 1, 'Tag', 'chkWrap', 'Tooltip', 'Simulate periodic boundary (pulse train)');
    uicheckbox(tabAcq, 'Text', 'Sync IRFs', 'Position', [120 yPos 80 22], 'Value', 1, 'Tag', 'chkSyncIRF', ...
        'ValueChangedFcn', @(src,ev) toggleIRFSync(fig));

    yPos = yPos - 25;
    uilabel(tabAcq, 'Text', 'Shift Ch1 (ps):', 'Position', [10 yPos 80 22]);
    uispinner(tabAcq, 'Limits', [-5000 5000], 'Value', 0, 'Step', 100, 'Position', [100 yPos 60 22], ...
        'Tag', 'irfShiftField_Ch1', 'ValueChangedFcn', @(src,ev) toggleIRFSync(fig));

    yPos = yPos - 25;
    uilabel(tabAcq, 'Text', 'Shift Ch2 (ps):', 'Position', [10 yPos 80 22]);
    uispinner(tabAcq, 'Limits', [-5000 5000], 'Value', 0, 'Step', 100, 'Position', [100 yPos 60 22], ...
        'Tag', 'irfShiftField_Ch2', 'Enable', 'off');

    % Background
    yPos = yPos - 30;
    uilabel(tabAcq, 'Text', 'Background (cts):', 'Position', [10 yPos 100 22]);
    uieditfield(tabAcq, 'numeric', 'Value', 0, 'Position', [110 yPos 60 22], 'Tag', 'darkCountsField');


    % --- Tab 2: Model & Sweeping ---
    tabModel = uitab(simTabGroup, 'Title', 'Model & Sweep');

    % --- Tab 3: Debug (Expert Only) ---
    % --- Tab 3: Debug (Expert Only) ---
    tabDebug = uitab(simTabGroup, 'Title', 'Debug', 'Tag', 'tabDebug');
    % Store handle in group UserData so we can retrieve it when unparented
    if isempty(simTabGroup.UserData), simTabGroup.UserData = struct(); end
    sGroupData = simTabGroup.UserData;
    sGroupData.tabDebug = tabDebug;
    simTabGroup.UserData = sGroupData;

    % Create Test Buttons
    for i = 1:5
        uibutton(tabDebug, 'Text', sprintf('Test %d', i), ...
            'Position', [40, 350 - (i*50), 200, 30], ...
            'ButtonPushedFcn', @(btn,ev) disp(['Test ' num2str(i) ' Clicked (Placeholder)']));
    end

    % Model Params Area
    yPos = 370; % Moved all the way up (was 300)
    uilabel(tabModel, 'Text', 'Model Parameters:', 'Position', [10 yPos 150 22], 'FontWeight', 'bold');

    % Container for Dynamic Model Inputs
    % pnlModelParams is positioned relative to the parent tab
    % Height: 140px
    uipanel(tabModel, 'BorderType', 'none', 'Position', [0 yPos-140 col1W-10 140], 'Tag', 'pnlModelParams');

    % Sweeping Area (Below model params)
    yPos = yPos - 160; % Start sweeping area at ~210
    uilabel(tabModel, 'Text', 'Parameter Sweeping:', 'Position', [10 yPos 150 22], 'FontWeight', 'bold');

    % Sweep X
    yPos = yPos - 25;
    uicheckbox(tabModel, 'Text', 'Sweep X', 'Position', [10 yPos 70 22], 'Tag', 'chkSweepX', ...
        'ValueChangedFcn', @(src,ev) updateSweepUI(fig));
    uidropdown(tabModel, 'Position', [80 yPos 100 22], 'Tag', 'ddSweepParamX', 'Enable', 'off', ...
        'ValueChangedFcn', @(src,ev) updateSweepUI(fig));

    yPos = yPos - 25;
    uilabel(tabModel, 'Text', 'Start:', 'Position', [20 yPos 35 22]);
    uieditfield(tabModel, 'numeric', 'Position', [55 yPos 50 22], 'Tag', 'sweepStartX', 'Enable', 'off');
    uilabel(tabModel, 'Text', '', 'Position', [108 yPos 25 22], 'Tag', 'lblStartUnitX'); % Unit Label

    uilabel(tabModel, 'Text', 'End:', 'Position', [125 yPos 30 22]);
    uieditfield(tabModel, 'numeric', 'Position', [155 yPos 50 22], 'Tag', 'sweepEndX', 'Enable', 'off');
    uilabel(tabModel, 'Text', '', 'Position', [208 yPos 25 22], 'Tag', 'lblEndUnitX'); % Unit Label

    yPos = yPos - 25;
    uilabel(tabModel, 'Text', 'Pad:', 'Position', [20 yPos 30 22]);
    uispinner(tabModel, 'Limits', [0 512], 'Value', 0, 'Position', [55 yPos 50 22], 'Tag', 'sweepPadStartX', 'Enable', 'off');
    uilabel(tabModel, 'Text', '-', 'Position', [115 yPos 10 22]);
    uispinner(tabModel, 'Limits', [0 512], 'Value', 0, 'Position', [130 yPos 50 22], 'Tag', 'sweepPadEndX', 'Enable', 'off');

    yPos = yPos - 25;
    uilabel(tabModel, 'Text', 'Gradient:', 'Position', [20 yPos 60 22]);
    uidropdown(tabModel, 'Items', {'Linear', 'Non-Linear'}, 'Position', [80 yPos 100 22], 'Tag', 'ddSweepTypeX', 'Enable', 'off');

    % Sweep Y
    yPos = yPos - 35;
    uicheckbox(tabModel, 'Text', 'Sweep Y', 'Position', [10 yPos 70 22], 'Tag', 'chkSweepY', ...
        'ValueChangedFcn', @(src,ev) updateSweepUI(fig));
    uidropdown(tabModel, 'Position', [80 yPos 100 22], 'Tag', 'ddSweepParamY', 'Enable', 'off', ...
        'ValueChangedFcn', @(src,ev) updateSweepUI(fig));

    yPos = yPos - 25;
    uilabel(tabModel, 'Text', 'Start:', 'Position', [20 yPos 35 22]);
    uieditfield(tabModel, 'numeric', 'Position', [55 yPos 50 22], 'Tag', 'sweepStartY', 'Enable', 'off');
    uilabel(tabModel, 'Text', '', 'Position', [108 yPos 25 22], 'Tag', 'lblStartUnitY'); % Unit Label

    uilabel(tabModel, 'Text', 'End:', 'Position', [125 yPos 30 22]);
    uieditfield(tabModel, 'numeric', 'Position', [155 yPos 50 22], 'Tag', 'sweepEndY', 'Enable', 'off');
    uilabel(tabModel, 'Text', '', 'Position', [208 yPos 25 22], 'Tag', 'lblEndUnitY'); % Unit Label

    yPos = yPos - 25;
    uilabel(tabModel, 'Text', 'Pad:', 'Position', [20 yPos 30 22]);
    uispinner(tabModel, 'Limits', [0 512], 'Value', 0, 'Position', [55 yPos 50 22], 'Tag', 'sweepPadStartY', 'Enable', 'off');
    uilabel(tabModel, 'Text', '-', 'Position', [115 yPos 10 22]);
    uispinner(tabModel, 'Limits', [0 512], 'Value', 0, 'Position', [130 yPos 50 22], 'Tag', 'sweepPadEndY', 'Enable', 'off');

    yPos = yPos - 25;
    uilabel(tabModel, 'Text', 'Gradient:', 'Position', [20 yPos 60 22]);
    uidropdown(tabModel, 'Items', {'Linear', 'Non-Linear'}, 'Position', [80 yPos 100 22], 'Tag', 'ddSweepTypeY', 'Enable', 'off');

    % Initial UI State
    setupModelParams(fig); % Create model fields
    toggleHILIGHTerModality(fig);
    updateRateDisplay(fig);

    % Ensure Debug tab is hidden initially if not Expert
    toggleExpertMode(fig, swExpert.Value);

    % Ensure correct App Mode (Simulator vs Analyser) panels are shown
    toggleAppMode(fig, initialMode);



    % === Instrument Parameters Panel (Below Config) ===
    % Fill the remaining vertical space in Column 1
    % === Instrument Parameters Panel ===
    % Fill remaining space, but 2x taller than before means we utilize the space freed by shrinking config
    % configPanelBottom is where the config controls end.
    % User Request: Make it 100px shorter, keeping bottom fixed.
    instPanelH = (configPanelBottom - 2*margin) - 100;
    if instPanelH < 250, instPanelH = 250; end % Force taller minimum

    instPanel = uipanel(fig, 'Title', 'Instrument Parameters', ...
        'Position', [col1X, margin, col1W, instPanelH]);

    d.Value = 0.25; d.Message = 'Setting up Instrument Parameters...';

    % Initialization of vizMode
    % (vizSwitch removed from sidebar, will be in tabs)

    % --- IRF Source Selection ---
    yPos = instPanelH - 55; % Moved down 20px (was -35)
    uilabel(instPanel, 'Text', 'IRF Source:', 'Position', [10, yPos, 80, 22]);
    uidropdown(instPanel, 'Items', {'Simulated', 'Estimated', 'Experimental'}, ...
        'Position', [90, yPos, 120, 22], 'Tag', 'ddIRFSource', ...
        'ValueChangedFcn', @(src, ev) onIRFSourceChanged(fig, src.Value));

    % Internal Axes for Instrument/IRF
    % Auto-resize based on panel height, leaving space for controls at top
    % yPos starts at top, minus controls (~60px)
    uiaxes(instPanel, 'Position', [45 45 col1W-65 yPos-60], 'Tag', 'axInst');

    yPos = yPos - 30;
    uibutton(instPanel, 'Text', 'Pick from File', 'Position', [10, yPos, 110, 22], ...
        'Visible', 'off', 'Tag', 'btnExpIRF', 'Tooltip', 'Use current channel average as IRF', ...
        'ButtonPushedFcn', @(btn, ev) onExtractExperimentalIRF(fig));

    uibutton(instPanel, 'Text', 'Estimate IRF', 'Position', [130, yPos, 110, 22], ...
        'Visible', 'off', 'Tag', 'btnEstIRF', 'Tooltip', 'Estimate from rising shoulder', ...
        'ButtonPushedFcn', @(btn, ev) onEstimateIRF(fig));

    yPos = yPos - 25;
    uilabel(instPanel, 'Text', 'Peak:', 'Position', [10, yPos, 35, 22], 'Tag', 'lblIRFPeakField', 'Visible', 'off');
    uilabel(instPanel, 'Text', '-', 'Position', [45, yPos, 60, 22], 'Tag', 'lblIRFPeak', 'Visible', 'off');
    uilabel(instPanel, 'Text', 'FWHM:', 'Position', [110, yPos, 45, 22], 'Tag', 'lblIRFFWHMField', 'Visible', 'off');
    uilabel(instPanel, 'Text', '-', 'Position', [155, yPos, 90, 22], 'Tag', 'lblIRFFWHM', 'Visible', 'off');



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
    % threshY was unused
    ytW = plotH * 0.3;
    ytX = col2X + plotH + margin;
    tabDataWidth = col2X + plotH + margin + ytW - col2X + 50; % User Request: Increase width by 50px

    dataPanelH = figHeight - 65 - margin; % User Request: Align top with Analysis Controls (Restore height)
    pnlData = uipanel(fig, 'Title', 'Data', 'Position', [col2X, margin, tabDataWidth, dataPanelH]);

    % Tab group inside Data Panel
    % Fill the panel (leave slight margin for border/title)
    % User Request: Move 3 pixels upwards (Increase height to reduce top margin)
    dataTabGroup = uitabgroup(pnlData, 'Position', [2, 2, tabDataWidth-4, dataPanelH-27], 'Tag', 'dataTabGroup');
    dataTabGroup.SelectionChangedFcn = @(~,~) onDataTabChange(fig);

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

    % === NEW DATA INTERFACE ===
    % Rebuilding Data Frame from scratch
    % 1. Tab Group with Groups and Image
    % Using pnlData (already created)

    % Ensure pnlData is cleaned (remove legacy uitabgroup if present from lines above?
    % The line creating dataTabGroup was: dataTabGroup = uitabgroup(pnlData, ...);
    % I should reuse THAT tabgroup or clear it.
    % Actually, I can just repurpose the variable `dataTabGroup` from line 474.

    % BUT, I need to configure the tabs NOW.

    % Tab 1: Groups (Modeled after Flow Analysis)
    tabGroups = uitab(dataTabGroup, 'Title', 'Groups');
    % We will call a helper to populate this below (defined at end of file)
    createGroupsTabInterface(fig, tabGroups);

    % Tab 2: Image (Single Channel View with Nav)
    tabImage = uitab(dataTabGroup, 'Title', 'Image');
    fig.UserData.navChannel = 1; % Start at Ch1
    createImageTabInterface(fig, tabImage, fig.UserData);

    % Commented out legacy per-channel tab creation:
    % createDataTab(dataTabGroup, 1, dataStruct);
    d.Value = 0.35; d.Message = 'Initializing Visualization Tabs...';

    % === Column 3: Analysis Results Tabs ===
    % === Column 3: Analysis Results Tabs ===
    col3X = col2X + tabDataWidth + margin - 50 + 45; % User Request: Make Analysis 75px larger (Reduce shrinkage)

    % Wrap in Analysis Panel
    analysisPanelH = dataPanelH; % Align top with Data Frame
    pnlAnalysis = uipanel(fig, 'Title', 'Analysis', 'Position', [col3X, margin, figWidth - col3X - margin, analysisPanelH]);

    % User Request: Move 7 pixels lower (Reduce height to increase top margin)
    tabGroup = uitabgroup(pnlAnalysis, 'Position', [2, 2, pnlAnalysis.Position(3)-4, pnlAnalysis.Position(4)-27]);
    tabGroup.Tag = 'analysisTabs';
    tabGroup.SelectionChangedFcn = @(src, event) refreshXYProjection(fig);

    % Relative alignment constants for use inside tabs
    % Update UserData incrementally to avoid overwriting GroupsTab
    uDat = fig.UserData;
    uDat.axL = 20;
    uDat.axW = 400;
    uDat.metX = 600;
    uDat.xyY_top = 530;
    uDat.xtH = xtH;
    fig.UserData = uDat;

    % Initial Analysis tabs (now permanent)
    % Initial Analysis tabs (now permanent)
    tabMLE = uitab(tabGroup, 'Title', 'Grid MLE');
    d.Value = 0.45; d.Message = 'Setting up Grid MLE Tab...';
    createNewFitTab(fig, tabMLE, 'Grid MLE', 1); % Pre-populate

    tabIter = uitab(tabGroup, 'Title', 'Iterative Reconvolution');
    d.Value = 0.55; d.Message = 'Setting up Iterative Reconvolution Tab...';
    createNewFitTab(fig, tabIter, 'Iterative Reconvolution', 1);

    tabTail = uitab(tabGroup, 'Title', 'Tail Fitting');
    d.Value = 0.65; d.Message = 'Setting up Tail Fitting Tab...';
    createNewFitTab(fig, tabTail, 'Tail Fitting', 1);


    tabPhasor = uitab(tabGroup, 'Title', 'Phasor Analysis');
    createNewPhasorTab(fig, tabPhasor, 1);

    tabPM = uitab(tabGroup, 'Title', 'Pattern Matching');
    createNewPatternTab(fig, tabPM, 1);

    tabLima = uitab(tabGroup, 'Title', 'LiMA');
    createNewLimaTab(fig, tabLima, 1);

    tabFisher = uitab(tabGroup, 'Title', 'Fisher Analysis');
    createNewFisherTab(fig, tabFisher, 1);
    uibutton(tabFisher, 'Text', 'Clear', 'Position', [240, 960, 60, 20], ...
        'ButtonPushedFcn', @(~,~) onClearTab(fig));

    tabCellSAM = uitab(tabGroup, 'Title', 'CellSAM');
    uibutton(tabCellSAM, 'Text', 'DOWNLOAD/LOAD MODEL', 'Position', [10, 960, 180, 20], ...
        'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [0 0.5 0], 'FontColor', [1 1 1], ...
        'ButtonPushedFcn', @(~,~) onLoadCellSAMModel(fig));

    uibutton(tabCellSAM, 'Text', 'SEGMENT IMAGE', 'Position', [200, 960, 180, 20], ...
        'FontSize', 12, 'FontWeight', 'bold', 'BackgroundColor', [0 0 1], 'FontColor', [1 1 1], ...
        'ButtonPushedFcn', @(~,~) onRunCellSAM(fig));


    d.Value = 0.75; d.Message = 'Initializing Advanced Analysis Methods...';

    tabML = uitab(tabGroup, 'Title', 'Machine Learning');
    createNewMLTab(fig, tabML, 'Machine Learning', 1);




    % Initial Instrument Update
    % Initial Instrument Update
    updateInstrumentPlot(fig);

    d.Value = 0.90; d.Message = 'Finalizing Interface Layout...';

    % === Analysis Methods Menu ===
    % === Analysis Methods Menu ===
    mAnalysis = uimenu(fig, 'Text', 'Analysis methods', 'Tag', 'mnuAnalysisMethods');
    methodList = {'Grid MLE', 'Iterative Reconvolution', 'Tail Fitting', 'Phasor Analysis', 'Pattern Matching', 'LiMA', 'Fisher Analysis', 'CellSAM', 'Machine Learning'};
    tabHandles = {tabMLE, tabIter, tabTail, tabPhasor, tabPM, tabLima, tabFisher, tabCellSAM, tabML};
    items = gobjects(1, length(methodList));

    % Settings File Path
    settingsFile = fullfile(fileparts(mfilename('fullpath')), 'AppProperties', 'settings.mat');

    % Load Settings
    savedMethods = methodList; % Default all on
    try
        if exist(settingsFile, 'file')
            vars = who('-file', settingsFile);
            if any(strcmp(vars, 'activeMethods'))
                loaded = load(settingsFile, 'activeMethods');
                if isfield(loaded, 'activeMethods')
                    savedMethods = loaded.activeMethods;
                end
            end
        end
    catch
    end

    % Create Menu Items
    for i = 1:length(methodList)
        is_active = any(strcmp(savedMethods, methodList{i}));
        if is_active
            chk = 'on';
            tabHandles{i}.Parent = tabGroup; % Relies on tabGroup defined above
        else
            chk = 'off';
            tabHandles{i}.Parent = [];
        end

        sep = 'off';
        if strcmp(methodList{i}, 'Phasor Analysis')
            sep = 'on';
        end

        tagStr = ['mnuMethod_' regexprep(methodList{i}, '\s+', '')];
        items(i) = uimenu(mAnalysis, 'Text', methodList{i}, 'Checked', chk, 'Separator', sep, ...
            'Tag', tagStr, 'MenuSelectedFcn', @(src, ev) toggleTab(src));
    end

    % Initialize Flows Data (User Request: Default to empty)
    if isfield(fig.UserData, 'Flows')
        fig.UserData.Flows = [];
    end
    dFlows = struct('Conditions', {{}});
    dFlows.config = struct('spatialBinning', 0, 'binType', 'None');
    fs = fig.UserData;
    fs.Flows = dFlows;
    fig.UserData = fs;

    % Refresh Lists (Ensure empty)
    flows_refreshCondList(fig);
    groupsTab_refreshUI(fig);

    d.Value = 1.0;
    close(d);

    % === Check for Previous Session ===
    manageSession(fig, 'HILIGHTer', 'check');
catch ME
    if exist('d','var') && isvalid(d), close(d); end
    rethrow(ME);
end

% --- Nested Helper Functions ---
    function toggleTab(src)
        if strcmp(src.Checked, 'on'), src.Checked = 'off'; else, src.Checked = 'on'; end
        syncAnalysisMethods();
        saveAnalysisSettings();
    end

    function syncAnalysisMethods(~)
        % fig arg optional if called internally, but needed if called from manageSession
        if ~iscell(tabHandles), return; end % Safety check
        for k = 1:length(tabHandles)
            if strcmp(items(k).Checked, 'on')
                tabHandles{k}.Parent = tabGroup;
            else
                tabHandles{k}.Parent = [];
            end
        end
    end

    function saveAnalysisSettings()
        activeMethods = cell(1, length(methodList));
        count = 0;
        for k = 1:length(methodList)
            if strcmp(items(k).Checked, 'on')
                count = count + 1;
                activeMethods{count} = methodList{k};
            end
        end
        activeMethods = activeMethods(1:count);
        try
            if exist(settingsFile, 'file'), save(settingsFile, 'activeMethods', '-append');
            else, save(settingsFile, 'activeMethods'); end
        catch
        end
    end
end


function onGenerate(fig)
try
    d = uiprogressdlg(fig, 'Title', 'Generating Data', 'Indeterminate', 'on');
    cleanObj = onCleanup(@() delete(d)); % Ensure progress dialog is closed

    data = fig.UserData;
    config = data.config;

    % --- Read Simulation Settings ---
    dimXF = findobj(fig, 'Tag', 'dimXField');
    dimYF = findobj(fig, 'Tag', 'dimYField');
    nX = dimXF.Value; nY = dimYF.Value;

    phF = findobj(fig, 'Tag', 'photonsField');
    dwS = findobj(fig, 'Tag', 'dwellField');
    dtS = findobj(fig, 'Tag', 'deadTimeField');
    chS = findobj(fig, 'Tag', 'numChannelsField');

    % N_ph is now treated as TOTAL Counts (Signal + Background)
    N_total = phF.Value;
    dwell_us = dwS.Value;
    dead_ns = dtS.Value;
    nC = chS.Value;

    N_bg_total = getVal('darkCountsField');

    % Calculate Signal and Background per gate
    N_sig = max(0, N_total - N_bg_total);
    % bg_per_gate will be calculated after n_gates is known

    bWrap = getVal('chkWrap');
    bMultihit = getVal('chkMultihit');

    % IRF Shifts
    irf1 = getVal('irfShiftField_Ch1');
    chkSync = findobj(fig, 'Tag', 'chkSyncIRF');
    if isvalid(chkSync) && chkSync.Value
        irf2 = irf1;
    else
        irf2 = getVal('irfShiftField_Ch2');
    end

    % Sync Config for Analysis
    config.irf_shift = irf1; % Use Ch1 shift as global fitting shift for now (or per-channel?)
    % Note: fitting assumes one shift. We'll save irf1.
    config.bWrap = bWrap;
    config.dead_time = dead_ns;
    config.bPulseTrain = bWrap; % Align naming
    % config.N_gates is set in setup? If user changes dwell, N_gates doesn't change.

    modeDD = findobj(fig, 'Tag', 'modeDropdown');
    Mode = modeDD.Value;

    T = config.T; if isempty(T) || T <= 0, T = 12.5; end

    % Setup Time and Gates
    % Simulation Time Resolution
    % Ensure dt is fine enough to avoid aliasing with gates
    % If gates are, say, 12.5ns/256 ~ 48ps, and dt=50ps, we get Moiré/beating.
    % We generally want dt <= gate_width / 4
    n_gates_actual = config.N_gates;
    if isempty(n_gates_actual), n_gates_actual = 64; end % Fallback

    min_gate_width = T / n_gates_actual;
    target_dt = min_gate_width / 5;

    % Cap at reasonable limit (e.g. 1ps) to prevent memory explode
    if target_dt < 0.001, target_dt = 0.001; end

    % Override config.dt for simulation generation loop (internal only)
    dt_sim = target_dt;
    t_vec = 0:dt_sim:T;

    actual_gate_edges = config.gate_edges;
    if isempty(actual_gate_edges), actual_gate_edges = linspace(0, T, config.N_gates + 1); end
    actual_gate_edges(actual_gate_edges > T) = T;

    gate_profiles = DTgates(t_vec, max(config.r, 1e-4), actual_gate_edges);
    nG = size(gate_profiles, 1);
    gate_interp_fns = cell(nG, 1);
    for i = 1:nG, gate_interp_fns{i} = griddedInterpolant(t_vec, gate_profiles(i, :), 'linear', 'nearest'); end

    irf_custom = [];
    if ~strcmp(data.irf_source, 'Simulated'), irf_custom = data.irf_data; end

    % Initialize
    if contains(Mode, 'seFRET') || contains(Mode, 'Anisotropy'), nC = 2; end
    P_model_Full = zeros(nY, nX, nG, nC);

    % --- Generate Parameter Maps ---
    Tau1 = getParameterMap(fig, 'Lifetime 1', getVal('tau1Field')/1000, nX, nY, 1/1000);
    Tau2 = getParameterMap(fig, 'Lifetime 2', getVal('tau2Field')/1000, nX, nY, 1/1000);
    Alpha = getParameterMap(fig, 'Mix Fraction', getVal('alphaField')/100, nX, nY, 1/100);

    tD = getParameterMap(fig, 'Donor Tau', getVal('fretTauField')/1000, nX, nY, 1/1000);
    tA = getParameterMap(fig, 'Acceptor Tau', getVal('fretAcceptorTauField')/1000, nX, nY, 1/1000);
    E_fret = getParameterMap(fig, 'FRET E', getVal('fretEField')/100, nX, nY, 1/100);
    f_fret = getParameterMap(fig, 'Frac FRET', getVal('fretFracField')/100, nX, nY, 1/100);
    dirEx = getVal('fretDirectExField')/100;
    bleed = getVal('fretBleedThroughField')/100;

    tAnis = getParameterMap(fig, 'Anis Tau', getVal('anisLifetimeField')/1000, nX, nY, 1/1000);
    Rot = getParameterMap(fig, 'Rotation', getVal('anisRotationField')/1000, nX, nY, 1/1000);
    r0_map = getParameterMap(fig, 'r0', getVal('anisR0Field'), nX, nY, 1);

    if contains(Mode, 'FRET') || contains(Mode, 'seFRET')
        % Ch1: Donor
        P_D = runMod(tD, irf1);
        tDA = tD .* (1 - E_fret);
        P_DA = runMod(tDA, irf1);

        % Mix
        f_3d = repmat(f_fret, 1, 1, nG);
        P_Ch1 = (1 - f_3d) .* P_D + f_3d .* P_DA;
        P_model_Full(:,:,:,1) = P_Ch1;

        if contains(Mode, 'seFRET') || nC > 1
            P_A = runMod(tA, irf2);
            P_DA_ch2 = runMod(tDA, irf2);

            B = tA ./ (tA - tDA + 1e-12);
            B_3d = repmat(B, 1, 1, nG);
            P_Sens = B_3d .* (P_A - P_DA_ch2);
            P_Sens(P_Sens < 0) = 0;

            % Simplify bleed
            P_A_ch2 = runMod(tA, irf2);
            P_Total2 = f_3d .* P_Sens + dirEx * P_A_ch2 + bleed * P_Ch1;
            P_model_Full(:,:,:,2) = P_Total2;
        end

        data.GroundTruthE = E_fret;
        data.GroundTruthFrac = f_fret;
        data.GroundTruthAlpha = f_fret;

    elseif contains(Mode, 'Anisotropy')
        te = 1 ./ (1./tAnis + 1./Rot);

        P_tau = runMod(tAnis, irf1);
        P_te  = runMod(te, irf1);
        r0_3d = repmat(r0_map, 1, 1, nG);

        P_model_Full(:,:,:,1) = (1/3) * (P_tau + 2*r0_3d.*P_te);
        P_tau2 = runMod(tAnis, irf2);
        P_te2  = runMod(te, irf2);
        P_model_Full(:,:,:,2) = (1/3) * (P_tau2 - r0_3d.*P_te2);

        data.GroundTruthTaus = tAnis;

    else
        % Lifetime
        P1 = runMod(Tau1, irf1);
        P_model_Full(:,:,:,1) = P1;

        if contains(Mode, 'Mix') || any(Alpha(:)>0)
            P2 = runMod(Tau2, irf1);
            a_3d = repmat(Alpha, 1, 1, nG);
            P_model_Full(:,:,:,1) = (1 - a_3d) .* P1 + a_3d .* P2;

            if nC > 1
                P1_2 = runMod(Tau1, irf2);
                P2_2 = runMod(Tau2, irf2);
                P_model_Full(:,:,:,2) = (1 - a_3d) .* P1_2 + a_3d .* P2_2;
            end
            data.GroundTruthAlpha = Alpha;
        else
            if nC > 1
                P_model_Full(:,:,:,2) = runMod(Tau1, irf2);
            end
        end
        if contains(Mode, 'Mix')
            data.GroundTruthTaus = Tau1 .* (1-Alpha) + Tau2 .* Alpha;
        else
            data.GroundTruthTaus = Tau1;
        end
    end

    % --- Noise and Pile-up ---
    RawData_Full = zeros(nY, nX, nG, nC);
    Trep = T; if isfield(config, 'PT_Trep') && config.PT_Trep > 0, Trep = config.PT_Trep; end
    num_pulses = (dwell_us * 1000) / Trep;

    for c = 1:nC
        Pc = P_model_Full(:,:,:,c);
        P_sum = sum(Pc, 3); P_sum(P_sum == 0) = 1;
        Pc_norm = Pc ./ P_sum;

        % bg_per_gate = N_bg_total / (nG * nC); % Assuming BG is split or per channel?
        % Actually usually BG is specified per channel. Let's assume N_bg_total is per channel.
        bg_per_gate = N_bg_total / nG;

        if bMultihit
            ExpCounts = N_sig * Pc_norm + bg_per_gate;
            RawData_Full(:,:,:,c) = poissrnd(ExpCounts);
        else
            mu = N_sig / num_pulses;
            P_cdf_prev = cumsum(Pc_norm, 3);
            P_cdf_prev = cat(3, zeros(nY, nX, 1), P_cdf_prev(:,:,1:end-1));
            ExpCounts = num_pulses * exp(-mu * P_cdf_prev) .* (1 - exp(-mu * Pc_norm)) + bg_per_gate;
            RawData_Full(:,:,:,c) = poissrnd(ExpCounts);
        end
    end

    data.RawData = RawData_Full;
    data.ProcData = cell(nC, 1);
    data.config = config; % Save updated config
    fig.UserData = data;
    close(d);

    syncAnalysisTabsWithConfig(fig);
    for c = 1:nC, processChannelData(fig, c); end
    refreshAllPlots(fig);

catch ME
    if exist('d','var') && isvalid(d), close(d); end
    uialert(fig, ['Generate Failed: ' ME.message], 'Error');
end

    function v = getVal(t)
        o=findobj(fig,'Tag',t);
        if isempty(o),v=0;else,v=o.Value;end
    end

    function P = runMod(t_map, shift)
        vec_t = t_map(:);
        P_flat = DTpmod(nG, vec_t, t_vec, gate_interp_fns, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma, shift, bWrap, dead_ns, irf_custom);
        P = permute(reshape(P_flat, nG, nX, nY), [3 2 1]);
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
        cData = getChannelData(fig, c);

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
            hImg = imagesc(axXY, projXY);
            hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(fig, ev.IntersectionPoint);
            colormap(axXY, 'gray');
            axis(axXY, 'image');
            cb = colorbar(axXY, 'Location', 'westoutside');
            cb.Label.String = 'Photons';
            maxCounts = max(projXY(:));
            title(axXY, sprintf('XY Channel %d | Max: %g', c, maxCounts));
            set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');
            title(axXY, sprintf('XY Channel %d | Max: %g', c, maxCounts));
            set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');

            % Re-overlay crosshair if it's the active channel
            curPos = [nan nan];
            hV = findobj(fig, 'Tag', 'crossV');
            hH = findobj(fig, 'Tag', 'crossH');
            if ~isempty(hV) && ~isempty(hH)
                curPos = [hV(1).Value, hH(1).Value];
            end

            % If we have a position, refresh analysis to draw markers on new image
            if ~isnan(curPos(1))
                % This will recreate markers on axXY because imagesc deleted them
                % but we should be careful not to trigger recursive refresh
            end

            % Update CLim Spinners (Sync with new data range)
            % This addresses the "no data" or "wrong range" visual bug
            dataTab = dataTabGroup.Children(c);
            spnMin = findobj(dataTab, 'Tag', sprintf('spnMin_Ch%d', c));
            spnMax = findobj(dataTab, 'Tag', sprintf('spnMax_Ch%d', c));

            if ~isempty(spnMin) && ~isempty(spnMax)
                % Only update if Range is significantly different or if it was default
                % Ideally we should adjust CLim to data always on refresh?
                cMin = min(projXY(:));
                cMax = maxCounts;
                if cMin==cMax, cMax = cMin + 1; end

                % Update GUI spinners
                spnMin.Value = cMin;
                spnMax.Value = cMax;

                % Apply to Axes
                set(axXY, 'CLim', [cMin cMax]);
            end
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
                    tVal = spnThresh.Value;
                    if isfield(thisTab.UserData, 'CustomMask') && ~isempty(thisTab.UserData.CustomMask)
                        maskSz = size(thisTab.UserData.CustomMask);
                        if all(maskSz(1:2) == sz(1:2))
                            alphaMap = double(thisTab.UserData.CustomMask);
                        else
                            % Size mismatch, clear custom mask to avoid crash
                            thisTab.UserData.CustomMask = [];
                            alphaMap = double(projXY <= tVal);
                        end
                    else
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

% adjustSize, onAnalyze functions removed as unused.


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

% toggleVizMode removed as unused.

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
cData = getChannelData(fig, chanIdx);
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
delete(t.Children); % fresh start
% --- Layout Constants ---
axW = 400;
mapH = 350;

% Main Grid for Layout
gMain = uigridlayout(t, [1 2]);
gMain.ColumnWidth = {'1x', '0.5x'};

% Left Side: Maps (Images)
pLeft = uipanel(gMain, 'BorderType', 'none');
tGroup = uitabgroup(pLeft, 'Tag', 'mapTg_Phasor_Analysis', ...
    'SelectionChangedFcn', @(src, ev) syncMapDisplay(t));

mapAxes = struct(); mapHists = struct(); mapSpins = struct();
pNames = {'Photons', 'Tau', 'Fraction'};
dNames = {'Intensity', 'Phasor Tau', 'Fraction'};

for i = 1:numel(pNames)
    nm = pNames{i};
    tabMap = uitab(tGroup, 'Title', dNames{i}, 'Tag', ['tab_' nm '_Phasor_Analysis']);

    % Axis for Image
    ax = uiaxes(tabMap, 'Position', [10, 160, axW, mapH], 'Tag', ['ax_' nm '_Phasor_Analysis']);
    disableDefaultInteractions(ax); colormap(ax, 'jet');
    mapAxes.(nm) = ax;

    % Axis for Histogram
    axH = uiaxes(tabMap, 'Position', [10, 10, axW, 140], 'Tag', ['hist_' nm '_Phasor_Analysis']);
    mapHists.(nm) = axH;

    % Controls (Spinners)
    uilabel(tabMap, 'Text', 'Min:', 'Position', [axW+20, 100, 30, 20]);
    spnMin = uispinner(tabMap, 'Position', [axW+60, 100, 60, 20], ...
        'ValueChangedFcn', @(src, ev) syncTabSpinners(t, 'Min', src.Value));

    uilabel(tabMap, 'Text', 'Max:', 'Position', [axW+20, 130, 30, 20]);
    spnMax = uispinner(tabMap, 'Position', [axW+60, 130, 60, 20], ...
        'ValueChangedFcn', @(src, ev) syncTabSpinners(t, 'Max', src.Value));

    mapSpins.(nm).Min = spnMin; mapSpins.(nm).Max = spnMax;
end

% Right Side: Phasor Plot & Controls
pRight = uipanel(gMain, 'Title', 'Phasor Plot');
gRight = uigridlayout(pRight, [2 1]);
gRight.RowHeight = {'1x', '0.3x'};

axP = uiaxes(gRight); axP.Tag = 'axPhasorRun';
title(axP, 'Phasor Plot'); xlabel(axP, 'G'); ylabel(axP, 'S');
axis(axP, 'equal'); grid(axP, 'on'); box(axP, 'on');

% Controls
pCtrl = uipanel(gRight, 'Title', 'Controls');
gCtrl = uigridlayout(pCtrl, [4 2]);

uibutton(gCtrl, 'Text', 'Add ROI', 'ButtonPushedFcn', @(~,~) addPhasorROI(fig, 1));
uibutton(gCtrl, 'Text', 'Clear ROI', 'ButtonPushedFcn', @(~,~) clearPhasorROI(fig, 'all'));
uibutton(gCtrl, 'Text', 'Batch Analysis', 'BackgroundColor', [0.2 0.3 0.6], 'FontColor', 'white', ...
    'ButtonPushedFcn', @(~,~) runBatchAnalysis(fig, t));

% Meta initialization
tabMeta = struct();
tabMeta.activeChanIdx = activeChanIdx;
tabMeta.algo = 'Phasor Analysis';
tabMeta.mapTg = tGroup;
tabMeta.mapAxes = mapAxes;
tabMeta.mapHists = mapHists;
tabMeta.mapSpins = mapSpins;
tabMeta.axPhasor = axP;
tabMeta.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});
tabMeta.harmonic = 1;
tabMeta.plotAllHarmonics = true;
tabMeta.phasorZoomMode = 'Full';

t.UserData = tabMeta;

refreshPhasorPlot(fig, axP);
end

function createNewMLTab(fig, tab, algo, activeChanIdx)
% Removed unused arguments and variables
data = fig.UserData;
axL = data.axL;
axW = data.axW;
metX = data.metX;


if isempty(tab.UserData) || ~isfield(tab.UserData, 'mapAxes')
    % --- Vertical Layout Constants (60/40 Split) ---
    hTop = 580; hBot = 380;
    topY = 980 - hTop;
    botY = 10;

    % --- Map Tab Group (Top 60%) ---
    mapH = 350; histH = 150;
    mapTgW = axW + 90;
    mapTgH = hTop;
    mapTgY = topY;

    tagAlgo = regexprep(algo, '[^a-zA-Z0-9]', '_');
    mapTg = uitabgroup(tab, 'Position', [axL, mapTgY, mapTgW, mapTgH], 'Tag', ['mapTg_', tagAlgo], ...
        'SelectionChangedFcn', @(src, ev) syncMapDisplay(tab));

    mapAxes = struct(); mapHists = struct(); mapSpins = struct();
    pNames = {'Photons', 'TauAvg', 'Chi2'}; % Simplified for now
    dNames = {'Photons', 'Tau Avg', 'Red. Chi2'};

    for i = 1:numel(pNames)
        p = pNames{i};
        t = uitab(mapTg, 'Title', dNames{i}, 'Tag', ['tab_' p '_' tagAlgo]);
        ax = uiaxes(t, 'Position', [5, histH + 50, axW, mapH], 'Tag', ['ax_' p '_' tagAlgo]);
        set(ax, 'XTick', [], 'YTick', [], 'Box', 'on', 'LineWidth', 2);
        disableDefaultInteractions(ax);
        colormap(ax, 'jet');
        mapAxes.(p) = ax;

        axH = uiaxes(t, 'Position', [10, 10, axW-10, histH], 'Tag', ['hist_' p '_' tagAlgo]);
        set(axH, 'Box', 'on', 'YTick', [], 'HitTest', 'on');
        disableDefaultInteractions(axH);
        mapHists.(p) = axH;

        % Colorbar (Outside only)
        cb = colorbar(ax);
        cb.Ticks = []; cb.Location = 'eastoutside'; cb.Units = 'pixels';
        axPos = ax.Position; cbW = 20; cbH = axPos(4) * 0.5;
        cbX = axPos(1) + axPos(3) + 10; cbY = axPos(2) + (axPos(4) - cbH)/2;
        cb.Position = [cbX, cbY, cbW, cbH];
        cb.Label.String = dNames{i};

        % Spinners (Aligned left to colorbar)
        spX = cbX;
        uilabel(t, 'Text', 'Max', 'Position', [spX, cbY + cbH + 28, 65, 20], 'HorizontalAlignment', 'left');
        spMax = uispinner(t, 'Position', [spX, cbY + cbH + 5, 65, 22], ...
            'ValueChangedFcn', @(src, ev) syncTabSpinners(tab, 'Max', src.Value));

        uilabel(t, 'Text', 'Min', 'Position', [spX, cbY - 45, 65, 20], 'HorizontalAlignment', 'left');
        spMin = uispinner(t, 'Position', [spX, cbY - 25, 65, 22], ...
            'ValueChangedFcn', @(src, ev) syncTabSpinners(tab, 'Min', src.Value));

        uilabel(t, 'Text', 'Bins:', 'Position', [axW + 15, 40, 40, 20]);
        spBins = uispinner(t, 'Limits', [2 1024], 'Value', 128, 'Position', [axW + 15, 15, 65, 22], ...
            'ValueChangedFcn', @(src, ev) syncTabSpinners(tab, 'Bins', src.Value));

        % Click-to-toggle axis labels
        ylabel(axH, 'Pixels', 'FontWeight', 'bold');
        axH.YLabel.ButtonDownFcn = @(src, ev) toggleHistYScale(src);
        xlabel(axH, dNames{i}, 'FontWeight', 'bold');
        axH.XLabel.ButtonDownFcn = @(src, ev) toggleHistXScale(src);

        mapSpins.(p).Max = spMax; mapSpins.(p).Min = spMin; mapSpins.(p).Bins = spBins;
    end

    % --- Results Tabs (Bottom 40%) ---
    resTabGroupH = hBot;
    resTabGroupW = metX - axL + 300;
    resTabGroup = uitabgroup(tab, 'Position', [axL, botY, resTabGroupW, resTabGroupH], 'Tag', ['resTabGroup_', tagAlgo]);
    tabRes = uitab(resTabGroup, 'Title', 'Analysis Results', 'Tag', ['tabRes_', tagAlgo]);
    uitab(resTabGroup, 'Title', 'Training Performance', 'Tag', ['tabTrain_', tagAlgo]);

    % Adjust to 5:1 ratio
    zH = round((resTabGroupH - 60) / 6);
    pixelH = zH * 5;
    groupW = 600;
    innerH = resTabGroup.Position(4);
    pixY = innerH - pixelH - 25;

    axStats = uiaxes(tabRes, 'Position', [10, pixY, groupW, pixelH]);
    axRes = uiaxes(tabRes, 'Position', [10, max(5, pixY - zH - 10), groupW, zH]);
    disableDefaultInteractions(axStats);
    disableDefaultInteractions(axRes);

    % --- ML Parameters Panel (Top 60%, Side-by-Side) ---
    paramPanel = uipanel(tab, 'Title', 'Machine Learning Parameters', 'Tag', 'paramPanelML', ...
        'Position', [metX, topY, 300, hTop]);

    uilabel(paramPanel, 'Text', 'Model Type:', 'Position', [10, 240, 100, 20]);
    uidropdown(paramPanel, 'Items', {'Random Forest', 'Neural Network', 'Custom ONNX'}, ...
        'Position', [110, 240, 170, 22], 'Tag', 'ddMLModel');

    uibutton(paramPanel, 'Text', 'LOAD MODEL', 'Position', [10, 180, 260, 30], ...
        'BackgroundColor', [0 0.45 0.74], 'FontColor', [1 1 1], 'FontWeight', 'bold');

    uilabel(paramPanel, 'Text', 'Feature Selection:', 'Position', [10, 140, 100, 20]);
    uicheckbox(paramPanel, 'Text', 'Intensity', 'Position', [10, 120, 100, 20], 'Value', 1);
    uicheckbox(paramPanel, 'Text', 'Gates1-32', 'Position', [120, 120, 100, 20], 'Value', 1);

    uibutton(paramPanel, 'Text', 'PREDICT', 'FontWeight', 'bold', 'Position', [10, 10, 120, 35], ...
        'BackgroundColor', [0.8 0 0], 'FontColor', [1 1 1], ...
        'ButtonPushedFcn', @(btn, ev) runMLAnalysis(fig, tab));
    uibutton(paramPanel, 'Text', 'TRAIN', 'Position', [140, 10, 120, 35]);

    % Metadata
    tabMeta = struct();
    tabMeta.mapTg = mapTg; tabMeta.mapAxes = mapAxes; tabMeta.mapHists = mapHists; tabMeta.mapSpins = mapSpins;
    tabMeta.axStats = axStats; tabMeta.axRes = axRes;
    tabMeta.activeChanIdx = activeChanIdx; tabMeta.algo = algo;

    % Initialize maps with placeholders based on best available data dimensions
    nY = 64; nX = 64;
    if isfield(data, 'currentData') && ~isempty(data.currentData)
        [nY, nX, ~, ~] = size(data.currentData);
    elseif isfield(data, 'RawData') && ~isempty(data.RawData)
        [nY, nX, ~, ~] = size(data.RawData);
    end
    for i = 1:numel(pNames)
        p = pNames{i};
        tabMeta.Maps.(p) = nan(nY, nX);
        ax = mapAxes.(p);
        hImg = imagesc(ax, tabMeta.Maps.(p));
        hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(fig, ev.IntersectionPoint);
        axis(ax, 'image');
    end
    tab.UserData = tabMeta;
else
    tabMeta = tab.UserData;
    tabMeta.activeChanIdx = activeChanIdx;
    tabMeta.algo = algo;
    tabMeta.lastBins = 128;
    tab.UserData = tabMeta;
end
end

function runMLAnalysis(fig, tab)
data = fig.UserData;
meta = tab.UserData;
% Dynamic Link
if isfield(data, 'navChannel'), activeChanIdx = data.navChannel;
else, activeChanIdx = meta.activeChanIdx; end
meta.activeChanIdx = activeChanIdx; tab.UserData = meta;

% Extract Data
RawData = getChannelData(fig, activeChanIdx);
if isempty(RawData)
    uialert(fig, 'No data available for analysis. Please load or generate data first.', 'Error');
    return;
end
RawData = double(RawData);
[nY, nX, ~] = size(RawData);

% Progress feedback
f = uiprogressdlg(fig, 'Title', 'Running ML Analysis', 'Message', 'Executing model...', 'Indeterminate', 'on');

try
    % Call skeletal ML backend
    MLResults = DTmachinelearning(RawData, data.config);

    % Populate Maps
    meta.Maps.Photons = MLResults.Photons;
    meta.Maps.TauAvg = MLResults.TauAvg;
    meta.Maps.Chi2 = MLResults.Chi2;

    % Save meta
    tab.UserData = meta;

    % Update all Map Displays
    pNames = fieldnames(meta.mapAxes);
    for i = 1:numel(pNames)
        p = pNames{i};
        ax = meta.mapAxes.(p);
        hImg = findobj(ax, 'Type', 'image');
        if isfield(meta.Maps, p)
            if isempty(hImg)
                hImg = imagesc(ax, meta.Maps.(p));
                hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(fig, ev.IntersectionPoint);
            else
                hImg.CData = meta.Maps.(p);
            end
            axis(ax, 'image');
            % Auto-scale CLim
            data_px = meta.Maps.(p)(~isnan(meta.Maps.(p)) & ~isinf(meta.Maps.(p)));
            if ~isempty(data_px)
                cmin = min(data_px); cmax = max(data_px);
                if cmin == cmax, cmax = cmin + 0.1; end
                set(ax, 'CLim', [cmin cmax]);
            end
        end
    end

    % Sync everything
    syncMapDisplay(tab);
    updatePixelAnalysis(fig, [nX/2, nY/2]);
catch ME
    uialert(fig, ['ML Analysis Failed: ' ME.message], 'Error');
end
close(f);
end

function createNewFitTab(fig, tab, algo, activeChanIdx)
data = fig.UserData;
config = data.config;
axL = data.axL;
axW = data.axW;
metX = data.metX;


if isempty(tab.UserData) || ~isfield(tab.UserData, 'mapAxes')
    % --- Vertical Layout Constants (60/40 Split) ---
    % Total usable area ~970px. Shift top 30px lower to 980.
    hTop = 580; hBot = 380;
    topY = 980 - hTop; % 400
    botY = 10;

    % --- Map Tab Group (Top 60%) ---
    mapH = 350; histH = 150;
    mapTgW = axW + 90;
    mapTgH = hTop;
    mapTgY = topY;

    tagAlgo = regexprep(algo, '[^a-zA-Z0-9]', '_');
    mapTg = uitabgroup(tab, 'Position', [axL, mapTgY, mapTgW, mapTgH], 'Tag', ['mapTg_', tagAlgo], ...
        'SelectionChangedFcn', @(src, ev) syncMapDisplay(tab));

    mapAxes = struct(); mapHists = struct(); mapSpins = struct();
    tabs = struct(); % Store tab handles
    pNames = {'Photons', 'TauAvg', 'Chi2', 'Back', 'Tau1', 'Frac1', 'Tau2', 'Frac2', 'Tau3', 'Frac3', 'Beta'};
    dNames = {'Photons', 'Tau Avg', 'Red. Chi2', 'Background', 'Tau 1', 'Frac 1', 'Tau 2', 'Frac 2', 'Tau 3', 'Frac 3', 'Beta'};

    for i = 1:numel(pNames)
        p = pNames{i};
        t = uitab(mapTg, 'Title', dNames{i}, 'Tag', ['tab_' p '_' tagAlgo]);
        tabs.(p) = t;

        % Map Axis
        ax = uiaxes(t, 'Position', [5, histH + 50, axW, mapH], 'Tag', ['ax_' p '_' tagAlgo]);
        set(ax, 'XTick', [], 'YTick', [], 'Box', 'on', 'LineWidth', 2);
        axis(ax, 'image'); axis(ax, 'tight');
        disableDefaultInteractions(ax); % Prevent mouse drag zoom/pan
        colormap(ax, 'jet');
        mapAxes.(p) = ax;

        % Colorbar (Outside only)
        cb = colorbar(ax);
        cb.Ticks = []; cb.Location = 'eastoutside'; cb.Units = 'pixels';
        axPos = ax.Position; cbW = 20; cbH = axPos(4) * 0.5;
        cbX = axPos(1) + axPos(3) + 10; cbY = axPos(2) + (axPos(4) - cbH)/2;
        cb.Position = [cbX, cbY, cbW, cbH];
        cb.Label.String = dNames{i};

        % Histogram Axis
        axH = uiaxes(t, 'Position', [10, 10, axW-10, histH], 'Tag', ['hist_' p '_' tagAlgo]);
        set(axH, 'Box', 'on', 'YTick', [], 'HitTest', 'on');
        disableDefaultInteractions(axH);
        mapHists.(p) = axH;

        % Repositioned Spinners (Left Aligned to colorbar)
        spX = cbX;
        uilabel(t, 'Text', 'Max', 'Position', [spX, cbY + cbH + 28, 65, 20], 'HorizontalAlignment', 'left');
        spMax = uispinner(t, 'Position', [spX, cbY + cbH + 5, 65, 22], 'Tag', ['spnCMax_' p], ...
            'ValueChangedFcn', @(src, ev) syncTabSpinners(tab, 'Max', src.Value, p));

        uilabel(t, 'Text', 'Min', 'Position', [spX, cbY - 45, 65, 20], 'HorizontalAlignment', 'left');
        spMin = uispinner(t, 'Position', [spX, cbY - 25, 65, 22], 'Tag', ['spnCMin_' p], ...
            'ValueChangedFcn', @(src, ev) syncTabSpinners(tab, 'Min', src.Value, p));

        uilabel(t, 'Text', 'Bins:', 'Position', [axW + 15, 40, 40, 20]);
        spBins = uispinner(t, 'Limits', [2 1024], 'Value', 128, 'Position', [axW + 15, 15, 65, 22], 'Tag', ['spnBins_' p], ...
            'ValueChangedFcn', @(src, ev) syncTabSpinners(tab, 'Bins', src.Value, p));

        % Click-to-toggle axis labels
        ylabel(axH, 'Pixels', 'FontWeight', 'bold');
        axH.YLabel.ButtonDownFcn = @(src, ev) toggleHistYScale(src);
        xlabel(axH, dNames{i}, 'FontWeight', 'bold');
        axH.XLabel.ButtonDownFcn = @(src, ev) toggleHistXScale(src);

        mapSpins.(p).Max = spMax;
        mapSpins.(p).Min = spMin;
        mapSpins.(p).Bins = spBins;
    end

    % --- Results Tabs (Bottom 40%, Spanning width) ---
    resTabGroupH = hBot;
    resTabGroupW = metX - axL + 375 - 60;
    resTabGroup = uitabgroup(tab, 'Position', [axL, botY, resTabGroupW, resTabGroupH], 'Tag', ['resTabGroup_', tagAlgo]);
    tabPixel = uitab(resTabGroup, 'Title', 'Analysis', 'Tag', ['tabPixel_', tagAlgo]);
    tabGT = uitab(resTabGroup, 'Title', 'Ground Truth', 'Tag', ['tabGT_', tagAlgo]);

    % Use 5:3 ratio for Pixel plot : Residuals (Residuals are 3x taller than previous 5:1 ratio)
    vUnit = (resTabGroupH - 80) / 8;
    zH = round(vUnit * 3);
    pixelH = round(vUnit * 5);
    groupW = resTabGroupW - 120;
    axesW = round(groupW * 0.75);

    % Start from bottom which is 0 inside tab (Moved 25px lower to avoid clipping)
    resY = 15;
    pixY = resY + zH + 20;

    axPix = uiaxes(tabPixel, 'Position', [10, pixY, axesW, pixelH]);
    axPixRes = uiaxes(tabPixel, 'Position', [10, resY, axesW, zH]);
    disableDefaultInteractions(axPix);
    disableDefaultInteractions(axPixRes);

    lblX = axesW + 30;

    uPixPos = uilabel(tabPixel, 'Text', 'Pos: --', 'FontWeight', 'bold', 'Position', [lblX, pixY + pixelH - 20, 150, 20]);
    uPixI0 = uilabel(tabPixel, 'Text', 'I0: --', 'FontWeight', 'bold', 'Position', [lblX, pixY + pixelH - 40, 150, 20], 'FontColor', [0 0.5 0]);
    uPixTau = uilabel(tabPixel, 'Text', 'Tau: --', 'FontWeight', 'bold', 'Position', [lblX, pixY + pixelH - 60, 150, 20]);

    uPixChi = uilabel(tabPixel, 'Text', 'Chi2: --', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 10, 150, 20]);
    uPixRE = uilabel(tabPixel, 'Text', 'R.E.: --%', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 30, 150, 20]);
    uPixRND = uilabel(tabPixel, 'Text', 'RND: --', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 50, 150, 20]);
    uPixBack = uilabel(tabPixel, 'Text', 'Bkg: --', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 70, 150, 20], 'FontSize', 9);

    uilabel(tabPixel, 'Text', 'Fit Range (Bins):', 'Position', [lblX, resY + zH - 95, 120, 20]);
    spnStart = uispinner(tabPixel, 'Limits', [1 config.N_gates], 'Value', 1, 'Position', [lblX, resY + zH - 120, 50, 22], ...
        'ValueChangedFcn', @(src, ev) updatePixelAnalysis(fig, [nan nan]));
    spnEnd = uispinner(tabPixel, 'Limits', [1 config.N_gates], 'Value', config.N_gates, 'Position', [lblX+70, resY + zH - 120, 50, 22], ...
        'ValueChangedFcn', @(src, ev) updatePixelAnalysis(fig, [nan nan]));

    % Ground Truth Tab content
    axStats = uiaxes(tabGT, 'Position', [10, pixY, axesW, pixelH]);
    axRes = uiaxes(tabGT, 'Position', [10, resY, axesW, zH]);
    disableDefaultInteractions(axStats);
    disableDefaultInteractions(axRes);
    uGT_I0 = uilabel(tabGT, 'Text', 'I0: --', 'FontWeight', 'bold', 'Position', [lblX, pixY + pixelH - 40, 150, 20], 'FontColor', [0 0.5 0]);
    uChi = uilabel(tabGT, 'Text', 'Chi2: --', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 10, 150, 20]);
    uRE = uilabel(tabGT, 'Text', 'R.E.: --%', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 30, 150, 20]);
    uRND = uilabel(tabGT, 'Text', 'RND: --', 'FontWeight', 'bold', 'Position', [lblX, resY + zH - 50, 150, 20]);

    % --- Analysis Parameters Panel (Top 60%, Side-by-Side) ---
    paramPanel = uipanel(tab, 'Title', 'Analysis Parameters', 'Tag', 'paramPanel', ...
        'Position', [metX - 60, topY, 375, hTop]);
    % Top reaches 980 (topY + hTop), resolving clipping.

    leftMargin = 30; % 10 + 20
    currY = hTop - 35;

    % 1. Decay Model Selector
    uilabel(paramPanel, 'Text', 'Decay Model:', 'Position', [leftMargin, currY, 100, 20]);
    ddModel = uidropdown(paramPanel, 'Items', {'Multiexponential decay', 'Stretched exponentials'}, ...
        'Position', [leftMargin + 100, currY, 170, 22], 'Tooltip', 'Select model');

    currY = currY - 45;
    % 2. Equation Label
    lblEquation = uilabel(paramPanel, 'Text', '', 'Position', [10, currY, 355, 45], ...
        'Interpreter', 'tex', 'HorizontalAlignment', 'center', 'FontSize', 12);

    currY = currY - 35;
    % 3. IRF Source Dropdown
    uilabel(paramPanel, 'Text', 'IRF Source:', 'Position', [leftMargin, currY, 100, 20]);
    ddIRF = uidropdown(paramPanel, 'Items', {'Estimated', 'Experimental', 'Simulated'}, ...
        'Value', 'Estimated', 'Position', [leftMargin + 100, currY, 170, 22], 'Tag', 'ddIRF');

    currY = currY - 22;
    % 4. IRF Usage Explanation
    lblIRFExpl = uilabel(paramPanel, 'Text', '-', 'Position', [leftMargin, currY, 315, 20], ...
        'FontSize', 8, 'FontColor', [0.4 0.4 0.4], 'Interpreter', 'tex', 'Tag', 'lblIRFExpl');

    currY = currY - 25;
    uilabel(paramPanel, 'Text', 'IRF FWHM (ns):', 'Position', [leftMargin, currY, 100, 20], 'FontSize', 10);
    lblIRFFWHM = uilabel(paramPanel, 'Text', '--', 'Position', [leftMargin + 100, currY, 170, 20], 'Tag', 'lblIRFFWHM', 'FontWeight', 'bold');

    currY = currY - 18;
    uilabel(paramPanel, 'Text', 'IRF Pos (ns):', 'Position', [leftMargin, currY, 100, 20], 'FontSize', 10);
    lblIRFPos = uilabel(paramPanel, 'Text', '--', 'Position', [leftMargin + 100, currY, 170, 20], 'Tag', 'lblIRFPos', 'FontWeight', 'bold');

    currY = currY - 30;
    % 5. Anscombe Transform
    chkAnscombe = uicheckbox(paramPanel, 'Text', 'Anscombe Transform', 'Position', [leftMargin, currY, 200, 22], ...
        'Tag', 'chkAnscombe');

    currY = currY - 35;
    % 6. Background
    uilabel(paramPanel, 'Text', 'Background:', 'Position', [leftMargin, currY, 80, 20]);
    spnBack = uispinner(paramPanel, 'Value', 0, 'Limits', [0 1e6], 'Position', [leftMargin + 95, currY, 65, 22]);
    chkFBack = uicheckbox(paramPanel, 'Text', '', 'Position', [leftMargin + 165, currY, 20, 22], 'Tag', 'chkFBack');
    chkGBack = uicheckbox(paramPanel, 'Text', '', 'Position', [leftMargin + 190, currY, 20, 22], 'Tag', 'chkGBack');
    uilabel(paramPanel, 'Text', 'F G', 'Position', [leftMargin + 165, currY + 18, 50, 15], 'FontSize', 8);

    % Update currY for pnlParams (Components and all components)
    currY = currY - 20;
    pnlParamsH = currY - 50;
    pnlParams = uipanel(paramPanel, 'BorderType', 'none', 'Position', [leftMargin, 60, 335, pnlParamsH]);

    % --- Multi-Exponential Panel ---
    pnlMultiExp = uipanel(pnlParams, 'BorderType', 'none', 'Position', [0, 60, 335, 210], 'Tag', 'pnlMultiExp');

    % Components Spinner & Checkbox
    uilabel(pnlMultiExp, 'Text', 'Components:', 'Position', [0, 185, 80, 20]);
    spnNExp = uispinner(pnlMultiExp, 'Limits', [1 3], 'Value', 1, 'Position', [85, 185, 45, 22], ...
        'Tooltip', 'Number of exponential components to fit (1-3).');
    chkNeg = uicheckbox(pnlMultiExp, 'Text', 'N', 'Position', [145, 185, 30, 22], ...
        'Tooltip', 'Allow negative coefficients.', 'FontSize', 9);

    % Spinner Width logic: 105 * 0.6 = 63 -> 65 px
    spW = 65;
    alphaX = 20 + spW + 55; % 20 + 65 + 55 = 140

    % Column Headers for Parameters
    % Col 1 (Tau): Start ~20. Width 65.
    % Col 2 (Alpha): Start ~140. Width 65.
    uilabel(pnlMultiExp, 'Text', '$\tau$ (ns)', 'Position', [20, 160, spW, 20], 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'Interpreter', 'latex');
    uilabel(pnlMultiExp, 'Text', 'F G', 'Position', [20+spW+5, 160, 40, 20], 'FontWeight', 'bold', 'FontSize', 9);

    uilabel(pnlMultiExp, 'Text', '$\alpha$ (%)', 'Position', [alphaX, 160, spW, 20], 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'Interpreter', 'latex');
    uilabel(pnlMultiExp, 'Text', 'F G', 'Position', [alphaX+spW+5, 160, 40, 20], 'FontWeight', 'bold', 'FontSize', 9);

    % Row Y positions
    y1 = 125; y2 = 100; y3 = 75;

    % Comp 1
    uilabel(pnlMultiExp, 'Text', '1:', 'Position', [0, y1, 15, 20], 'FontWeight', 'bold');
    spnTau1 = uispinner(pnlMultiExp, 'Value', 1.0, 'Position', [20, y1, spW, 22]);
    chkFTau1 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [20+spW+5, y1, 15, 22], 'Tag', 'chkFTau1');
    chkGTau1 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [20+spW+20, y1, 15, 22], 'Tag', 'chkGTau1');

    spnFrac1 = uispinner(pnlMultiExp, 'Value', 100, 'Position', [alphaX, y1, spW, 22], 'Editable', 'off');
    chkFFrac1 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [alphaX+spW+5, y1, 15, 22], 'Tag', 'chkFFrac1', 'Enable', 'off');
    chkGFrac1 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [alphaX+spW+20, y1, 15, 22], 'Tag', 'chkGFrac1', 'Enable', 'off');

    % Comp 2
    lblComp2 = uilabel(pnlMultiExp, 'Text', '2:', 'Position', [0, y2, 15, 20], 'Visible', 'off', 'FontWeight', 'bold');
    spnTau2 = uispinner(pnlMultiExp, 'Value', 2.0, 'Position', [20, y2, spW, 22], 'Visible', 'off');
    chkFTau2 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [20+spW+5, y2, 15, 22], 'Visible', 'off', 'Tag', 'chkFTau2');
    chkGTau2 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [20+spW+20, y2, 15, 22], 'Visible', 'off', 'Tag', 'chkGTau2');

    spnFrac2 = uispinner(pnlMultiExp, 'Value', 0, 'Position', [alphaX, y2, spW, 22], 'Visible', 'off');
    chkFFrac2 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [alphaX+spW+5, y2, 15, 22], 'Visible', 'off', 'Tag', 'chkFFrac2');
    chkGFrac2 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [alphaX+spW+20, y2, 15, 22], 'Visible', 'off', 'Tag', 'chkGFrac2');

    % Comp 3
    lblComp3 = uilabel(pnlMultiExp, 'Text', '3:', 'Position', [0, y3, 15, 20], 'Visible', 'off', 'FontWeight', 'bold');
    spnTau3 = uispinner(pnlMultiExp, 'Value', 0.5, 'Position', [20, y3, spW, 22], 'Visible', 'off');
    chkFTau3 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [20+spW+5, y3, 15, 22], 'Visible', 'off', 'Tag', 'chkFTau3');
    chkGTau3 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [20+spW+20, y3, 15, 22], 'Visible', 'off', 'Tag', 'chkGTau3');

    spnFrac3 = uispinner(pnlMultiExp, 'Value', 0, 'Position', [alphaX, y3, spW, 22], 'Visible', 'off');
    chkFFrac3 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [alphaX+spW+5, y3, 15, 22], 'Visible', 'off', 'Tag', 'chkFFrac3');
    chkGFrac3 = uicheckbox(pnlMultiExp, 'Text', '', 'Position', [alphaX+spW+20, y3, 15, 22], 'Visible', 'off', 'Tag', 'chkGFrac3');

    % Logic for Negative Exponentials and Alpha 1
    updateAlpha1State = @(src, ev) set([chkFFrac1, chkGFrac1], 'Enable', ...
        string(matlab.lang.OnOffSwitchState(src.Value)));
    chkNeg.ValueChangedFcn = updateAlpha1State;

    % Fraction logic
    updateFrac = @(~,~) set(spnFrac1, 'Value', max(0, min(100, 100 - (spnFrac2.Value + spnFrac3.Value))));
    spnFrac2.ValueChangedFcn = updateFrac;
    spnFrac3.ValueChangedFcn = updateFrac;

    % --- Stretched Exponential Panel ---
    pnlStretchedExp = uipanel(pnlParams, 'BorderType', 'none', 'Position', [0, 60, 335, 210], 'Visible', 'off');
    uilabel(pnlStretchedExp, 'Text', 'Base $\tau$ (ns):', 'Position', [0, 125, 90, 20], 'Interpreter', 'latex');
    spnSTau = uispinner(pnlStretchedExp, 'Value', 1.0, 'Step', 0.1, 'Position', [95, 125, spW, 22]);
    chkFSTau = uicheckbox(pnlStretchedExp, 'Text', '', 'Position', [95+spW+5, 125, 20, 22], 'Tag', 'chkFSTau');
    chkGSTau = uicheckbox(pnlStretchedExp, 'Text', '', 'Position', [95+spW+30, 125, 20, 22], 'Tag', 'chkGSTau');

    uilabel(pnlStretchedExp, 'Text', '$\beta$ Factor:', 'Position', [0, 100, 90, 20], 'Interpreter', 'latex');
    spnBeta = uispinner(pnlStretchedExp, 'Value', 0.8, 'Limits', [0.1 1.0], 'Step', 0.05, 'Position', [95, 100, spW, 22]);
    chkFBeta = uicheckbox(pnlStretchedExp, 'Text', '', 'Position', [95+spW+5, 100, 20, 22], 'Tag', 'chkFBeta');
    chkGBeta = uicheckbox(pnlStretchedExp, 'Text', '', 'Position', [95+spW+30, 100, 20, 22], 'Tag', 'chkGBeta');

    pnlStretchedExp.Visible = 'off';

    % Callbacks & Buttons located at bottom of paramPanel
    ddModel.ValueChangedFcn = @(src, ev) onModelChange(src, pnlMultiExp, pnlStretchedExp, tab, lblEquation);
    spnNExp.ValueChangedFcn = @(src, ev) setComponentVisibility(src, ...
        {lblComp2, spnTau2, spnFrac2, chkFTau2, chkGTau2, chkFFrac2, chkGFrac2}, ...
        {lblComp3, spnTau3, spnFrac3, chkFTau3, chkGTau3, chkFFrac3, chkGFrac3}, tab, lblEquation);

    % Attach equation updater to checkboxes (Tau, Frac, etc.)
    chkAll = {chkFTau1, chkGTau1, chkFFrac1, chkGFrac1, ...
        chkFTau2, chkGTau2, chkFFrac2, chkGFrac2, ...
        chkFTau3, chkGTau3, chkFFrac3, chkGFrac3, ...
        chkFSTau, chkGSTau, chkFBeta, chkGBeta, chkFBack, chkGBack};
    for k=1:numel(chkAll)
        chkAll{k}.ValueChangedFcn = @(src, ev) updateEquationDisplay(tab, lblEquation);
    end

    uibutton(paramPanel, 'Text', 'Analyse', 'FontWeight', 'bold', 'Position', [leftMargin, 10, 80, 35], ...
        'BackgroundColor', [0.8 0 0], 'FontColor', [1 1 1], 'ButtonPushedFcn', @(btn, ev) runFitAnalysis(fig, tab), ...
        'Tooltip', 'Run Analysis on Active Channel.');

    uibutton(paramPanel, 'Text', 'Analyse All', 'FontWeight', 'bold', 'Position', [leftMargin+85, 10, 80, 35], ...
        'BackgroundColor', [0.6 0 0], 'FontColor', [1 1 1], 'ButtonPushedFcn', @(btn, ev) runFitAnalysisAll(fig, tab), ...
        'Tooltip', 'Run Analysis on ALL Channels.');

    uibutton(paramPanel, 'Text', 'Batch', 'FontWeight', 'bold', 'Position', [leftMargin+235, 10, 60, 35], ...
        'BackgroundColor', [0.2 0.3 0.6], 'FontColor', [1 1 1], 'ButtonPushedFcn', @(~,~) runBatchAnalysis(fig, tab), ...
        'Tooltip', 'Run Analysis on all files in current group.');
    uibutton(paramPanel, 'Text', 'Limits', 'Position', [leftMargin+300, 10, 60, 35], 'ButtonPushedFcn', @(~,~) openLimitDialog(fig), ...
        'Tooltip', 'Set parameter limits.');

    % Assemble tabMeta
    tabMeta = struct();
    tabMeta.mapTg = mapTg; tabMeta.mapAxes = mapAxes; tabMeta.mapHists = mapHists; tabMeta.mapSpins = mapSpins;
    tabMeta.tabs = tabs; % Store tab references

    % Pixel Analysis Handles
    tabMeta.axPix = axPix;
    tabMeta.axPixRes = axPixRes;
    tabMeta.uPixPos = uPixPos;
    tabMeta.uPixI0 = uPixI0;
    tabMeta.uPixTau = uPixTau;
    tabMeta.uPixChi = uPixChi;
    tabMeta.uPixRE = uPixRE;
    tabMeta.uPixRND = uPixRND;
    tabMeta.uPixBack = uPixBack;

    % Ground Truth Handles
    tabMeta.axStats = axStats;
    tabMeta.axRes = axRes; % Was axStatsRes
    tabMeta.uGT_I0 = uGT_I0;
    tabMeta.uChi = uChi; % Was uGT_Chi
    tabMeta.uRE = uRE;   % Was uGT_RE
    tabMeta.uRND = uRND;

    % IRF & Controls
    tabMeta.lblIRFFWHM = lblIRFFWHM;
    tabMeta.lblIRFPos = lblIRFPos;
    tabMeta.spnStart = spnStart;
    tabMeta.spnEnd = spnEnd;

    % Initialize Multi-Channel Maps Storage
    tabMeta.ChanMaps = cell(1, 4);
    tabMeta.ChanIRFs = cell(1, 4);
    tabMeta.activeChanIdx = activeChanIdx;
    tabMeta.ddModel = ddModel; tabMeta.spnNExp = spnNExp; tabMeta.chkNegExp = chkNeg;
    tabMeta.spnTau1 = spnTau1; tabMeta.spnFrac1 = spnFrac1;
    tabMeta.chkFTau1 = chkFTau1; tabMeta.chkFFrac1 = chkFFrac1; % Store handles for logic check

    tabMeta.spnTau2 = spnTau2; tabMeta.spnFrac2 = spnFrac2;
    tabMeta.chkFTau2 = chkFTau2; tabMeta.chkFFrac2 = chkFFrac2;

    tabMeta.spnTau3 = spnTau3; tabMeta.spnFrac3 = spnFrac3;
    tabMeta.chkFTau3 = chkFTau3; tabMeta.chkFFrac3 = chkFFrac3;
    tabMeta.ddIRF = ddIRF; tabMeta.lblIRFExpl = lblIRFExpl;
    tabMeta.lblIRFFWHM = lblIRFFWHM; tabMeta.lblIRFPos = lblIRFPos;
    tabMeta.spnSTau = spnSTau; tabMeta.spnBeta = spnBeta;
    tabMeta.chkFSTau = chkFSTau; tabMeta.chkFBeta = chkFBeta; % Needed for equation color
    tabMeta.spnBack = spnBack;
    tabMeta.chkFBack = chkFBack;
    tabMeta.chkAnscombe = chkAnscombe;

    tabMeta.activeChanIdx = activeChanIdx; tabMeta.algo = algo;

    % Initialize maps with placeholders based on best available data dimensions
    nY = 64; nX = 64;
    if isfield(data, 'currentData') && ~isempty(data.currentData)
        [nY, nX, ~, ~] = size(data.currentData);
    elseif isfield(data, 'RawData') && ~isempty(data.RawData)
        [nY, nX, ~, ~] = size(data.RawData);
    end
    for i = 1:numel(pNames)
        p = pNames{i};
        tabMeta.Maps.(p) = nan(nY, nX);
        ax = mapAxes.(p);
        hImg = imagesc(ax, tabMeta.Maps.(p));
        hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(fig, ev.IntersectionPoint);
        axis(ax, 'image');
        cb = colorbar(ax);
        cb.Ticks = []; cb.Location = 'eastoutside'; cb.Units = 'pixels';
        axPos = ax.Position; cbW = 20; cbH = axPos(4) * 0.5;
        cbX = axPos(1) + axPos(3) + 10; cbY = axPos(2) + (axPos(4) - cbH)/2;
        cb.Position = [cbX, cbY, cbW, cbH];
        cb.Label.String = dNames{i};
    end

    % --- Initial Updates ---
    % Store handle in metadata first
    tabMeta.lblEquation = lblEquation;

    % Update equation immediately to show default state
    % (We need tab.UserData to be set for the helper to work)
    tab.UserData = tabMeta;
    updateEquationDisplay(tab, lblEquation);

    % Handle IRF Explanation and Pixel plot update
    updateIRFUI = @(~,~) handleIRFChange(fig, tab, lblIRFExpl, algo, ddIRF.Value);
    ddIRF.ValueChangedFcn = updateIRFUI;
    updateIRFUI([], []);

    % Update visibility after metadata is set
    updateTabVisibility(tab);
else % Tab already exists, just update metadata
    tabMeta = tab.UserData; % Retrieve existing metadata
    tabMeta.algo = algo;
    tabMeta.activeChanIdx = activeChanIdx;

    % Update limits if config changed
    if isfield(tabMeta, 'spnStart') && isgraphics(tabMeta.spnStart)
        tabMeta.spnStart.Limits = [1 config.N_gates];
        tabMeta.spnEnd.Limits = [1 config.N_gates];
    end
    tab.UserData = tabMeta;
end

% Clean Stats/Residuals as no data
axStats = tabMeta.axStats;
axRes = tabMeta.axRes;
cla(axStats); title(axStats, 'Statistics (No Analysis)');
cla(axRes); title(axRes, 'Residuals (No Analysis)');

% Show initial pixel data (default center pixel)
updatePixelAnalysis(fig, [nX/2, nY/2]);
end


function runFitAnalysis(fig, tab, ~)
try
    data = fig.UserData;
    dFlow = flows_getData(fig);
    meta = tab.UserData;
    if isempty(meta), return; end

    % Configuration retrieval (Prioritize navigated file in Unified Flow)
    config = data.config;
    if isfield(dFlow, 'navGroup') && isfield(dFlow, 'navFile') && isfield(dFlow, 'Conditions') && ~isempty(dFlow.Conditions)
        try
            cIdx = dFlow.navGroup; fIdx = dFlow.navFile;
            if cIdx <= numel(dFlow.Conditions) && fIdx <= numel(dFlow.Conditions{cIdx}.Analysis)
                if isfield(dFlow.Conditions{cIdx}.Analysis(fIdx), 'Config')
                    fileCfg = dFlow.Conditions{cIdx}.Analysis(fIdx).Config;
                    if ~isempty(fileCfg), config = fileCfg; end
                end
            end
        catch
        end
    end

    % Data retrieval
    activeChanIdx = 1;
    if isfield(dFlow, 'navChannel'), activeChanIdx = dFlow.navChannel;
    elseif isfield(data, 'navChannel'), activeChanIdx = data.navChannel; end

    RawData = double(getChannelData(fig, activeChanIdx));
    if isempty(RawData)
        uialert(fig, 'No data available for analysis in current channel.', 'Error');
        return;
    end
    [nY, nX, nGates] = size(RawData);

    % Background handling
    backVal = 0; if isfield(meta, 'spnBack') && isgraphics(meta.spnBack), backVal = meta.spnBack.Value; end
    fitData = RawData - (backVal / nGates);
    fitData(fitData < 0) = 0;

    % Fitting parameters
    irf_shift = 0; if isfield(config, 'irf_shift'), irf_shift = config.irf_shift / 1000; end
    bWrap = false; if isfield(config, 'bWrap'), bWrap = config.bWrap; end
    dead_time = 0; if isfield(config, 'dead_time'), dead_time = config.dead_time; end

    % Fit Range
    start_gate = 1; end_gate = nGates;
    if isfield(meta, 'spnStart') && isgraphics(meta.spnStart), start_gate = meta.spnStart.Value; end
    if isfield(meta, 'spnEnd') && isgraphics(meta.spnEnd), end_gate = meta.spnEnd.Value; end

    % Models and Execution
    algo = meta.algo; numExp = 1; if isfield(meta, 'spnNExp') && isgraphics(meta.spnNExp), numExp = meta.spnNExp.Value; end

    % Prep Gate Functions for DTpmod
    % Prep Gate Functions for DTpmod
    % Ensure simulation time resolution and gates match actual data dimensions
    dt = config.dt; T = config.T;

    % If data has different N_gates than config, we must adapt simulation to data
    if isempty(config.gate_edges) || numel(config.gate_edges) ~= nGates + 1
        % Recalculate basic linear gates for this data size
        gate_edges = linspace(0, T, nGates + 1);
    else
        gate_edges = config.gate_edges;
    end

    t = 0:dt:T;
    gate_profiles = DTgates(t, config.r, gate_edges);

    % Safety check: DTgates might return different size if T/dt/edges not aligned?
    if size(gate_profiles, 1) ~= nGates
        % Fallback if DTgates logic differs
        % For now, trust DTgates but let's be explicit
    end

    gate_interp_fns = cell(nGates, 1);
    for i = 1:nGates
        % Safe indexing
        if i <= size(gate_profiles, 1)
            gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
        else
            % Should not happen if edges set correctly
            error('Mismatch between Data Gates (%d) and Simulation Gates (%d).', nGates, size(gate_profiles, 1));
        end
    end

    [irf_custom, ~] = getIRFFromSource(fig, tab, RawData);

    if strcmpi(algo, 'Grid MLE')
        tau_grid = linspace(0.1, 10, 100);
        P_model_grid = DTpmod(nGates, tau_grid, t, gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma, ...
            irf_shift, bWrap, dead_time, irf_custom);
        flatData = reshape(fitData, nY*nX, nGates)';
        [tau_est_flat, ~] = DTmle(sum(flatData,1), flatData, tau_grid, P_model_grid, fig, start_gate, end_gate);
        Results.Tau1 = reshape(tau_est_flat, nY, nX);
        Results.Frac1 = repmat(100, nY, nX);
    elseif strcmpi(algo, 'Tail Fitting')
        [Results.Tau1, ~] = DTtailfit(fitData, config, start_gate, end_gate);
        Results.Frac1 = repmat(100, nY, nX);
    else
        [Results, ~] = DTiterative(fitData, config, fig, start_gate, end_gate, numExp, irf_custom);
    end

    % Post-process Results
    if isfield(Results, 'Tau1'), meta.Maps.TauAvg = Results.Tau1; end
    if isfield(Results, 'Tau1'), meta.Maps.Tau1 = Results.Tau1; end
    if isfield(Results, 'Frac1'), meta.Maps.Frac1 = Results.Frac1; end
    meta.Maps.Photons = sum(RawData, 3);

    tab.UserData = meta;
    syncMapDisplay(tab);
    drawnow;
catch ME
    uialert(fig, ['Analysis Error: ' ME.message], 'Error');
    rethrow(ME);
end
end

function createNewPatternTab(fig, t, activeChanIdx)
% Logic cleanup
delete(t.Children);

try
    data = fig.UserData;
    if (isempty(data.RawData) && (~isfield(data, 'currentData') || isempty(data.currentData)))
        uialert(fig, 'No data found. Please load or generate data first.', 'Error');
        return;
    end

    % Get dimensions from any available source
    nY = 64; nX = 64; % Default values
    if isfield(data, 'currentData') && ~isempty(data.currentData), [nY, nX, ~, ~] = size(data.currentData);
    elseif isfield(data, 'RawData') && ~isempty(data.RawData), [nY, nX, ~, ~] = size(data.RawData); end

    % Layout
    mainGrid = uigridlayout(t, [2 2]);
    mainGrid.ColumnWidth = {'1x', 340};
    mainGrid.RowHeight = {'1x', '1x'};
    mainGrid.Padding = [10 10 10 10];

    % Top Left: DDM
    axDDM = uiaxes(mainGrid); axDDM.Tag = 'axDDM';
    title(axDDM, 'Decay Diversity Map');
    xlabel(axDDM, 'Mean \tau (ns)'); ylabel(axDDM, 'Heterogeneity (ns)');
    grid(axDDM, 'on'); box(axDDM, 'on');

    % Bottom Left: RGB Fit
    axFit = uiaxes(mainGrid); axFit.Tag = 'axFit';
    title(axFit, 'Pattern Match RGB');
    set(axFit, 'XTick', [], 'YTick', []);

    % Right panel for controls
    pnl = uipanel(mainGrid, 'Title', 'Pattern Management');
    pnl.Layout.Row = [1 2]; pnl.Layout.Column = 2;
    cGrid = uigridlayout(pnl, [9 1]); % Adjusted row count for new buttons
    cGrid.RowHeight = {'1x', 30, 30, 30, 30, 30, 30, 30, 30}; % Flexible for listbox, fixed for buttons

    uilabel(cGrid, 'Text', 'Defined Patterns:', 'FontWeight', 'bold');
    lbPatterns = uilistbox(cGrid, 'Items', {}, 'Tag', 'lbPatterns');
    lbPatterns.Layout.Row = [1 4]; % Span multiple rows for the listbox

    uibutton(cGrid, 'Text', 'Draw ROI & Add Pattern', 'ButtonPushedFcn', @(~,~) addPatternROI(fig, 'poly'));
    uibutton(cGrid, 'Text', 'Delete Selected', 'ButtonPushedFcn', @(~,~) deletePattern(fig));
    uibutton(cGrid, 'Text', 'Save Library', 'ButtonPushedFcn', @(~,~) savePatternLibrary(fig));
    uibutton(cGrid, 'Text', 'Load Library', 'ButtonPushedFcn', @(~,~) loadPatternLibrary(fig));

    % Checkbox Anscombe (re-added)
    chkAns = uicheckbox(cGrid, 'Text', 'Anscombe Transform', ...
        'Tooltip', 'Apply 2*sqrt(x + 3/8) to stabilize variance before fitting.', ...
        'Tag', 'chkAnscombe');

    uibutton(cGrid, 'Text', 'RUN FIT', 'FontWeight', 'bold', 'BackgroundColor', [0.8 0 0], 'FontColor', [1 1 1], ...
        'ButtonPushedFcn', @(~,~) runPatternFit(fig)); % Changed to runPatternFit

    uibutton(cGrid, 'Text', 'Batch Analysis', 'FontWeight', 'bold', 'BackgroundColor', [0.2 0.3 0.6], 'FontColor', 'white', ...
        'ButtonPushedFcn', @(~,~) runBatchAnalysis(fig, t));

    % Meta
    tabMeta = struct('algo', 'Pattern Matching', 'activeChanIdx', activeChanIdx);
    tabMeta.axDDM = axDDM; tabMeta.axFit = axFit; tabMeta.lbPatterns = lbPatterns;
    tabMeta.patterns = struct('name', {}, 'color', {}, 'decay', {}, 'roi', {});
    tabMeta.ddm_scatter = [];
    tabMeta.chkAnscombe = chkAns;
    tabMeta.nX = nX; tabMeta.nY = nY; % Store dimensions

    % Multi-channel support
    if ~isfield(tabMeta, 'ChanMaps'), tabMeta.ChanMaps = cell(1, 4); end
    if ~isfield(tabMeta, 'ChanIRFs'), tabMeta.ChanIRFs = cell(1, 4); end
    if ~isfield(tabMeta, 'Maps'), tabMeta.Maps = struct(); end % Initialize Maps struct

    t.UserData = tabMeta;

    % -- Initialize DDM Data (One time calc) --
    % We interpret this as LiMA moments: Mean Tau vs Sigma
    % Use the data for the active channel extracted at the beginning of the function
    RawData = getChannelData(fig, activeChanIdx);
    [limaResults, ~] = DTlima(RawData, data.config, 1, []); % Call with empty fig to suppress waiting

    if isstruct(limaResults) && isfield(limaResults, 'mu_tau') && isfield(limaResults, 'sigma_tau')
        tabMeta.mu_flat = limaResults.mu_tau(:);
        tabMeta.sig_flat = limaResults.sigma_tau(:);
    else
        error('DTlima failed to return valid results struct for DDM.');
    end
    t.UserData = tabMeta; % Update meta with DDM data

    % Initial Plot
    plotDDM(fig);

catch ME
    uialert(fig, ME.message, 'Pattern Creator Error');
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
RawData = getChannelData(fig, activeChanIdx);

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [~, ~, nGates] = size(RawData);
    mask3D = repmat(mask, 1, 1, nGates);
    RawData(mask3D) = 0;
else
    [~, ~, nGates] = size(RawData);
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

function runFitAnalysisAll(fig, tab)
% Helper to run analysis for all available channels
data = fig.UserData;
if isempty(data) || ~isfield(data, 'RawData'), return; end
nC = size(data.RawData, 4);

currentChan = 1;
if isfield(tab.UserData, 'activeChanIdx'), currentChan = tab.UserData.activeChanIdx; end

d = uiprogressdlg(fig, 'Title', 'Analysing All Channels', 'Message', 'Starting...', 'Indeterminate', 'off');

for c = 1:nC
    d.Value = (c-1)/nC;
    d.Message = sprintf('Processing Channel %d...', c);

    % Ideally we should be able to set the tab's active channel context temporarily
    % but runFitAnalysis relies on tab.UserData.activeChanIdx.
    % So we update it, run, then restore.
    % BUT: changing activeChanIdx changes where results are stored if results are channel-specific?
    % Currently results map to tab.UserData.Maps. If we want separate results per channel,
    % we need separate Map storage in the tab UserData per channel, e.g. meta.ChanMaps{c}.

    % Given current architecture, 'Analyse' usually overwrites 'Maps'.
    % If user wants to keep results, we need 'Grid MLE - Ch1', 'Grid MLE - Ch2' etc. tabs?
    % OR we store multi-channel results in one tab.

    % SIMPLIFICATION: Update the tab context to channel 'c', run analysis.
    % The results will overwrite the current view.
    % Wait... if we overwrite, we lose previous.
    % Recommendation: We should store results in a struct array in UserData?
    % For now, let's just loop and run, assuming the user is watching or saving.
    % Actually, without structural change to store N channels of maps, 'Analyse All'
    % effectively leaves the last channel data visible.
    % Let's implement activeChanIdx switching so at least the computation happens correctly per channel.

    % NOTE: To support true independent analysis storage, a deeper refactor of 'tab.UserData' is needed.
    % For now, we will perform the analysis sequentially.

    tab.UserData.activeChanIdx = c;
    tab.UserData.activeChanIdx = c;
    % Swap Maps before running
    meta = tab.UserData;
    if c <= numel(meta.ChanMaps) && ~isempty(meta.ChanMaps{c})
        meta.Maps = meta.ChanMaps{c};
    else
        % Reset Maps if empty
        if isfield(meta, 'Maps')
            pNames = fieldnames(meta.Maps);
            for i = 1:numel(pNames)
                meta.Maps.(pNames{i}) = zeros(size(meta.Maps.(pNames{i})));
            end
        end
        meta.irf_data = [];
    end
    tab.UserData = meta;

    runFitAnalysis(fig, tab, true);

    % Save back results
    meta = tab.UserData;
    meta.ChanMaps{c} = meta.Maps;
    if isfield(meta, 'irf_data'), meta.ChanIRFs{c} = meta.irf_data; end
    tab.UserData = meta;
end

% Restore original channel or leave at last?
tab.UserData.activeChanIdx = currentChan;

% Refresh view for current channel
meta = tab.UserData;
if currentChan <= numel(meta.ChanMaps) && ~isempty(meta.ChanMaps{currentChan})
    meta.Maps = meta.ChanMaps{currentChan};
    tab.UserData = meta;
end
updatePixelAnalysis(fig, [nan nan]);
close(d);
end

function onDataTabChange(fig)
try
    fprintf('Triggered onDataTabChange\n');
    % Update Analysis context when Data Channel Tab changes
    dtg = findobj(fig, 'Tag', 'dataTabGroup');
    if isempty(dtg), return; end

    % 1-based index of selected data tab corresponds to channel index
    newC = find(dtg.Children == dtg.SelectedTab, 1);
    if isempty(newC), return; end

    % Update ALL analysis tabs to this new channel context
    ats = findobj(fig, 'Tag', 'analysisTabs');
    if ~isempty(ats)
        for k = 1:numel(ats.Children)
            t = ats.Children(k);
            if isstruct(t.UserData)
                meta = t.UserData;
                oldC = meta.activeChanIdx;

                % Save Current to Old Channel Slot
                if isfield(meta, 'Maps')
                    meta.ChanMaps{oldC} = meta.Maps;
                    if isfield(meta, 'irf_data'), meta.ChanIRFs{oldC} = meta.irf_data; end
                end

                % Load New Channel Slot (if exists)
                if newC <= numel(meta.ChanMaps) && ~isempty(meta.ChanMaps{newC})
                    meta.Maps = meta.ChanMaps{newC};
                    if ~isempty(meta.ChanIRFs{newC})
                        meta.irf_data = meta.ChanIRFs{newC};
                        % Also update ddIRF if needed? (optional, source choice might be global)
                    end
                else
                    % Reset Maps if visiting channel for first time?
                    if isfield(meta, 'Maps')
                        pNames = fieldnames(meta.Maps);
                        for i = 1:numel(pNames)
                            meta.Maps.(pNames{i}) = zeros(size(meta.Maps.(pNames{i})));
                        end
                    end
                    meta.irf_data = [];
                end

                meta.activeChanIdx = newC;
                t.UserData = meta;

                % Refresh visual maps (re-plot currently visible result map)
                try syncMapDisplay(t); catch, end
            end
        end
    end

    % Trigger refresh of the currently visible analysis tab (plots & IRF)
    updatePixelAnalysis(fig, [nan nan]);

    % Ensure IRF FWHM labels are updated for the new channel context
    ats = findobj(fig, 'Tag', 'analysisTabs');
    if ~isempty(ats) && ~isempty(ats.SelectedTab)
        t = ats.SelectedTab;
        if isstruct(t.UserData) && isfield(t.UserData, 'lblIRFFWHM')
            % Re-calculate/Get existing IRF for this channel
            [irf, ~] = getIRFFromSource(fig, t, []);
            % Update params display manually
            updateIRFStatsDisplay(irf, t);
        end
    end
catch ME
    fprintf(2, 'CRITICAL ERROR in onDataTabChange: %s\n', ME.message);
    disp(ME.stack(1));
    rethrow(ME);
end
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

% axPats is no longer part of the Pattern Matching tab's layout.
% This function should ideally be removed or adapted if patterns are to be plotted elsewhere.
% For now, it's called but will not plot anything if axPats is not defined in meta.
% The instruction removed axPats from the layout.

% ax = meta.axPats; % This will error if axPats is not defined.
% Let's make it robust by checking if axPats exists.
if ~isfield(meta, 'axPats') || ~isvalid(meta.axPats)
    % No dedicated pattern plot axis in the new layout.
    % If patterns need to be visualized, a new axis should be added to the layout.
    return;
end

ax = meta.axPats;
cla(ax); hold(ax, 'on');
config = t.Parent.Parent.UserData.config;
% Decay is gates, not time bins?
% Patterns are N_gates.
% Plot Patterns robustness check
for i = 1:length(meta.patterns)
    p = meta.patterns(i);
    y = p.decay;
    N = length(y);

    % Determine x-axis
    if isfield(config, 'gate_edges') && ~isempty(config.gate_edges) && numel(config.gate_edges) == N + 1
        % Use mid-points of edges
        x = (config.gate_edges(1:end-1) + config.gate_edges(2:end)) / 2;
    else
        % Fallback to indices or generate linspace if T is known, otherwise just indices
        if isfield(config, 'T') && isfield(config, 'dt')
            % Approx gate size
            x = linspace(config.dt/2, config.T - config.dt/2, N);
        else
            x = 1:N;
        end
    end

    plot(ax, x, y, '.-', 'Color', p.color, 'LineWidth', 2, 'DisplayName', p.name);
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
irf_custom = [];
if ~strcmp(data.irf_source, 'Simulated'), irf_custom = data.irf_data; end
[fractionMaps, ~, ~] = DTpatternmatching(RawData, patMat, data.config, fig, irf_custom);

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
% Logic cleanup
delete(t.Children);

try
    data = fig.UserData;
    if (isempty(data.RawData) && (~isfield(data, 'currentData') || isempty(data.currentData)))
        uialert(fig, 'No data found. Please load or generate data first.', 'Error');
        return;
    end

    % Use Grid Layout for robust resizing
    mainGrid = uigridlayout(t, [1 2]);
    mainGrid.ColumnWidth = {'1x', 230};
    mainGrid.Padding = [10 10 10 10];

    % Main Plotting Area (Left)
    pGrid = uigridlayout(mainGrid, [2 2]);
    pGrid.ColumnWidth = {'1x', '1x'};
    pGrid.RowHeight = {'1x', '1x'};

    axMu = uiaxes(pGrid); title(axMu, '\mu_1 (ns) - Mean Lifetime'); axMu.Tag = 'axMu';
    axSig = uiaxes(pGrid); title(axSig, '\sigma (ns) - Heterogeneity'); axSig.Tag = 'axSig';
    axPhasor = uiaxes(pGrid); title(axPhasor, 'Phasor Space'); axPhasor.Tag = 'axPhasor';
    axHist = uiaxes(pGrid); title(axHist, '\mu_1 Histogram'); axHist.Tag = 'axHist';

    arrayfun(@(ax) set(ax, 'Box', 'on', 'GridAlpha', 0.1), [axMu, axSig, axPhasor, axHist]);

    % Controls Panel (Right)
    ctrlPanel = uipanel(mainGrid, 'Title', 'LiMA Controls');
    cGrid = uigridlayout(ctrlPanel, [12 1]);
    cGrid.RowHeight = {30,30,30,30,30,30,30,30,40,40,30,'1x'};

    % metadata
    tabMeta = struct('algo', 'LiMA Analysis', 'activeChanIdx', activeChanIdx);
    tabMeta.axMu = axMu; tabMeta.axSig = axSig; tabMeta.axPhasor = axPhasor; tabMeta.axHist = axHist;
    t.UserData = tabMeta;

    % Fill controls (Simplified version of original logic)
    uibutton(cGrid, 'Text', 'Analyse Channel', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.8 0 0], 'FontColor', 'white', ...
        'ButtonPushedFcn', @(~,~) runLimaAnalysis(fig));

    chkAnscombe = uicheckbox(cGrid, 'Text', 'Anscombe Transform', ...
        'Tooltip', 'Apply 2*sqrt(x + 3/8) to stabilize variance before fitting.', ...
        'Tag', 'chkAnscombe');

    uibutton(cGrid, 'Text', 'Batch Analysis', 'FontWeight', 'bold', ...
        'BackgroundColor', [0.2 0.3 0.6], 'FontColor', 'white', ...
        'ButtonPushedFcn', @(~,~) runBatchAnalysis(fig, t), ...
        'Tooltip', 'Run LiMA analysis on all files in the current group.');

    % Zoom helper
    gZoom = uigridlayout(cGrid, [1 2]);
    uibutton(gZoom, 'Text', '', 'Tooltip', 'Zoom Data', 'Icon', 'zoom_in', ...
        'ButtonPushedFcn', @(~,~) setPhasorZoom(fig, 'Data'));
    uibutton(gZoom, 'Text', '', 'Tooltip', 'Zoom Full', 'Icon', 'zoom_out', ...
        'ButtonPushedFcn', @(~,~) setPhasorZoom(fig, 'Full'));

    % Update tabMeta with chkAnscombe
    meta = t.UserData;
    meta.chkAnscombe = chkAnscombe;
    meta.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});
    meta.phasorZoomMode = 'Full';
    meta.harmonic = 1;
    % Multi-channel support
    if ~isfield(meta, 'ChanMaps'), meta.ChanMaps = cell(1, 4); end
    if ~isfield(meta, 'ChanIRFs'), meta.ChanIRFs = cell(1, 4); end
    if ~isfield(meta, 'Maps'), meta.Maps = struct(); end
    t.UserData = meta;

    runLimaAnalysis(fig); % Initial run
catch ME
    uialert(fig, ['LiMA Creator Error: ' ME.message], 'Error');
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
if isfield(data, 'navChannel'), activeChanIdx = data.navChannel;
else, activeChanIdx = meta.activeChanIdx; end
meta.activeChanIdx = activeChanIdx; t.UserData = meta;
RawData = getChannelData(fig, activeChanIdx);

% Apply Mask
mask = getChannelMask(fig, activeChanIdx);
if ~isempty(mask)
    [~, ~, nGates] = size(RawData);
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

% Store Results for multi-channel sync
meta.Maps.Mu = limaResults.mu_tau;
meta.Maps.Sigma = limaResults.sigma_tau;

meta.mu_vals = stats.S(:) ./ max(stats.G(:), 1e-9);
M_val_tmp = sqrt(stats.G(:).^2 + stats.S(:).^2);
meta.I2_vals = 0.5 * (max(M_val_tmp.^-2 - 1, 0) + meta.mu_vals.^2);

if ~isstruct(limaResults) || ~isfield(limaResults, 'mu_tau')
    error('DTlima returned invalid results structure (not a struct or missing mu_tau).');
end

if ~isempty(meta.axMu) && isvalid(meta.axMu)
    imagesc(meta.axMu, meta.Maps.Mu); colorbar(meta.axMu); axis(meta.axMu, 'image');
end
if ~isempty(meta.axSig) && isvalid(meta.axSig)
    imagesc(meta.axSig, meta.Maps.Sigma); colorbar(meta.axSig); axis(meta.axSig, 'image');
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
% 1. Corrected IRF for Phonons-Phasors
irf_shift = 0; if isfield(config, 'irf_shift'), irf_shift = config.irf_shift; end
irf = DTexcitation(t_vec, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);

% Apply IRF Shift
if irf_shift ~= 0
    dt_step = t_vec(2) - t_vec(1);
    shift_bins = round((irf_shift/1000) / dt_step);
    irf = circshift(irf, [0, shift_bins]);
    if shift_bins > 0
        irf(1:min(shift_bins, end)) = 0;
    elseif shift_bins < 0
        irf(max(1, end+shift_bins):end) = 0;
    end
end
irf = irf / sum(irf);

omega = harmonic * (2*pi / T);
g_irf = sum(irf .* cos(omega * t_vec(:)'));
s_irf = sum(irf .* sin(omega * t_vec(:)'));
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
    config.bPulseTrain, config.PT_Trep, config.PT_sigma, irf_shift);

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

function updateInstrumentPlot(fig)
% UPDATEINSTRUMENTPLOT - Refresh the instrument settings plot
axInstrument = findobj(fig, 'Tag', 'axInst');
if isempty(axInstrument), return; end
if numel(axInstrument) > 1, axInstrument = axInstrument(1); end

data = fig.UserData;
if ~isfield(data, 'config'), return; end
config = data.config;

% Time vector
if ~isfield(config, 'dt') || isempty(config.dt), config.dt = 0.05; end
if ~isfield(config, 'T') || isempty(config.T), config.T = 12.5; end
dt = config.dt;
t = 0:dt:config.T;

% Helper for DTexcitation access (local path should be set)
% Calculate IRF based on source
if strcmp(data.irf_source, 'Simulated')
    irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);

    % Apply IRF Shift for visualization
    % Apply IRF Shift for visualization
    irfShiftField = findobj(fig, 'Tag', 'irfShiftField_Ch1');
    if ~isempty(irfShiftField)
        shift_ns = irfShiftField.Value / 1000;
        dt_v = t(2) - t(1);
        shift_b = round(shift_ns / dt_v);
        irf = circshift(irf, [0, shift_b]);
        % Zero padding if shifting
        if shift_b > 0
            irf(1:min(shift_b, end)) = 0;
        elseif shift_b < 0
            irf(max(1, end+shift_b):end) = 0;
        end
        % Wrap check
        chkWrap = findobj(fig, 'Tag', 'chkWrap');
        if ~isempty(chkWrap) && chkWrap.Value
            % (Simple wrap visualization not strictly implemented here for display, but could be)
        end
    end
else
    % Use irf_data if available
    if ~isempty(data.irf_data)
        irf_raw = data.irf_data;
        if numel(irf_raw) == numel(t)
            irf = irf_raw;
        else
            irf = interp1(linspace(0, config.T, numel(irf_raw)), irf_raw, t, 'linear', 0);
        end
    else
        irf = zeros(size(t));
    end
end

% Shift IRF by toff (Removed: toff is 'Last Gate Edge', i.e. integration window width, not a delay)
% if isfield(config, 'toff'), toff = config.toff; end
% if toff ~= 0
%    irf = interp1(t, irf, t - toff, 'linear', 0);
% end

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
tau1Field = findobj(fig, 'Tag', 'tau1Field');
tau2Field = findobj(fig, 'Tag', 'tau2Field');

if ~isempty(tau1Field)
    try
        % Handle potentially empty or non-numeric values
        if isnumeric(tau1Field), v1=tau1Field; else, v1=tau1Field.Value; end

        tau1 = v1 / 1000; % ps to ns

        % Simple exponential decay for viz
        d1 = exp(-t/tau1); d1 = d1/max(d1);

        plot(axInstrument, t, d1, 'b--', 'LineWidth', 1, 'DisplayName', sprintf('\\tau_1=%.1gns (Exp)', tau1));

        % Calculated expected decay (PDF) for visualization
        % Create simple decay
        decay_ideal = exp(-t/tau1);
        decay_ideal(t < 0) = 0;

        % Normalize IRF for conv
        irf_norm = irf / sum(irf);

        % Convolve
        decay_conv = conv(decay_ideal, irf_norm, 'full');
        decay_conv = decay_conv(1:length(t));

        % Scale for display (to match IRF peak or arbitrary)
        if max(decay_conv) > 0, decay_conv = decay_conv / max(decay_conv); end

        plot(axInstrument, t, decay_conv, 'k-', 'LineWidth', 2, 'DisplayName', sprintf('Model PDF (%.1fns)', tau1));

        if ~isempty(tau2Field) && isvalid(tau2Field) && strcmp(tau2Field.Visible, 'on')
            if isnumeric(tau2Field), v2=tau2Field; else, v2=tau2Field.Value; end
            tau2 = v2 / 1000;
            d2 = exp(-t/tau2); d2 = d2/max(d2);
            plot(axInstrument, t, d2, 'g:', 'LineWidth', 1.5, 'DisplayName', sprintf('\\tau_2=%.1gns', tau2));
        end
    catch
    end
end
% Add Legend at bottom
legend(axInstrument, 'Location', 'south');

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
if isempty(data) || ~isfield(data, 'RawData') || isempty(data.RawData), return; end

tabGroup = findobj(fig, 'Tag', 'analysisTabs');
if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
if isempty(tab.UserData) || ~isfield(tab.UserData, 'Maps'), return; end
meta = tab.UserData;

% Use Unified Navigation Channel if available (Dynamic Link)
chanIdx = 1;
if isfield(data, 'navChannel')
    chanIdx = data.navChannel;
elseif isfield(meta, 'activeChanIdx')
    chanIdx = meta.activeChanIdx;
end

cData = getChannelData(fig, chanIdx);
[nY, nX, ~] = size(cData);

% Check if point is NaN (triggered by spinner)
if isnan(point(1))
    % Use existing crosshair position if available
    hV = findobj(fig, 'Tag', 'crossV');
    hH = findobj(fig, 'Tag', 'crossH');
    if ~isempty(hV) && ~isempty(hH)
        px = round(hV(1).Value); py = round(hH(1).Value);
    else
        % Default to center
        px = round(nX/2); py = round(nY/2);
    end
else
    px = round(point(1)); py = round(point(2));
end

if px < 1 || px > nX || py < 1 || py > nY, return; end

% Update Crosshair on ALL relevant axes (Data tab and Analysis tabs)
% Ensure markers exist in current active axes if missing
% 1. Main Unified Axis
axXY_Unified = findobj(fig, 'Tag', 'axXY_Unified');
if ~isempty(axXY_Unified)
    hV_main = findobj(axXY_Unified, 'Tag', 'crossV');
    if isempty(hV_main)
        hold(axXY_Unified, 'on');
        xline(axXY_Unified, px, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossV');
        yline(axXY_Unified, py, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossH');
    end
end
% 2. Legacy Channel Axis (if still visible)
c = chanIdx;
axXY = findobj(fig, 'Tag', sprintf('axXY_Ch%d', c));
if ~isempty(axXY)
    hV_main = findobj(axXY, 'Tag', 'crossV');
    if isempty(hV_main)
        hold(axXY, 'on');
        xline(axXY, px, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossV');
        yline(axXY, py, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossH');
    end
end

% Current Result Map Axis
if isfield(meta, 'mapAxes') && isstruct(meta.mapAxes)
    pNames = fieldnames(meta.mapAxes);
    for i=1:numel(pNames)
        ax = meta.mapAxes.(pNames{i});
        if isvalid(ax)
            hV_map = findobj(ax, 'Tag', 'crossV');
            if isempty(hV_map)
                hold(ax, 'on');
                xline(ax, px, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossV');
                yline(ax, py, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossH');
            end
        end
    end
end

% Now update all values
hVs = findobj(fig, 'Tag', 'crossV');
hHs = findobj(fig, 'Tag', 'crossH');
if ~isempty(hVs), set(hVs, 'Value', px, 'Visible', 'on'); end
if ~isempty(hHs), set(hHs, 'Value', py, 'Visible', 'on'); end

% Extract Pixel Data
pixelCounts = squeeze(cData(py, px, :));
totalPhotons = sum(pixelCounts);

% Background value for visualization
backVal = 0; if isfield(meta, 'spnBack') && isvalid(meta.spnBack), backVal = meta.spnBack.Value; end
% If we have a background map from fitting, use the pixel-specific value
if isfield(meta, 'Maps') && isfield(meta.Maps, 'Back')
    [mH, mW] = size(meta.Maps.Back);
    if py <= mH && px <= mW
        backVal = meta.Maps.Back(py, px);
    end
end

signalI0 = totalPhotons - backVal;
if signalI0 < 0, signalI0 = 0; end

estTau = NaN;
if isfield(meta, 'Maps') && isfield(meta.Maps, 'TauAvg')
    [mH, mW] = size(meta.Maps.TauAvg);
    if py <= mH && px <= mW
        estTau = meta.Maps.TauAvg(py, px);
    end
end
% Configuration retrieval (Prioritize navigated file in Unified Flow)
% This mirrors logic in runFitAnalysis to prevent mismatch errors
dFlow = flows_getData(fig);
config = data.config; % Default global config
if isfield(dFlow, 'navGroup') && isfield(dFlow, 'navFile') && isfield(dFlow, 'Conditions') && ~isempty(dFlow.Conditions)
    try
        cIdx = dFlow.navGroup; fIdx = dFlow.navFile;
        if cIdx <= numel(dFlow.Conditions) && fIdx <= numel(dFlow.Conditions{cIdx}.Analysis)
            if isfield(dFlow.Conditions{cIdx}.Analysis(fIdx), 'Config')
                fileCfg = dFlow.Conditions{cIdx}.Analysis(fIdx).Config;
                if ~isempty(fileCfg), config = fileCfg; end
            end
        end
    catch
    end
end

% Define Time and Gate Vectors locally to ensure availability
dt = config.dt; T = config.T; t = 0:dt:T;
% Robust Gate Edge Calculation
nGatesPixel = numel(pixelCounts);
if isempty(config.gate_edges) || numel(config.gate_edges) ~= nGatesPixel + 1
    % Mismatch: Regenerate edges based on data dimension
    gate_edges = linspace(0, T, nGatesPixel + 1);
else
    gate_edges = config.gate_edges;
end
gate_centers = 0.5 * (gate_edges(1:end-1) + gate_edges(2:end));
irf_shift = 0; if isfield(config, 'irf_shift'), irf_shift = config.irf_shift; end

% Check if we are inside a Result Tab Group with Pixel Analysis support
if ~isfield(meta, 'axPix'), return; end
axPixel = meta.axPix;
axPixelRes = meta.axPixRes;

% Update Labels
if isfield(meta, 'uPixPos'), meta.uPixPos.Text = sprintf('Pos: %d, %d', px, py); end
if isfield(meta, 'uPixI0'), meta.uPixI0.Text = sprintf('I0: %.1f photons', signalI0); end
if isfield(meta, 'uPixTau')
    if isnan(estTau)
        meta.uPixTau.Text = 'Tau: --';
    else
        meta.uPixTau.Text = sprintf('Tau: %.2f ns', estTau);
    end
end
if isfield(meta, 'uPixBack'), meta.uPixBack.Text = sprintf('Bkg: %.1f (tot)', backVal); end

% GT Labels
if isfield(meta, 'uGT_I0'), meta.uGT_I0.Text = sprintf('I0: %.1f photons', signalI0); end

cla(axPixel);
hold(axPixel, 'on');

hold(axPixelRes, 'on'); % axPixelRes is cleared later via cla

% === PLOT DATA & FITS ===
% Data
plot(axPixel, gate_centers(:), pixelCounts(:), 'bo', 'MarkerSize', 6, 'LineWidth', 1.5, 'DisplayName', 'Data', 'Tag', 'hData');

try
    % IRF Source Selection
    [irf, irf_t] = getIRFFromSource(fig, tab, cData);

    maxI = max(irf); if maxI == 0, maxI = 1; end
    maxP = max(pixelCounts); if maxP == 0, maxP = 1; end
    irf_scaled = (irf(:)/maxI) * double(maxP) * 0.5;
    plot(axPixel, irf_t, irf_scaled, 'r-', 'LineWidth', 1, 'DisplayName', 'IRF', 'Tag', 'hIRF');

    % Fit (Only if analysis has been run)
    isFitValid = ~isnan(estTau);

    if isFitValid
        % Ensure gate interpolation functions exist (critical for DTpmod)
        if ~isfield(meta, 'gate_interp_fns') || isempty(meta.gate_interp_fns)
            dt = config.dt; T = config.T; t_interp = 0:dt:T;
            gate_profiles = DTgates(t_interp, config.r, config.gate_edges);
            meta.gate_interp_fns = cell(config.N_gates, 1);
            for i = 1:config.N_gates
                meta.gate_interp_fns{i} = griddedInterpolant(t_interp, gate_profiles(i, :), 'linear', 'nearest');
            end
            % Update tab user data to cache it
            tab.UserData = meta;
        end

        [decay_smooth, ~] = DTpdf(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma, estTau, ...
            irf_shift, config.bWrap, config.dead_time, irf);

        % Recalculate discrete fit for scaling
        n_det = signalI0; % Intensity excluding background

        P_pixel = DTpmod(config.N_gates, estTau, t, meta.gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma, ...
            irf_shift, config.bWrap, config.dead_time, irf);

        % --- Scaling and Masking (Moved inside Try block) ---
        sP = sum(P_pixel);
        if sP == 0, sP = 1; end
        P_pixel = P_pixel / sP;

        fittedCounts = (P_pixel * n_det) + (backVal / config.N_gates);
        decay_smooth = (decay_smooth * (n_det / sum(decay_smooth))) + (backVal / config.T);

        % Determine Fit Range Time Window
        sg = 1; eg = config.N_gates;
        if isfield(meta, 'spnStart') && isvalid(meta.spnStart), sg = meta.spnStart.Value; end
        if isfield(meta, 'spnEnd') && isvalid(meta.spnEnd), eg = meta.spnEnd.Value; end
        t_start = gate_edges(sg);
        t_end = gate_edges(eg+1);

        % Mask fit curve
        mask_fit = (t >= t_start) & (t <= t_end);
        t_fit = t;
        decay_fit = decay_smooth;
        t_fit(~mask_fit) = nan; % Hide outside range
        decay_fit(~mask_fit) = nan;

        % Discrete fit points
        mask_discrete = false(size(gate_centers));
        mask_discrete(sg:eg) = true;
        gc_fit = gate_centers;
        fc_fit = fittedCounts;
        gc_fit(~mask_discrete) = nan;
        fc_fit(~mask_discrete) = nan;
    else
        % Fallback for invalid fit
        decay_fit = nan(size(t)); t_fit = t; fittedCounts = nan(size(gate_centers));
        gc_fit = gate_centers; fc_fit = fittedCounts;
    end
catch ME
    fprintf('Error in updatePixelAnalysis calculation: %s\n', ME.message);
    disp(ME.stack(1));
    % keyboard; % Removed as requested
    decay_fit = nan(size(t)); t_fit = t; fittedCounts = nan(size(gate_centers));
    gc_fit = nan; fc_fit = nan;
    isFitValid = false;
end

if isFitValid
    plot(axPixel, t_fit, decay_fit, 'k-', 'LineWidth', 1.5, 'DisplayName', sprintf('Fit (%.2fns)', estTau), 'Tag', 'hFit');
    % Clarify dashed curve in legend
    plot(axPixel, gc_fit(:), fc_fit(:), 'k--', 'LineWidth', 0.5, 'DisplayName', 'Discrete Fit', 'Tag', 'hConn');
end

% Formatting
title(axPixel, '(In-pixel fitting)');
legend(axPixel, 'Location', 'northeast', 'FontSize', 8);
grid(axPixel, 'on');
set(axPixel, 'XTickLabel', []);
ylabel(axPixel, 'Counts', 'FontWeight', 'bold');
xlim(axPixel, [0 config.T]);
maxVal = max(pixelCounts(:));
if isnan(maxVal) || maxVal <= 0, maxVal = 1; end
ylim(axPixel, [0, 1.2 * maxVal]);

% === RESIDUALS ===
cla(axPixelRes); % Safe to clear residuals as no interaction there
z_pixel = (pixelCounts(:) - fittedCounts(:)) ./ sqrt(fittedCounts(:) + 1e-10);
if ~all(isnan(z_pixel))
    stem(axPixelRes, gate_centers(:), z_pixel, 'Marker', 'o', 'MarkerSize', 4, 'LineWidth', 1.5, 'Color', [0.4 0.4 0.4]);
end
hold(axPixelRes, 'on');
yline(axPixelRes, 0, 'k-');
yline(axPixelRes, [1.96, -1.96], 'r--');
grid(axPixelRes, 'on');
xlim(axPixelRes, [0 config.T]);
xlabel(axPixelRes, 'Time (ns)', 'FontWeight', 'bold');
ylabel(axPixelRes, 'Z-score', 'FontWeight', 'bold');
drawnow limitrate;

% === INTERACTIVE MARKERS ===
if isfield(meta, 'spnStart') && isvalid(meta.spnStart) && isfield(meta, 'spnEnd') && isvalid(meta.spnEnd)

    % Get Settings
    gateIdx_Start = meta.spnStart.Value;
    gateIdx_End = meta.spnEnd.Value;

    % Map to Time Coordinates (Use Gate Edges)
    % Start Marker: Left Edge of start gate
    % End Marker: Right Edge of end gate
    if gateIdx_Start < 1, gateIdx_Start = 1; end
    if gateIdx_End > numel(gate_edges)-1, gateIdx_End = numel(gate_edges)-1; end

    t_start = gate_edges(gateIdx_Start);
    t_end = gate_edges(gateIdx_End + 1);

    yLim = ylim(axPixel);

    % Helper to create/update line
    updateMarkerLine(axPixel, 'roiStart', t_start, yLim, 'g', meta.spnStart, gate_edges);
    updateMarkerLine(axPixel, 'roiEnd', t_end, yLim, 'r', meta.spnEnd, gate_edges);
end

% Update Pixel Info Labels
meta.uPixPos.Text = sprintf('Pos: %d, %d', px, py);
meta.uPixTau.Text = sprintf('%c: %.2f ns', 964, estTau);

% == Update Pixel-Level Metrics ==
pix_chi2 = mean(z_pixel.^2);
meta.uPixChi.Text = sprintf('%c%c%c: %.3f', 967, 178, 7523, pix_chi2);
meta.uPixRE.Text = sprintf('R.E.: %.1f%%', (1/pix_chi2)*100);

% Runs test
s_pix = sign(z_pixel); s_pix(s_pix==0) = 1;
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

function updateMarkerLine(ax, tag, t_val, yLim, color, spinner, edges)
if any(isnan(t_val)) || any(isnan(yLim)), return; end
hLine = findobj(ax, 'Tag', tag);
if isempty(hLine)
    % Create new interactive line
    hLine = drawline(ax, 'Position', [t_val yLim(1); t_val yLim(2)], ...
        'Color', color, 'LineWidth', 2, 'Tag', tag, ...
        'InteractionsAllowed', 'translate');

    % Add Listeners
    addlistener(hLine, 'MovingROI', @(src, ev) onMarkerMoving(src, ev, spinner, edges, tag));
else
    % Update position only if deviation is significant (avoid fighting loop)
    currentPos = hLine.Position;
    if abs(currentPos(1,1) - t_val) > 1e-4 || abs(currentPos(1,2) - yLim(1)) > 1e-1 || abs(currentPos(2,2) - yLim(2)) > 1e-1
        hLine.Position = [t_val yLim(1); t_val yLim(2)];
    end
end
end

function onMarkerMoving(~, evt, spinner, edges, tag)
% Constrain to vertical movement
pos = evt.CurrentPosition;
x = pos(1,1);

% Find nearest gate edge
[~, nearestIdx] = min(abs(edges - x));

% Map back to Gate Index
% Start Marker (Green): Corresponds to edges(gateIdx).
% End Marker (Red): Corresponds to edges(gateIdx + 1).
if contains(tag, 'Start')
    gateIdx = nearestIdx;
else
    gateIdx = nearestIdx - 1;
end

% Clamp
if gateIdx < 1, gateIdx = 1; end
if gateIdx > numel(edges)-1, gateIdx = numel(edges)-1; end

% Update Spinner (only if changed to avoid spam)
if spinner.Value ~= gateIdx
    spinner.Value = gateIdx;
    % Spinner ValueChanged usually triggers updatePixelAnalysis.
    % But programmatically setting it usually DOES NOT in modern MATLAB uifigures?
    % Actually, it often doesn't.
    % If it doesn't, we should manually trigger simple update or text update?
    % But we don't want to redraw the WHOLE plot while dragging.
    % We just update the line position to snap to grid?

    % Snap source to grid visually
    % src.Position = [edges(nearestIdx) src.Position(1,2); edges(nearestIdx) src.Position(2,2)];
end

% Force vertical constraint visually during drag
% evt.Source.Position(:,1) = x; % Basic vertical constraint handled by drawline logic?
% drawline 'translate' moves everything.
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

function refreshPhasorPlot(fig, axIn)
data = fig.UserData;
% Data check moved to after getChannelData

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
    % Find ancestor tab to get meta
    tab = ancestor(axPhasor, 'uitab');
    if ~isempty(tab)
        meta = tab.UserData;
    else
        % Fallback check on direct parent (in case not in tab)
        if isprop(axPhasor.Parent, 'UserData')
            meta = axPhasor.Parent.UserData;
        end
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
    if isfield(data, 'navChannel'), chanIdx = data.navChannel;
    elseif isfield(meta, 'activeChanIdx'), chanIdx = meta.activeChanIdx; end
end

config = data.config;
cData = getChannelData(fig, chanIdx);
if isempty(cData), return; end

% Apply Mask
mask = getChannelMask(fig, chanIdx);
if ~isempty(mask)
    [~, ~, nGates] = size(cData);
    mask3D = repmat(mask, 1, 1, nGates);
    cData(mask3D) = 0;
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

    irf_shift_val = 0; if isfield(config, 'irf_shift'), irf_shift_val = config.irf_shift; end
    P_locus = DTpmod(config.N_gates, tau_locus, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma, irf_shift_val);
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

if isempty(tab.UserData) || ~isfield(tab.UserData, 'algo')
    % If we don't know what it is, just clear it
    delete(tab.Children);
    tab.UserData = [];
    return;
end

algo = tab.UserData.algo;
activeChanIdx = 1;
if isfield(tab.UserData, 'activeChanIdx'), activeChanIdx = tab.UserData.activeChanIdx; end

% Wipe and rebuild
delete(tab.Children);
tab.UserData = [];

switch lower(algo)
    case 'grid mle'
        createNewFitTab(fig, tab, 'Grid MLE', activeChanIdx);
    case 'iterative reconvolution'
        createNewFitTab(fig, tab, 'Iterative Reconvolution', activeChanIdx);
    case 'tail fitting'
        createNewFitTab(fig, tab, 'Tail Fitting', activeChanIdx);
    case 'phasor analysis'
        createNewPhasorTab(fig, tab, activeChanIdx);
    case 'pattern matching'
        createNewPatternTab(fig, tab, activeChanIdx);
    case 'lima'
        createNewLimaTab(fig, tab, activeChanIdx);
    case 'fisher analysis'
        createNewFisherTab(fig, tab, activeChanIdx);
    case 'machine learning'
        createNewMLTab(fig, tab, 'Machine Learning', activeChanIdx);
    otherwise
        createNewFitTab(fig, tab, algo, activeChanIdx);
end
end

function createNewFisherTab(~, t, activeChanIdx)
delete(t.Children); % fresh start

% --- Layout Constants ---
axW = 400;
mapH = 350;

% Main Grid for Layout
gMain = uigridlayout(t, [1 2]);
gMain.ColumnWidth = {'1x', '0.5x'};

% Left Side: Maps (Images)
pLeft = uipanel(gMain, 'BorderType', 'none');
tGroup = uitabgroup(pLeft, 'Tag', 'mapTg_Fisher_Analysis', ...
    'SelectionChangedFcn', @(src, ev) syncMapDisplay(t));

mapAxes = struct(); mapHists = struct(); mapSpins = struct();
pNames = {'Photons', 'Alpha', 'Delta'};
dNames = {'Photons', 'Analysis (\alpha)', 'Residual (\delta)'};

for i = 1:numel(pNames)
    nm = pNames{i};
    tabMap = uitab(tGroup, 'Title', dNames{i}, 'Tag', ['tab_' nm '_Fisher_Analysis']);

    % Axis for Image
    ax = uiaxes(tabMap, 'Position', [10, 160, axW, mapH], 'Tag', ['ax_' nm '_Fisher_Analysis']);
    disableDefaultInteractions(ax); colormap(ax, 'jet');
    mapAxes.(nm) = ax;

    % Axis for Histogram
    axH = uiaxes(tabMap, 'Position', [10, 10, axW, 140], 'Tag', ['hist_' nm '_Fisher_Analysis']);
    mapHists.(nm) = axH;

    % Controls (Spinners)
    uilabel(tabMap, 'Text', 'Min:', 'Position', [axW+20, 100, 30, 20]);
    spnMin = uispinner(tabMap, 'Position', [axW+60, 100, 60, 20], ...
        'ValueChangedFcn', @(src, ev) syncTabSpinners(t, 'Min', src.Value));

    uilabel(tabMap, 'Text', 'Max:', 'Position', [axW+20, 130, 30, 20]);
    spnMax = uispinner(tabMap, 'Position', [axW+60, 130, 60, 20], ...
        'ValueChangedFcn', @(src, ev) syncTabSpinners(t, 'Max', src.Value));

    mapSpins.(nm).Min = spnMin; mapSpins.(nm).Max = spnMax;
end

% Right Side: Fisher Plot & Controls
pRight = uipanel(gMain, 'Title', 'Fisher Projection');
gRight = uigridlayout(pRight, [2 1]);
gRight.RowHeight = {'1x', '0.3x'};

% Fisher Parameter Plot
axFPP = uiaxes(gRight); axFPP.Tag = 'axFPP';
title(axFPP, 'Fisher Parameter Space'); xlabel(axFPP, '\alpha'); ylabel(axFPP, '\delta');
grid(axFPP, 'on'); box(axFPP, 'on');

% Controls
pCtrl = uipanel(gRight, 'Title', 'Controls');
gCtrl = uigridlayout(pCtrl, [4 2]);

uibutton(gCtrl, 'Text', 'Set Ref 1 (Red)', 'FontColor', [0.8 0 0], 'ButtonPushedFcn', @(~,~) addFisherROI(fig, 1));
uibutton(gCtrl, 'Text', 'Set Ref 2 (Blue)', 'FontColor', [0 0 0.8], 'ButtonPushedFcn', @(~,~) addFisherROI(fig, 2));

% Calculate Button
btnCalc = uibutton(gCtrl, 'Text', 'CALCULATE', 'FontWeight', 'bold', 'BackgroundColor', [0.8 0 0], 'FontColor', 'white', ...
    'ButtonPushedFcn', @(~,~) runFisherAnalysis(fig));
btnCalc.Layout.Row = 2;
btnCalc.Layout.Column = [1 2];

% Spacer or other controls could go here (Row 3 empty in original desire?)

% Batch Analysis Button
btnBatch = uibutton(gCtrl, 'Text', 'Batch Analysis', 'BackgroundColor', [0.2 0.3 0.6], 'FontColor', 'white', ...
    'ButtonPushedFcn', @(~,~) runBatchAnalysis(fig, t));
btnBatch.Layout.Row = 4;
btnBatch.Layout.Column = [1 2];

% Meta initialization
tabMeta = struct();
tabMeta.activeChanIdx = activeChanIdx;
tabMeta.algo = 'Fisher Analysis';
tabMeta.mapTg = tGroup;
tabMeta.mapAxes = mapAxes;
tabMeta.mapHists = mapHists;
tabMeta.mapSpins = mapSpins;
tabMeta.axFPP = axFPP;
tabMeta.refROIs = {[], []};

% We need to carry over GT axis handle or standard logic?
% Standard logic uses syncMapDisplay to update maps.
% GT comparison is specific to this tab.
% Let's add GT axis if needed or just skip for now.

t.UserData = tabMeta;
end

function addFisherROI(fig, refIdx)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;
meta = t.UserData;
axXY = findobj(fig, 'Tag', 'axXY_Unified');
if isempty(axXY), axXY = findobj(fig, 'Tag', 'axXY'); end
if isempty(axXY), return; end

col = [0 0 1]; if refIdx == 1, col = [1 0 0]; end

if isfield(meta, 'refROIs') && numel(meta.refROIs) >= refIdx
    if isvalid(meta.refROIs{refIdx}), delete(meta.refROIs{refIdx}); end
end

try
    hROI = drawpolygon(axXY, 'Color', col, 'LineWidth', 2, 'Label', sprintf('Ref %d', refIdx));
    wait(hROI);
    if ~isvalid(hROI), return; end

    mask = hROI.createMask();
    cData = getChannelData(fig, meta.activeChanIdx);
    [~, ~, nGates] = size(cData);
    flatData = reshape(permute(cData, [3, 1, 2]), nGates, []);
    decay = sum(flatData(:, mask(:)), 2);
    decaySum = sum(decay);
    if decaySum == 0
        uialert(fig, 'Selected region has 0 photons.', 'Warning');
        delete(hROI); return;
    end
    decay = decay / decaySum;

    if refIdx == 1, meta.ref1 = decay; else, meta.ref2 = decay; end
    meta.refROIs{refIdx} = hROI;
    t.UserData = meta;
catch ME
    uialert(fig, ['Error setting ROI: ' ME.message], 'Error');
end
end

function runFisherAnalysis(fig)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;
meta = t.UserData;

if isempty(meta) || ~isfield(meta, 'ref1') || ~isfield(meta, 'ref2')
    uialert(fig, 'Fisher analysis state is invalid. Please reset.', 'Error');
    return;
end

try
    P1 = meta.ref1(:);
    P2 = meta.ref2(:);
    activeChanIdx = meta.activeChanIdx;
    RawData = getChannelData(fig, activeChanIdx);

    mask = getChannelMask(fig, activeChanIdx);
    if ~isempty(mask)
        [nY, nX, nGates] = size(RawData);
        mask3D = repmat(mask, 1, 1, nGates);
        RawData(mask3D) = 0;
    else
        [nY, nX, nGates] = size(RawData);
    end

    meta.Maps.Photons = sum(RawData, 3);
    flatData = reshape(permute(double(RawData), [3, 1, 2]), nGates, []);

    % 1. Fisher Mixing Component (FMC)
    A = [(P1 - P2)'; P2'];
    p_ref = 0.5 * P1 + 0.5 * P2;
    D_inv = diag(1 ./ (p_ref + 1e-9));
    b = [1; 0];
    M_mat = A * D_inv * A';
    beta = M_mat \ b;
    f_FMC = D_inv * A' * beta;
    Alpha_est = f_FMC' * flatData;

    % 2. Fisher Orthogonal Residual (FOR)
    [U_S, ~] = qr([P1, P2], 0);
    Proj_S = U_S * U_S';
    Residuals = flatData - Proj_S * flatData;
    [u_res, ~, ~] = svds(Residuals, 1);
    if sum(u_res) < 0, u_res = -u_res; end
    f_FOR = u_res;
    Delta_est = f_FOR' * flatData;

    meta.Maps.Alpha = reshape(Alpha_est, nY, nX);
    meta.Maps.Delta = reshape(Delta_est, nY, nX);

    t.UserData = meta;
    syncMapDisplay(t);

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
    dd = findobj(fig, 'Tag', 'ddIRFSource');
    if ~isempty(dd), dd.Items = {'Simulated', 'Estimated', 'Experimental'}; end
else
    pConfig.Visible = 'off';
    pAnalyzer.Visible = 'on';
    dd = findobj(fig, 'Tag', 'ddIRFSource');
    if ~isempty(dd)
        dd.Items = {'Estimated', 'Experimental'};
        if strcmp(dd.Value, 'Simulated'), dd.Value = 'Experimental'; end
    end
end
end

function toggleExpertMode(fig, mode)
lbl = findobj(fig, 'Tag', 'lblExpertStatus');
if ~isempty(lbl), lbl.Text = mode; end

% Logic for Expert Mode
% Logic for Expert Mode
swDebug = findobj(fig, 'Tag', 'swDebug');
lblDebug = findobj(fig, 'Tag', 'lblDebugStatus');

if strcmpi(mode, 'Expert')
    lbl.FontColor = [0.8 0 0]; % Red for Expert
    if ~isempty(swDebug), swDebug.Visible = 'on'; end
    if ~isempty(lblDebug), lblDebug.Visible = 'on'; end
else
    lbl.FontColor = [0.5 0.5 0.5];
    if ~isempty(swDebug)
        swDebug.Value = 'Off';
        swDebug.Visible = 'off';
        toggleDebugMode(fig, 'Off'); % Ensure off
    end
    if ~isempty(lblDebug), lblDebug.Visible = 'off'; end
end

% Find Debug Tab and Wrapper
tabGroup = findobj(fig, 'Tag', 'simTabGroup');
tabDebug = [];
% Try to retrieve from UserData first (reliable if unparented)
if ~isempty(tabGroup) && isstruct(tabGroup.UserData) && isfield(tabGroup.UserData, 'tabDebug')
    tabDebug = tabGroup.UserData.tabDebug;
end
% Fallback search
if isempty(tabDebug)
    tabDebug = findall(fig, 'Tag', 'tabDebug');
end

% Buttons
btnExp = findobj(fig, 'Tag', 'btnExpIRF');
btnEst = findobj(fig, 'Tag', 'btnEstIRF');

if strcmp(mode, 'Expert')
    % Show Debug Tab
    if ~isempty(tabDebug)
        set(tabDebug, 'Parent', tabGroup);
    end
    set(btnExp, 'Visible', 'on');
    set(btnEst, 'Visible', 'on');
else
    % Hide Debug Tab
    if ~isempty(tabDebug)
        set(tabDebug, 'Parent', []);
    end
    set(btnExp, 'Visible', 'off');
    set(btnEst, 'Visible', 'off');
end
end

% === IRF Callbacks ===
function onIRFSourceChanged(fig, source)
data = fig.UserData;
data.irf_source = source;
fig.UserData = data;

btnExp = findobj(fig, 'Tag', 'btnExpIRF');
btnEst = findobj(fig, 'Tag', 'btnEstIRF');
lblPField = findobj(fig, 'Tag', 'lblIRFPeakField');
lblPValue = findobj(fig, 'Tag', 'lblIRFPeak');
lblFField = findobj(fig, 'Tag', 'lblIRFFWHMField');
lblFValue = findobj(fig, 'Tag', 'lblIRFFWHM');

vis = 'on';
if strcmp(source, 'Simulated'), vis = 'off'; end
set([lblPField, lblPValue, lblFField, lblFValue], 'Visible', vis);

if strcmp(source, 'Experimental')
    btnExp.Visible = 'on'; btnEst.Visible = 'off';
elseif strcmp(source, 'Estimated')
    btnExp.Visible = 'off'; btnEst.Visible = 'on';
else
    btnExp.Visible = 'off'; btnEst.Visible = 'off';
end
updateInstrumentPlot(fig, [], []);
end

function onExtractExperimentalIRF(fig)
data = fig.UserData;
if isempty(data.RawData)
    uialert(fig, 'No data loaded to extract IRF from.', 'Missing Data');
    return;
end
raw = data.RawData(:,:,:,1);
irf = squeeze(mean(raw, [1 2]));
irf = irf / max(irf);
data.irf_data = irf;
fig.UserData = data;

stats = calculateIRFStats(irf, data.config.T);
lblP = findobj(fig, 'Tag', 'lblIRFPeak');
lblF = findobj(fig, 'Tag', 'lblIRFFWHM');
if ~isempty(lblP), lblP.Text = sprintf('%.2f ns', stats.peakPos); end
if ~isempty(lblF), lblF.Text = sprintf('%.0f ps', stats.fwhm_ps); end

updateInstrumentPlot(fig, [], []);
fprintf('Extracted Experimental IRF.\n');
end

function onEstimateIRF(fig)
data = fig.UserData;
if isempty(data.RawData)
    uialert(fig, 'No data loaded for estimation.', 'Missing Data');
    return;
end
raw = squeeze(mean(data.RawData(:,:,:,1), [1 2]));
[~, pIdx] = max(raw);
est = raw;
% Zero out decay after peak + small buffer
m = min(numel(raw), pIdx + round(5 / (data.config.T / numel(raw))));
est(m:end) = 0;
est = est / max(est);
data.irf_data = est;
fig.UserData = data;

stats = calculateIRFStats(est, data.config.T);
lblP = findobj(fig, 'Tag', 'lblIRFPeak');
lblF = findobj(fig, 'Tag', 'lblIRFFWHM');
if ~isempty(lblP), lblP.Text = sprintf('%.2f ns', stats.peakPos); end
if ~isempty(lblF), lblF.Text = sprintf('%.0f ps', stats.fwhm_ps); end

updateInstrumentPlot(fig, [], []);
fprintf('Estimated IRF from rising shoulder.\n');
end

function stats = calculateIRFStats(irf, T_ns)
N = numel(irf);
t = linspace(0, T_ns, N);
[pVal, pIdx] = max(irf);
stats.peakPos = t(pIdx);

% FWHM
hm = pVal / 2;
% Simple threshold search from left and right of peak
idx1 = find(irf(1:pIdx) >= hm, 1, 'first');
idx2 = pIdx + find(irf(pIdx+1:end) <= hm, 1, 'first') - 1;

if isempty(idx1), idx1 = 1; end
if isempty(idx2), idx2 = N; end

stats.fwhm_ns = t(idx2) - t(idx1);
stats.fwhm_ps = stats.fwhm_ns * 1000;
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
fig = ancestor(tabGroup, 'figure');
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

% === Binning Controls ===
binY = threshY_local - 35;
uilabel(tab, 'Text', 'Binning:', 'FontWeight', 'bold', 'Position', [10, binY, 60, 22]);
% Default is 'Off' as requested
ddBin = uidropdown(tab, 'Items', {'Off', 'Binning', 'Convolution'}, 'Value', 'Off', ...
    'Position', [70, binY, 100, 22], 'Tag', sprintf('ddBin_Ch%d', chanIdx), ...
    'ValueChangedFcn', @(src, ev) onBinningChange(fig, chanIdx));

% ... (Rest of UI definition remains same, but initial Visibility will handle 'Off' state correctly) ...

% Binning Params
lblBinF = uilabel(tab, 'Text', 'Factor:', 'Position', [180, binY, 45, 22], 'Tag', sprintf('lblBinF_Ch%d', chanIdx));
spnBinF = uispinner(tab, 'Limits', [1 32], 'Value', 2, 'Position', [225, binY, 50, 22], ...
    'Tag', sprintf('spnBinF_Ch%d', chanIdx), 'ValueChangedFcn', @(src, ev) onBinningChange(fig, chanIdx));

% Convolution Params
lblKern = uilabel(tab, 'Text', 'Kernel:', 'Position', [180, binY, 45, 22], 'Tag', sprintf('lblKern_Ch%d', chanIdx), 'Visible', 'off');
ddKern = uidropdown(tab, 'Items', {'Square', 'Gaussian'}, 'Value', 'Gaussian', ...
    'Position', [225, binY, 80, 22], 'Tag', sprintf('ddKern_Ch%d', chanIdx), 'Visible', 'off', ...
    'ValueChangedFcn', @(src, ev) onBinningChange(fig, chanIdx));

lblSize = uilabel(tab, 'Text', 'Size:', 'Position', [315, binY, 30, 22], 'Tag', sprintf('lblSize_Ch%d', chanIdx), 'Visible', 'off');
spnSize = uispinner(tab, 'Limits', [1 99], 'Value', 5, 'Position', [345, binY, 45, 22], ...
    'Tag', sprintf('spnSize_Ch%d', chanIdx), 'Visible', 'off', 'ValueChangedFcn', @(src, ev) onBinningChange(fig, chanIdx));

lblSig = uilabel(tab, 'Text', 'Sigma:', 'Position', [395, binY, 40, 22], 'Tag', sprintf('lblSig_Ch%d', chanIdx), 'Visible', 'off');
spnSig = uispinner(tab, 'Limits', [0.1 20], 'Value', 2, 'Step', 0.1, 'Position', [435, binY, 45, 22], ...
    'Tag', sprintf('spnSig_Ch%d', chanIdx), 'Visible', 'off', 'ValueChangedFcn', @(src, ev) onBinningChange(fig, chanIdx));

% Initial Visibility Update (Will hide everything for 'Off')
updateBinningUI(ddBin, lblBinF, spnBinF, lblKern, ddKern, lblSize, spnSize, lblSig, spnSig);

% Initial Apply
processChannelData(fig, chanIdx);

tab.UserData = struct();
end

function updateBinningUI(ddBin, lblBinF, spnBinF, lblKern, ddKern, lblSize, spnSize, lblSig, spnSig)
mode = ddBin.Value;
if strcmp(mode, 'Binning')
    lblBinF.Visible = 'on'; spnBinF.Visible = 'on';
    lblKern.Visible = 'off'; ddKern.Visible = 'off';
    lblSize.Visible = 'off'; spnSize.Visible = 'off';
    lblSig.Visible = 'off'; spnSig.Visible = 'off';
elseif strcmp(mode, 'Convolution')
    lblBinF.Visible = 'off'; spnBinF.Visible = 'off';
    lblKern.Visible = 'on'; ddKern.Visible = 'on';
    lblSize.Visible = 'on'; spnSize.Visible = 'on';
    if strcmp(ddKern.Value, 'Gaussian')
        lblSig.Visible = 'on'; spnSig.Visible = 'on';
    else
        lblSig.Visible = 'off'; spnSig.Visible = 'off';
    end
else % Off
    lblBinF.Visible = 'off'; spnBinF.Visible = 'off';
    lblKern.Visible = 'off'; ddKern.Visible = 'off';
    lblSize.Visible = 'off'; spnSize.Visible = 'off';
    lblSig.Visible = 'off'; spnSig.Visible = 'off';
end
end

function onBinningChange(fig, chanIdx)
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
if isempty(dataTabGroup), return; end
tab = dataTabGroup.Children(chanIdx);

ddBin = findobj(tab, 'Tag', sprintf('ddBin_Ch%d', chanIdx));
lblBinF = findobj(tab, 'Tag', sprintf('lblBinF_Ch%d', chanIdx));
spnBinF = findobj(tab, 'Tag', sprintf('spnBinF_Ch%d', chanIdx));

lblKern = findobj(tab, 'Tag', sprintf('lblKern_Ch%d', chanIdx));
ddKern = findobj(tab, 'Tag', sprintf('ddKern_Ch%d', chanIdx));
lblSize = findobj(tab, 'Tag', sprintf('lblSize_Ch%d', chanIdx));
spnSize = findobj(tab, 'Tag', sprintf('spnSize_Ch%d', chanIdx));
lblSig = findobj(tab, 'Tag', sprintf('lblSig_Ch%d', chanIdx));
spnSig = findobj(tab, 'Tag', sprintf('spnSig_Ch%d', chanIdx));

% Update UI
updateBinningUI(ddBin, lblBinF, spnBinF, lblKern, ddKern, lblSize, spnSize, lblSig, spnSig);

% Apply Processing
processChannelData(fig, chanIdx);

% Auto-Scale CLims based on new processed data
cData = getChannelData(fig, chanIdx);
if ~isempty(cData)
    newImg = sum(cData, 3);
    cmin = min(newImg(:));
    cmax = max(newImg(:));
    if cmin == cmax, cmax = cmin + 0.1; end

    spnMin = findobj(tab, 'Tag', sprintf('spnMin_Ch%d', chanIdx));
    spnMax = findobj(tab, 'Tag', sprintf('spnMax_Ch%d', chanIdx));

    if ~isempty(spnMin), spnMin.Value = cmin; end
    if ~isempty(spnMax), spnMax.Value = cmax; end

    % Force update of plots (Contrast Change listener handles CLims, but we update explicit values)
    % Call specific helpers to ensure propagation
    onContrastControlChange(tab, chanIdx, 'spnMin', cmin); % Triggers CLim update
    onContrastControlChange(tab, chanIdx, 'spnMax', cmax); % Triggers CLim update
end

% Refresh
refreshAllPlots(fig);
% refreshXYProjection is called by refreshAllPlots via update, but explicit call ensures partials
end

function processChannelData(fig, chanIdx)
% Reads RawData and UI settings, populates ProcData
data = fig.UserData;
if isempty(data.RawData), return; end

% Ensure ProcData exists
if ~isfield(data, 'ProcData')
    data.ProcData = cell(size(data.RawData, 4), 1);
    fig.UserData = data;
end

try
    % Get Settings
    dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');
    if isempty(dataTabGroup), return; end
    if chanIdx > numel(dataTabGroup.Children), return; end
    tab = dataTabGroup.Children(chanIdx);

    ddBin = findobj(tab, 'Tag', sprintf('ddBin_Ch%d', chanIdx));
    if isempty(ddBin)
        data.ProcData{chanIdx} = [];
        fig.UserData = data;
        return;
    end

    mode = ddBin.Value;

    if strcmp(mode, 'Off')
        data.ProcData{chanIdx} = [];
    else
        rawDataSlice = squeeze(data.RawData(:,:,:,chanIdx));
        [nY, nX, nG] = size(rawDataSlice);

        if strcmp(mode, 'Binning')
            spnBinF = findobj(tab, 'Tag', sprintf('spnBinF_Ch%d', chanIdx));
            factor = spnBinF.Value;
            if factor > 1
                % Check if imresize is available
                if exist('imresize', 'file')
                    scale = 1/factor;
                    % Calc new size first to preallocate
                    tmp = imresize(rawDataSlice(:,:,1), scale, 'box');
                    [ny, nx] = size(tmp);
                    procData = zeros(ny, nx, nG);
                    for g = 1:nG
                        % Multiply by factor^2 to approximate Sum (imresize box is average)
                        procData(:,:,g) = imresize(rawDataSlice(:,:,g), scale, 'box') * (factor^2);
                    end
                    data.ProcData{chanIdx} = procData;
                else
                    % Fallback: Blockproc/Conv? Just warn and skip
                    fprintf('Warning: imresize not found. Binning disabled.\n');
                    data.ProcData{chanIdx} = [];
                end
            else
                data.ProcData{chanIdx} = [];
            end

        elseif strcmp(mode, 'Convolution')
            ddKern = findobj(tab, 'Tag', sprintf('ddKern_Ch%d', chanIdx));
            spnSize = findobj(tab, 'Tag', sprintf('spnSize_Ch%d', chanIdx));
            sz = spnSize.Value;

            if strcmp(ddKern.Value, 'Square')
                hK = ones(sz, sz);
            else
                spnSig = findobj(tab, 'Tag', sprintf('spnSig_Ch%d', chanIdx));
                sig = spnSig.Value;
                if exist('fspecial', 'file')
                    hK = fspecial('gaussian', [sz sz], sig);
                else
                    % Fallback gaussian kernel approx
                    [x,y] = meshgrid(-(sz-1)/2:(sz-1)/2, -(sz-1)/2:(sz-1)/2);
                    hK = exp(-(x.^2+y.^2)/(2*sig^2));
                    hK = hK / sum(hK(:));
                end
            end

            procData = zeros(nY, nX, nG);
            for g = 1:nG
                procData(:,:,g) = conv2(rawDataSlice(:,:,g), hK, 'same');
            end
            data.ProcData{chanIdx} = procData;
        end
    end
    fig.UserData = data;
catch ME
    fprintf('Error in processChannelData: %s\n', ME.message);
    % Fallback to clear
    data.ProcData{chanIdx} = [];
    fig.UserData = data;
end
end

function cData = getChannelData(fig, chanIdx)
d = flows_getData(fig);

% Priority 1: Dynamic Lookup from Navigation State (Group/File)
% "Change it to the group, file, and channel visualized in the data>image tab"
if isfield(d, 'navGroup') && isfield(d, 'navFile') && isfield(d, 'Conditions') && ~isempty(d.Conditions)
    try
        grp = d.navGroup; file = d.navFile;
        if grp <= numel(d.Conditions) && isfield(d.Conditions{grp}, 'Analysis') && file <= numel(d.Conditions{grp}.Analysis)
            target = d.Conditions{grp}.Analysis(file);
            if isfield(target, 'Data') && ~isempty(target.Data)
                % Validate channel index
                if chanIdx <= size(target.Data, 4)
                    cData = double(target.Data(:,:,:,chanIdx));
                    return;
                end
            end
        end
    catch
        % Fallback if lookup fails
    end
end

% Priority 2: Cached Current Data (if valid)
if isfield(d, 'currentData') && ~isempty(d.currentData) && chanIdx <= size(d.currentData, 4)
    cData = double(d.currentData(:,:,:,chanIdx));
    return;
end

% Priority 3: Legacy/Root Data
if isfield(d, 'ProcData') && ~isempty(d.ProcData) && numel(d.ProcData) >= chanIdx && ~isempty(d.ProcData{chanIdx})
    cData = d.ProcData{chanIdx};
elseif isfield(d, 'RawData') && ~isempty(d.RawData)
    cData = squeeze(d.RawData(:,:,:,chanIdx));
else
    cData = [];
end
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

    baseStr = 'Pixels';
    if ~isempty(strfind(src.String, 'Count')), baseStr = 'Count'; end

    if strcmp(ax.YScale, 'linear')
        ax.YScale = 'log';
        src.String = [baseStr ' (Log)'];
    else
        ax.YScale = 'linear';
        src.String = baseStr;
    end
catch
end
end

function toggleHistXScale(src, ~)
% Toggle X-axis Log/Lin
try
    ax = ancestor(src, 'axes');
    if isempty(ax), return; end

    currentStr = src.String;
    % Remove ' (Log)' if present to get base
    baseStr = strrep(currentStr, ' (Log)', '');

    if strcmp(ax.XScale, 'linear')
        ax.XScale = 'log';
        src.String = [baseStr ' (Log)'];
    else
        ax.XScale = 'linear';
        src.String = baseStr;
    end
catch
end
end



% onEditMask removed as unused.
% onEditMask body removed

function mask = getChannelMask(fig, chanIdx)
% Helper to retrieve the current mask (Custom or Threshold)
% Returns logical matrix where 1 = Background (masked out), 0 = Signal (valid)
mask = [];
dataTabGroup = findobj(fig, 'Tag', 'dataTabGroup');

thisTab = [];
if ~isempty(dataTabGroup) && chanIdx <= numel(dataTabGroup.Children)
    thisTab = dataTabGroup.Children(chanIdx);
end

if isempty(thisTab) || ~isvalid(thisTab)
    % Attempt to find within Unified Image View
    thisTab = findobj(fig, 'Tag', 'dataPlotArea');
    if isempty(thisTab) || ~isvalid(thisTab), return; end
end
meta = thisTab.UserData;

if isfield(meta, 'CustomMask') && ~isempty(meta.CustomMask)
    mask = logical(meta.CustomMask);
else
    % Threshold calculation

    % Priority 1: Unified Config (Global intensity threshold)
    guiData = fig.UserData;
    thVal = [];
    if isfield(guiData, 'config') && isfield(guiData.config, 'thresholdMin') && ~isempty(guiData.config.thresholdMin)
        thVal = guiData.config.thresholdMin;
    end

    % Priority 2: Legacy Tab Spinner
    if isempty(thVal)
        spnThresh = findobj(thisTab, 'Tag', sprintf('spnThresh_Ch%d', chanIdx));
        if ~isempty(spnThresh), thVal = spnThresh.Value; end
    end

    if ~isempty(thVal)
        if ~isempty(guiData.RawData) || (isfield(guiData, 'currentData') && ~isempty(guiData.currentData))
            cData = getChannelData(fig, chanIdx);
            if ~isempty(cData)
                projXY = sum(cData, 3);
                mask = (projXY <= thVal);
            else
                mask = [];
            end
        else
            mask = [];
        end
    else
        mask = [];
    end
end
end


function toggleHILIGHTerModality(fig)
% Finds fields by Tag
pnl = findobj(fig, 'Tag', 'pnlModelParams');
if isempty(pnl), return; end

gLife = findobj(pnl, 'Tag', 'gLife');
gFret = findobj(pnl, 'Tag', 'gFret');
gAnis = findobj(pnl, 'Tag', 'gAnis');

groups = [gLife, gFret, gAnis];
for i=1:numel(groups), if ~isempty(groups(i)), groups(i).Visible = 'off'; end; end

dd = findobj(fig, 'Tag', 'modeDropdown');
if isempty(dd), return; end
val = dd.Value;

% Update Sweep Dropdowns
ddSx = findobj(fig, 'Tag', 'ddSweepParamX');
ddSy = findobj(fig, 'Tag', 'ddSweepParamY');

lblCh = findobj(fig, 'Tag', 'lblNumCh');
spnCh = findobj(fig, 'Tag', 'numChannelsField');
if ~isempty(lblCh), lblCh.Visible = 'on'; end
if ~isempty(spnCh), spnCh.Visible = 'on'; end

if contains(val, 'FRET (Donor') % FRET
    if ~isempty(gFret), gFret.Visible = 'on'; end
    % Toggle sub-elements based on user request
    % "Donor FLIM does not require acceptor lifetime parameters, direct excitation or bleed through"
    % Hide Acceptor Tau, Direct Ex, Bleed
    set(findobj(gFret, 'Tag', 'fretAcceptorTauField'), 'Visible', 'off');
    set(findobj(gFret, 'Tag', 'lblAccTau'), 'Visible', 'off');
    set(findobj(gFret, 'Tag', 'fretDirectExField'), 'Visible', 'off');
    set(findobj(gFret, 'Tag', 'lblDirectEx'), 'Visible', 'off');
    set(findobj(gFret, 'Tag', 'fretBleedThroughField'), 'Visible', 'off');
    set(findobj(gFret, 'Tag', 'lblBleed'), 'Visible', 'off');

    sweepItems = {'Donor Tau', 'FRET E', 'Frac FRET'};

elseif contains(val, 'seFRET') % FRET 2-Channel
    if ~isempty(gFret), gFret.Visible = 'on'; end
    % Ensure All Visible
    set(findall(gFret, 'Type', 'uilabel'), 'Visible', 'on');
    set(findall(gFret, 'Type', 'uieditfield'), 'Visible', 'on');
    set(findall(gFret, 'Type', 'uinumericfield'), 'Visible', 'on');

    sweepItems = {'Donor Tau', 'Acceptor Tau', 'FRET E', 'Frac FRET', 'Direct Ex', 'Bleed Through'};
    % Explicitly hide Num Channels (forced 2)
    if ~isempty(lblCh), lblCh.Visible = 'off'; end
    if ~isempty(spnCh), spnCh.Visible = 'off'; end
    % Also force Num Channels to 2?
    if ~isempty(spnCh), spnCh.Value = 2; end

elseif contains(val, 'Anisotropy')
    if ~isempty(gAnis), gAnis.Visible = 'on'; end
    sweepItems = {'Anis Tau', 'Rotation', 'r0'};
    if ~isempty(lblCh), lblCh.Visible = 'off'; end
    if ~isempty(spnCh), spnCh.Visible = 'off'; end

else % Lifetime Gradient or Mix
    if ~isempty(gLife), gLife.Visible = 'on'; end
    % Check single vs mix
    t2 = findobj(gLife, 'Tag', 'tau2Field');
    alp = findobj(gLife, 'Tag', 'alphaField');
    lblT2 = findobj(gLife, 'Type', 'uilabel', 'Text', 'Lifetime 2 (ps):');
    lblAlp = findobj(gLife, 'Type', 'uilabel', 'Text', 'Mix Fraction (%):');

    if strcmp(val, 'Single Lifetime')
        % Hide second component fields entirely
        if ~isempty(t2), t2.Visible = 'off'; end
        if ~isempty(alp), alp.Visible = 'off'; end
        if ~isempty(lblT2), lblT2.Visible = 'off'; end
        if ~isempty(lblAlp), lblAlp.Visible = 'off'; end

        sweepItems = {'Lifetime 1'};
    else
        % Show fields for mix/other modes
        if ~isempty(t2), t2.Visible = 'on'; t2.Enable = 'on'; end
        if ~isempty(alp), alp.Visible = 'on'; alp.Enable = 'on'; end
        if ~isempty(lblT2), lblT2.Visible = 'on'; end
        if ~isempty(lblAlp), lblAlp.Visible = 'on'; end

        sweepItems = {'Lifetime 1', 'Lifetime 2', 'Mix Fraction'};
    end
end

if ~isempty(ddSx)
    ddSx.Items = sweepItems;
    if ~ismember(ddSx.Value, sweepItems) && ~isempty(sweepItems), ddSx.Value = sweepItems{1}; end
end

if ~isempty(ddSy)
    ddSy.Items = sweepItems;
    if ~ismember(ddSy.Value, sweepItems) && ~isempty(sweepItems), ddSy.Value = sweepItems{1}; end
end

updateSweepUI(fig);
end

function updateCLimFit(tab, type, val, pName)
meta = tab.UserData;
if isempty(meta) || ~isfield(meta, 'mapTg'), return; end

if nargin < 4 || isempty(pName)
    % Target active axis
    selTab = meta.mapTg.SelectedTab;
    % Robust pName extraction
    parts = strsplit(selTab.Tag, '_');
    if numel(parts) >= 2
        pName = parts{2};
    else
        pName = strrep(selTab.Tag, 'tab_', '');
    end
end

if ~isfield(meta.mapAxes, pName), return; end
ax = meta.mapAxes.(pName);
if isempty(ax) || ~isvalid(ax), return; end

lims = ax.CLim;
if strcmp(type, 'Min')
    lims(1) = val;
    if lims(1) >= lims(2), lims(2) = lims(1) + 0.001; end
else
    lims(2) = val;
    if lims(2) <= lims(1), lims(1) = lims(2) - 0.001; end
end

set(ax, 'CLim', lims);

% Sync Spinners (using correct structure)
if isfield(meta, 'mapSpins') && isfield(meta.mapSpins, pName)
    s = meta.mapSpins.(pName);
    if isvalid(s.Min), s.Min.Value = lims(1); end
    if isvalid(s.Max), s.Max.Value = lims(2); end
end

refreshTauHist(tab);
end

function syncTabSpinners(tab, type, val, pName)
meta = tab.UserData;
if isempty(meta) || ~isfield(meta, 'mapSpins'), return; end

if strcmp(type, 'Bins')
    % Power of 2 logic - specific to this histogram
    % Actually Bins might be individual per parameter?
    % Currently meta.lastBins implies global?
    % Let's make it local if possible, or keep global if intended.
    % User didn't complain about bins.
    % But logic below updates ALL bins.
    % Let's keep bins behavior for now or fix it too?
    % Let's fix ONLY the Max/Min issue first to be safe.

    % Wait, if I change signature, I must update call sites.
    % The logic below for Power of 2 seems to update meta.lastBins which is global.
    % Let's just fix the loop.

    if ~isfield(meta, 'lastBins'), meta.lastBins = 128; end
    oldVal = meta.lastBins;
    if val > oldVal
        val = 2^ceil(log2(val + 0.1));
    elseif val < oldVal
        val = 2^floor(log2(val - 0.1));
    end
    val = max(2, min(1024, val));
    if isnan(val), return; end
    meta.lastBins = val;
    tab.UserData = meta;

    % Update this spinner value
    s = meta.mapSpins.(pName);
    s.Bins.Value = val;

    refreshTauHist(tab); % This uses selected tab, so works if pName is selected
    return;
end

% For Max/Min, only update the relevant pName
if strcmp(type, 'Max') || strcmp(type, 'Min')
    if isnan(val), return; end
    % Update CLim for this parameter
    updateCLimFit(tab, type, val, pName);
end
end

function syncMapDisplay(tab)
try
    meta = tab.UserData;
    if isempty(meta) || ~isfield(meta, 'mapTg'), return; end

    % Get CLim of new active map
    selTab = meta.mapTg.SelectedTab;
    % Robust pName extraction: split by '_' and take second element
    % Tag format: 'tab_ParamName_AlgoName'
    parts = strsplit(selTab.Tag, '_');
    if numel(parts) >= 2
        pName = parts{2};
    else
        pName = strrep(selTab.Tag, 'tab_', '');
    end
    ax = meta.mapAxes.(pName);

    if isgraphics(ax)
        % Update Image CData from meta.Maps
        if isfield(meta, 'Maps') && isfield(meta.Maps, pName)
            hImg = findobj(ax, 'Type', 'image');
            if isempty(hImg)
                hImg = imagesc(ax, meta.Maps.(pName));
                hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(ancestor(tab, 'figure'), ev.IntersectionPoint);
            else
                hImg.CData = meta.Maps.(pName);
                if isempty(hImg.ButtonDownFcn)
                    hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(ancestor(tab, 'figure'), ev.IntersectionPoint);
                end
            end
        end

        lims = ax.CLim;
        if ~any(isnan(lims))
            % Safely access spinners if they exist
            if isfield(meta, 'mapSpins') && isfield(meta.mapSpins, pName)
                meta.mapSpins.(pName).Min.Value = lims(1);
                meta.mapSpins.(pName).Max.Value = lims(2);
            end
        end
        % Photons/Alpha/Delta Colormaps
        switch lower(pName)
            case 'photons', colormap(ax, 'parula');
            case 'alpha', colormap(ax, 'parula');
            case 'delta', colormap(ax, 'jet');
            otherwise, colormap(ax, 'jet');
        end
        % LiMA
        if isfield(meta, 'axMu') && isfield(meta.Maps, 'Mu')
            h = findobj(meta.axMu, 'Type', 'image');
            if ~isempty(h), h.CData = meta.Maps.Mu; end
        end
        if isfield(meta, 'axSig') && isfield(meta.Maps, 'Sigma')
            h = findobj(meta.axSig, 'Type', 'image');
            if ~isempty(h), h.CData = meta.Maps.Sigma; end
        end
        % Fisher
        if isfield(meta, 'axAlpha') && isfield(meta.Maps, 'Alpha')
            h = findobj(meta.axAlpha, 'Type', 'image');
            if ~isempty(h), h.CData = meta.Maps.Alpha; end
        end
        if isfield(meta, 'axDelta') && isfield(meta.Maps, 'Delta')
            h = findobj(meta.axDelta, 'Type', 'image');
            if ~isempty(h), h.CData = meta.Maps.Delta; end
        end
    end

    refreshTauHist(tab);
catch ME
    fprintf('Error in syncMapDisplay: %s\n', ME.message);
    disp(ME.stack(1));
end
end

% updateTauHistLines and onTauHistBinChange removed as unused.

function onTauHistLineMoving(~, tab, type, src)
val = src.Position(1,1);
updateCLimFit(tab, type, val);
end


function refreshTauHist(tab)
meta = tab.UserData;
if isempty(meta) || ~isfield(meta, 'mapTg'), return; end
fig = ancestor(tab, 'figure');

% Identify active parameter
selTab = meta.mapTg.SelectedTab;
parts = strsplit(selTab.Tag, '_');
if numel(parts) >= 2
    pName = parts{2};
else
    pName = strrep(selTab.Tag, 'tab_', '');
end
dName = selTab.Title;
axMain = meta.mapAxes.(pName);
axH = meta.mapHists.(pName);

% Get Data
MapData = [];
if isfield(meta, 'Maps') && isfield(meta.Maps, pName), MapData = meta.Maps.(pName); end
if isempty(MapData) || all(isnan(MapData(:))), return; end

% Get Bins from current tab spinner
bins = 128;
if isfield(meta, 'mapSpins') && isfield(meta.mapSpins, pName)
    bins = meta.mapSpins.(pName).Bins.Value;
end
clim = [0 1]; if ~isempty(axMain), clim = axMain.CLim; end

xLabels = struct('TauAvg', 'Lifetime (ns)', 'Intensity', 'Intensity (counts)', ...
    'Chi2', 'Chi-Squared', 'Back', 'Background (counts)', 'Photons', 'Total Photons', ...
    'Tau1', 'Tau 1 (ns)', 'Tau2', 'Tau 2 (ns)', 'Tau3', 'Tau 3 (ns)', ...
    'Frac1', 'Fraction 1 (%)', 'Frac2', 'Fraction 2 (%)', 'Frac3', 'Fraction 3 (%)', ...
    'Beta', 'Beta Factor', 'Alpha', 'Mixing Component (\alpha)', 'Delta', 'Residual (\delta)');

xLab = '--'; if isfield(xLabels, pName), xLab = xLabels.(pName); end

if ~isempty(axH) && isvalid(axH)
    cla(axH);
    hold(axH, 'on');
    % Clean data: Remove NaN, Inf
    data_clean = MapData(~isnan(MapData) & ~isinf(MapData));

    % Remove outliers (Use percentiles 1% - 99%)
    if ~isempty(data_clean)
        p1 = prctile(data_clean, 1);
        p99 = prctile(data_clean, 99);
        % Keep only data within this range for plotting
        data_clean = data_clean(data_clean >= p1 & data_clean <= p99);
    end

    if ~isempty(data_clean)
        histogram(axH, data_clean, bins, 'FaceColor', [0.6 0.6 0.6], 'EdgeColor', 'none');
        % Redraw lines with current CLim if valid
        if ~any(isnan(clim))
            lMin = drawline(axH, 'Position', [clim(1) 0; clim(1) 1e9], 'Color', 'y', 'Label', 'Min', 'Tag', 'lMin');
            lMax = drawline(axH, 'Position', [clim(2) 0; clim(2) 1e9], 'Color', [1 0.5 0], 'Label', 'Max', 'Tag', 'lMax');
            addlistener(lMin, 'MovingROI', @(src, ev) onTauHistLineMoving(fig, tab, 'Min', src));
            addlistener(lMax, 'MovingROI', @(src, ev) onTauHistLineMoving(fig, tab, 'Max', src));
            addlistener(lMin, 'ROIMoved', @(src, ev) updateCLimFit(tab, 'Min', src.Position(1,1)));
            addlistener(lMax, 'ROIMoved', @(src, ev) updateCLimFit(tab, 'Max', src.Position(1,1)));
        end

        xrange = max(data_clean) - min(data_clean);
        if xrange <= 0, xrange = 1; end
        axH.XLim = [min(data_clean)-0.1*xrange, max(data_clean)+0.1*xrange];
    end
    title(axH, sprintf('%s Distribution', dName), 'FontSize', 9);
    xlabel(axH, xLab);
    ylabel(axH, 'Pixels');
end
end
function onModelChange(src, pMulti, pStretch, tab, lblEq)
% Wrapper to handle visibility and update equation
setModelVisibility(src, pMulti, pStretch, tab);
updateEquationDisplay(tab, lblEq);
end

function setModelVisibility(src, pMulti, pStretch, tab)
if strcmp(src.Value, 'Multiexponential decay')
    pMulti.Visible = 'on'; pStretch.Visible = 'off';
else
    pMulti.Visible = 'off'; pStretch.Visible = 'on';
end
updateTabVisibility(tab);
end

function setComponentVisibility(src, comp2, comp3, tab, lblEq)
try
    N = src.Value;
    v2 = 'off'; if N >= 2, v2 = 'on'; end
    v3 = 'off'; if N >= 3, v3 = 'on'; end

    if iscell(comp2)
        for k = 1:numel(comp2), if isgraphics(comp2{k}), comp2{k}.Visible = v2; end; end
    end
    if iscell(comp3)
        for k = 1:numel(comp3), if isgraphics(comp3{k}), comp3{k}.Visible = v3; end; end
    end
    drawnow limitrate;
    updateTabVisibility(tab);
    if nargin > 4 && isgraphics(lblEq)
        updateEquationDisplay(tab, lblEq);
    end
catch ME
    fprintf(2, 'Error in setComponentVisibility: %s\n', ME.message);
end
end

function updateTabVisibility(tab)
try
    if isempty(tab) || ~isgraphics(tab), return; end
    meta = tab.UserData;
    % Check if meta is a standard struct, might be just []
    if isempty(meta) || ~isstruct(meta) || ~isfield(meta, 'mapTg'), return; end

    % Base tabs always visible: Photons, TauAvg, Red. Chi2, Background
    % Conditional tabs: Tau1, Frac1, Tau2, Frac2, Tau3, Frac3, Beta
    mode = 'Multiexponential decay';
    if isfield(meta, 'ddModel') && isgraphics(meta.ddModel), mode = meta.ddModel.Value; end
    numExp = 1;
    if isfield(meta, 'spnNExp') && isgraphics(meta.spnNExp), numExp = meta.spnNExp.Value; end

    pNames = {'Tau1', 'Frac1', 'Tau2', 'Frac2', 'Tau3', 'Frac3', 'Beta', 'TauAvg'};
    vis = struct();
    for i=1:numel(pNames), vis.(pNames{i}) = 'off'; end

    if strcmp(mode, 'Multiexponential decay')
        vis.Tau1 = 'on'; vis.Frac1 = 'on';
        % TauAvg hidden for N=1
        if numExp == 1
            vis.TauAvg = 'off';
        else
            vis.TauAvg = 'on';
        end

        if numExp >= 2, vis.Tau2 = 'on'; vis.Frac2 = 'on'; end
        if numExp >= 3, vis.Tau3 = 'on'; vis.Frac3 = 'on'; end
    else
        % Stretched: Tau1 not fitted. TauAvg IS fitted.
        vis.Beta = 'on';
        vis.TauAvg = 'on';
    end

    for i=1:numel(pNames)
        p = pNames{i};
        % t = findobj(meta.mapTg, 'Tag', ['tab_' p]);
        % findobj fails if parent is []

        if isfield(meta, 'tabs') && isfield(meta.tabs, p)
            t = meta.tabs.(p);
        else
            t = findobj(meta.mapTg, 'Tag', ['tab_' p]);
        end

        if ~isempty(t) && isgraphics(t)
            if strcmp(vis.(p), 'on')
                if ~isequal(t.Parent, meta.mapTg)
                    t.Parent = meta.mapTg;
                end
            else
                if ~isempty(t.Parent)
                    t.Parent = [];
                end
            end
        end
    end
catch ME
    fprintf(2, 'Error in updateTabVisibility: %s\n', ME.message);
end
end

function updateEquationDisplay(tab, lbl)
if isempty(lbl) || ~isgraphics(lbl), return; end
meta = tab.UserData;

mode = 'Multiexponential decay';
if isfield(meta, 'ddModel') && isgraphics(meta.ddModel), mode = meta.ddModel.Value; end

% Helper for Colors - Using RGB with SPACES (MATLAB standard)
    function c = pCol(fixTag, globTag)
        c = '[rgb]{1 0 0}'; % Red
        % Check Fixed
        cbF = findobj(tab, 'Tag', fixTag);
        if ~isempty(cbF) && cbF.Value, c = '[rgb]{0 0 1}'; end % Blue
        % Check Global
        cbG = findobj(tab, 'Tag', globTag);
        if ~isempty(cbG) && cbG.Value, c = '[rgb]{1 0 1}'; end % Magenta
    end

% Safe TeX color wrapper using character concatenation
    function out = colorTex(txt, fixTag, globTag)
        c = pCol(fixTag, globTag);
        % TeX syntax: \color[rgb]{1 0 0} text \color{black}
        % Using simple concatenation. Assuming default text color is black
        out = ['\color' c ' ' txt ' \color{black}'];
    end

str = '';
if strcmp(mode, 'Multiexponential decay')
    N = 1;
    if isfield(meta, 'spnNExp') && isgraphics(meta.spnNExp), N = meta.spnNExp.Value; end

    cBack = colorTex('C', 'chkFBack', 'chkGBack');

    if N == 1
        tau1 = colorTex('\tau', 'chkFTau1', 'chkGTau1');
        str = ['I(t) = I_0 e^{-t/' tau1 '} + ' cBack];
    elseif N == 2
        tau1 = colorTex('\tau_1', 'chkFTau1', 'chkGTau1');
        tau2 = colorTex('\tau_2', 'chkFTau2', 'chkGTau2');
        a2   = colorTex('\alpha_2', 'chkFFrac2', 'chkGFrac2');
        str = ['I(t) = I_0 [ (1-' a2 ')e^{-t/' tau1 '} + ' a2 'e^{-t/' tau2 '} ] + ' cBack];
    elseif N == 3
        tau1 = colorTex('\tau_1', 'chkFTau1', 'chkGTau1');
        tau2 = colorTex('\tau_2', 'chkFTau2', 'chkGTau2');
        tau3 = colorTex('\tau_3', 'chkFTau3', 'chkGTau3');
        a2   = colorTex('\alpha_2', 'chkFFrac2', 'chkGFrac2');
        a3   = colorTex('\alpha_3', 'chkFFrac3', 'chkGFrac3');
        str = ['I(t) = I_0 [ (1-' a2 '-' a3 ')e^{-t/' tau1 '} + ' a2 'e^{-t/' tau2 '} + ' a3 'e^{-t/' tau3 '} ] + ' cBack];
    end

else
    % Stretched
    ct = colorTex('\tau', 'chkFSTau', 'chkGSTau');
    cb = colorTex('\beta', 'chkFBeta', 'chkGBeta');
    cc = colorTex('C', 'chkFBack', 'chkGBack');
    str = ['I(t) = I_0 e^{-(t/' ct ')^{' cb '}} + ' cc];
end

lbl.Text = str;
end

% -------------------------------------------------------------------------
% CellSAM Integration
% -------------------------------------------------------------------------
function onLoadCellSAMModel(fig)
try
    fw = fig.UserData.CellSAMWrapper;
catch
    % Initialize if not exists
    try
        fw = CellSAMWrapper();
        d = fig.UserData;
        d.CellSAMWrapper = fw;
        fig.UserData = d;
    catch ME
        uialert(fig, ['Failed to init CellSAM: ' ME.message], 'Error');
        return;
    end
end

% Trigger download/load
f = uiprogressdlg(fig, 'Title', 'Loading CellSAM Model', 'Indeterminate', 'on');
try
    fw.downloadCheckpoint();
    success = fw.loadModel();
    if success
        uialert(fig, 'Model Loaded Successfully!', 'Success');
    else
        uialert(fig, 'Model Failed to Load. Check console.', 'Error');
    end
catch ME
    uialert(fig, ['Error: ' ME.message], 'Error');
end
close(f);
end

function onRunCellSAM(fig)
d = fig.UserData;
if ~isfield(d, 'CellSAMWrapper') || isempty(d.CellSAMWrapper)
    uialert(fig, 'Please load model first.', 'Warning');
    return;
end

if isempty(d.RawData)
    uialert(fig, 'No data loaded.', 'Error');
    return;
end

imgRaw = d.RawData(:,:,:,1);
imgParam = sum(imgRaw, 3);
imgNorm = imgParam / max(imgParam(:));

f = uiprogressdlg(fig, 'Title', 'Segmenting...', 'Indeterminate', 'on');
try
    masks = d.CellSAMWrapper.segment(imgNorm);

    tabCellSAM = findobj(fig, 'Title', 'CellSAM');
    if isempty(tabCellSAM), close(f); return; end

    ax = findobj(tabCellSAM, 'Type', 'axes');
    if isempty(ax)
        ax = uiaxes(tabCellSAM, 'Position', [50 50 500 500]);
    end

    imshow(imgNorm, 'Parent', ax); hold(ax, 'on');

    if ~isempty(masks)
        B = bwboundaries(masks);
        for k = 1:length(B)
            boundary = B{k};
            plot(ax, boundary(:,2), boundary(:,1), 'r', 'LineWidth', 2);
        end
    end
    title(ax, 'Segmentation Result');

catch ME
    uialert(fig, ['Segmentation failed: ' ME.message], 'Error');
end
close(f);
end

function handleIRFChange(fig, ~, lblIRFExpl, algo, src)
if isempty(lblIRFExpl) || ~isgraphics(lblIRFExpl), return; end
set(lblIRFExpl, 'Text', getIRFExplString(algo, src));
updatePixelAnalysis(fig, [nan nan]);
end

function txt = getIRFExplString(algo, src)
switch algo
    case 'Iterative Reconvolution'
        txt = sprintf('Model: $I(t) = IRF(1\\dots G, %s) \\otimes \\sum \\alpha_i e^{-t/\\tau_i}$', src);
    case 'Grid MLE'
        txt = sprintf('IRF (%s) used to generate model library $P(g|\\tau)$', src);
    case 'Tail Fitting'
        txt = 'IRF is not used (fitting starts after peak delay window)';
    otherwise
        txt = sprintf('IRF (%s) integrated into %s analysis', src, algo);
end
end

function [irf, irf_t] = getIRFFromSource(fig, tab, RawData)
data = fig.UserData;
meta = tab.UserData;
% Unified Config Retrieval (same as runFitAnalysis)
dFlow = flows_getData(fig);
config = data.config; % Default
if isfield(dFlow, 'navGroup') && isfield(dFlow, 'navFile') && isfield(dFlow, 'Conditions') && ~isempty(dFlow.Conditions)
    try
        cIdx = dFlow.navGroup; fIdx = dFlow.navFile;
        if cIdx <= numel(dFlow.Conditions) && fIdx <= numel(dFlow.Conditions{cIdx}.Analysis)
            if isfield(dFlow.Conditions{cIdx}.Analysis(fIdx), 'Config')
                fileCfg = dFlow.Conditions{cIdx}.Analysis(fIdx).Config;
                if ~isempty(fileCfg), config = fileCfg; end
            end
        end
    catch
    end
end
irf_src = meta.ddIRF.Value;

% Robustness Check: Data Gates vs Config Gates
nGatesData = size(RawData, 3);
if isempty(config.gate_edges) || numel(config.gate_edges) ~= nGatesData + 1
    % Regenerate edges based on data dimension
    gate_edges = linspace(0, config.T, nGatesData + 1);
    % Also regenerate t if necessary for simulation model consistency
    % (Assuming dt needs to be fine enough)
    dt = config.dt; T = config.T; t = 0:dt:T;
else
    gate_edges = config.gate_edges;
    dt = config.dt; T = config.T; t = 0:dt:T;
end
gate_centers = 0.5 * (gate_edges(1:end-1) + gate_edges(2:end));

if strcmp(irf_src, 'Simulated')
    irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);

    % Apply IRF Shift (irf_shift in ps)
    irf_shift = 0;
    if isfield(config, 'irf_shift'), irf_shift = config.irf_shift; end
    if irf_shift ~= 0
        dt_step = t(2) - t(1);
        shift_bins = round((irf_shift/1000) / dt_step);
        irf = circshift(irf, [0, shift_bins]);
        if shift_bins > 0
            irf(1:min(shift_bins, end)) = 0;
        elseif shift_bins < 0
            irf(max(1, end+shift_bins):end) = 0;
        end
    end
    irf_t = t;
    fwhm_val = config.fwhm;
    pos_val = t(1); % Approximate
elseif strcmp(irf_src, 'Estimated')
    if nargin < 3 || isempty(RawData)
        RawData = getChannelData(fig, meta.activeChanIdx);
    end
    % Sum data across all pixels to get a high-SNR decay curve
    sum_decay = squeeze(sum(double(RawData), [1 2]));

    % Robust baseline estimation (from the region before the rise)
    % Find rough peak first
    [~, rawPeakIdx] = max(sum_decay);
    % Estimate baseline from pre-peak region if possible, else median
    if rawPeakIdx > 10
        baseline = median(sum_decay(1:rawPeakIdx-10));
    else
        baseline = min(sum_decay);
    end

    signal = max(0, sum_decay - baseline);
    [maxVal, pIdx] = max(signal);

    if maxVal == 0
        % No signal found, fallback to simulated
        irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma);
        irf_t = t;
        fwhm_val = config.fwhm;
        pos_val = t(1);
    else
        % Improved Gaussian Fit:
        % 1. Find the numerical gradient
        d_decay = diff([0; signal]);
        [~, ~] = max(d_decay);

        % Peak of gradient is roughly the center of the IRF
        % Rise time (10% to 90%) relates to FWHM
        p10 = find(signal > 0.1 * maxVal, 1, 'first');
        p90 = find(signal > 0.9 * maxVal, 1, 'first');
        if isempty(p10), p10 = max(1, pIdx-2); end
        if isempty(p90), p90 = pIdx; end
        riseTime_ns = gate_centers(p90) - gate_centers(p10);

        % Refined Guess:
        % Center it at the 50% point of the rise
        p50 = find(signal > 0.5 * maxVal, 1, 'first');
        mu_guess = gate_centers(p50);
        fwhm_guess = max(0.05, riseTime_ns);

        % Fit to the left side (up to peak)
        fitIdxs = max(1, p10-3):pIdx;
        t_fit = gate_centers(fitIdxs);
        v_fit = signal(fitIdxs);

        p0 = [maxVal, mu_guess, fwhm_guess];
        gaussFunc = @(p, x) p(1) * exp(-(x - p(2)).^2 ./ (2 * (p(3)/(2*sqrt(2*log(2))))^2));
        obj = @(p) sum((gaussFunc(p, t_fit(:)) - v_fit(:)).^2);

        opts = optimset('Display', 'off', 'TolX', 1e-4);
        p_opt = fminsearch(obj, p0, opts);

        pos_val = p_opt(2);
        fwhm_val = abs(p_opt(3));

        % Ensure fwhm is not crazy
        if fwhm_val > 1.5, fwhm_val = 0.4; end
        if fwhm_val < 0.02, fwhm_val = 0.02; end

        % Generate Gaussian IRF on the dense grid t
        irf = exp(-((t - pos_val).^2) / (2 * (fwhm_val / (2 * sqrt(2 * log(2))))^2));
        irf_t = t;
    end

elseif strcmp(irf_src, 'Experimental')
    irf = data.irf_data;
    if isempty(irf)
        % Fallback if no experimental data loaded
        irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma);
        irf_t = t;
        fwhm_val = config.fwhm;
        pos_val = t(1);
    else
        irf_t = gate_centers;
        % Rough FWHM Estimate
        [m, p] = max(irf);
        pos_val = irf_t(p);
        halfMax = m / 2;
        i1 = find(irf(1:p) >= halfMax, 1, 'first');
        i2 = find(irf(p:end) <= halfMax, 1, 'first');
        if ~isempty(i1) && ~isempty(i2)
            fwhm_val = irf_t(p + i2 - 1) - irf_t(i1);
        else
            fwhm_val = 0.5;
        end
    end
end

% Update Labels in GUI if they exist
if isfield(meta, 'lblIRFFWHM') && isvalid(meta.lblIRFFWHM)
    meta.lblIRFFWHM.Text = sprintf('%.3f', fwhm_val);
end
if isfield(meta, 'lblIRFPos') && isvalid(meta.lblIRFPos)
    meta.lblIRFPos.Text = sprintf('%.3f', pos_val);
end
end

function disableDefaultInteractions(ax)
if isempty(ax) || ~isvalid(ax), return; end
if isprop(ax, 'Interactions')
    ax.Interactions = [];
end
try
    ax.Toolbar.Visible = 'off';
catch
end
end

function syncAnalysisTabsWithConfig(fig)
% SYNCANALYSISTABSWITHCONFIG - Updates "Fit Range (Bins)" spinners in all
% analysis tabs to match the current gate count.

data = fig.UserData;
if isempty(data) || ~isfield(data, 'config'), return; end
N = data.config.N_gates;

% Find the analysis tab group
ats = findobj(fig, 'Tag', 'analysisTabs');
if isempty(ats), return; end

% Iterate through all analysis tabs (Grid MLE, Iterative, etc.)
for k = 1:numel(ats.Children)
    t = ats.Children(k);
    meta = t.UserData;

    % Check if tab has the spinners we need to update
    if isstruct(meta) && isfield(meta, 'spnStart') && isfield(meta, 'spnEnd')
        % Update Limits to match new N_gates
        if isvalid(meta.spnStart)
            meta.spnStart.Limits = [1 N];
            if meta.spnStart.Value > N, meta.spnStart.Value = 1; end
        end
        if isvalid(meta.spnEnd)
            meta.spnEnd.Limits = [1 N];
            if meta.spnEnd.Value > N || meta.spnEnd.Value < 1, meta.spnEnd.Value = N; end
        end

        % Resize/Reset Maps if dimensions changed
        if isfield(data, 'RawData')
            [nY, nX, ~, ~] = size(data.RawData);
            if isfield(meta, 'Maps') && isfield(meta.Maps, 'Photons')
                [mH, mW] = size(meta.Maps.Photons);
                if mH ~= nY || mW ~= nX
                    % Re-initialize maps with zero placeholders as requested
                    pNames = fieldnames(meta.Maps);
                    for i = 1:numel(pNames)
                        meta.Maps.(pNames{i}) = zeros(nY, nX);
                    end
                    t.UserData = meta;
                end
            end
        end
    end
end
end

function updateIRFStatsDisplay(irf, ~)
% Helper to calculate and display FWHM/Pos from an IRF vector
% Replicates logic from getIRFFromSource but without needing config struct
if isempty(irf), return; end

[~, ~] = max(irf);
% We assume standard gate time scaling if t vector unknown
% Just approximation for display if accurate t not passed
% But we really want consistent values.
% Best relies on getIRFFromSource doing it.

% Actually, getIRFFromSource updates the labels!
% So just calling getIRFFromSource is enough.
end

% === Simulation UI Helper Functions ===

function manageSimulationConfig(fig, dropdown)
val = dropdown.Value;
dropdown.Value = 'Default'; % Reset
switch val
    case 'Load...'
        [file, path] = uigetfile('*.mat', 'Load Config');
        if isequal(file, 0), return; end
        try
            d = load(fullfile(path, file), 'simConfig');
            if isfield(d, 'simConfig')
                % logic to populate fields from struct
                % Requires mapping struct fields to UI tags
                uialert(fig, 'Config Loaded (Placeholder)', 'Info');
            end
        catch
            uialert(fig, 'Invalid config file', 'Error');
        end
    case 'Save Current...'
        [file, path] = uiputfile('*.mat', 'Save Config', 'HILIGHTer_Config.mat');
        if isequal(file, 0), return; end
        simConfig = struct(); % Placeholder
        save(fullfile(path, file), 'simConfig');
end
end

function onDimChange(fig, type)
dx = findobj(fig, 'Tag', 'dimXField');
dy = findobj(fig, 'Tag', 'dimYField');
asp = findobj(fig, 'Tag', 'chkAspect');

src = [];
if strcmp(type, 'X'), src = dx; elseif strcmp(type, 'Y'), src = dy; end

% Enforce Power of 2 Stepping
if ~isempty(src)
    if isempty(src.UserData), src.UserData = src.Value; end

    newVal = src.Value;
    oldVal = src.UserData;

    if newVal ~= oldVal
        % Determine if this was a step click (1 step) or manual entry
        % Step is 1 in spinner properties
        if abs(newVal - oldVal) <= 1.5
            if newVal > oldVal
                % Power Up
                val = 2^(floor(log2(oldVal)) + 1);
            else
                % Power Down
                val = 2^(ceil(log2(oldVal)) - 1);
            end
        else
            % Manual entry: Snap nearest
            val = 2^round(log2(newVal));
        end

        % Clamp limits
        val = max(1, min(4096, val));
        src.Value = val;
        src.UserData = val;
    end
end

if strcmp(type, 'Aspect')
    if asp.Value
        dy.Enable = 'off';
        dy.Value = dx.Value;
        dy.UserData = dx.Value;
    else
        dy.Enable = 'on';
    end
elseif strcmp(type, 'X')
    if asp.Value
        dy.Value = dx.Value;
        dy.UserData = dx.Value;
    end
end
end

function onPhotonChange(fig)
ph = findobj(fig, 'Tag', 'photonsField');
if isempty(ph), return; end

if isempty(ph.UserData), ph.UserData = ph.Value; end

newVal = ph.Value;
oldVal = ph.UserData;

if newVal ~= oldVal
    % Determine increment direction
    % Spinner step is 1, so check relative change
    if abs(newVal - oldVal) <= 1.5 % Likely a spinner click
        if newVal > oldVal
            % Power Up: e.g. 100 -> 1000
            val = 10^(floor(log10(oldVal)) + 1);
        else
            % Power Down
            val = 10^(ceil(log10(oldVal)) - 1);
        end
    else
        % Manual entry: Accept value
        val = newVal;
    end

    % Clamp
    val = max(1, val);
    ph.Value = val;
    ph.UserData = val;
end

updateRateDisplay(fig);
end

function updateRateDisplay(fig)
ph = findobj(fig, 'Tag', 'photonsField');
dw = findobj(fig, 'Tag', 'dwellField');
dt = findobj(fig, 'Tag', 'deadTimeField');
lr = findobj(fig, 'Tag', 'lblRate');
lp = findobj(fig, 'Tag', 'lblPileUp');

if isempty(ph) || isempty(dw), return; end

rateMHz = ph.Value / dw.Value;
lr.Text = sprintf('Rate: %.1f MHz', rateMHz);

rd = rateMHz * dt.Value * 1e-3;
loss = (1 - 1/(1 + rd)) * 100;
lp.Text = sprintf('Lost: %.1f %%', loss);
end

function toggleIRFSync(fig)
chk = findobj(fig, 'Tag', 'chkSyncIRF');
s1 = findobj(fig, 'Tag', 'irfShiftField_Ch1');
s2 = findobj(fig, 'Tag', 'irfShiftField_Ch2');

if chk.Value
    s2.Enable = 'off';
    s2.Value = s1.Value;
else
    s2.Enable = 'on';
end
end

function updateSweepUI(fig)
chkX = findobj(fig, 'Tag', 'chkSweepX');
chkY = findobj(fig, 'Tag', 'chkSweepY');

controlsX = {findobj(fig, 'Tag', 'ddSweepParamX'), findobj(fig, 'Tag', 'sweepStartX'), ...
    findobj(fig, 'Tag', 'sweepEndX'), findobj(fig, 'Tag', 'sweepPadStartX'), ...
    findobj(fig, 'Tag', 'sweepPadEndX'), findobj(fig, 'Tag', 'ddSweepTypeX')};

controlsY = {findobj(fig, 'Tag', 'ddSweepParamY'), findobj(fig, 'Tag', 'sweepStartY'), ...
    findobj(fig, 'Tag', 'sweepEndY'), findobj(fig, 'Tag', 'sweepPadStartY'), ...
    findobj(fig, 'Tag', 'sweepPadEndY'), findobj(fig, 'Tag', 'ddSweepTypeY')};

set([controlsX{:}], 'Enable', 'off');
set([controlsY{:}], 'Enable', 'off');

if isvalid(chkX) && chkX.Value, set([controlsX{:}], 'Enable', 'on'); end
if isvalid(chkY) && chkY.Value, set([controlsY{:}], 'Enable', 'on'); end

ddX = findobj(fig, 'Tag', 'ddSweepParamX');
ddY = findobj(fig, 'Tag', 'ddSweepParamY');

pnl = findobj(fig, 'Tag', 'pnlModelParams');
if isempty(pnl), return; end

% Re-enable all fields that are currently visible
% This fixes the issue where unchecking sweep didn't re-enable the field
visFields = findobj(pnl, 'Type', 'uieditfield', 'Visible', 'on');
if ~isempty(visFields), set(visFields, 'Enable', 'on'); end
visSpinners = findobj(pnl, 'Type', 'uispinner', 'Visible', 'on');
if ~isempty(visSpinners), set(visSpinners, 'Enable', 'on'); end

% Ensure specific fields like Lifetime 1 are definitely enabled if visible
tau1 = findobj(pnl, 'Tag', 'tau1Field');
if ~isempty(tau1) && strcmp(tau1.Visible, 'on'), tau1.Enable = 'on'; end

% Helper to get unit string
getUnit = @(tag) getUnitForParam(tag);

if isvalid(chkX) && chkX.Value && ~isempty(ddX.Value)
    tag = getTagForParam(ddX.Value, fig);
    f = findobj(pnl, 'Tag', tag);
    if ~isempty(f), f.Enable = 'off'; end

    % Update Units X
    uStr = getUnit(tag);
    lblSU = findobj(fig, 'Tag', 'lblStartUnitX');
    lblEU = findobj(fig, 'Tag', 'lblEndUnitX');
    if ~isempty(lblSU), lblSU.Text = uStr; end
    if ~isempty(lblEU), lblEU.Text = uStr; end
else
    % Clear Units
    lblSU = findobj(fig, 'Tag', 'lblStartUnitX');
    lblEU = findobj(fig, 'Tag', 'lblEndUnitX');
    if ~isempty(lblSU), lblSU.Text = ''; end
    if ~isempty(lblEU), lblEU.Text = ''; end
end

if isvalid(chkY) && chkY.Value && ~isempty(ddY.Value)
    tag = getTagForParam(ddY.Value, fig);
    f = findobj(pnl, 'Tag', tag);
    if ~isempty(f), f.Enable = 'off'; end

    % Update Units Y
    uStr = getUnit(tag);
    lblSU = findobj(fig, 'Tag', 'lblStartUnitY');
    lblEU = findobj(fig, 'Tag', 'lblEndUnitY');
    if ~isempty(lblSU), lblSU.Text = uStr; end
    if ~isempty(lblEU), lblEU.Text = uStr; end
else
    % Clear Units
    lblSU = findobj(fig, 'Tag', 'lblStartUnitY');
    lblEU = findobj(fig, 'Tag', 'lblEndUnitY');
    if ~isempty(lblSU), lblSU.Text = ''; end
    if ~isempty(lblEU), lblEU.Text = ''; end
end

end

function u = getUnitForParam(tag)
u = '';
if contains(tag, 'tau') || contains(tag, 'Tau') || contains(tag, 'Time'), u = 'ps'; end
if contains(tag, 'frac') || contains(tag, 'Frac') || contains(tag, 'alpha') ...
        || contains(tag, 'EField') || contains(tag, 'Direct') || contains(tag, 'Bleed'), u = '%'; end
if contains(tag, 'rotation') || contains(tag, 'Rotation'), u = 'ps'; end
if contains(tag, 'R0'), u = ''; end
end

function tag = getTagForParam(paramName, ~)
tag = '';
switch paramName
    case 'Lifetime 1', tag = 'tau1Field';
    case 'Lifetime 2', tag = 'tau2Field';
    case 'Mix Fraction', tag = 'alphaField';
    case 'Donor Tau', tag = 'fretTauField';
    case 'Acceptor Tau', tag = 'fretAcceptorTauField';
    case 'FRET E', tag = 'fretEField';
    case 'Frac FRET', tag = 'fretFracField';
    case 'Anis Tau', tag = 'anisLifetimeField';
    case 'Rotation', tag = 'anisRotationField';
    case 'r0', tag = 'anisR0Field';
end
end

function setupModelParams(fig)
pnl = findobj(fig, 'Tag', 'pnlModelParams');
if isempty(pnl), return; end
delete(pnl.Children);

inputH = 22;

% --- 1. Lifetime Fields ---
% --- 1. Lifetime Fields ---
% Height matches pnlModelParams (140)
gLife = uipanel(pnl, 'BorderType', 'none', 'Position', [0 0 280 140], 'Tag', 'gLife', 'Visible', 'off');
currY = 110; % Reset top Y for 140px height
uilabel(gLife, 'Text', 'Lifetime 1 (ps):', 'Position', [10 currY 90 inputH]);
uieditfield(gLife, 'numeric', 'Value', 1000, 'Position', [100 currY 80 inputH], 'Tag', 'tau1Field', 'Tooltip', 'Lifetime 1');

currY = currY - 35;
uilabel(gLife, 'Text', 'Lifetime 2 (ps):', 'Position', [10 currY 90 inputH]);
uieditfield(gLife, 'numeric', 'Value', 2000, 'Position', [100 currY 80 inputH], 'Tag', 'tau2Field', 'Tooltip', 'Lifetime 2');

currY = currY - 35;
uilabel(gLife, 'Text', 'Mix Fraction (%):', 'Position', [10 currY 90 inputH]);
uieditfield(gLife, 'numeric', 'Value', 50, 'Position', [100 currY 80 inputH], 'Tag', 'alphaField', 'Tooltip', 'Fraction of Component 2');

% --- 2. FRET Fields ---
gFret = uipanel(pnl, 'BorderType', 'none', 'Position', [0 0 280 140], 'Tag', 'gFret', 'Visible', 'off');
currY = 110;
uilabel(gFret, 'Text', 'Donor T (ps):', 'Position', [10 currY 80 inputH]);
uieditfield(gFret, 'numeric', 'Value', 2500, 'Position', [100 currY 60 inputH], 'Tag', 'fretTauField');

uilabel(gFret, 'Text', 'Acc T (ps):', 'Position', [170 currY 60 inputH]);
uieditfield(gFret, 'numeric', 'Value', 1500, 'Position', [230 currY 50 inputH], 'Tag', 'fretAcceptorTauField');

currY = currY - 35;
uilabel(gFret, 'Text', 'FRET E (%):', 'Position', [10 currY 80 inputH]);
uieditfield(gFret, 'numeric', 'Value', 50, 'Position', [100 currY 60 inputH], 'Tag', 'fretEField');

uilabel(gFret, 'Text', 'Frac FRET(%):', 'Position', [170 currY 80 inputH]);
uieditfield(gFret, 'numeric', 'Value', 50, 'Position', [250 currY 30 inputH], 'Tag', 'fretFracField');

currY = currY - 35;
uilabel(gFret, 'Text', 'Dir.Ex (%):', 'Position', [10 currY 80 inputH]);
uieditfield(gFret, 'numeric', 'Value', 5, 'Position', [100 currY 60 inputH], 'Tag', 'fretDirectExField');

uilabel(gFret, 'Text', 'Bleed (%):', 'Position', [170 currY 80 inputH]);
uieditfield(gFret, 'numeric', 'Value', 10, 'Position', [250 currY 30 inputH], 'Tag', 'fretBleedThroughField');

% --- 3. Anisotropy Fields ---
gAnis = uipanel(pnl, 'BorderType', 'none', 'Position', [0 0 280 140], 'Tag', 'gAnis', 'Visible', 'off');
currY = 110;
uilabel(gAnis, 'Text', 'Lifetime (ps):', 'Position', [10 currY 80 inputH]);
uieditfield(gAnis, 'numeric', 'Value', 2500, 'Position', [100 currY 60 inputH], 'Tag', 'anisLifetimeField');

currY = currY - 35;
uilabel(gAnis, 'Text', 'Rotation(ps):', 'Position', [10 currY 80 inputH]);
uieditfield(gAnis, 'numeric', 'Value', 500, 'Position', [100 currY 60 inputH], 'Tag', 'anisRotationField');

currY = currY - 35;
uilabel(gAnis, 'Text', 'Initial r0:', 'Position', [10 currY 80 inputH]);
uieditfield(gAnis, 'numeric', 'Value', 0.4, 'Position', [100 currY 60 inputH], 'Tag', 'anisR0Field');
end

function map = getParameterMap(fig, pName, baseVal, nX, nY, scale)
% Base
map = repmat(baseVal, nY, nX);
if nargin < 6, scale = 1; end

% Check Sweeps
cx = findobj(fig, 'Tag', 'chkSweepX');
dx = findobj(fig, 'Tag', 'ddSweepParamX');
cy = findobj(fig, 'Tag', 'chkSweepY');
dy = findobj(fig, 'Tag', 'ddSweepParamY');

if isvalid(cx) && cx.Value && (strcmp(dx.Value, pName) || contains(dx.Value, pName))
    % Sweep X (Now generates vertical gradient per user request "other way round")
    sx = findobj(fig, 'Tag', 'sweepStartX').Value;
    ex = findobj(fig, 'Tag', 'sweepEndX').Value;
    ps = findobj(fig, 'Tag', 'sweepPadStartX').Value;
    pe = findobj(fig, 'Tag', 'sweepPadEndX').Value;
    type = findobj(fig, 'Tag', 'ddSweepTypeX').Value;

    % Use nY for length, transpose to column, repeat across X
    grad = createGradient(sx, ex, nY, ps, pe, type) * scale;
    map = repmat(grad', 1, nX);
end

if isvalid(cy) && cy.Value && (strcmp(dy.Value, pName) || contains(dy.Value, pName))
    % Sweep Y (Now generates horizontal gradient per user request "other way round")
    sy = findobj(fig, 'Tag', 'sweepStartY').Value;
    ey = findobj(fig, 'Tag', 'sweepEndY').Value;
    ps = findobj(fig, 'Tag', 'sweepPadStartY').Value;
    pe = findobj(fig, 'Tag', 'sweepPadEndY').Value;
    type = findobj(fig, 'Tag', 'ddSweepTypeY').Value;

    % Use nX for length, repeat rows
    grad = createGradient(sy, ey, nX, ps, pe, type) * scale;
    map = repmat(grad, nY, 1);
end
end

function g = createGradient(s, e, N, padS, padE, type)
nGrad = N - padS - padE;
if nGrad < 1
    % Just padS and padE (truncate)
    g = [repmat(s, 1, padS), repmat(e, 1, padE)];
    if length(g)>N, g=g(1:N); end
    if length(g)<N, g(end+1:N)=e; end
    return;
end

if strcmp(type, 'Non-Linear')
    % Quadratic
    t = linspace(0, 1, nGrad);
    vals = s + (e - s) * (t.^2);
else
    vals = linspace(s, e, nGrad);
end

g = [repmat(s, 1, padS), vals, repmat(e, 1, padE)];
end


% === FLOWS PORTED FUNCTIONALITY ===

function d = flows_getData(fig)
dAll = fig.UserData;
if ~isfield(dAll, 'Flows') || isempty(dAll.Flows)
    dAll.Flows = struct('Conditions', {{}});
    fig.UserData = dAll;
end
d = dAll.Flows;
end

function flows_setData(fig, d)
dAll = fig.UserData;
dAll.Flows = d;
fig.UserData = dAll;
end

function flows_refreshCondList(fig)
d = flows_getData(fig);
nC = numel(d.Conditions);
items = cell(1, nC);
for i = 1:nC
    if strcmp(d.Conditions{i}.Type, 'Positive Control'), prefix = "✓ [P] ";
    elseif strcmp(d.Conditions{i}.Type, 'Negative Control'), prefix = "✗ [N] ";
    else, prefix = "○ [E] ";
    end
    items{i} = sprintf('%s%s (%d)', prefix, d.Conditions{i}.Name, numel(d.Conditions{i}.Files));
end
% Find Listbox in the new panel
lb = findobj(fig, 'Tag', 'condListBox');
if ~isempty(lb), lb.Items = items; end
end

function idx = flows_getSelectedCondIndex(fig)
lb = findobj(fig, 'Tag', 'condListBox');
if isempty(lb), idx = []; return; end
val = lb.Value;
if isempty(val), idx = []; return; end
idx = find(strcmp(lb.Items, val));
end

function flows_updateFileDisplay(fig)
idx = flows_getSelectedCondIndex(fig);
lbFiles = findobj(fig, 'Tag', 'fileListBox');
if isempty(lbFiles), return; end

if isempty(idx)
    lbFiles.Items = {};
    return;
end
d = flows_getData(fig);
files = d.Conditions{idx}.Files;
nF = numel(files);
dispFiles = cell(1, nF);
for i = 1:nF
    [p, n, e] = fileparts(files{i});
    [~, parent] = fileparts(p);
    dispFiles{i} = sprintf('[%s] %s%s', parent, n, e);
end
lbFiles.Items = dispFiles;
lbFiles.UserData = files; % Store raw paths in listbox userdata for easy access
end

function flows_promptConditionName(fig, newFiles)
d = flows_getData(fig);
newName = char(inputdlg('Enter Name for New Condition:', 'Create Condition', [1 50], {['Group_' char(datetime("now", 'Format', 'HHmmss'))]}));
if isempty(newName), return; end

newCond = struct('Name', newName, 'Type', 'Experimental', 'Files', {newFiles(:)});
d.Conditions{end+1} = newCond;
flows_setData(fig, d);

flows_refreshCondList(fig);
% Auto-select
lb = findobj(fig, 'Tag', 'condListBox');
if ~isempty(lb) && ~isempty(lb.Items)
    lb.Value = lb.Items{end};
    flows_updateFileDisplay(fig);
end
end

function flows_createFromFiles(fig)
[files, path] = uigetfile({'*.sdt;*.SDT;*.ptu', 'TCSPC Files (*.sdt, *.ptu)'}, 'Select Files', 'MultiSelect', 'on');
if isequal(files, 0), return; end
if ischar(files), files = {files}; end
fullPaths = cellfun(@(f) fullfile(path, f), files, 'UniformOutput', false);
flows_promptConditionName(fig, fullPaths);
end

function flows_createFromFolder(fig)
folder = uigetdir(pwd, 'Select Folder');
if isequal(folder, 0), return; end
dDir = dir(fullfile(folder, '**', '*.*'));
dDir = dDir(~[dDir.isdir]);
% Filter basic extensions if needed, but taking all for now as per Flows
paths = arrayfun(@(x) fullfile(x.folder, x.name), dDir, 'UniformOutput', false);
if isempty(paths), return; end
flows_promptConditionName(fig, paths(:));
end

function flows_renameCondition(fig)
idx = flows_getSelectedCondIndex(fig); if isempty(idx), return; end
d = flows_getData(fig);
answer = inputdlg('Rename Condition:', 'Manage', [1 50], {d.Conditions{idx}.Name});
if ~isempty(answer)
    d.Conditions{idx}.Name = char(answer);
    flows_setData(fig, d);
    flows_refreshCondList(fig);
end
end

function flows_flagCondition(fig)
idx = flows_getSelectedCondIndex(fig); if isempty(idx), return; end
d = flows_getData(fig);
types = {'Experimental', 'Positive Control', 'Negative Control'};
currType = d.Conditions{idx}.Type;
if contains(currType, 'Experimental'), currType = 'Experimental'; end
cIdx = find(strcmp(types, currType));
if isempty(cIdx), cIdx = 1; end
d.Conditions{idx}.Type = types{mod(cIdx, 3)+1};
flows_setData(fig, d);
flows_refreshCondList(fig);
end

function flows_deleteCondition(fig)
idx = flows_getSelectedCondIndex(fig); if isempty(idx), return; end
d = flows_getData(fig);
d.Conditions(idx) = [];
flows_setData(fig, d);
flows_refreshCondList(fig);
flows_updateFileDisplay(fig);
end

function flows_mergeConditions(fig)
lb = findobj(fig, 'Tag', 'condListBox');
if isempty(lb) || numel(lb.Items) < 2, return; end
[sel, ok] = listdlg('ListString', lb.Items, 'PromptString', 'Select to merge:', 'Name', 'Merge');
if ~ok || numel(sel) < 2, return; end

d = flows_getData(fig);
for i = 2:numel(sel)
    d.Conditions{sel(1)}.Files = unique([d.Conditions{sel(1)}.Files; d.Conditions{sel(i)}.Files]);
end
d.Conditions(sel(2:end)) = [];
flows_setData(fig, d);
flows_refreshCondList(fig);
flows_updateFileDisplay(fig);
end

function flows_duplicateCondition(fig)
idx = flows_getSelectedCondIndex(fig); if isempty(idx), return; end
d = flows_getData(fig);
newC = d.Conditions{idx};
newC.Name = [newC.Name '_Copy'];
d.Conditions{end+1} = newC;
flows_setData(fig, d);
flows_refreshCondList(fig);
end

function flows_addFiles(fig)
cIdx = flows_getSelectedCondIndex(fig); if isempty(cIdx), return; end
[f, p] = uigetfile({'*.sdt;*.SDT;*.ptu', 'TCSPC Files'}, 'Import', 'MultiSelect', 'on');
if isequal(f,0), return; end
if ischar(f), f = {f}; end
d = flows_getData(fig);
d.Conditions{cIdx}.Files = unique([d.Conditions{cIdx}.Files; fullfile(p, f(:))]);
flows_setData(fig, d);
flows_updateFileDisplay(fig);
flows_refreshCondList(fig);
end

function flows_removeFiles(fig)
cIdx = flows_getSelectedCondIndex(fig); if isempty(cIdx), return; end
lbFiles = findobj(fig, 'Tag', 'fileListBox');
sel = lbFiles.Value; if isempty(sel), return; end
if ischar(sel), sel = {sel}; end

d = flows_getData(fig);
uPaths = lbFiles.UserData;
isSel = ismember(lbFiles.Items, sel);
pathsToRemove = uPaths(isSel);
d.Conditions{cIdx}.Files = setdiff(d.Conditions{cIdx}.Files, pathsToRemove);
flows_setData(fig, d);
flows_updateFileDisplay(fig);
flows_refreshCondList(fig);
end

function flows_moveFiles(fig)
cIdx = flows_getSelectedCondIndex(fig); if isempty(cIdx), return; end
lbFiles = findobj(fig, 'Tag', 'fileListBox');
sel = lbFiles.Value; if isempty(sel), return; end

d = flows_getData(fig);
names = cellfun(@(c) c.Name, d.Conditions, 'UniformOutput', false);
[dIdx, ok] = listdlg('ListString', names, 'SelectionMode', 'single', 'PromptString', 'Move to:');
if ~ok || isequal(dIdx, cIdx), return; end

uPaths = lbFiles.UserData;
if ischar(sel), sel = {sel}; end
isSel = ismember(lbFiles.Items, sel);
pathsToMove = uPaths(isSel);
d.Conditions{cIdx}.Files = setdiff(d.Conditions{cIdx}.Files, pathsToMove);
d.Conditions{dIdx}.Files = unique([d.Conditions{dIdx}.Files; pathsToMove(:)]);
flows_setData(fig, d);
flows_updateFileDisplay(fig);
flows_refreshCondList(fig);
end

function flows_onBinTypeChange(fig, dd)
spn = findobj(fig, 'Tag', 'flowsBinSpinner');
if isempty(spn), return; end
switch dd.Value
    case 'Simple Binning'
        spn.Limits = [1 10]; spn.Value = 1; spn.Enable = 'on';
    case 'Gaussian Filter'
        spn.Limits = [0.1 10]; spn.Value = 1.0; spn.Step = 0.1; spn.Enable = 'on';
    otherwise
        spn.Enable = 'off';
end
end

function flows_runAnalysis(fig)
d = flows_getData(fig);
if isempty(d.Conditions), uialert(fig, 'No conditions defined!', 'Error'); return; end

% Prepare Config
dd = findobj(fig, 'Tag', 'flowsBinType');
spn = findobj(fig, 'Tag', 'flowsBinSpinner');
binType = 'None'; binVal = 0;
if ~isempty(dd), binType = dd.Value; end
if ~isempty(spn), binVal = spn.Value; end
d.config.spatialBinning = binVal;
d.config.binType = binType;

% Channel Config
ddCh = findobj(fig, 'Tag', 'flowsChannelMode');
spnCh = findobj(fig, 'Tag', 'flowsChannelSpinner');
chMode = 'Keep All Channels'; chVal = 1;
if ~isempty(ddCh), chMode = ddCh.Value; end
if ~isempty(spnCh), chVal = spnCh.Value; end
d.config.channelMode = chMode;
d.config.channelVal = chVal;

% Check duplicate load
if isfield(d.Conditions{1}, 'Analysis') && ~isempty(d.Conditions{1}.Analysis)
    choice = uiconfirm(fig, 'Data seems to be already loaded. Reload?', 'Load Data', ...
        'Options', {'Reload', 'Keep Existing'}, 'DefaultOption', 'Keep Existing');
    if strcmp(choice, 'Keep Existing')
        groupsTab_refreshUI(fig);
        return;
    end
end

totalFiles = 0;
for i = 1:numel(d.Conditions), totalFiles = totalFiles + numel(d.Conditions{i}.Files); end
if totalFiles == 0, uialert(fig, 'No files to load!', 'Error'); return; end

prog = uiprogressdlg(fig, 'Title', 'Loading Data', 'Message', 'Initializing...', 'Cancelable', true);
cleanObj = onCleanup(@() delete(prog)); % Ensure progress dialog is closed

try
    % Ensure read_SDT
    if exist('read_SDT', 'file')~=2 && exist('AppProperties/read_SDT.m', 'file')==2
        addpath('AppProperties');
    end

    count = 0;
    for i = 1:numel(d.Conditions)
        files = d.Conditions{i}.Files;
        % Pre-initialize struct to ensure Data field exists even if empty
        d.Conditions{i}.Analysis = struct('Config', cell(1, numel(files)), 'Data', cell(1, numel(files)));

        for f = 1:numel(files)
            if prog.CancelRequested, error('UserCancelled'); end
            count = count + 1;
            [~, fname, ~] = fileparts(files{f});
            prog.Message = sprintf('Loading %s (%d/%d)...', fname, count, totalFiles);
            prog.Value = count / totalFiles;

            try
                if exist('read_SDT', 'file') == 2
                    [sdt, cfg] = read_SDT(files{f});
                    d.Conditions{i}.Analysis(f).Config = cfg;

                    % Channel Processing
                    if exist('chMode', 'var')
                        if strcmp(chMode, 'Sum All Channels')
                            sdt = sum(sdt, 4); % Sum (Result is 1 Channel)
                        elseif strcmp(chMode, 'Force Single Channel')
                            if chVal <= size(sdt, 4)
                                sdt = sdt(:,:,:,chVal);
                            else
                                warning('Requested Channel %d exceeds data channels (%d). Using all.', chVal, size(sdt,4));
                            end
                        end
                    end

                    % Pre-Processing
                    if ~strcmp(d.config.binType, 'None') && d.config.spatialBinning > 0
                        param = d.config.spatialBinning;
                        [~, ~, nT, nC] = size(sdt);
                        if strcmp(d.config.binType, 'Simple Binning')
                            scale = 1/param;
                            tmp = imresize(sdt(:,:,1,1), scale, 'box');
                            [newY, newX] = size(tmp);
                            newSDT = zeros(newY, newX, nT, nC, 'like', sdt);
                            for c=1:nC, for t=1:nT, newSDT(:,:,t,c) = imresize(sdt(:,:,t,c), scale, 'box') * (param^2); end; end
                            sdt = newSDT;
                        elseif strcmp(d.config.binType, 'Gaussian Filter')
                            for c=1:nC, for t=1:nT, sdt(:,:,t,c) = imgaussfilt(sdt(:,:,t,c), param); end; end
                        end
                    end

                    d.Conditions{i}.Analysis(f).Data = sdt;
                else
                    warning('read_SDT function not found.');
                    d.Conditions{i}.Analysis(f).Data = [];
                end
            catch err
                warning('Failed to load %s: %s', fname, err.message);
            end
        end
    end

    % Save Data & Refresh UI
    flows_setData(fig, d);
    close(prog);
    groupsTab_refreshUI(fig);
    refreshUnifiedPlots(fig);
    uialert(fig, 'Data Loaded Successfully!', 'Success');

catch ME
    close(prog);
    if ~strcmp(ME.message, 'UserCancelled')
        uialert(fig, ['Load Failed: ' ME.message], 'Error');
    end
end
end

% === NEW DATA FRAME HELPERS ===

function createGroupsTabInterface(fig, parentTab)
% Modeled accurately after FlowsAnalysis.m LEFT PANEL

% Initialize State for this tab if needed
if ~isfield(fig.UserData, 'GroupsTab')
    fig.UserData.GroupsTab = struct('CurrentChannel', 1, 'ControlOpacity', 0.3, 'ExpOpacity', 0.3);
end

% Main Layout: 3 Rows (Toolbar, Controls, Experiments)
grid = uigridlayout(parentTab, [3 1]);
grid.RowHeight = {50, '1x', '1x'};
grid.Padding = [5 5 5 5];
grid.RowSpacing = 5;

% --- 1. Toolbar (Channel Selection) ---
toolGrid = uigridlayout(grid, [1 3]);
toolGrid.ColumnWidth = {60, '1x', 150};
toolGrid.Padding = [0 0 0 0];

uilabel(toolGrid, 'Text', 'Channel:', 'FontWeight', 'bold');

% Channel Radio Group (Dynamic based on data?)
% We'll create a container that we populate dynamically
bg = uibuttongroup(toolGrid, 'BorderType', 'none', 'BackgroundColor', [0.94 0.94 0.94], ...
    'Tag', 'groupsTab_ChannelGrp', 'SelectionChangedFcn', @(s,e) groupsTab_onChannelChange(fig, e));
% Initial dummy buttons (will be refreshed)
uiradiobutton(bg, 'Text', 'Ch 1', 'Position', [5 5 50 30], 'Tag', '1');

uibutton(toolGrid, 'Text', 'Filtering / Threshold ⚡', ...
    'BackgroundColor', [0.6 0.2 0.8], 'FontColor', 'white', ...
    'ButtonPushedFcn', @(s,e) safeOpenThreshold(fig));

% --- 2. Controls Panel ---
ctrlP = uipanel(grid, 'Title', 'CONTROLS', 'BackgroundColor', [0.2 0.25 0.2], 'ForegroundColor', 'white');
cGrid = uigridlayout(ctrlP, [1 2]);
cGrid.ColumnWidth = {150, '1x'};

% Left Side: Selector
cSide = uigridlayout(cGrid, [3 1]);
cSide.RowHeight = {20, 25, '1x'};
uilabel(cSide, 'Text', 'Select Group:', 'FontColor', 'white');
uidropdown(cSide, 'Items', {'None'}, 'Tag', 'groupsTab_ddCtrl', ...
    'ValueChangedFcn', @(s,e) groupsTab_updateTabs(fig, 'Ctrl'));

% Right Side: Tabs
uitabgroup(cGrid, 'Tag', 'groupsTab_tgCtrl');

% --- 3. Experimental Panel ---
expP = uipanel(grid, 'Title', 'EXPERIMENTAL CONDITIONS', 'BackgroundColor', [0.2 0.2 0.25], 'ForegroundColor', 'white');
eGrid = uigridlayout(expP, [1 2]);
eGrid.ColumnWidth = {150, '1x'};

% Left Side: Selector
eSide = uigridlayout(eGrid, [3 1]);
eSide.RowHeight = {20, 25, '1x'};
uilabel(eSide, 'Text', 'Select Group:', 'FontColor', 'white');
uidropdown(eSide, 'Items', {'None'}, 'Tag', 'groupsTab_ddExp', ...
    'ValueChangedFcn', @(s,e) groupsTab_updateTabs(fig, 'Exp'));

% Right Side: Tabs
uitabgroup(eGrid, 'Tag', 'groupsTab_tgExp');

% Initial Update
groupsTab_refreshUI(fig);
end

function groupsTab_refreshUI(fig)
d = flows_getData(fig);

% 1. Channels
bg = findobj(fig, 'Tag', 'groupsTab_ChannelGrp');
if ~isempty(bg)
    delete(bg.Children);
    nCh = 1;
    % Try to find channel count from first file
    if ~isempty(d.Conditions) && isfield(d.Conditions{1}, 'Analysis') && ~isempty(d.Conditions{1}.Analysis)
        dat = d.Conditions{1}.Analysis(1).Data;
        if ~isempty(dat), nCh = size(dat, 4); end
    end
    % Create Buttons
    btnW = 60; spacing = 5;
    for i = 1:nCh
        xPos = 5 + (i-1)*(btnW + spacing);
        rb = uiradiobutton(bg, 'Text', sprintf('Ch %d', i), ...
            'Tag', num2str(i), 'Position', [xPos, 5, btnW, 30]);
        if i == fig.UserData.GroupsTab.CurrentChannel, rb.Value = true; end
    end
end

% 2. Dropdowns
if ~isempty(d.Conditions)
    types = cellfun(@(c) c.Type, d.Conditions, 'UniformOutput', false);
    names = cellfun(@(c) c.Name, d.Conditions, 'UniformOutput', false);
    isCtrl = contains(types, 'Control', 'IgnoreCase', true);
    ctrlGroups = names(isCtrl);
    expGroups = names(~isCtrl);
else
    ctrlGroups = {}; expGroups = {};
end
if isempty(ctrlGroups), ctrlGroups = {'None'}; end
if isempty(expGroups), expGroups = {'None'}; end

ddC = findobj(fig, 'Tag', 'groupsTab_ddCtrl');
if ~isempty(ddC), ddC.Items = ctrlGroups; end

ddE = findobj(fig, 'Tag', 'groupsTab_ddExp');
if ~isempty(ddE), ddE.Items = expGroups; end

% 3. Update Tabs Content based on selection
groupsTab_updateTabs(fig, 'Ctrl');
groupsTab_updateTabs(fig, 'Exp');
end

function groupsTab_updateTabs(fig, type)
d = flows_getData(fig);
chan = fig.UserData.GroupsTab.CurrentChannel;

tagDD = ['groupsTab_dd' type];
tagTG = ['groupsTab_tg' type];

dd = findobj(fig, 'Tag', tagDD);
tg = findobj(fig, 'Tag', tagTG);
if isempty(dd) || isempty(tg), return; end

val = dd.Value; delete(tg.Children);
if strcmp(val, 'None'), return; end

% Find Condition Index
cIdx = 0;
for i = 1:numel(d.Conditions)
    if strcmp(d.Conditions{i}.Name, val), cIdx = i; break; end
end
if cIdx == 0, return; end

% Populate Tabs
cond = d.Conditions{cIdx};
if ~isfield(cond, 'Analysis') || isempty(cond.Analysis), return; end

for i = 1:numel(cond.Analysis)
    [~, fname, ~] = fileparts(cond.Files{i});
    t = uitab(tg, 'Title', fname);
    g = uigridlayout(t, [1 1]); g.Padding = [0 0 0 0];
    ax = uiaxes(g, 'BackgroundColor', 'black');

    rawData = cond.Analysis(i).Data;
    if ~isempty(rawData) && chan <= size(rawData, 4)
        img = sum(rawData(:,:,:,chan), 3);
        imagesc(ax, img); colormap(ax, 'turbo');
        axis(ax, 'image', 'off');
        colorbar(ax, 'Color', 'white');
    else
        title(ax, 'No Data', 'Color', 'white');
    end
end
end

function groupsTab_onChannelChange(fig, event)
fig.UserData.GroupsTab.CurrentChannel = str2double(event.NewValue.Tag);
groupsTab_updateTabs(fig, 'Ctrl');
groupsTab_updateTabs(fig, 'Exp');
end

function createImageTabInterface(fig, parentTab, ~)
% Main Layout
mainGrid = uigridlayout(parentTab, [3 1]);
mainGrid.RowHeight = {40, 40, '1x'};
mainGrid.Padding = [0 0 0 0];
mainGrid.RowSpacing = 0;

% --- 1. File Navigation Bar ---
fileBar = uipanel(mainGrid);
fileGrid = uigridlayout(fileBar, [1 4]);
fileGrid.ColumnWidth = {150, 40, 40, '1x'};
fileGrid.Padding = [2 2 2 2];

uidropdown(fileGrid, 'Tag', 'ddImgGroup', 'Items', {'No Groups'}, 'ValueChangedFcn', @(s,e) navFile(fig, 'group'));
uibutton(fileGrid, 'Text', '◀', 'ButtonPushedFcn', @(s,e) navFile(fig, 'prevFile'), 'Tooltip', 'Prev File');
uibutton(fileGrid, 'Text', '▶', 'ButtonPushedFcn', @(s,e) navFile(fig, 'nextFile'), 'Tooltip', 'Next File');
uidropdown(fileGrid, 'Tag', 'ddImgFile', 'Items', {'No Files'}, 'ValueChangedFcn', @(s,e) navFile(fig, 'file'));

% --- 2. Channel Navigation Bar ---
topBar = uipanel(mainGrid);
navLayout = uigridlayout(topBar, [1 6]);
navLayout.ColumnWidth = {40, 40, '1x', 40, 40, 100};
navLayout.Padding = [2 2 2 2];

uibutton(navLayout, 'Text', '⏮', 'ButtonPushedFcn', @(s,e) navChannel(fig, 'first'), 'Tooltip', 'First Channel');
uibutton(navLayout, 'Text', '◀', 'ButtonPushedFcn', @(s,e) navChannel(fig, 'prev'), 'Tooltip', 'Previous Channel');
uilabel(navLayout, 'Text', 'Channel 1', 'HorizontalAlignment', 'center', 'Tag', 'lblNavChannel', 'FontWeight', 'bold');
uibutton(navLayout, 'Text', '▶', 'ButtonPushedFcn', @(s,e) navChannel(fig, 'next'), 'Tooltip', 'Next Channel');
uibutton(navLayout, 'Text', '⏭', 'ButtonPushedFcn', @(s,e) navChannel(fig, 'last'), 'Tooltip', 'Last Channel');
uidropdown(navLayout, 'Items', {'Channel 1', 'Channel 2', 'Channel 3', 'Channel 4'}, 'Tag', 'ddNavChannel', ...
    'ValueChangedFcn', @(s,e) navChannel(fig, 'jump'));

% --- 2. Visualization Panel ---
plotArea = uipanel(mainGrid, 'BorderType', 'none', 'Tag', 'dataPlotArea');

% New Layout: Grid for Plots & Controls
pGrid = uigridlayout(plotArea, [4 2]);
% Rows: XY Area (Large), XT Area (Medium), Hist Area (Medium), Bottom Controls (Small)
pGrid.RowHeight = {'1x', 100, 100, 40};
pGrid.ColumnWidth = {'1x', 140}; % Scan Area (Flexible), Controls (Fixed)
pGrid.Padding = [5 5 5 5];
pGrid.RowSpacing = 5;

% 1. XY Projection (Top Left)
axXY = uiaxes(pGrid, 'Tag', 'axXY_Unified', 'BackgroundColor', 'black');
axXY.Layout.Row = 1; axXY.Layout.Column = 1;
disableDefaultInteractivity(axXY);
axXY.Toolbar.Visible = 'off';

% 2. XT Projection (Row 2, Full Width)
axXT = uiaxes(pGrid, 'Tag', 'axXT_Unified', 'BackgroundColor', 'black');
axXT.Layout.Row = 2; axXT.Layout.Column = [1 2];
disableDefaultInteractivity(axXT);
axXT.Toolbar.Visible = 'off';

% 3. Histogram (Row 3, Left)
axHist = uiaxes(pGrid, 'Tag', 'axHist_Unified', 'BackgroundColor', 'white');
axHist.Layout.Row = 3; axHist.Layout.Column = 1;
disableDefaultInteractivity(axHist);
axHist.Toolbar.Visible = 'off';

% 4. Contrast Controls (Row 3, Right)
ctrlHist = uigridlayout(pGrid, [4 2]);
ctrlHist.Layout.Row = 3; ctrlHist.Layout.Column = 2;
ctrlHist.RowHeight = {20, 22, 20, 22};
ctrlHist.ColumnWidth = {'fit', '1x'};
ctrlHist.Padding = [0 0 0 0];

uilabel(ctrlHist, 'Text', 'Contrast:');
uilabel(ctrlHist, 'Text', '');
uilabel(ctrlHist, 'Text', 'Min');
spnMin = uispinner(ctrlHist, 'Tag', 'spnMin_Unified', 'Value', 0, 'Limits', [0 Inf], 'ValueChangedFcn', @(s,e) refreshUnifiedPlots(fig));
uilabel(ctrlHist, 'Text', 'Max');
spnMax = uispinner(ctrlHist, 'Tag', 'spnMax_Unified', 'Value', 1000, 'Limits', [0 Inf], 'ValueChangedFcn', @(s,e) refreshUnifiedPlots(fig));

% 5. Bottom Controls (Row 4, Full Width)
btmGrid = uigridlayout(pGrid, [1 7]);
btmGrid.Layout.Row = 4; btmGrid.Layout.Column = [1 2];
btmGrid.ColumnWidth = {'fit', 60, 40, 40, 50, 80, '1x'};
btmGrid.Padding = [0 0 0 0];

uilabel(btmGrid, 'Text', 'Threshold:');
uispinner(btmGrid, 'Tag', 'spnThresh_Unified', 'Value', 10, 'Limits', [0 Inf]);
uibutton(btmGrid, 'Text', 'Set');
uibutton(btmGrid, 'Text', 'Auto');
uibutton(btmGrid, 'Text', 'Reset');
uibutton(btmGrid, 'Text', 'Edit Mask');

binPanel = uipanel(btmGrid, 'BorderType', 'none');
binGrid = uigridlayout(binPanel, [1 2]);
binGrid.Padding = [0 0 0 0];
uilabel(binGrid, 'Text', 'Binning:', 'HorizontalAlignment', 'right');
uidropdown(binGrid, 'Items', {'Off', '2x2', '3x3', '4x4'}, 'Tag', 'ddBinning_Unified');

% Store Handles
uiData.axXY = axXY;
uiData.axXT = axXT;
uiData.axHist = axHist;
uiData.spnMin = spnMin;
uiData.spnMax = spnMax;
plotArea.UserData = uiData;
end

function navChannel(fig, action)
d = flows_getData(fig);
curr = d.navChannel;
maxCh = 1;

% Get Max Ch from current data
if isfield(d, 'currentData') && ~isempty(d.currentData)
    maxCh = size(d.currentData, 4);
elseif isfield(d, 'RawData') && ~isempty(d.RawData)
    maxCh = size(d.RawData, 4);
end

switch action
    case 'next', curr = min(curr + 1, maxCh);
    case 'prev', curr = max(curr - 1, 1);
    case 'first', curr = 1;
    case 'last', curr = maxCh;
    case 'jump'
        dd = findobj(fig, 'Tag', 'ddNavChannel');
        val = dd.Value;
        parsed = sscanf(val, 'Channel %d');
        if ~isempty(parsed), curr = parsed; end
end
d.navChannel = curr;
flows_setData(fig, d);

% Update Label & Dropdown
lbl = findobj(fig, 'Tag', 'lblNavChannel');
if ~isempty(lbl), lbl.Text = sprintf('Channel %d', curr); end
dd = findobj(fig, 'Tag', 'ddNavChannel');
if ~isempty(dd), dd.Value = sprintf('Channel %d', curr); end

% Refresh plots
refreshUnifiedPlots(fig);

% Update Analysis Tabs to match the new channel context
updateAnalysisContext(fig, curr);
end

function updateAnalysisContext(fig, newChan)
try
    ats = findobj(fig, 'Tag', 'analysisTabs');
    if isempty(ats), return; end
    for k = 1:numel(ats.Children)
        t = ats.Children(k);
        if isstruct(t.UserData) && isfield(t.UserData, 'activeChanIdx')
            meta = t.UserData;
            meta.activeChanIdx = newChan;
            t.UserData = meta;

            % Trigger live refresh if the tab is visible
            if strcmp(ats.SelectedTab.Title, t.Title)
                try
                    if contains(t.Title, 'Phasor'), refreshPhasorPlot(fig, []); end
                    % Add others if they have specific refresh fns
                catch
                end
            end
        end
    end
catch
end
end

function refreshUnifiedPlots(fig)
d = flows_getData(fig); % Use correct accessor
plotArea = findobj(fig, 'Tag', 'dataPlotArea');
if isempty(plotArea), return; end
uiData = plotArea.UserData;

axXY = uiData.axXY;
axXT = uiData.axXT;
axHist = uiData.axHist;

% Update Dropdowns (Group/File)
ddGrp = findobj(fig, 'Tag', 'ddImgGroup');
ddFile = findobj(fig, 'Tag', 'ddImgFile');

% Ensure indices exist
if ~isfield(d, 'navGroup'), d.navGroup = 1; end
if ~isfield(d, 'navFile'), d.navFile = 1; end
if ~isfield(d, 'navChannel'), d.navChannel = 1; end

currentData = [];

% Debug output (optional, remove later if spammy)
% disp(['Refreshing Image Tab. Groups: ' num2str(numel(d.Conditions))]);

if isfield(d, 'Conditions') && ~isempty(d.Conditions)
    grpNames = cellfun(@(x) x.Name, d.Conditions, 'UniformOutput', false);
    ddGrp.Items = grpNames;

    % Validate navGroup
    if d.navGroup > numel(grpNames), d.navGroup = 1; end
    ddGrp.Value = grpNames{d.navGroup};

    % Files
    if isfield(d.Conditions{d.navGroup}, 'Files')
        files = d.Conditions{d.navGroup}.Files;
        nF = numel(files);
        fileNames = cell(1, nF);
        for k=1:nF, [~,n,~]=fileparts(files{k}); fileNames{k}=n; end
        if isempty(fileNames), fileNames = {'No Files'}; end
        ddFile.Items = fileNames;

        % Validate navFile
        if d.navFile > numel(fileNames), d.navFile = 1; end
        if ~strcmpi(fileNames{1}, 'No Files')
            ddFile.Value = fileNames{d.navFile};

            % DATA
            if isfield(d.Conditions{d.navGroup}, 'Analysis') && numel(d.Conditions{d.navGroup}.Analysis) >= d.navFile
                currentData = d.Conditions{d.navGroup}.Analysis(d.navFile).Data;
            end
        else
            ddFile.Value = 'No Files';
        end
    else
        ddFile.Items = {'No Files'};
    end
else
    ddGrp.Items = {'No Groups'};
    ddFile.Items = {'No Files'};
end

% Persist current data for channel nav
d.currentData = currentData;
% We don't necessarily need to save back here unless we fixed indices, but good practice if state is self-correcting
flows_setData(fig, d);

% Plotting
if isempty(currentData)
    cla(axXY); title(axXY, 'No Data', 'Color', 'white'); axis(axXY, 'off');
    cla(axXT); axis(axXT, 'off');
    cla(axHist); axis(axHist, 'off');
    return;
end

ch = d.navChannel;
if ch > size(currentData, 4), ch = 1; d.navChannel=1; flows_setData(fig, d); end

dataCh = currentData(:,:,:,ch);

% 1. XY Projection (Sum over time)
imgXY = sum(dataCh, 3);

% Auto-Scale Contrast (if spinners default or invalid)
mn = uiData.spnMin.Value; mx = uiData.spnMax.Value;
if (mn == 0 && mx == 1000) || (mx <= mn)
    mn = min(imgXY(:)); mx = max(imgXY(:));
    if mx <= mn, mx = mn + 1; end
    if isnan(mn), mn=0; end
    if isnan(mx), mx=1; end
    uiData.spnMin.Value = mn; uiData.spnMax.Value = mx;
end

% Plot XY
hImg = imagesc(axXY, imgXY);
hImg.ButtonDownFcn = @(src, ev) updatePixelAnalysis(fig, ev.IntersectionPoint);
colormap(axXY, getAppColormap());
colorbar(axXY);
axis(axXY, 'image', 'off');
clim(axXY, [mn mx]);
title(axXY, sprintf('Channel %d - XY Projection', ch), 'Color', 'white');

% 2. XT Projection (Sum over Y -> X, Time)
imgXT = squeeze(sum(dataCh, 1))';
hImgXT = imagesc(axXT, imgXT);
hImgXT.HitTest = 'off'; % XT usually doesn't need click
colormap(axXT, getAppColormap());
axis(axXT, 'normal', 'off');
title(axXT, 'XT Projection', 'Color', 'white');

% 3. Histogram
histogram(axHist, imgXY(:), 50, 'FaceColor', [0.8 0.8 0.8], 'EdgeColor', 'none');
xlim(axHist, [mn mx]);
title(axHist, 'Intensity Histogram');
axHist.XColor = 'black'; axHist.YColor = 'black';
grid(axHist, 'on');
end

function cmap = getAppColormap()
cmap = turbo(256);
end

% loadSelected placeholders removed as unused.

function openGroupsThresholdGUI(parentFig)
% Create Modal Dialog
dWidth = 500; dHeight = 400;
dlg = uifigure('Name', 'Threshold Settings', 'Position', [100 100 dWidth dHeight], ...
    'WindowStyle', 'modal', 'Resize', 'off', 'Color', 'white');
movegui(dlg, 'center');

% Layout
mainGrid = uigridlayout(dlg, [4 1]);
mainGrid.RowHeight = {40, '1x', 50, 40};
mainGrid.Padding = [10 10 10 10];

% Header
uilabel(mainGrid, 'Text', 'Intensity Threshold Configuration', 'FontSize', 16, 'FontWeight', 'bold', ...
    'HorizontalAlignment', 'center');

% Histogram Axis
axAndControl = uigridlayout(mainGrid, [1 2]);
axAndControl.ColumnWidth = {'1x', 120};
axAndControl.Padding = [0 0 0 0];

ax = uiaxes(axAndControl);
title(ax, 'Intensity Distribution');
xlabel(ax, 'Photons');
ylabel(ax, 'Count');

% Controls (Right of Hist)
ctrlP = uipanel(axAndControl, 'BorderType', 'none');
cGrid = uigridlayout(ctrlP, [5 1]);
cGrid.RowHeight = {22, 22, 22, 22, '1x'};
cGrid.Padding = [0 0 0 0];
uilabel(cGrid, 'Text', 'Thresholds:', 'FontWeight', 'bold');

uilabel(cGrid, 'Text', 'Min:');
spnMin = uispinner(cGrid, 'Limits', [0 Inf], 'Value', 0, 'Tag', 'thMin');

uilabel(cGrid, 'Text', 'Max:');
spnMax = uispinner(cGrid, 'Limits', [0 Inf], 'Value', 10000, 'Tag', 'thMax');

% Histogram Data Loading
fData = flows_getData(parentFig);
AGG_DATA_SIZE = 0;
if ~isempty(fData.Conditions)
    for i = 1:numel(fData.Conditions)
        if isfield(fData.Conditions{i}, 'Analysis')
            AGG_DATA_SIZE = AGG_DATA_SIZE + numel(fData.Conditions{i}.Analysis);
        end
    end
end
allDataCell = cell(1, AGG_DATA_SIZE);
kIter = 1;
% Aggregate data for histogram
if ~isempty(fData.Conditions)
    for i = 1:numel(fData.Conditions)
        if isfield(fData.Conditions{i}, 'Analysis')
            for f = 1:numel(fData.Conditions{i}.Analysis)
                if ~isfield(fData.Conditions{i}.Analysis(f), 'Data'), continue; end
                tmp = fData.Conditions{i}.Analysis(f).Data;
                if ~isempty(tmp)
                    % Use sum projection for intensity
                    img = sum(tmp, 3);
                    allDataCell{kIter} = img(:);
                    kIter = kIter + 1;
                end
            end
        end
    end
end
% Trim empty cells if any
allDataCell = allDataCell(1:kIter-1);
allData = cell2mat(allDataCell(:));

if isempty(allData)
    title(ax, 'No Data Available');
else
    histogram(ax, allData, 100, 'FaceColor', [0.4 0.4 0.4]);
    grid(ax, 'on');

    mn = min(allData); mx = max(allData);
    if isfield(fData.config, 'thresholdMin'), mn = fData.config.thresholdMin; end
    if isfield(fData.config, 'thresholdMax'), mx = fData.config.thresholdMax; end

    spnMin.Value = mn;
    spnMax.Value = mx;
end

% Draw Lines
% Draw Lines
updateThresholdLines(ax, spnMin.Value, spnMax.Value);

spnMin.ValueChangedFcn = @(s,e) updateThresholdLines(ax, spnMin.Value, spnMax.Value);
spnMax.ValueChangedFcn = @(s,e) updateThresholdLines(ax, spnMin.Value, spnMax.Value);

% Footer Buttons
btnGrid = uigridlayout(mainGrid, [1 3]);
uibutton(btnGrid, 'Text', 'Auto Threshold', 'ButtonPushedFcn', @(s,e) autoThreshold(spnMin, spnMax, allData, ax));
uibutton(btnGrid, 'Text', 'Cancel', 'ButtonPushedFcn', @(s,e) delete(dlg));
uibutton(btnGrid, 'Text', 'APPLY', 'FontWeight', 'bold', 'BackgroundColor', [0.2 0.6 0.2], 'FontColor', 'white', ...
    'ButtonPushedFcn', @(s,e) applyThreshold(parentFig, dlg, spnMin.Value, spnMax.Value));

    function updateThresholdLines(theAx, mn, mx)
        try
            delete(findobj(theAx, 'Tag', 'thLine'));
            yl = get(theAx, 'YLim');
            line(theAx, [mn mn], yl, 'Color', 'r', 'LineWidth', 2, 'Tag', 'thLine');
            line(theAx, [mx mx], yl, 'Color', 'r', 'LineWidth', 2, 'Tag', 'thLine');
        catch
        end
    end

    function autoThreshold(sMin, sMax, data, ax)
        if isempty(data), return; end
        sMin.Value = prctile(data, 1);
        sMax.Value = prctile(data, 99);
        updateThresholdLines(ax, sMin.Value, sMax.Value);
    end

    function applyThreshold(fig, dlg, mn, mx)
        fData = flows_getData(fig);
        fData.config.thresholdMin = mn;
        fData.config.thresholdMax = mx;
        flows_setData(fig, fData);

        delete(dlg);
        groupsTab_refreshUI(fig);
        uialert(fig, 'Thresholds Updated.', 'Success');
    end
end

function manageSession(fig, ~, action)
if strcmp(action, 'closing')
    % Prompt for Save
    selection = uiconfirm(fig, 'Save session before closing?', 'Close HILIGHTer', ...
        'Options', {'Save', 'Don''t Save', 'Cancel'}, ...
        'DefaultOption', 1, 'CancelOption', 3);

    switch selection
        case 'Save'
            saved = saveSessionData(fig);
            if saved, delete(fig); end
        case 'Don''t Save'
            delete(fig);
        case 'Cancel'
            return;
    end
end
end

function saved = saveSessionData(fig)
saved = false;
data = fig.UserData;
[file, path] = uiputfile('*.mat', 'Save Session Data', 'HILIGHTer_Session.mat');
if isequal(file, 0), return; end

try
    save(fullfile(path, file), 'data');
    saved = true;
catch ME
    uialert(fig, ['Save Failed: ' ME.message], 'Error');
end
end

function safeOpenThreshold(fig)
try
    openGroupsThresholdGUI(fig);
catch ME
    uialert(fig, ME.message, 'Threshold Error');
end
end

function navFile(fig, action, jumpIdx)
d = flows_getData(fig);
if ~isfield(d, 'navGroup'), d.navGroup = 1; end
if ~isfield(d, 'navFile'), d.navFile = 1; end
if ~isfield(d, 'navChannel'), d.navChannel = 1; end

nGrps = numel(d.Conditions);
if nGrps == 0
    refreshUnifiedPlots(fig);
    return;
end

switch action
    case 'group'
        if nargin > 2 && ~isempty(jumpIdx)
            d.navGroup = jumpIdx;
        else
            dd = findobj(fig, 'Tag', 'ddImgGroup');
            idx = find(strcmp(dd.Items, dd.Value), 1);
            if ~isempty(idx), d.navGroup = idx; end
        end
        d.navFile = 1;
    case 'prevGroup'
        d.navGroup = max(d.navGroup - 1, 1);
        d.navFile = 1;
    case 'file'
        if nargin > 2 && ~isempty(jumpIdx)
            d.navFile = jumpIdx;
        else
            dd = findobj(fig, 'Tag', 'ddImgFile');
            idx = find(strcmp(dd.Items, dd.Value), 1);
            if ~isempty(idx), d.navFile = idx; end
        end
    case 'prevFile'
        d.navFile = max(d.navFile - 1, 1);
    case 'nextFile'
        if ~isempty(d.Conditions) && isfield(d.Conditions{d.navGroup}, 'Files')
            nFiles = numel(d.Conditions{d.navGroup}.Files);
            d.navFile = min(d.navFile + 1, nFiles);
        end
end
flows_setData(fig, d); % Save updated state
refreshUnifiedPlots(fig);
end

function runBatchAnalysis(fig, tab)
data = fig.UserData;
if ~isfield(data, 'navGroup') || isempty(data.Conditions), return; end
cIdx = data.navGroup;
nFiles = numel(data.Conditions{cIdx}.Analysis);
d = uiprogressdlg(fig, 'Title', 'Batch Analysis', 'Message', 'Starting...', 'Indeterminate', 'off');
originalFile = data.navFile;
try
    for f = 1:nFiles
        d.Value = (f-1)/nFiles;
        d.Message = sprintf('Analyzing file %d of %d...', f, nFiles);
        navFile(fig, 'file', f); % Pass 'file' action and file index
        drawnow;
        meta = tab.UserData;
        if isfield(meta, 'algo')
            algo = meta.algo;
            if contains(lower(algo), 'phasor')
                refreshPhasorPlot(fig, meta.axPhasor);
            elseif contains(lower(algo), 'lima')
                runLimaAnalysis(fig);
            elseif contains(lower(algo), 'fisher')
                runFisherAnalysis(fig);
            elseif contains(lower(algo), 'pattern')
                runPatternFit(fig);
            else
                runFitAnalysis(fig, tab, true);
            end
        end
    end
catch ME
    uialert(fig, ME.message, 'Batch Error');
end
navFile(fig, 'file', originalFile); % Pass 'file' action and original file index
close(d);
end

function toggleDebugMode(fig, state)
if strcmp(state, 'On')
    showDebugLabels(fig);
else
    hideDebugLabels(fig);
end
end

function showDebugLabels(fig)
% Remove existing if any to avoid duplicates
hideDebugLabels(fig);

% Find all relevant UI components
% We want controls that user interacts with (Buttons, Dropdowns, Spinners, EditFields, etc.)
allObjs = findall(fig, '-property', 'Tag');
relevantTypes = {'matlab.ui.control.Button', 'matlab.ui.control.DropDown', ...
    'matlab.ui.control.Spinner', 'matlab.ui.control.EditField', ...
    'matlab.ui.control.CheckBox', 'matlab.ui.control.Switch', ...
    'matlab.ui.control.ListBox', 'matlab.ui.control.Slider', ...
    'matlab.ui.control.Label', 'matlab.ui.container.Panel', 'matlab.ui.container.Tab', ...
    'matlab.ui.control.Image', 'matlab.ui.control.UIAxes'};

for i = 1:numel(allObjs)
    obj = allObjs(i);
    if isempty(obj.Tag), continue; end
    if strcmp(obj.Tag, 'debugOverlayLabel'), continue; end % constant ignore

    % Check type
    if ~ismember(class(obj), relevantTypes), continue; end

    % Calculations for position
    try
        absPos = getAbsolutePosition(obj);
        if isempty(absPos), continue; end

        % Create overlay label
        % Using HTML for better visibility (Yellow background, Black text)
        txt = sprintf('<div style="background-color:yellow; color:black; border:1px solid red; font-size:10px; padding:1px;">%s</div>', obj.Tag);

        lbl = uilabel(fig, 'Text', txt, 'Interpreter', 'html');

        % Position: Top-Left of the component
        % absPos is [x, y, w, h] relative to bottom-left of figure
        % We want label at top-left of component
        % uilabel is also bottom-left relative

        lW = min(150, absPos(3));
        lH = 15;
        lX = absPos(1);
        lY = absPos(2) + absPos(4) - lH;

        lbl.Position = [lX, lY, lW, lH];
        lbl.BackgroundColor = [1 1 0];
        lbl.Tag = 'debugOverlayLabel';

        % Pass through clicks
        % lbl.Interactions = []; % Not supported on labels?
        % We just hope it doesn't block too much.
    catch
        % ignore layout errors
    end
end
end

function hideDebugLabels(fig)
delete(findall(fig, 'Tag', 'debugOverlayLabel'));
end

function pos = getAbsolutePosition(h)
% Recursively calculate absolute position in pixels relative to the Figure
pos = [0 0 0 0];
if ~isvalid(h), return; end

try
    % Current object position
    % If it is a child of uigridlayout, Position is read-only pixel value relative to parent
    % If it is child of uipanel/figure (absolute), Position is relative to parent

    p = h.Position;
    % Handle unit conversion if necessary (assuming pixels mostly)

    parent = h.Parent;


    absX = p(1);
    absY = p(2);

    while ~isempty(parent) && ~isa(parent, 'matlab.ui.Figure')
        % Add parent's position
        % Caveat: If parent is uigridlayout, it has a Position property relative to ITS parent
        % If parent is Tab, it doesn't really have a position offset relative to TabGroup content area easily accessible?
        % Actually TabGroup content area is usually defined by TabGroup position.

        if isa(parent, 'matlab.ui.container.Tab')
            % Tab inner area usually starts at (0,0) of TabGroup?
            % Need to find TabGroup
            parent = parent.Parent; % Go to TabGroup
            continue;
        end

        if isprop(parent, 'Position')
            pp = parent.Position;
            absX = absX + pp(1);
            absY = absY + pp(2);
        end
        parent = parent.Parent;
    end

    pos = [absX, absY, p(3), p(4)];
catch
    pos = [];
end
end