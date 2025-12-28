function applyInstrumentToDT(data)
% APPLYINSTRUMENTTODT - Applies instrument settings structure to the open Digital Twin GUI
% content of data should match the structure saved by InstrumentWizard

% Store currently active figure to restore focus later if needed
currentFig = get(0, 'CurrentFigure');

dtFig = findall(0, 'Name', 'HILIGHT FLIM Digital Twin');
hlFig = findall(0, 'Name', 'HILIGHTer');

% 1. Update Digital Twin GUI if open
if ~isempty(dtFig)
    fig = dtFig(1);
    % We update the UI elements, but avoid bringing to front if HILIGHTer was active
    % However, typical MATLAB UI updates might not stealing focus, but 'figure(fig)' command does.

    applyToFigTags(fig, data);

    % If HILIGHTer is NOT open, we definitely want to see DT changes.
    % If HILIGHTer IS open, and was active, we want to keep HILIGHTer active.
end

% 2. Update HILIGHTer if open
if ~isempty(hlFig)
    hFig = hlFig(1);
    updateHILIGHTerConfig(hFig, data);
end

% --- Focus Management ---
if ~isempty(currentFig) && isvalid(currentFig)
    % If the user was interacting with HILIGHTer (e.g. via menu which triggers this),
    % ensure it remains the focused window.
    if strcmp(currentFig.Name, 'HILIGHTer')
        figure(currentFig);
    elseif ~isempty(dtFig) && strcmp(currentFig.Name, 'HILIGHT FLIM Digital Twin')
        figure(dtFig(1));
    end
else
    % Fallback: if no clear active figure, prioritize HILIGHTer if updated, else DT
    if ~isempty(hlFig)
        figure(hFig);
    elseif ~isempty(dtFig)
        figure(dtFig(1));
    end
end

if isempty(dtFig) && isempty(hlFig)
    % Optionally warn if neither open
end
end

function applyToFigTags(fig, data)
% Helper to set value by Tag
    function setTag(t, v)
        if isempty(v), return; end
        obj = findobj(fig, 'Tag', t);
        if ~isempty(obj)
            % Handle numeric vs string fields
            if isa(obj, 'matlab.ui.control.NumericEditField')
                if isnumeric(v), obj.Value = v; else, obj.Value = str2double(v); end
            elseif isa(obj, 'matlab.ui.control.EditField') % Text
                if ischar(v) || isstring(v), obj.Value = v; else, obj.Value = num2str(v); end
            elseif isa(obj, 'matlab.ui.control.DropDown')
                if any(strcmp(obj.Items, v))
                    obj.Value = v;
                end
            elseif isa(obj, 'matlab.ui.control.CheckBox')
                obj.Value = logical(v);
            end

            % Trigger callback if present to update UI state (e.g. visibility)
            if isprop(obj, 'ValueChangedFcn') && ~isempty(obj.ValueChangedFcn)
                try
                    obj.ValueChangedFcn(obj, []);
                catch
                end
            end
        end
    end

if isfield(data, 'T'), setTag('TField', data.T); end
if isfield(data, 'fwhm'), setTag('fwhmField', data.fwhm); end
if isfield(data, 'profile'), setTag('profileDropdown', data.profile); end
if isfield(data, 'toff'), setTag('toffField', data.toff); end
if isfield(data, 'rise_time'), setTag('riseField', data.rise_time); end
if isfield(data, 'fall_time'), setTag('fallField', data.fall_time); end

if isfield(data, 'bPulseTrain'), setTag('PTCheck', data.bPulseTrain); end
if isfield(data, 'PT_Trep'), setTag('PTTField', data.PT_Trep); end
if isfield(data, 'PT_sigma'), setTag('PTSField', data.PT_sigma); end

if isfield(data, 'gate_type'), setTag('gateDropdown', data.gate_type); end
if isfield(data, 'N_gates'), setTag('NGateField', data.N_gates); end
if isfield(data, 'r'), setTag('rField', data.r); end

% Custom Gates
if isfield(data, 'gate_widths') && ~isempty(data.gate_widths)
    gw = data.gate_widths;
    for k=1:min(8, numel(gw))
        setTag(sprintf('gField%d', k), gw(k));
    end
end
end

function updateHILIGHTerConfig(fig, data)
% Update UserData.config
ud = fig.UserData;
if ~isfield(ud, 'config'), ud.config = struct(); end

% Map fields
baseFields = {'T', 'fwhm', 'profile', 'toff', 'rise_time', 'fall_time', ...
    'bPulseTrain', 'PT_Trep', 'PT_sigma', 'gate_type', 'N_gates', 'r'};

for i=1:length(baseFields)
    Fn = baseFields{i};
    if isfield(data, Fn)
        ud.config.(Fn) = data.(Fn);
    end
end

% Recompute Gate Edges
% Default logic: Equal gates from 0 to T (or toff?)
% Standard DigitalTwin logic often uses 0 to T for equal gates.
% But if toff is specified, maybe up to toff.
% Let's use T as safe default if toff is missing, or max(T, toff).
% Actually, commonly gates cover the period T.

T = ud.config.T;
if isfield(ud.config, 'gate_type') && strcmpi(ud.config.gate_type, 'Custom')
    if isfield(data, 'gate_widths')
        widths = data.gate_widths;
        edges = [0, cumsum(widths(:))'];
        ud.config.gate_edges = edges;
    end
else
    % Equal
    N = ud.config.N_gates;
    % Check if toff is relevant for range end?
    % Usually gates span the whole period in many FLIM systems, or a specific window.
    % HILIGHTer default was linspace(0, 12.5, 33) where T=12.5. So 0 to T.
    ud.config.gate_edges = linspace(0, T, N + 1);
end

fig.UserData = ud;

% Refresh Plot
refreshHILIGHTerInstPlot(fig, ud.config);
end

function refreshHILIGHTerInstPlot(fig, config)
ax = findobj(fig, 'Tag', 'axInst');
if isempty(ax), return; end

cla(ax, 'reset');
ax.Tag = 'axInst'; % vital to restore tag after reset
hold(ax, 'on');

% Time vector
dt = 0.05; % Fixed resolution for viz
t = 0:dt:config.T;

% Calculate IRF
base_irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);

% Shift IRF by toff
toff = 0;
if isfield(config, 'toff'), toff = config.toff; end

if toff ~= 0
    % Interpolate: New Value at t is Old Value at (t - toff)
    irf = interp1(t, base_irf, t - toff, 'linear', 0);
else
    irf = base_irf;
end

% Normalize for display
if max(irf(:)) > 0
    irf = irf / max(irf(:));
end

% Plot IRF
plot(ax, t, irf, 'r-', 'LineWidth', 1.5, 'DisplayName', 'IRF');

% Plot Gates
edges = config.gate_edges;
ylim(ax, [0 1.1]);

if numel(edges) > 32
    % Too many gates to draw individually without clutter
    % Draw bounding box of the gated region
    xRegion = [edges(1), edges(end), edges(end), edges(1)];
    yRegion = [0 0 1.1 1.1];
    patch(ax, xRegion, yRegion, [0.9 0.9 0.9], 'FaceAlpha', 0.3, 'EdgeColor', 'none', 'DisplayName', 'Gated Region');
    if exist('xline', 'file')
        xline(ax, edges(1), 'k:', 'HandleVisibility', 'off');
        xline(ax, edges(end), 'k:', 'HandleVisibility', 'off');
    else
        plot(ax, [edges(1) edges(1)], [0 1.1], 'k:', 'HandleVisibility', 'off');
        plot(ax, [edges(end) edges(end)], [0 1.1], 'k:', 'HandleVisibility', 'off');
    end
else
    for i = 1:length(edges)
        if exist('xline', 'file')
            xline(ax, edges(i), 'k:', 'HandleVisibility', 'off');
        else
            plot(ax, [edges(i) edges(i)], [0 1.1], 'k:', 'HandleVisibility', 'off');
        end
    end
end

% Plot rectangular gate boxes explicitly?
% gate_profiles = DTgates(t, config.r, edges);
% Plot first few? Or sum?
% Plotting all might be messy. Let's just plot edges and maybe a sample profile
% transparent filling?
% Just edges is standard for many views.

title(ax, sprintf('IRF & %d Gates', config.N_gates));
xlabel(ax, 'Time (ns)');
grid(ax, 'on');
% Restore axis properties? Reset removes them.
box(ax, 'on');

end
