function menuProp = setupAppProperties(fig)
% setupAppProperties - Sets up the standard 'Properties' menu for HILIGHT applications
% and applies the last used theme.

% === Menu Bar ===
% Add App properties > Theme > Select / Customize
menuProp = findall(fig, 'Type', 'uimenu', 'Text', 'App properties');
if isempty(menuProp)
    menuProp = uimenu(fig, 'Text', 'App properties');
end

% Clear existing submenus to avoid duplicates
delete(findall(menuProp, 'Text', 'Theme'));
delete(findall(menuProp, 'Text', 'Instruments'));
delete(findall(menuProp, 'Text', 'Colormaps'));

% === Theme Menu ===
menuTheme = uimenu(menuProp, 'Text', 'Theme');
uimenu(menuTheme, 'Text', 'Select', 'Tag', 'menuSelectTheme');

% Actions
uimenu(menuTheme, 'Text', 'Save Current As...', 'Separator', 'on', ...
    'MenuSelectedFcn', @(src, ev) saveCurrentThemeAs(fig));

% Theme Manager
uimenu(menuTheme, 'Text', 'Theme manager', 'Separator', 'on', ...
    'MenuSelectedFcn', @(src, ev) ThemeManager(fig));

% Initial Populate
refreshThemesMenu(fig);

% === Instruments Menu ===
uimenu(menuProp, 'Text', 'Instruments', 'Separator', 'on', 'Tag', 'menuInstruments');

% Initial Populate (refreshInstrumentsMenu is in the same folder)
try
    refreshInstrumentsMenu(fig);
catch
end

% Initial Populate
try
    refreshInstrumentsMenu(fig);
catch
end


% --- Load Saved Theme ---
try
    fPath = fileparts(mfilename('fullpath'));
    settingsFile = fullfile(fPath, 'settings.mat');
    if exist(settingsFile, 'file')
        loaded = load(settingsFile);
        if isfield(loaded, 'lastTheme')
            applyAppTheme(fig, loaded.lastTheme);
        end
    end
catch
    % Ignore theme load errors
end
end

% --- Helpers ---

function saveCurrentThemeAs(fig)
[file, path] = uiputfile('*.css', 'Save Theme As', 'new_theme.css');
if isequal(file, 0), return; end

theme = struct();
theme.UIFigure.Color = rgb2hex(fig.Color);

p = findall(fig, 'Type', 'uipanel');
if ~isempty(p)
    theme.UIPanel.BackgroundColor = rgb2hex(p(1).BackgroundColor);
    theme.UIPanel.ForegroundColor = rgb2hex(p(1).ForegroundColor);
end

b = findall(fig, 'Type', 'uibutton');
if ~isempty(b)
    theme.UIButton.BackgroundColor = rgb2hex(b(1).BackgroundColor);
end

l = findall(fig, 'Type', 'uilabel');
if ~isempty(l)
    theme.UILabel.FontColor = rgb2hex(l(1).FontColor);
end

ax = findall(fig, 'Type', 'uiaxes');
if ~isempty(ax)
    theme.UIAxes.Color = rgb2hex(ax(1).Color);
    theme.UIAxes.XColor = rgb2hex(ax(1).XColor);
    theme.UIAxes.YColor = rgb2hex(ax(1).YColor);
end

if isfield(fig.UserData, 'Theme')
    theme.HILIGHTer = fig.UserData.Theme;
    fn = fieldnames(theme.HILIGHTer);
    for i=1:numel(fn)
        if contains(lower(fn{i}), 'color') && isnumeric(theme.HILIGHTer.(fn{i}))
            theme.HILIGHTer.(fn{i}) = rgb2hex(theme.HILIGHTer.(fn{i}));
        end
    end
end

fullPath = fullfile(path, file);
fid = fopen(fullPath, 'w', 'n', 'UTF-8');
fprintf(fid, '%s', jsonencode(theme, 'PrettyPrint', true));
fclose(fid);

refreshThemesMenu(fig);
end

function ThemeManager(parentFig)
fPath = fileparts(mfilename('fullpath'));
mgr = uifigure('Name', 'Theme Manager', 'Position', [200 200 600 500]);
g = uigridlayout(mgr, [2 2]);
g.ColumnWidth = {200, '1x'};
g.RowHeight = {'1x', 40};

lst = uilistbox(g);
lst.Layout.Row = 1; lst.Layout.Column = 1;

tGroup = uitabgroup(g);
tGroup.Layout.Row = 1; tGroup.Layout.Column = 2;
tabSource = uitab(tGroup, 'Title', 'JSON Source');
tabGUI = uitab(tGroup, 'Title', 'GUI Editor');

txtArea = uitextarea(tabSource, 'Position', [10 10 380 400], 'FontName', 'monospaced');

refreshList = @() set(lst, 'Items', {dir(fullfile(fPath, '*.css')).name});
refreshList();

lst.ValueChangedFcn = @(src, ev) loadSelected(src.Value);

bBox = uipanel(g, 'BorderType', 'none');
bBox.Layout.Row = 2; bBox.Layout.Column = [1 2];
bg = uigridlayout(bBox, [1 5]);
uibutton(bg, 'Text', 'Refresh', 'ButtonPushedFcn', @(s,e) refreshList());
uibutton(bg, 'Text', 'Copy', 'ButtonPushedFcn', @(s,e) copyTheme());
uibutton(bg, 'Text', 'Rename', 'ButtonPushedFcn', @(s,e) renameTheme());
uibutton(bg, 'Text', 'Delete', 'ButtonPushedFcn', @(s,e) deleteTheme());
uibutton(bg, 'Text', 'Apply', 'ButtonPushedFcn', @(s,e) applyThis());

currentThemeData = struct();

    function loadSelected(fname)
        path = fullfile(fPath, fname);
        content = fileread(path);
        txtArea.Value = content;
        currentThemeData = jsondecode(content);
        buildGUIEditor(tabGUI, currentThemeData);
    end

    function buildGUIEditor(parent, data)
        delete(parent.Children);

        % Calculate total rows: sections + each property
        numRows = numel(fieldnames(data));
        secs = fieldnames(data);
        for i=1:numel(secs), numRows = numRows + numel(fieldnames(data.(secs{i}))); end

        gl = uigridlayout(parent, [max(1, numRows) 2]);
        gl.Scrollable = 'on';
        gl.ColumnWidth = {120, '1x'};
        gl.RowHeight = repmat({30}, 1, max(1, numRows));

        row = 1;
        sections = fieldnames(data);
        for i = 1:numel(sections)
            sec = sections{i};
            sectionLabel = uilabel(gl, 'Text', sec, 'FontWeight', 'bold');
            sectionLabel.Layout.Row = row;
            sectionLabel.Layout.Column = [1 2];
            row = row + 1;

            props = fieldnames(data.(sec));
            for j = 1:numel(props)
                pName = props{j};
                val = data.(sec).(pName);
                uilabel(gl, 'Text', ['  ' pName]).Layout.Row = row;
                if contains(lower(pName), 'color')
                    b = uibutton(gl, 'Text', val, 'BackgroundColor', hex2rgb2(val));
                    b.Layout.Row = row; b.Layout.Column = 2;
                    b.ButtonPushedFcn = @(s,e) pickColor(sec, pName, s);
                else
                    e = uieditfield(gl, 'Value', string(val));
                    e.Layout.Row = row; e.Layout.Column = 2;
                    e.ValueChangedFcn = @(s,e) updateProp(sec, pName, s.Value);
                end
                row = row + 1;
            end
        end
    end

    function pickColor(sec, prop, btn)
        c = uisetcolor(btn.BackgroundColor);
        if length(c) == 3
            hex = rgb2hex(c);
            btn.Text = hex;
            btn.BackgroundColor = c;
            updateProp(sec, prop, hex);
        end
    end

    function updateProp(sec, prop, val)
        currentThemeData.(sec).(prop) = val;
        txtArea.Value = jsonencode(currentThemeData, 'PrettyPrint', true);
        saveSource();
    end

    function saveSource()
        if isempty(lst.Value), return; end
        path = fullfile(fPath, lst.Value);
        fid = fopen(path, 'w', 'n', 'UTF-8');
        fprintf(fid, '%s', txtArea.Value);
        fclose(fid);
    end

    function applyThis()
        if isempty(lst.Value), return; end
        applyAppTheme(parentFig, lst.Value);
    end

    function copyTheme()
        if isempty(lst.Value), return; end
        name = inputdlg('New name:', 'Copy Theme', [1 50], {['copy_of_' lst.Value]});
        if ~isempty(name)
            copyfile(fullfile(fPath, lst.Value), fullfile(fPath, name{1}));
            refreshList();
        end
    end

    function renameTheme()
        if isempty(lst.Value), return; end
        if strcmp(lst.Value, 'default.css') || strcmp(lst.Value, 'dark.css'), return; end
        name = inputdlg('New name:', 'Rename Theme', [1 50], {lst.Value});
        if ~isempty(name)
            movefile(fullfile(fPath, lst.Value), fullfile(fPath, name{1}));
            refreshList();
        end
    end

    function deleteTheme()
        if isempty(lst.Value), return; end
        if strcmp(lst.Value, 'default.css') || strcmp(lst.Value, 'dark.css'), return; end
        delete(fullfile(fPath, lst.Value));
        refreshList();
    end
end

function hex = rgb2hex(rgb)
if ischar(rgb), hex = rgb; return; end
hex = sprintf('#%02X%02X%02X', round(rgb(1)*255), round(rgb(2)*255), round(rgb(3)*255));
end

function rgb = hex2rgb2(hexStr)
if startsWith(hexStr, '#'), hexStr = hexStr(2:end); end
if length(hexStr) == 6
    rgb = [hex2dec(hexStr(1:2)) hex2dec(hexStr(3:4)) hex2dec(hexStr(5:6))] / 255;
else
    rgb = [0.5 0.5 0.5];
end
end

function createNewInstrument(fig)
InstrumentWizard();
end

function manageInstruments(fig)
InstrumentManager(fig);
end

function loadInstrument(fig, filePath)
try
    txt = fileread(filePath);
    instData = jsondecode(txt);
    applyInstrumentToDT(instData);
catch ME
    uialert(fig, ['Error loading instrument: ' ME.message], 'Error');
end
end
