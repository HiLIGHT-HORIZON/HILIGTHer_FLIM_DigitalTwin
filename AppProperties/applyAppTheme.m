function applyAppTheme(fig, themeFile)
% APPLYAPPTHEME Read a JSON-like .css file and apply properties to UI components
% This is a shared utility for HILIGHT applications.

try
    % Locate AppProperties folder relative to this script
    fPath = fileparts(mfilename('fullpath'));
    propFile = fullfile(fPath, themeFile);

    if ~exist(propFile, 'file')
        % Try absolute path if not found in folder
        if ~exist(themeFile, 'file')
            uialert(fig, sprintf('Theme file not found: %s', propFile), 'Theme Error');
            return;
        else
            propFile = themeFile;
        end
    end

    % Read and Parse JSON
    txt = fileread(propFile);
    theme = jsondecode(txt);

    % Apply to specific types
    if isfield(theme, 'UIPanel'), applyProps(fig, 'uipanel', theme.UIPanel); end
    if isfield(theme, 'UIButton'), applyProps(fig, 'uibutton', theme.UIButton); end
    if isfield(theme, 'UILabel'), applyProps(fig, 'uilabel', theme.UILabel); end
    if isfield(theme, 'UISpinner'), applyProps(fig, 'uispinner', theme.UISpinner); end
    if isfield(theme, 'UICheckbox'), applyProps(fig, 'uicheckbox', theme.UICheckbox); end
    if isfield(theme, 'UIDropDown'), applyProps(fig, 'uidropdown', theme.UIDropDown); end
    if isfield(theme, 'UIEditField'), applyProps(fig, 'uieditfield', theme.UIEditField); end

    if isfield(theme, 'UIFigure')
        props = theme.UIFigure;
        fNames = fieldnames(props);
        for i=1:numel(fNames)
            prop = fNames{i}; val=props.(prop);
            if contains(lower(prop), 'color') && ischar(val), val=hex2rgb(val); end
            try fig.(prop)=val; catch; end
        end
    end

    % Axes
    if isfield(theme, 'UIAxes')
        axProps = theme.UIAxes;
        axs = findall(fig, 'Type', 'uiaxes');
        fNames = fieldnames(axProps);
        for k = 1:numel(axs)
            ax = axs(k);
            for j = 1:numel(fNames)
                prop = fNames{j}; val = axProps.(prop);
                if contains(lower(prop), 'color') && ischar(val), val=hex2rgb(val); end
                try ax.(prop) = val; catch; end
            end
        end
    end

    drawnow;

    % Save Preference
    try
        settingsFile = fullfile(fPath, 'settings.mat');
        lastTheme = themeFile;
        save(settingsFile, 'lastTheme');
    catch
    end

catch ME
    uialert(fig, ['Error applying theme: ' ME.message], 'Theme Error');
end
end

% --- Helper Functions for Theme ---

function rgb = hex2rgb(hexStr)
% Convert hex string "#RRGGBB" to [r g b]
if startsWith(hexStr, '#')
    hexStr = hexStr(2:end);
end
if length(hexStr) == 6
    r = hex2dec(hexStr(1:2)) / 255;
    g = hex2dec(hexStr(3:4)) / 255;
    b = hex2dec(hexStr(5:6)) / 255;
    rgb = [r g b];
else
    rgb = [0 0 0]; % Fallback
end
end

function applyProps(fig, type, propStruct)
% Helper to apply props to all findall(type)
objs = findall(fig, 'Type', type);
fNames = fieldnames(propStruct);
for k = 1:numel(objs)
    obj = objs(k);
    for j = 1:numel(fNames)
        prop = fNames{j};
        val = propStruct.(prop);

        % Convert Hex Color
        if contains(lower(prop), 'color') && ischar(val)
            val = hex2rgb(val);
        end

        try obj.(prop) = val; catch; end
    end
end
end
