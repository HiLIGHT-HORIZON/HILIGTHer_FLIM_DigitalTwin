function MockData_GUI(configStruct)
% MOCKDATA_GUI - GUI for generating mock FLIM data
% ConfigStruct contains settings imported from the main FLIM_GUI

% === Main Figure ===
figWidth = 1500;
figHeight = 1050;
fig = uifigure('Name', 'HILIGHT Data Analysis Simulator', 'Position', [50 50 figWidth figHeight]);

% Store config and data in a struct
dataStruct.config = configStruct;
dataStruct.RawData = [];
dataStruct.TauMap = [];
dataStruct.projXY = [];  % Store for ROI colorization
dataStruct.G_vals = [];  % Store phasor coordinates
dataStruct.S_vals = [];
dataStruct.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});
dataStruct.vizMode = 'Default'; % 'Default' or 'ROI Overlay'
dataStruct.harmonic = 1;         % Harmonic for phasor analysis (1, 2, or 3)
dataStruct.plotAllHarmonics = true;
dataStruct.phasorZoomMode = 'Full'; % 'Full' or 'Data'
fig.UserData = dataStruct;

% === Layout Constants ===
margin = 15;

% --- Column 1: Controls ---
col1W = 280;
col1X = margin;

% Remaining width for cols 2 and 3
col2X = col1X + col1W + margin;

% === Configuration Panel (Top Left) ===
configPanelH = 280;
configPanel = uipanel(fig, 'Title', 'Configuration', ...
    'Position', [col1X, figHeight - configPanelH - margin, col1W, configPanelH]);

inputH = 22;

% -- Mode Selection --
currY = configPanelH - 50;
uilabel(configPanel, 'Text', 'Mode:', 'Position', [10 currY 50 inputH]);
modeDropdown = uidropdown(configPanel, ...
    'Items', {'Lifetime Gradient', 'Lifetime Mix'}, ...
    'Value', 'Lifetime Gradient', ...
    'Tooltip', 'Select simulation mode: Lifetime Gradient (column-wise tau) or Lifetime Mix (2-exponential mixture)', ...
    'Position', [70 currY 120 inputH]);

currY = currY - 35;
% -- Image Dimensions --
uilabel(configPanel, 'Text', 'Size (X, Y):', 'Position', [10 currY 70 inputH]);
dimXField = uieditfield(configPanel, 'numeric', 'Value', 256, 'Position', [80 currY 50 inputH], 'Tooltip', 'Image width (X) in pixels');
dimYField = uieditfield(configPanel, 'numeric', 'Value', 256, 'Position', [140 currY 50 inputH], 'Tooltip', 'Image height (Y) in pixels');

uibutton(configPanel, 'Text', 'x2', 'Position', [200 currY 25 inputH], 'Tooltip', 'Double image size', ...
    'ButtonPushedFcn', @(btn, event) adjustSize(dimXField, dimYField, 2));
uibutton(configPanel, 'Text', '/2', 'Position', [230 currY 25 inputH], 'Tooltip', 'Halve image size', ...
    'ButtonPushedFcn', @(btn, event) adjustSize(dimXField, dimYField, 0.5));

currY = currY - 35;
% -- Lifetimes --
uilabel(configPanel, 'Text', 'Lifetime 1 (ps):', 'Position', [10 currY 90 inputH]);
tau1Field = uieditfield(configPanel, 'numeric', 'Value', 1000, 'Position', [100 currY 60 inputH], 'Tooltip', 'Base lifetime 1');

currY = currY - 35;
uilabel(configPanel, 'Text', 'Lifetime 2 (ps):', 'Position', [10 currY 90 inputH]);
tau2Field = uieditfield(configPanel, 'numeric', 'Value', 2000, 'Position', [100 currY 60 inputH], 'Tooltip', 'Base lifetime 2');

% Callbacks for instant updating of Instrument Plot
tau1Field.ValueChangedFcn = @(src, event) updateInstrumentPlot(fig, tau1Field, tau2Field);
tau2Field.ValueChangedFcn = @(src, event) updateInstrumentPlot(fig, tau1Field, tau2Field);

currY = currY - 35;
uilabel(configPanel, 'Text', 'Photons/Px:', 'Position', [10 currY 90 inputH]);
photonsField = uieditfield(configPanel, 'numeric', 'Value', dataStruct.config.N_photons, 'Position', [100 currY 60 inputH], 'Tooltip', 'Expected average photons per pixel');

currY = currY - 35;
uilabel(configPanel, 'Text', 'Background (cts):', 'Position', [10 currY 90 inputH]);
darkCountsField = uieditfield(configPanel, 'numeric', 'Value', 0, 'Position', [100 currY 60 inputH], 'Tooltip', 'Expected dark counts / background per pixel per gate');

currY = currY - 45;
% -- Generate Button --
uibutton(configPanel, 'Text', 'GENERATE', 'FontWeight','bold', 'Tooltip', 'Create mock data based on settings', ...
    'Position', [20 currY 240 30], ...
    'ButtonPushedFcn', @(btn, event) onGenerate(fig, modeDropdown, dimXField, dimYField, tau1Field, tau2Field, photonsField, darkCountsField));


% === Analysis Panel (Below Config) ===
analysisPanelH = 130;
analysisPanel = uipanel(fig, 'Title', 'Analysis', ...
    'Position', [col1X, figHeight - configPanelH - analysisPanelH - 2*margin, col1W, analysisPanelH]);

currY = analysisPanelH - 50;
uilabel(analysisPanel, 'Text', 'Algorithm:', 'Position', [10 currY 70 inputH]);
algoDropdown = uidropdown(analysisPanel, ...
    'Items', {'Default (Grid MLE)', 'Iterative Reconvolution'}, ...
    'Value', 'Default (Grid MLE)', 'Tooltip', 'Select estimator algorithm', ...
    'Position', [80 currY 180 inputH]);

currY = currY - 50;
uibutton(analysisPanel, 'Text', 'ANALYSE', 'FontWeight','bold', 'Tooltip', 'Run lifetime estimation', ...
    'Position', [20 currY 240 30], ...
    'ButtonPushedFcn', @(btn, event) onAnalyze(fig, algoDropdown));


% === Instrument Parameters Panel (Below Analysis) ===
instPanelH = 200;
instPanel = uipanel(fig, 'Title', 'Instrument Parameters', ...
    'Position', [col1X, figHeight - configPanelH - analysisPanelH - instPanelH - 3*margin, col1W, instPanelH]);

% === ROI Control Panel (Bottom Left) ===
% Fill the remaining vertical space in Column 1
roiPanelH = figHeight - configPanelH - analysisPanelH - instPanelH - 5*margin - 20;
roiPanel = uipanel(fig, 'Title', 'Phasor ROIs', ...
    'Position', [col1X, margin, col1W, roiPanelH]);

currY = roiPanelH - 35;
uibutton(roiPanel, 'Text', 'Add ROI (Red)', 'FontColor', [0.8 0 0], 'Position', [10 currY 120 25], ...
    'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 1));
uibutton(roiPanel, 'Text', 'Clear R', 'Position', [140 currY 60 25], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 1));

currY = currY - 30;
uibutton(roiPanel, 'Text', 'Add ROI (Green)', 'FontColor', [0 0.6 0], 'Position', [10 currY 120 25], ...
    'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 2));
uibutton(roiPanel, 'Text', 'Clear G', 'Position', [140 currY 60 25], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 2));

currY = currY - 30;
uibutton(roiPanel, 'Text', 'Add ROI (Blue)', 'FontColor', [0 0 0.8], 'Position', [10 currY 120 25], ...
    'ButtonPushedFcn', @(btn, event) addPhasorROI(fig, 3));
uibutton(roiPanel, 'Text', 'Clear B', 'Position', [140 currY 60 25], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 3));

currY = currY - 40;
uibutton(roiPanel, 'Text', 'CLEAR ALL ROIs', 'FontWeight', 'bold', 'Position', [10 currY 190 30], ...
    'ButtonPushedFcn', @(btn, event) clearPhasorROI(fig, 'all'));

currY = currY - 45;
uilabel(roiPanel, 'Text', 'Visualization:', 'Position', [10 currY 80 20]);
vizSwitch = uiswitch(roiPanel, 'toggle', 'Items', {'Default', 'Overlay'}, 'Value', 'Default', ...
    'Position', [100 currY + 10 50 20], ...
    'ValueChangedFcn', @(sw, event) toggleVizMode(fig, sw.Value));

currY = currY - 45;
uilabel(roiPanel, 'Text', 'Harmonic:', 'Position', [10 currY 70 20]);
hSpin = uispinner(roiPanel, 'Limits', [1 3], 'Value', dataStruct.harmonic, ...
    'Position', [80 currY 50 22], ...
    'ValueChangedFcn', @(sp, event) updateHarmonic(fig, sp.Value, []));

uicheckbox(roiPanel, 'Text', 'All', 'Value', 1, ...
    'Position', [135 currY 45 22], ...
    'Tooltip', 'Show all harmonics up to selected', ...
    'ValueChangedFcn', @(cb, event) updateHarmonic(fig, [], cb.Value));

uibutton(roiPanel, 'Text', '', 'Position', [190 currY-5 32 32], 'Tooltip', 'Zoom to Data only', ...
    'Icon', 'C:/Users/ae275/.gemini/antigravity/brain/eb553d2f-4539-4e9a-94c9-4c463a29c28a/zoom_in_icon_1766743622031.png', ...
    'ButtonPushedFcn', @(btn, event) setPhasorZoom(fig, 'Data'));
uibutton(roiPanel, 'Text', '', 'Position', [225 currY-5 32 32], 'Tooltip', 'Zoom to Full (Data + Curves)', ...
    'Icon', 'C:/Users/ae275/.gemini/antigravity/brain/eb553d2f-4539-4e9a-94c9-4c463a29c28a/zoom_out_icon_1766743633452.png', ...
    'ButtonPushedFcn', @(btn, event) setPhasorZoom(fig, 'Full'));

% Plot Ax
axInst = uiaxes(instPanel, 'Position', [5 5 col1W-10 instPanelH-25]);
axInst.Tag = 'axInst';
title(axInst, 'IRF & Gates'); xlabel(axInst, 'Time (ns)');
grid(axInst, 'on');


% === Column 2: Data Projections (Center) ===
% Stack 3 axes: XY, XT, YT
% Available Height
% Make plots bigger: e.g. 500px, but limited by available width/height
% Let's increase plotH significantly. Previous was roughly 1/3 ~ 280px.
% 2x bigger is too big for figHeight 900.
% User said "make them 2x bigger".
% Let's try explicit size.
plotH = 375; % Scaled to 75% of 500

% 1. XY Projection (Top)
% Force width = height to ensure square aspect ratio alignment
% Top of XY should be at figHeight - margin
xyY = figHeight - margin - plotH;
axXY = uiaxes(fig, 'Position', [col2X, xyY, plotH, plotH]);
title(axXY, 'XY Projection (Total Photons)');
axXY.Tag = 'axXY';
axXY.XTick = []; axXY.YTick = []; axXY.Box = 'on';

% 2. XT Projection (Middle)
% Alter aspect ratio to 1:0.3 (Height = 0.3 * Width)
xtH = 0.3 * plotH;
xtY = xyY - margin - xtH; % Sit just below XY
axXT = uiaxes(fig, 'Position', [col2X, xtY, plotH, xtH]);
xlabel(axXT, 'XT Projection');
axXT.Tag = 'axXT';
axXT.XTick = []; axXT.YTick = []; axXT.Box = 'on';

% 3. Phasor Plot (Bottom)
% Place under XT
phasorH = plotH * 0.8; % Slightly smaller than XY
phasorY = xtY - margin - phasorH;
axPhasor = uiaxes(fig, 'Position', [col2X, phasorY, plotH, phasorH]);
title(axPhasor, 'Phasor Plot');
axPhasor.Tag = 'axPhasor';
xlabel(axPhasor, 'G'); ylabel(axPhasor, 'S');
axPhasor.Box = 'on';
grid(axPhasor, 'on');
axis(axPhasor, 'equal');
xlim(axPhasor, [0 1]); ylim(axPhasor, [0 0.6]);

% 4. YT Projection (Right)
% Place to the right of XY (col2X + plotH + margin)
% Aspect ratio: Width = xtH, Height = plotH (to match XY height)
% Adjust position so the *axes border* aligns with axXY.
% 'northoutside' colorbar pushes the axes down, so we compensate.
ytW = xtH;
ytX = col2X + plotH + margin;
cbHeightComp = 60; % Compensation for horizontal colorbar and its labels
axYT = uiaxes(fig, 'Position', [ytX, xyY - 20, ytW, plotH + cbHeightComp]);
axYT.Tag = 'axYT';
axYT.XTick = []; axYT.YTick = []; axYT.Box = 'on';

% Update Column 3 position
col3X = ytX + ytW + margin + 80; % Extra margin for YT colorbar labels


% Standard alignment constants for frame-to-frame vertical alignment
axL = col3X + 70;      % Left edge of axes frame
axW = 320;             % Width of axes frame
metX = axL + axW + 15; % Metrics column X
xyY_top = xyY + (plotH - axW); % Align top of axTau with top of axXY/axYT

% 1. Estimated Lifetime Map (Top)
axTau = uiaxes(fig, 'PositionConstraint', 'innerposition');
axTau.InnerPosition = [axL, xyY_top, axW, axW]; % Force pixel box to be square
axTau.Tag = 'axTau';
axTau.XTick = []; axTau.YTick = []; axTau.Box = 'on';

% 2. Lifetime Statistics (Middle)
statsY = xyY_top - 20 - xtH; % Move closer to map
axStats = uiaxes(fig, 'PositionConstraint', 'innerposition');
axStats.InnerPosition = [axL, statsY, axW, xtH];
axStats.Tag = 'axStats';
axStats.Box = 'on';
grid(axStats, 'on');

% 3. Standardized Residuals
zH = xtH * 0.5;
resY = statsY - 5 - zH; % Move very close to Statistics
axRes = uiaxes(fig, 'PositionConstraint', 'innerposition');
axRes.InnerPosition = [axL, resY, axW, zH];
axRes.Tag = 'axRes';
axRes.Box = 'on';
axRes.XTickLabel = [];
ylabel(axRes, 'Z-score', 'FontWeight', 'bold');
grid(axRes, 'on');

% Metrics Group 1 (Right of axRes)
uilabel(fig, 'Text', [char(967) char(178) char(7523) ': --'], 'FontWeight', 'bold', ...
    'Position', [metX, resY + zH - 20, 120, 20], 'Tag', 'lblChi2');
uilabel(fig, 'Text', 'R.E.: --%', 'FontWeight', 'bold', ...
    'Position', [metX, resY + zH - 40, 120, 20], 'Tag', 'lblRE');
uilabel(fig, 'Text', 'RND: --', 'FontWeight', 'bold', ...
    'Position', [metX, resY + zH - 60, 160, 20], 'Tag', 'lblRandom');

% Help Button (Moved away from labels)
uibutton(fig, 'Text', '?', 'FontWeight', 'bold', ...
    'Position', [metX + 110, resY + zH - 25, 25, 25], ...
    'Tooltip', 'Open Digital Twin Manual', ...
    'ButtonPushedFcn', @(btn, event) helpwin('DigitalTwin_Manual'));

% 4. Pixel Decay Analysis (Center-bottom)
pixelH = 160;
pixelY = resY - 75 - pixelH; % Increased gap for "In-pixel fitting" title
axPixel = uiaxes(fig, 'PositionConstraint', 'innerposition');
axPixel.InnerPosition = [axL, pixelY, axW, pixelH];
axPixel.Tag = 'axPixel';
axPixel.Box = 'on';
ylabel(axPixel, 'Counts', 'FontWeight', 'bold');
grid(axPixel, 'on');

% Pixel-level info (Right of axPixel)
uilabel(fig, 'Text', 'Pos: --, --', 'FontWeight', 'bold', ...
    'Position', [metX, pixelY + pixelH - 20, 120, 20], 'Tag', 'lblPixPos');
uilabel(fig, 'Text', [char(964) ': -- ns'], 'FontWeight', 'bold', ...
    'Position', [metX, pixelY + pixelH - 40, 120, 20], 'Tag', 'lblPixTauVal');

% 5. Pixel Residuals (Bottom-most)
pixelResY = pixelY - 10 - zH; % Move closer to decay plot
axPixelRes = uiaxes(fig, 'PositionConstraint', 'innerposition');
axPixelRes.InnerPosition = [axL, pixelResY, axW, zH];
axPixelRes.Tag = 'axPixelRes';
axPixelRes.Box = 'on';
ylabel(axPixelRes, 'Z-score', 'FontWeight', 'bold');
grid(axPixelRes, 'on');

% Metrics Group 2 (Right of axPixelRes)
uilabel(fig, 'Text', [char(967) char(178) char(7523) ': --'], 'FontWeight', 'bold', ...
    'Position', [metX, pixelResY + zH - 20, 120, 20], 'Tag', 'lblPixChi2');
uilabel(fig, 'Text', 'R.E.: --%', 'FontWeight', 'bold', ...
    'Position', [metX, pixelResY + zH - 40, 120, 20], 'Tag', 'lblPixRE');
uilabel(fig, 'Text', 'RND: --', 'FontWeight', 'bold', ...
    'Position', [metX, pixelResY + zH - 60, 160, 20], 'Tag', 'lblPixRND');

% Initial Plot update
updateInstrumentPlot(fig, tau1Field, tau2Field);

end

function onGenerate(fig, modeDropdown, dimXField, dimYField, tau1Field, tau2Field, photonsField, darkCountsField)
% Retrieve config and params
data = fig.UserData;
config = data.config;

Mode = modeDropdown.Value;
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

% 1. Create Model Probabilities
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

% 5. Projections
projXY = sum(RawData, 3);
projXT = squeeze(sum(RawData, 1))'; % (Gates, X)
projYT = squeeze(sum(RawData, 2));  % (Y, Gates)

% Store Data for Analysis
data.RawData = RawData;
data.GroundTruthTaus = unique_taus;
data.projXY = projXY; % Store for ROI overlay
fig.UserData = data;

% 6. Plotting
axXY = findobj(fig, 'Tag', 'axXY');
axXT = findobj(fig, 'Tag', 'axXT');
axYT = findobj(fig, 'Tag', 'axYT');
axTau = findobj(fig, 'Tag', 'axTau');
axStats = findobj(fig, 'Tag', 'axStats');
axRes = findobj(fig, 'Tag', 'axRes');
lblChi2 = findobj(fig, 'Tag', 'lblChi2');
lblRE = findobj(fig, 'Tag', 'lblRE');
lblRandom = findobj(fig, 'Tag', 'lblRandom');

imagesc(axXY, projXY);
colormap(axXY, 'parula');
cb = colorbar(axXY, 'Location', 'westoutside');
cb.Label.String = 'Photons';
title(axXY, 'XY (Total Photons)'); axis(axXY, 'image');
set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');

imagesc(axXT, projXT);
cb = colorbar(axXT, 'Location', 'westoutside');
cb.Label.String = 'Photons';
title(axXT, ''); % Clear top title
xlabel(axXT, 'XT Projection', 'Visible', 'on', 'FontWeight', 'bold'); % Moves title to bottom
axis(axXT, 'tight');
set(axXT, 'XTick', [], 'YTick', [], 'Box', 'on');

imagesc(axYT, projYT);
cb = colorbar(axYT, 'Location', 'northoutside');
cb.Label.String = 'Photons';
title(axYT, ''); % Clear top title
xlabel(axYT, 'YT Projection', 'Visible', 'on', 'FontWeight', 'bold'); % Using label as title
axis(axYT, 'tight');
set(axYT, 'XTick', [], 'YTick', [], 'Box', 'on');

% Clear Analysis plots until analyzed
cla(axTau);
title(axTau, 'Estimated Lifetime (Click ANALYSE)');

cla(axStats);
title(axStats, 'Lifetime Statistics');

cla(axRes);

cla(findobj(fig, 'Tag', 'axPixel'));
cla(findobj(fig, 'Tag', 'axPixelRes'));
cla(findobj(fig, 'Tag', 'axPhasor')); % Clear Phasor plot too

% Reset Pixel Info Labels
hPixPos = findobj(fig, 'Tag', 'lblPixPos');
hPixTauVal = findobj(fig, 'Tag', 'lblPixTauVal');
if ~isempty(hPixPos), hPixPos.Text = 'Pos: --, --'; end
if ~isempty(hPixTauVal), hPixTauVal.Text = '\tau: -- ns'; end
if ~isempty(lblChi2)
    lblChi2.Text = [char(967) char(178) char(7523) ': --'];
end
if ~isempty(lblRE)
    lblRE.Text = 'R.E.: --%';
end
if ~isempty(lblRandom)
    lblRandom.Text = 'RND: --';
    lblRandom.FontColor = [0 0 0];
end

% 7. Update Instrument Plot
updateInstrumentPlot(fig, tau1Field, tau2Field);
end

function adjustSize(dimXField, dimYField, factor)
dimXField.Value = round(dimXField.Value * factor);
dimYField.Value = round(dimYField.Value * factor);
end

function onAnalyze(fig, algoDropdown)
try
    data = fig.UserData;
    if isempty(data.RawData)
        uialert(fig, 'No data generated. Click GENERATE first.', 'Error');
        return;
    end

    config = data.config;
    RawData = data.RawData;
    [nY, nX, nGates] = size(RawData);

    % Reuse DT logic used in generate to setup interp functions
    dt = config.dt;
    T = config.T;
    t = 0:dt:T;
    actual_gate_edges = config.gate_edges;
    gate_profiles = DTgates(t, config.r, actual_gate_edges);
    gate_interp_fns = cell(config.N_gates, 1);
    for i = 1:config.N_gates
        gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
    end

    % Flatten Data for Analysis: (N_gates x M)
    % RawData is (nY, nX, N_gates) -> Need to reshape
    % Permute to (N_gates, nY, nX) -> (N_gates, M)
    M = nY * nX;
    flatData = permute(RawData, [3, 1, 2]);
    flatData = reshape(flatData, nGates, M);

    % Fake N_detections (just sum counts, though DTmle recalculates it)
    N_detections = sum(flatData, 1);

    % Get Algorithm
    algo = algoDropdown.Value;

    % Display "Processing..." on title?
    axTau = findobj(fig, 'Tag', 'axTau');
    title(axTau, ['Analyzing (' algo ')... please wait']);
    drawnow;

    tau_est_flat = [];

    if strcmpi(algo, 'Default (Grid MLE)') || strcmp(algo, 'Default')
        % Define Search Grid for MLE
        % Search 0.1ns to 10ns
        tau_grid = linspace(0.1, 10, 100);

        % Generate Library for Grid
        P_model_grid = DTpmod(config.N_gates, tau_grid, t, gate_interp_fns, ...
            config.fwhm, config.profile, config.rise_time, config.fall_time, ...
            config.bPulseTrain, config.PT_Trep, config.PT_sigma);

        % Run MLE (Grid Search)
        [tau_est_flat, ~] = DTmle(N_detections, flatData, tau_grid, P_model_grid, fig);

    elseif strcmpi(algo, 'Iterative Reconvolution')
        % Run Iterative LSQ
        % This function will process pixel-by-pixel
        [TauMap_Iter, ~] = DTiterative(RawData, config, fig);
        tau_est_flat = reshape(TauMap_Iter, 1, []);
    end

    % Reshape back to image
    TauMap = reshape(tau_est_flat, nY, nX);

    % Statistics along Y (axis 1)
    meanTau = mean(TauMap, 1, 'omitnan'); % Result is 1 x nX
    stdTau = std(TauMap, 0, 1, 'omitnan'); % Result is 1 x nX

    % == Plot 1: Map ==
    hImg = imagesc(axTau, TauMap);
    colormap(axTau, 'jet'); colorbar(axTau);
    title(axTau, 'Estimated Lifetime (ns)');
    axis(axTau, 'image');
    set(axTau, 'XTick', [], 'YTick', [], 'Box', 'on');

    % Add crosshair and interaction
    hold(axTau, 'on');
    xline(axTau, 1, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossV', 'Visible', 'off');
    yline(axTau, 1, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossH', 'Visible', 'off');
    hold(axTau, 'off');

    hImg.ButtonDownFcn = @(src, event) updatePixelAnalysis(fig, event.IntersectionPoint);

    % Store results in UserData for the interaction
    data.TauMap = TauMap;
    data.gate_interp_fns = gate_interp_fns;
    fig.UserData = data;

    % == Plot 2: Stats ==
    axStats = findobj(fig, 'Tag', 'axStats');
    cla(axStats); hold(axStats, 'on');

    xVec = 1:nX;
    ci95 = 1.96 * stdTau;
    upper = meanTau + ci95;
    lower = meanTau - ci95;

    % Shaded Confidence Interval
    fill(axStats, [xVec, fliplr(xVec)], [upper, fliplr(lower)], ...
        [0.6 0.8 1], 'EdgeColor', 'none', 'FaceAlpha', 0.5);

    % Mean Line
    plot(axStats, xVec, meanTau, 'b-', 'LineWidth', 1.5);

    % Force axes alignment with Z-score plot
    axRes = findobj(fig, 'Tag', 'axRes');
    pos_res = axRes.InnerPosition;
    inner_pos = axStats.InnerPosition;
    inner_pos(1) = pos_res(1);
    inner_pos(3) = pos_res(3);
    axStats.InnerPosition = inner_pos;

    % Legend for Statistics - Manually positioned to align with metrics column
    L = legend(axStats, {'95% CI', 'Mean'}, 'Location', 'none', 'FontSize', 8);
    metX_calc = pos_res(1) + pos_res(3) + 15;
    L.Units = 'pixels';
    L.Position = [metX_calc, inner_pos(2) + 5, 85, 35];

    title(axStats, 'Lifetime Statistics');
    xlabel(axStats, ''); % Remove X position label here
    ylabel(axStats, 'Lifetime (ns)', 'FontWeight', 'bold');
    grid(axStats, 'on');
    xlim(axStats, [1 nX]);
    set(axStats, 'XTick', [], 'Box', 'on');
    % Note: YTick is intentionally left enabled per user request

    % == Plot 3: Lifetime Residuals & Chi2 ==
    cla(axRes); hold(axRes, 'on');

    % Standardized Residuals in Lifetime Domain
    % We compare estimated tau per pixel vs ground truth tau
    % GroundTruthTaus is (1, nX)
    tau_true = data.GroundTruthTaus;

    % 1. Compute Theoretical Precision (CRLB)
    % We need FI for the true lifetimes
    irf_params.fwhm = config.fwhm;
    irf_params.profile = config.profile;
    irf_params.rise_time = config.rise_time;
    irf_params.fall_time = config.fall_time;
    irf_params.bPulseTrain = config.bPulseTrain;
    irf_params.PT_Trep = config.PT_Trep;
    irf_params.PT_sigma = config.PT_sigma;

    % Fisher info per pixel: using photonsField value
    n_ph_px = sum(N_detections) / (nX * nY);
    [~, f_vals_true] = DTcomputeFisherInfo(config.gate_edges, irf_params, config.r, config.T, tau_true, n_ph_px);
    % sigma_crlb = (f_val * tau) / sqrt(N)
    sigma_crlb = (f_vals_true .* tau_true) / sqrt(n_ph_px);

    % 2. Calculate Standardized Errors per pixel
    % error(y, x) = TauMap(y, x) - tau_true(x)
    delta_tau = TauMap - repmat(tau_true, nY, 1);
    z_map = delta_tau ./ repmat(sigma_crlb, nY, 1);

    % 3. Reduced Chi2 (for the parameter estimate)
    % If estimator is optimal and unbiased, z_map ~ N(0, 1), so mean(z^2) ~ 1
    % This measures EFFICIENCY (1 / Chi2_red)
    chi2_red = mean(z_map(:).^2, 'omitnan');

    % 4. Residuals Plot: Average Z-score along Y
    z_mean = mean(z_map, 1, 'omitnan');
    stem(axRes, 1:nX, z_mean, 'Marker', 'none', 'LineWidth', 1.5);
    yline(axRes, 0, 'k-');
    yline(axRes, [2, -2], 'r--'); % 2-sigma thresholds for the mean

    % Title and X-ticks
    xlabel(axRes, 'X Position', 'FontWeight', 'bold');
    ylabel(axRes, 'Z-score', 'FontWeight', 'bold');
    grid(axRes, 'on');
    xlim(axRes, [0.5 nX + 0.5]);
    set(axRes, 'XTickLabelMode', 'auto'); % Enable X-ticks here

    % Update Labels
    lblChi2 = findobj(fig, 'Tag', 'lblChi2');
    lblRE = findobj(fig, 'Tag', 'lblRE');
    if ~isempty(lblChi2)
        lblChi2.Text = sprintf('%c%c%c: %.3f', 967, 178, 7523, chi2_red);
    end
    if ~isempty(lblRE)
        re_val = (1 / chi2_red) * 100;
        lblRE.Text = sprintf('R.E.: %.1f%%', re_val);
    end

    % == Randomness Test (Runs Test on X-axis bias) ==
    % We check if the bias (z_mean) is random across the lifetime range
    signs = sign(z_mean);
    signs(signs == 0) = 1;
    runs = 1 + sum(diff(signs) ~= 0);
    n_pos = sum(signs > 0);
    n_neg = sum(signs < 0);

    lblRandom = findobj(fig, 'Tag', 'lblRandom');
    if ~isempty(lblRandom)
        if n_pos == 0 || n_neg == 0
            lblRandom.Text = 'RND: NO (Bias)';
            lblRandom.FontColor = [0.8 0 0];
        else
            % Expected runs
            mu_runs = 1 + (2 * n_pos * n_neg) / (n_pos + n_neg);
            sigma2_runs = (2 * n_pos * n_neg * (2 * n_pos * n_neg - n_pos - n_neg)) / ...
                ((n_pos + n_neg)^2 * (n_pos + n_neg - 1));
            z_test = (runs - mu_runs) / sqrt(sigma2_runs);

            if z_test < -1.645
                lblRandom.Text = sprintf('RND: NO (Trend, Z=%.2f)', z_test);
                lblRandom.FontColor = [0.8 0 0];
            else
                lblRandom.Text = sprintf('RND: YES (Z=%.2f)', z_test);
                lblRandom.FontColor = [0 0.6 0];
            end
        end
    end

    % == Plot Phasor ==
    refreshPhasorPlot(fig);

    % Automatically activate crosshair in the middle after analysis
    updatePixelAnalysis(fig, [nX/2, nY/2]);
    refreshXYProjection(fig); % Update with potential ROI overlay
catch ME
    fprintf('Error in onAnalyze: %s\n', ME.message);
    uialert(fig, ['Analysis failed: ' ME.message], 'Error');
end
end

function addPhasorROI(fig, idx)
data = fig.UserData;
ax = findobj(fig, 'Tag', 'axPhasor');
if isempty(ax), return; end

% Colors: 1=Red, 2=Green, 3=Blue
colors = {[1 0 0], [0 0.8 0], [0 0 1]};

% Remove existing if present
if ~isempty(data.ROIs(idx).handle) && isvalid(data.ROIs(idx).handle)
    delete(data.ROIs(idx).handle);
end

% Draw new circle at center
h = drawcircle(ax, 'Center', [0.5, 0.3], 'Radius', 0.05, ...
    'Color', colors{idx}, 'Label', sprintf('ROI %d', idx));

% Add listener for movement
addlistener(h, 'ROIMoved', @(src, event) refreshXYProjection(fig));

data.ROIs(idx).handle = h;
data.ROIs(idx).active = true;
fig.UserData = data;

refreshXYProjection(fig);
end

function clearPhasorROI(fig, idxOrAll)
data = fig.UserData;
if ischar(idxOrAll) && strcmpi(idxOrAll, 'all')
    for i = 1:3
        if ~isempty(data.ROIs(i).handle) && isvalid(data.ROIs(i).handle)
            delete(data.ROIs(i).handle);
        end
        data.ROIs(i).handle = [];
        data.ROIs(i).active = false;
    end
else
    idx = idxOrAll;
    if ~isempty(data.ROIs(idx).handle) && isvalid(data.ROIs(idx).handle)
        delete(data.ROIs(idx).handle);
    end
    data.ROIs(idx).handle = [];
    data.ROIs(idx).active = false;
end
fig.UserData = data;
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
axXY = findobj(fig, 'Tag', 'axXY');
if isempty(axXY) || isempty(data.projXY), return; end

% Capture current crosshair positions if they exist
hV_old = findobj(fig, 'Tag', 'crossV');
hH_old = findobj(fig, 'Tag', 'crossH');
lastX = 1; lastY = 1; vVisible = 'off';
if ~isempty(hV_old) && isvalid(hV_old(1))
    lastX = hV_old(1).Value;
    vVisible = hV_old(1).Visible;
end
if ~isempty(hH_old) && isvalid(hH_old(1))
    lastY = hH_old(1).Value;
end

cla(axXY);

if strcmpi(data.vizMode, 'Default') || isempty(data.G_vals)
    % Standard Photons Map
    hImg = imagesc(axXY, data.projXY);
    colormap(axXY, 'parula');
    cb = colorbar(axXY, 'Location', 'westoutside');
    cb.Label.String = 'Photons';
    title(axXY, 'XY (Total Photons)');
else
    % ROI Overlay mode
    [nY, nX] = size(data.projXY);
    I = double(data.projXY);
    I_norm = (I - min(I(:))) / (max(I(:)) - min(I(:)) + 1e-10);

    % Background: Full brightness grayscale
    RGB = repmat(I_norm, [1, 1, 3]);

    % For each pixel, determine which ROIs it's in
    % 1=Red, 2=Green, 3=Blue
    pixelMasks = false(3, length(data.G_vals));
    for i = 1:3
        if data.ROIs(i).active && isvalid(data.ROIs(i).handle)
            roi = data.ROIs(i).handle;
            distSq = (data.G_vals - roi.Center(1)).^2 + (data.S_vals - roi.Center(2)).^2;
            pixelMasks(i, :) = distSq <= roi.Radius^2;
        end
    end

    % Construct RGB image: Highlight ROI pixels with additive mixing + Intensity modulation
    isAnyROI = any(pixelMasks, 1);

    % Background: Slightly dimmed grayscale for context
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
                % Modulation by intensity
                chan = RGB(:,:,i); chan(mask) = I_norm(mask); RGB(:,:,i) = chan;
            end
        end
    end

    hImg = imagesc(axXY, RGB);
    title(axXY, 'XY (Phasor ROI Overlay)');
    colorbar(axXY, 'off');
end

axis(axXY, 'image');
set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');
hImg.ButtonDownFcn = @(src, event) updatePixelAnalysis(fig, event.IntersectionPoint);

% Restore crosshair
hold(axXY, 'on');
xline(axXY, lastX, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossV', 'Visible', vVisible);
yline(axXY, lastY, 'w-', 'LineWidth', 1, 'HitTest', 'off', 'Tag', 'crossH', 'Visible', vVisible);
hold(axXY, 'off');
end

function updateInstrumentPlot(fig, tau1Field, tau2Field)
% Update the Instrument Parameters plot based on current Lifetime inputs

data = fig.UserData;
config = data.config;
axInst = findobj(fig, 'Tag', 'axInst');
if isempty(axInst), return; end

tau1_ns = tau1Field.Value / 1000;
tau2_ns = tau2Field.Value / 1000;

% Setup Time
dt = config.dt;
T = config.T;
t = 0:dt:T;

% Gates
% Gates
actual_gate_edges = config.gate_edges;
gate_profiles = DTgates(t, config.r, actual_gate_edges);

% Prepare Plot
cla(axInst); hold(axInst, 'on');

% a. Plot Gates (Left Axis)
yyaxis(axInst, 'left');
ylabel(axInst, 'Gate Sensitivity');
colors = lines(config.N_gates);
for i = 1:config.N_gates
    plot(axInst, t, gate_profiles(i, :), 'Color', [colors(i,:) 0.3], 'LineWidth', 1, 'Marker', 'none');
end

% b. Plot IRF (Normalized)
excitation = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, config.bPulseTrain, config.PT_Trep, config.PT_sigma);
IRF_norm = excitation / max(excitation);
plot(axInst, t, IRF_norm, 'k--', 'LineWidth', 1.5, 'DisplayName', 'IRF', 'Marker', 'none');

% c. Plot Decays (Right Axis)
yyaxis(axInst, 'right');
ylabel(axInst, 'Fluorescence');

decay1 = exp(-t ./ tau1_ns);
decay2 = exp(-t ./ tau2_ns);

plot(axInst, t, decay1, 'r-', 'LineWidth', 1.5, 'DisplayName', ['\tau_1=' num2str(tau1_ns) 'ns'], 'Marker', 'none');
plot(axInst, t, decay2, 'b-', 'LineWidth', 1.5, 'DisplayName', ['\tau_2=' num2str(tau2_ns) 'ns'], 'Marker', 'none');

legend(axInst, {'IRF', '\tau_1', '\tau_2'}, 'Location', 'best');
axis(axInst, 'tight');
end

function updatePixelAnalysis(fig, point)
data = fig.UserData;
if isempty(data.RawData) || ~isfield(data, 'TauMap'), return; end

% Round to pixel coordinates
px = round(point(1));
py = round(point(2));
[nY, nX, nGates] = size(data.RawData);

if px < 1 || px > nX || py < 1 || py > nY, return; end

% Update Crosshair
hV = findobj(fig, 'Tag', 'crossV');
hH = findobj(fig, 'Tag', 'crossH');
if ~isempty(hV), set(hV, 'Value', px, 'Visible', 'on'); end
if ~isempty(hH), set(hH, 'Value', py, 'Visible', 'on'); end

% Extract Pixel Data
pixelCounts = squeeze(data.RawData(py, px, :));
estTau = data.TauMap(py, px);
config = data.config;

% 1. Clean up axes immediately for visual feedback
axPixel = findobj(fig, 'Tag', 'axPixel');
axPixelRes = findobj(fig, 'Tag', 'axPixelRes');

% Use 'reset' to completely wipe any hidden handles/ghost traces
if ~isempty(axPixel)
    cla(axPixel, 'reset');
    set(axPixel, 'Tag', 'axPixel', 'Box', 'on', 'XTickLabel', []);
    ylabel(axPixel, 'Counts', 'FontWeight', 'bold');
    grid(axPixel, 'on');
    hold(axPixel, 'on');
end
if ~isempty(axPixelRes)
    cla(axPixelRes, 'reset');
    set(axPixelRes, 'Tag', 'axPixelRes', 'Box', 'on');
    ylabel(axPixelRes, 'Z-score', 'FontWeight', 'bold');
    xlabel(axPixelRes, 'Time (ns)', 'FontWeight', 'bold');
    grid(axPixelRes, 'on');
    hold(axPixelRes, 'on');
end

drawnow; % Ensure old traces are definitively deleted

% 2. Time Vector and Gate Centers
t = 0:config.dt:config.T;
gate_edges = config.gate_edges;
gate_centers = 0.5 * (gate_edges(1:end-1) + gate_edges(2:end));

% 2. Calculate Fitted Model Gate Counts
% Need to match scaling of the original photon count
n_det = sum(pixelCounts);
P_pixel = DTpmod(nGates, estTau, t, data.gate_interp_fns, ...
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
hPixPos = findobj(fig, 'Tag', 'lblPixPos');
hPixTauVal = findobj(fig, 'Tag', 'lblPixTauVal');
if ~isempty(hPixPos), hPixPos.Text = sprintf('Pos: %d, %d', px, py); end
if ~isempty(hPixTauVal), hPixTauVal.Text = sprintf('%c: %.2f ns', 964, estTau); end

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
lblPixChi2 = findobj(fig, 'Tag', 'lblPixChi2');
lblPixRE = findobj(fig, 'Tag', 'lblPixRE');
lblPixRND = findobj(fig, 'Tag', 'lblPixRND');

pix_chi2 = mean(z_pixel.^2);
if ~isempty(lblPixChi2)
    lblPixChi2.Text = sprintf('%c%c%c: %.3f', 967, 178, 7523, pix_chi2);
end
if ~isempty(lblPixRE)
    lblPixRE.Text = sprintf('R.E.: %.1f%%', (1/pix_chi2)*100);
end

% Runs test on the decay residuals for this pixel
if ~isempty(lblPixRND)
    s_pix = sign(z_pixel);
    s_pix(s_pix==0) = 1;
    r_pix = 1 + sum(diff(s_pix)~=0);
    n1 = sum(s_pix>0); n2 = sum(s_pix<0);
    if n1==0 || n2==0
        lblPixRND.Text = 'RND: NO (Bias)';
        lblPixRND.FontColor = [0.8 0 0];
    else
        mu_r = 1 + (2*n1*n2)/(n1+n2);
        s_r = sqrt((2*n1*n2*(2*n1*n2-n1-n2))/((n1+n2)^2 * (n1+n2-1)));
        z_r = (r_pix - mu_r)/s_r;
        if z_r < -1.645
            lblPixRND.Text = sprintf('RND: NO (Z=%.1f)', z_r);
            lblPixRND.FontColor = [0.8 0 0];
        else
            lblPixRND.Text = sprintf('RND: YES (Z=%.1f)', z_r);
            lblPixRND.FontColor = [0 0.6 0];
        end
    end
end
end

function setPhasorZoom(fig, mode)
data = fig.UserData;
data.phasorZoomMode = mode;
fig.UserData = data;
refreshPhasorPlot(fig);
end

function updateHarmonic(fig, spinVal, cbVal)
data = fig.UserData;
if ~isempty(spinVal), data.harmonic = spinVal; end
if ~isempty(cbVal), data.plotAllHarmonics = cbVal; end
fig.UserData = data;
refreshPhasorPlot(fig);
refreshXYProjection(fig);
end

function refreshPhasorPlot(fig)
data = fig.UserData;
if isempty(data.RawData), return; end

axPhasor = findobj(fig, 'Tag', 'axPhasor');
if isempty(axPhasor), return; end

config = data.config;
[nY, nX, nGates] = size(data.RawData);
M = nX * nY;
flatData = double(reshape(permute(data.RawData, [3, 1, 2]), nGates, M));
sumIntensity = sum(flatData, 1);
sumIntensity(sumIntensity == 0) = 1e-10;

% Setup Time and Gates for Locus
dt = config.dt; T = config.T; t = 0:dt:T;
gate_profiles = DTgates(t, config.r, config.gate_edges);
gate_interp_fns = cell(config.N_gates, 1);
for i = 1:config.N_gates
    gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
end
tau_locus = logspace(log10(0.05), log10(50), 100);

max_h = data.harmonic;
if data.plotAllHarmonics
    h_range = 1:max_h;
else
    h_range = max_h;
end

cla(axPhasor); hold(axPhasor, 'on');

% Draw Universal Circle once
gArc = linspace(0, 1, 100);
sArc = sqrt(gArc .* (1 - gArc));
plot(axPhasor, gArc, sArc, 'k-', 'LineWidth', 1, 'HandleVisibility', 'off');

hColors = {[0 0 1], [0 0.7 0], [1 0 0]}; % Blue, Green, Red
names = {};
hPlots = [];

if config.bPulseTrain && isfield(config, 'PT_Trep')
    f_base = 1/config.PT_Trep;
else
    f_base = 1/config.T;
end

gate_centers = 0.5 * (config.gate_edges(1:end-1) + config.gate_edges(2:end));

for h = h_range
    f_h = h * f_base;

    % Data Phasors
    cosT = cos(2 * pi * f_h * gate_centers(:));
    sinT = sin(2 * pi * f_h * gate_centers(:));
    Gh = (cosT' * flatData) ./ sumIntensity;
    Sh = (sinT' * flatData) ./ sumIntensity;

    % Store latest selected harmonic's GS for ROI selection
    if h == max_h
        data.G_vals = Gh;
        data.S_vals = Sh;
    end

    % Plot Data
    if M > 5000
        idx = round(linspace(1, M, 5000));
        hp = plot(axPhasor, Gh(idx), Sh(idx), '.', 'Color', hColors{h}, 'MarkerSize', 2);
    else
        hp = plot(axPhasor, Gh, Sh, '.', 'Color', hColors{h}, 'MarkerSize', 2);
    end
    hPlots = [hPlots, hp];
    names{end+1} = sprintf('H%d Data', h);

    % Plot Locus
    P_locus = DTpmod(config.N_gates, tau_locus, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);
    sumP = sum(P_locus, 1); sumP(sumP == 0) = 1e-10;
    GLocus = (cosT' * P_locus) ./ sumP;
    SLocus = (sinT' * P_locus) ./ sumP;
    plot(axPhasor, GLocus, SLocus, '--', 'Color', [0.4 0.4 0.4], 'LineWidth', 0.8, 'HandleVisibility', 'off');
end

fig.UserData = data;

% Zoom and Layout
grid(axPhasor, 'on');
xlabel(axPhasor, 'G'); ylabel(axPhasor, 'S');
axis(axPhasor, 'equal');

% Adjust limits based on Zoom Mode
all_children = axPhasor.Children;

if strcmpi(data.phasorZoomMode, 'Data')
    % Target ONLY experimental data points (Dots)
    minG = inf; maxG = -inf; minS = inf; maxS = -inf;
    for i = 1:numel(all_children)
        % Data points have '.' marker and were plotted in the loop
        if matches(all_children(i).Type, 'line') && strcmp(all_children(i).Marker, '.')
            minG = min(minG, min(all_children(i).XData(:)));
            maxG = max(maxG, max(all_children(i).XData(:)));
            minS = min(minS, min(all_children(i).YData(:)));
            maxS = max(maxS, max(all_children(i).YData(:)));
        end
    end
    if isinf(minG), minG=0; maxG=1; minS=0; maxS=0.5; end
    padding = 0.10; % 10% space in all directions
else
    % 'Full' Mode: See everything (Data + Curves + Circle)
    minG = 0; maxG = 1; minS = 0; maxS = 0.5;
    for i = 1:numel(all_children)
        if isprop(all_children(i), 'XData') && ~isempty(all_children(i).XData)
            minG = min(minG, min(all_children(i).XData(:)));
            maxG = max(maxG, max(all_children(i).XData(:)));
            minS = min(minS, min(all_children(i).YData(:)));
            maxS = max(maxS, max(all_children(i).YData(:)));
        end
    end
    padding = 0.05; % Default padding
end

gw = maxG - minG; sh = maxS - minS;
if gw == 0, gw = 1; end
if sh == 0, sh = 1; end

xlim(axPhasor, [minG - padding*gw, maxG + padding*gw]);
ylim(axPhasor, [minS - padding*sh, maxS + padding*sh]);

title(axPhasor, 'Phasor FLIM Analysis');
legend(axPhasor, hPlots, names, 'Location', 'eastoutside', 'FontSize', 8);
hold(axPhasor, 'off');
end
