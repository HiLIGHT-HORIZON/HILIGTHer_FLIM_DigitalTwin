function MockData_GUI(configStruct)
% MOCKDATA_GUI - GUI for generating mock FLIM data
% ConfigStruct contains settings imported from the main FLIM_GUI

% === Main Figure ===
figWidth = 1800;
figHeight = 1050;
fig = uifigure('Name', 'HILIGHTer', 'Position', [50 50 figWidth figHeight]);

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


% === Instrument Parameters Panel (Below Config) ===
% Fill the remaining vertical space in Column 1
instPanelH = figHeight - configPanelH - 3*margin - 20;
instPanel = uipanel(fig, 'Title', 'Instrument Parameters', ...
    'Position', [col1X, margin, col1W, instPanelH]);

% Initialization of vizMode
% (vizSwitch removed from sidebar, will be in tabs)

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

% (Phasor Plot removed from here, now in Column 3 tabs)

% 4. YT Projection (Right)
ytW = plotH * 0.3; % Consistent width
ytX = col2X + plotH + margin;
axYT = uiaxes(fig, 'Position', [ytX, xyY, ytW, plotH]);
axYT.Tag = 'axYT';
axYT.XTick = []; axYT.YTick = []; axYT.Box = 'on';

% === Column 3: Analysis Results Tabs ===
col3X = ytX + ytW + margin + 80;
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

% 6. Plotting (Column 2)
axXY = findobj(fig, 'Tag', 'axXY');
axXT = findobj(fig, 'Tag', 'axXT');
axYT = findobj(fig, 'Tag', 'axYT');

imagesc(axXY, projXY);
colormap(axXY, 'parula');
cb = colorbar(axXY, 'Location', 'westoutside');
cb.Label.String = 'Photons';
title(axXY, 'XY (Total Photons)'); axis(axXY, 'image');
set(axXY, 'XTick', [], 'YTick', [], 'Box', 'on');

imagesc(axXT, projXT);
cb = colorbar(axXT, 'Location', 'westoutside');
cb.Label.String = 'Photons';
title(axXT, '');
xlabel(axXT, 'XT Projection', 'Visible', 'on', 'FontWeight', 'bold');
axis(axXT, 'tight');
set(axXT, 'XTick', [], 'YTick', [], 'Box', 'on');

imagesc(axYT, projYT);
cb = colorbar(axYT, 'Location', 'eastoutside');
cb.Label.String = 'Photons';
title(axYT, 'YT Proj');
axis(axYT, 'tight');
set(axYT, 'XTick', [], 'YTick', [], 'Box', 'on');

% Note: Analysis results (tabs) are preserved as history.
% To clear them, one would interact with the tab group.

% 7. Update Instrument Plot
updateInstrumentPlot(fig, tau1Field, tau2Field);
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

    if strcmpi(algo, 'Phasor Analysis')
        createNewPhasorTab(fig, destTab);
    elseif strcmpi(algo, 'Pattern Matching')
        createNewPatternTab(fig, destTab);
    elseif strcmpi(algo, 'LiMA')
        createNewLimaTab(fig, destTab);
    elseif strcmpi(algo, 'Fisher Analysis')
        createNewFisherTab(fig, destTab);
    else
        createNewFitTab(fig, destTab, algo);
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

if strcmpi(data.vizMode, 'Default')
    % Standard Photons Map
    hImg = imagesc(axXY, data.projXY);
    colormap(axXY, 'parula');
    cb = colorbar(axXY, 'Location', 'westoutside');
    cb.Label.String = 'Photons';
    title(axXY, 'XY (Total Photons)');
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
        hImg = imagesc(axXY, data.projXY);
    else
        [nY, nX] = size(data.projXY);
        I = double(data.projXY);
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

function createNewPhasorTab(fig, t)
data = fig.UserData;

% If UI already exists in this tab, just refresh and return
if ~isempty(t.UserData) && isfield(t.UserData, 'axPhasor')
    refreshPhasorPlot(fig, t.UserData.axPhasor);
    return;
end

% Local settings for this run
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

function createNewFitTab(fig, tab, algo)
data = fig.UserData;
config = data.config;
RawData = data.RawData;
[nY, nX, nGates] = size(RawData);

axL = data.axL; axW = data.axW; metX = data.metX; xyY_top = data.xyY_top;

% If UI already exists, skip creation
if isempty(tab.UserData) || ~isfield(tab.UserData, 'axTau')
    axTau = uiaxes(tab, 'PositionConstraint', 'innerposition');
    axTau.InnerPosition = [axL, xyY_top, axW, axW]; axTau.Tag = 'axTauLocal';

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
        'Position', [metX, xyY_top + axW - 150, 220, 150]);
    uilabel(paramPanel, 'Text', 'Algorithm: --', 'Tag', 'uAlgo', 'Position', [10, 100, 180, 20]);
    uilabel(paramPanel, 'Text', 'Gates: --', 'Tag', 'uGates', 'Position', [10, 80, 180, 20]);
    uilabel(paramPanel, 'Text', 'FWHM: --', 'Tag', 'uFWHM', 'Position', [10, 60, 180, 20]);

    tabMeta.axTau = axTau; tabMeta.axStats = axStats; tabMeta.axRes = axRes;
    tabMeta.axPix = axPix; tabMeta.axPixRes = axPixRes;
    tabMeta.uChi = uChi; tabMeta.uRE = uRE; tabMeta.uRND = uRND;
    tabMeta.uPixPos = uPixPos; tabMeta.uPixTau = uPixTau;
    tabMeta.uPixChi = uPixChi; tabMeta.uPixRE = uPixRE; tabMeta.uPixRND = uPixRND;
    tab.UserData = tabMeta;
else
    tabMeta = tab.UserData;
    axTau = tabMeta.axTau; axStats = tabMeta.axStats; axRes = tabMeta.axRes;
    axPix = tabMeta.axPix; axPixRes = tabMeta.axPixRes;
    uChi = tabMeta.uChi; uRE = tabMeta.uRE; uRND = tabMeta.uRND;
end

% Update Parameters Panel
pnl = findobj(tab, 'Tag', 'paramPanel');
if ~isempty(pnl)
    uAlgo = findobj(pnl, 'Tag', 'uAlgo'); uAlgo.Text = sprintf('Algorithm: %s', algo);
    uGates = findobj(pnl, 'Tag', 'uGates'); uGates.Text = sprintf('Gates: %d', config.N_gates);
    uFWHM = findobj(pnl, 'Tag', 'uFWHM'); uFWHM.Text = sprintf('FWHM: %.1f ps', config.fwhm*1000);
end

dt = config.dt; T = config.T; t = 0:dt:T;
gate_profiles = DTgates(t, config.r, config.gate_edges);
gate_interp_fns = cell(config.N_gates, 1);
for i = 1:config.N_gates
    gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
end
M = nY * nX; flatData = double(reshape(permute(RawData, [3, 1, 2]), nGates, M));
N_detections = sum(flatData, 1);

if strcmpi(algo, 'Grid MLE')
    tau_grid = linspace(0.1, 10, 100);
    P_model_grid = DTpmod(config.N_gates, tau_grid, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);
    [tau_est_flat, ~] = DTmle(N_detections, flatData, tau_grid, P_model_grid, fig);
else
    [TauMap_Iter, ~] = DTiterative(RawData, config, fig);
    tau_est_flat = reshape(TauMap_Iter, 1, []);
end
TauMap = reshape(tau_est_flat, nY, nX);

hImg = imagesc(axTau, TauMap); colormap(axTau, 'jet'); colorbar(axTau);
hImg.ButtonDownFcn = @(src, event) updatePixelAnalysis(fig, event.IntersectionPoint);
title(axTau, tab.Title);

tabMeta.axTau = axTau; tabMeta.axStats = axStats; tabMeta.axRes = axRes;
tabMeta.axPix = axPix; tabMeta.axPixRes = axPixRes;
tabMeta.uChi = uChi; tabMeta.uRE = uRE; tabMeta.uRND = uRND;
tabMeta.uPixPos = uPixPos; tabMeta.uPixTau = uPixTau;
tabMeta.uPixChi = uPixChi; tabMeta.uPixRE = uPixRE; tabMeta.uPixRND = uPixRND;
tabMeta.TauMap = TauMap; tabMeta.gate_interp_fns = gate_interp_fns;
tabMeta.nX = nX; tabMeta.nY = nY;
tab.UserData = tabMeta;

meanTau = mean(TauMap, 1, 'omitnan'); stdTau = std(TauMap, 0, 1, 'omitnan');
xVec = 1:nX;
fill(axStats, [xVec, fliplr(xVec)], [meanTau+1.96*stdTau, fliplr(meanTau-1.96*stdTau)], ...
    [0.6 0.8 1], 'EdgeColor', 'none', 'FaceAlpha', 0.5);
hold(axStats, 'on'); plot(axStats, xVec, meanTau, 'b-', 'LineWidth', 1.5);
grid(axStats, 'on');

tau_true = data.GroundTruthTaus(:)'; % Ensure row vector
irf_params = struct('fwhm',config.fwhm,'profile',config.profile,'rise_time',config.rise_time,'fall_time',config.fall_time,...
    'bPulseTrain',config.bPulseTrain,'PT_Trep',config.PT_Trep,'PT_sigma',config.PT_sigma);
n_ph_px = sum(N_detections) / M;
[~, f_vals_true] = DTcomputeFisherInfo(config.gate_edges, irf_params, config.r, config.T, tau_true, n_ph_px);
sigma_crlb = (f_vals_true .* tau_true) / sqrt(n_ph_px);
z_map = (TauMap - repmat(tau_true, nY, 1)) ./ repmat(sigma_crlb, nY, 1);

stem(axRes, 1:nX, mean(z_map, 1, 'omitnan'), 'Marker', 'none');
yline(axRes, [2, -2], 'r--'); grid(axRes, 'on');

uChi.Text = sprintf('Chi2: %.3f', mean(z_map(:).^2, 'omitnan'));
uRE.Text = sprintf('R.E.: %.1f%%', (1/mean(z_map(:).^2, 'omitnan'))*100);

updatePixelAnalysis(fig, [nX/2, nY/2]);
end

function createNewPatternTab(fig, t)
data = fig.UserData;
if ~isfield(data, 'RawData') || isempty(data.RawData)
    error('RawData is missing from fig.UserData. Please generate data first.');
end
if ~isfield(data, 'config') || isempty(data.config)
    error('Config is missing from fig.UserData.');
end

[nY, nX, ~] = size(data.RawData);
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
    t.UserData = meta;

    % -- Initialize DDM Data (One time calc) --
    % We interpret this as LiMA moments: Mean Tau vs Sigma
    % Reuse DTlima logic silently
    [limaResults, ~] = DTlima(data.RawData, data.config, 1, []); % Call with empty fig to suppress waiting

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
% RawData is (nY, nX, nGates). meta.mu_flat is (nY * nX, 1).
% We can simply reshape RawData to (Gates, Pixels).
[~, ~, nGates] = size(data.RawData);
flatData = reshape(permute(data.RawData, [3, 1, 2]), nGates, []); % (Gates, M)

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
[nY, nX, nGates] = size(data.RawData);
patMat = zeros(nGates, K);
for i = 1:K
    patMat(:, i) = meta.patterns(i).decay;
end

% 2. Run Fit
[fractionMaps, ~, ~] = DTpatternmatching(data.RawData, patMat, data.config, fig);

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

function createNewLimaTab(fig, t)
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
    RawData = data.RawData;

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

        meta = struct();
        meta.axMu = axMu; meta.axSig = axSig; meta.axGraph = axGraph;
        meta.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});
        meta.phasorZoomMode = 'Full';
        meta.harmonic = 1;
        t.UserData = meta;
        debugInfo = 'UI Initialized and UserData set';
    end

    % Retrieve meta and enforce struct integrity
    meta = t.UserData;
    if isempty(meta) || ~isstruct(meta)
        % Force reset if corrupted
        meta = struct('harmonic', 1, 'phasorZoomMode', 'Full');
        meta.ROIs = struct('color', {'Red','Green','Blue'}, 'handle', {[],[],[]}, 'active', {false,false,false});

        % Re-bind axes handles
        meta.axMu = findobj(t, 'Tag', 'axMu');
        meta.axSig = findobj(t, 'Tag', 'axSig');
        meta.axGraph = findobj(t, 'Tag', 'axGraph');
    end
    debugInfo = 'Meta validated';

    harmonic = 1;
    if isfield(meta, 'harmonic'), harmonic = meta.harmonic; end

    % Run LiMA
    debugInfo = 'Calling DTlima';
    [limaResults, stats] = DTlima(RawData, config, harmonic, fig);
    debugInfo = 'DTlima returned';

    % Validate stats
    if ~isstruct(stats) || ~isfield(stats, 'S') || ~isfield(stats, 'G')
        error('DTlima returned invalid stats structure.');
    end

    % Store Results
    meta.mu_vals = stats.S(:) ./ max(stats.G(:), 1e-9);

    M_val_tmp = sqrt(stats.G(:).^2 + stats.S(:).^2);
    meta.I2_vals = 0.5 * (max(M_val_tmp.^-2 - 1, 0) + meta.mu_vals.^2);

    debugInfo = 'Updating maps';
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

    debugInfo = 'Calculating Loop';
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
catch ME
    uialert(fig, sprintf('LiMA Error at step "%s": %s', debugInfo, ME.message), 'Error');
    fprintf('LiMA Error Stack:\n');
    disp(ME.stack);
end
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
tabGroup = findobj(fig, 'Tag', 'analysisTabs');
if isempty(tabGroup) || isempty(tabGroup.SelectedTab), return; end
tab = tabGroup.SelectedTab;
if isempty(tab.UserData) || ~isfield(tab.UserData, 'TauMap'), return; end
meta = tab.UserData;

px = round(point(1)); py = round(point(2));
% Use tab-local dimensions if available, else fallback to current data
if isfield(meta, 'nX')
    nX = meta.nX; nY = meta.nY;
else
    [nY, nX, ~] = size(data.RawData);
end

if px < 1 || px > nX || py < 1 || py > nY, return; end

% Update Crosshair
hV = findobj(fig, 'Tag', 'crossV');
hH = findobj(fig, 'Tag', 'crossH');
if ~isempty(hV), set(hV, 'Value', px, 'Visible', 'on'); end
if ~isempty(hH), set(hH, 'Value', py, 'Visible', 'on'); end

% Extract Pixel Data (Note: RawData is still global for now, but estTau is tab-local)
pixelCounts = squeeze(data.RawData(py, px, :));
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
    harmonic = 1; plotAllHarmonics = true; zoomMode = 'Full';
else
    harmonic = meta.harmonic;
    plotAllHarmonics = meta.plotAllHarmonics;
    zoomMode = meta.phasorZoomMode;
end

config = data.config;
[nY, nX, nGates] = size(data.RawData);
M = nX * nY;
flatData = double(reshape(permute(data.RawData, [3, 1, 2]), nGates, M));
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

function createNewFisherTab(fig, t)

if isempty(t.UserData)
    meta = struct(); % Initialize meta
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
    t.UserData = meta;
end
end

function addFisherROI(fig, refIdx)
t = findobj(fig, 'Tag', 'analysisTabs').SelectedTab;
meta = t.UserData;
data = fig.UserData;

axXY = findobj(fig, 'Tag', 'axXY');
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

    [nY, nX, nGates] = size(data.RawData);
    flatData = reshape(permute(data.RawData, [3, 1, 2]), nGates, []);

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
