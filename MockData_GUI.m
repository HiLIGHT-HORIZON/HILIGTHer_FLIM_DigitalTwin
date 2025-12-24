function MockData_GUI(configStruct)
% MOCKDATA_GUI - GUI for generating mock FLIM data
% ConfigStruct contains settings imported from the main FLIM_GUI

% === Main Figure ===
figWidth = 1500;
figHeight = 900;
fig = uifigure('Name', 'HILIGHT Data Analysis Simulator', 'Position', [50 50 figWidth figHeight]);

% Store config and data in a struct
dataStruct.config = configStruct;
dataStruct.RawData = [];
fig.UserData = dataStruct;

% === Layout Constants ===
margin = 15;

% --- Column 1: Controls ---
col1W = 280;
col1X = margin;

% --- Column 2: Data Projections ---
% XY, XT, YT vertically stacked
% Remaining width for cols 2 and 3
remainingW = figWidth - col1W - 4*margin;
col2W = remainingW * 0.45; % Slightly narrower for data? or equal? Let's do equal split of remainder
col2W = floor(remainingW / 2);
col3W = col2W;

col2X = col1X + col1W + margin;
col3X = col2X + col2W + margin;

% === Configuration Panel (Top Left) ===
configPanelH = 260;
configPanel = uipanel(fig, 'Title', 'Configuration', ...
    'Position', [col1X, figHeight - configPanelH - margin, col1W, configPanelH]);

inputH = 22;

% -- Mode Selection --
currY = configPanelH - 50;
uilabel(configPanel, 'Text', 'Mode:', 'Position', [10 currY 50 inputH]);
modeDropdown = uidropdown(configPanel, ...
    'Items', {'Gradient', 'Mix'}, ...
    'Value', 'Gradient', ...
    'Position', [70 currY 120 inputH]);

currY = currY - 35;
% -- Image Dimensions --
uilabel(configPanel, 'Text', 'Size (X, Y):', 'Position', [10 currY 70 inputH]);
dimXField = uieditfield(configPanel, 'numeric', 'Value', 256, 'Position', [80 currY 50 inputH]);
dimYField = uieditfield(configPanel, 'numeric', 'Value', 256, 'Position', [140 currY 50 inputH]);

uibutton(configPanel, 'Text', 'x2', 'Position', [200 currY 25 inputH], ...
    'ButtonPushedFcn', @(btn, event) adjustSize(dimXField, dimYField, 2));
uibutton(configPanel, 'Text', '/2', 'Position', [230 currY 25 inputH], ...
    'ButtonPushedFcn', @(btn, event) adjustSize(dimXField, dimYField, 0.5));

currY = currY - 35;
% -- Lifetimes --
uilabel(configPanel, 'Text', 'Lifetime 1 (ps):', 'Position', [10 currY 90 inputH]);
tau1Field = uieditfield(configPanel, 'numeric', 'Value', 1000, 'Position', [100 currY 60 inputH]);

currY = currY - 35;
uilabel(configPanel, 'Text', 'Lifetime 2 (ps):', 'Position', [10 currY 90 inputH]);
tau2Field = uieditfield(configPanel, 'numeric', 'Value', 2000, 'Position', [100 currY 60 inputH]);

% Callbacks for instant updating of Instrument Plot
tau1Field.ValueChangedFcn = @(src, event) updateInstrumentPlot(fig, tau1Field, tau2Field);
tau2Field.ValueChangedFcn = @(src, event) updateInstrumentPlot(fig, tau1Field, tau2Field);

currY = currY - 35;
uilabel(configPanel, 'Text', 'Photons/Px:', 'Position', [10 currY 90 inputH]);
photonsField = uieditfield(configPanel, 'numeric', 'Value', dataStruct.config.N_photons, 'Position', [100 currY 60 inputH]);

currY = currY - 45;
% -- Generate Button --
uibutton(configPanel, 'Text', 'GENERATE', 'FontWeight','bold', ...
    'Position', [20 currY 240 30], ...
    'ButtonPushedFcn', @(btn, event) onGenerate(fig, modeDropdown, dimXField, dimYField, tau1Field, tau2Field, photonsField));


% === Analysis Panel (Below Config) ===
analysisPanelH = 150;
analysisPanel = uipanel(fig, 'Title', 'Analysis', ...
    'Position', [col1X, figHeight - configPanelH - analysisPanelH - 2*margin, col1W, analysisPanelH]);

currY = analysisPanelH - 50;
uilabel(analysisPanel, 'Text', 'Algorithm:', 'Position', [10 currY 70 inputH]);
algoDropdown = uidropdown(analysisPanel, ...
    'Items', {'Default (Grid MLE)', 'Iterative Reconvolution'}, ...
    'Value', 'Default (Grid MLE)', ...
    'Position', [80 currY 180 inputH]);

currY = currY - 50;
uibutton(analysisPanel, 'Text', 'ANALYSE', 'FontWeight','bold', ...
    'Position', [20 currY 240 30], ...
    'ButtonPushedFcn', @(btn, event) onAnalyze(fig, algoDropdown));


% === Instrument Parameters Panel (Below Analysis) ===
instPanelH = 250;
instPanel = uipanel(fig, 'Title', 'Instrument Parameters', ...
    'Position', [col1X, figHeight - configPanelH - analysisPanelH - instPanelH - 3*margin, col1W, instPanelH]);

% Plot Ax
axInst = uiaxes(instPanel, 'Position', [5 5 col1W-10 instPanelH-25]);
axInst.Tag = 'axInst';
title(axInst, 'IRF & Gates'); xlabel(axInst, 'Time (ns)');
grid(axInst, 'on');


% === Column 2: Data Projections (Center) ===
% Stack 3 axes: XY, XT, YT
% Available Height
totalPlotH = figHeight - 2*margin;
% Make plots bigger: e.g. 500px, but limited by available width/height
% Let's increase plotH significantly. Previous was roughly 1/3 ~ 280px.
% 2x bigger is too big for figHeight 900.
% User said "make them 2x bigger".
% Let's try explicit size.
plotH = 375; % Scaled to 75% of 500

col2W = plotH; % Force column width to match plot width
col3X = col2X + col2W + margin + 100; % Shift col 3 further right (colorbar space)

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

% 3. YT Projection (Bottom)
% Use same size/aspect as XY (square) or XT? User script had projYT as map.
% Wait, YT projection is usually (Y, Time).
% If it's Y vs Time, Y axis matches XY Y-axis. Time is x-axis.
% Previous code:
% axYT = uiaxes(fig, 'Position', [col2X, figHeight - margin - 3*plotH - 2*margin, plotH, plotH]);
% Let's double size.
ytY = xtY - margin - plotH;
axYT = uiaxes(fig, 'Position', [col2X, ytY, plotH, plotH]);
title(axYT, 'YT Projection (Time vs Y)');
axYT.Tag = 'axYT';
axYT.XTick = []; axYT.YTick = []; axYT.Box = 'on';


% === Column 3: Analysis Results (Right) ===
% Stack 2 axes: Map, Stats
% 2 plots -> 1/2 each
plotHalfH = floor((totalPlotH - margin) / 2);

% 1. Estimated Lifetime Map (Top)
axTau = uiaxes(fig, 'Position', [col3X, figHeight - margin - plotHalfH, col3W, plotHalfH]);
title(axTau, 'Estimated Lifetime (ns)'); xlabel(axTau, 'X'); ylabel(axTau, 'Y');
axTau.Tag = 'axTau';

% 2. Lifetime Statistics (Bottom)
axStats = uiaxes(fig, 'Position', [col3X, figHeight - margin - 2*plotHalfH - margin, col3W, plotHalfH]);
title(axStats, 'Lifetime Statistics (Mean \pm Std along Y)'); xlabel(axStats, 'X'); ylabel(axStats, 'Estimated \tau (ns)');
axStats.Tag = 'axStats';
grid(axStats, 'on');

% Initial Plot update
updateInstrumentPlot(fig, tau1Field, tau2Field);

end

function onGenerate(fig, modeDropdown, dimXField, dimYField, tau1Field, tau2Field, photonsField)
% Retrieve config and params
data = fig.UserData;
config = data.config;

Mode = modeDropdown.Value;
nX = dimXField.Value;
nY = dimYField.Value;
tau1_ns = tau1Field.Value / 1000; % convert ps to ns
tau2_ns = tau2Field.Value / 1000;

% Setup Time and Gates (Reuse logic)
dt = config.dt;
T = config.T;
t = 0:dt:T;

% Reconstruct Gate Interp Functions
% Reconstruct Gate Interp Functions
actual_gate_edges = config.gate_edges;

gate_profiles = DTgates(t, config.r, actual_gate_edges);
gate_interp_fns = cell(config.N_gates, 1);
for i = 1:config.N_gates
    gate_interp_fns{i} = griddedInterpolant(t, gate_profiles(i, :), 'linear', 'nearest');
end

% 1. Create Model Probabilities
if strcmp(Mode, 'Gradient')
    unique_taus = linspace(tau1_ns, tau2_ns, nX);
    P_model = DTpmod(config.N_gates, unique_taus, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);
else
    % Mix Mode
    taus_base = [tau1_ns, tau2_ns];
    P_base = DTpmod(config.N_gates, taus_base, t, gate_interp_fns, ...
        config.fwhm, config.profile, config.rise_time, config.fall_time, ...
        config.bPulseTrain, config.PT_Trep, config.PT_sigma);
    P_tau1 = P_base(:, 1);
    P_tau2 = P_base(:, 2);
    alpha = linspace(0, 1, nX);
    P_model = P_tau1 * (1 - alpha) + P_tau2 * alpha;
end

% 3. Calculate Expected Photons
N_generated = photonsField.Value;

% Normalize P_model so that specificed N_generated is the DETECTED sum (Expected)
% Sum over gates (axis 1)
P_sum = sum(P_model, 1);
% Avoid division by zero
P_sum(P_sum == 0) = 1;

P_model_norm = P_model ./ P_sum;

ExpCounts_1Row = P_model_norm * N_generated;

% 4. Expand to full image AND STORE RawData (nY, nX, N_gates)
% IMPORTANT: poissrnd needs distinct noise per pixel.
ExpCounts_Full = repmat(reshape(ExpCounts_1Row', 1, nX, config.N_gates), nY, 1, 1);
RawData = poissrnd(ExpCounts_Full);

% Store Data for Analysis
data.RawData = RawData;
fig.UserData = data;

% 5. Projections
projXY = sum(RawData, 3);
projXT = squeeze(sum(RawData, 1))'; % (Gates, X)
projYT = squeeze(sum(RawData, 2));  % (Y, Gates)

% 6. Plotting
axXY = findobj(fig, 'Tag', 'axXY');
axXT = findobj(fig, 'Tag', 'axXT');
axYT = findobj(fig, 'Tag', 'axYT');
axTau = findobj(fig, 'Tag', 'axTau');
axStats = findobj(fig, 'Tag', 'axStats');

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
cb = colorbar(axYT, 'Location', 'westoutside');
cb.Label.String = 'Photons';
title(axYT, 'YT Projection');
axis(axYT, 'normal');
set(axYT, 'XTick', [], 'YTick', [], 'Box', 'on');

% Clear Analysis plots until analyzed
cla(axTau);
title(axTau, 'Estimated Lifetime (Click ANALYSE)');

cla(axStats);
title(axStats, 'Lifetime Statistics');

% 7. Update Instrument Plot
updateInstrumentPlot(fig, tau1Field, tau2Field);
end

function adjustSize(dimXField, dimYField, factor)
dimXField.Value = round(dimXField.Value * factor);
dimYField.Value = round(dimYField.Value * factor);
end

function onAnalyze(fig, algoDropdown)
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
imagesc(axTau, TauMap);
colormap(axTau, 'jet'); colorbar(axTau);
title(axTau, 'Estimated Lifetime (ns)');
axis(axTau, 'image');
xlabel(axTau, 'X'); ylabel(axTau, 'Y');

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

title(axStats, 'Lifetime Statistics (Vertical Average \pm 95% CI)');
xlabel(axStats, 'X Position'); ylabel(axStats, 'Estimated \tau (ns)');
grid(axStats, 'on');
xlim(axStats, [1 nX]);

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

legend(axInst, {'IRF', ['\tau_1'], ['\tau_2']}, 'Location', 'best');
axis(axInst, 'tight');
end
