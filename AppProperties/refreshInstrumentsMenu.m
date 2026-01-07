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
mNew = uimenu(mInst);
mNew.Text = 'New...';
mNew.MenuSelectedFcn = @(s,e) InstrumentWizard();

mManage = uimenu(mInst);
mManage.Text = 'Manage...';
mManage.MenuSelectedFcn = @(s,e) InstrumentManager(fig);

mSep = uimenu(mInst);
mSep.Text = '---';
mSep.Enable = 'off';
mSep.Separator = 'on';

% --- Dynamic Items ---
fPath = fileparts(mfilename('fullpath'));
instFolder = fullfile(fPath, 'instruments');

if ~exist(instFolder, 'dir')
    mkdir(instFolder);
end

files = dir(fullfile(instFolder, '*.json'));
if isempty(files)
    mNone = uimenu(mInst);
    mNone.Text = '(No instruments found)';
    mNone.Enable = 'off';
else
    for k = 1:length(files)
        fname = files(k).name;
        fullP = fullfile(instFolder, fname);
        [~, name, ~] = fileparts(fname);

        mItem = uimenu(mInst);
        mItem.Text = name;
        mItem.MenuSelectedFcn = @(s,e) safeLoad(fig, fullP);
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
