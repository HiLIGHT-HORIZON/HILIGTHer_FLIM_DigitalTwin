function setupAppProperties(fig)
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

% === Theme Menu ===
menuTheme = uimenu(menuProp, 'Text', 'Theme');
menuSelect = uimenu(menuTheme, 'Text', 'Select');

% Theme Options
uimenu(menuSelect, 'Text', 'Default', 'MenuSelectedFcn', @(src, ev) applyAppTheme(fig, 'default.css'));
uimenu(menuSelect, 'Text', 'Dark', 'MenuSelectedFcn', @(src, ev) applyAppTheme(fig, 'dark.css'));
uimenu(menuSelect, 'Text', 'Custom', 'MenuSelectedFcn', @(src, ev) applyAppTheme(fig, 'custom.css'));

% Customize
uimenu(menuTheme, 'Text', 'Customise...', 'Separator', 'on', ...
    'MenuSelectedFcn', @(src, ev) ThemeEditor());

% === Instruments Menu ===
menuInst = uimenu(menuProp, 'Text', 'Instruments', 'Separator', 'on', 'Tag', 'menuInstruments');

% Initial Populate
refreshInstrumentsMenu(fig);


% --- Load Saved Theme ---
try
    fPath = fileparts(mfilename('fullpath'));
    % The settings file is expected to be in the same folder as this script
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

% --- Instrument Helpers ---


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
