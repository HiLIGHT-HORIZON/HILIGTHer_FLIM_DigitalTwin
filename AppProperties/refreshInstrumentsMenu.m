function refreshInstrumentsMenu(fig)
% REFRESHINSTRUMENTSMENU - Rebuilds the Instruments menu in the main figure
% Assumes the menu has Tag 'menuInstruments'

mInst = findobj(fig, 'Type', 'uimenu', 'Tag', 'menuInstruments');
if isempty(mInst)
    return;
end

% Clear existing items
delete(mInst.Children);

% --- Static Items ---
uimenu(mInst, 'Text', 'New...', 'MenuSelectedFcn', @(s,e) InstrumentWizard());
uimenu(mInst, 'Text', 'Manage...', 'MenuSelectedFcn', @(s,e) InstrumentManager(fig));
uimenu(mInst, 'Text', '---', 'Enable', 'off', 'Separator', 'on');

% --- Dynamic Items ---
fPath = fileparts(mfilename('fullpath'));
instFolder = fullfile(fPath, 'instruments');

if ~exist(instFolder, 'dir')
    mkdir(instFolder);
end

files = dir(fullfile(instFolder, '*.json'));
if isempty(files)
    uimenu(mInst, 'Text', '(No instruments found)', 'Enable', 'off');
else
    for k = 1:length(files)
        fname = files(k).name;
        fullP = fullfile(instFolder, fname);
        [~, name, ~] = fileparts(fname);

        % Callback to load
        uimenu(mInst, 'Text', name, 'MenuSelectedFcn', @(s,e) safeLoad(fig, fullP));
    end
end

    function safeLoad(f, p)
        try
            txt = fileread(p);
            data = jsondecode(txt);
            applyInstrumentToDT(data);
        catch ME
            uialert(f, ['Error loading instrument: ' ME.message], 'Error');
        end
    end
end
