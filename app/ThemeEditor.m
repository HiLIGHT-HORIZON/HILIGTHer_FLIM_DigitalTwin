function ThemeEditor()
% THEMEEDITOR Simple editor for HILIGHTer CSS theme files across

% Create UI
hFig = uifigure('Name', 'Theme Editor', 'Position', [100 100 500 600]);

% Layout
g = uigridlayout(hFig, [3, 2]);
g.RowHeight = {40, '1x', 40};
g.ColumnWidth = {'1x', '1x'};

% Toolbar / File selection
lblFile = uilabel(g, 'Text', 'Select Theme File:');
ddFile = uidropdown(g, 'Items', {'custom.css', 'default.css', 'dark.css'}, ...
    'ValueChangedFcn', @(src,e) loadFile(src.Value));

% Text Area
txtEditor = uitextarea(g, 'FontName', 'Consolas');
txtEditor.Layout.Row = 2;
txtEditor.Layout.Column = [1 2];

% Buttons
btnSave = uibutton(g, 'Text', 'Save', ...
    'ButtonPushedFcn', @(src,e) saveFile());

btnClose = uibutton(g, 'Text', 'Close', ...
    'ButtonPushedFcn', @(src,e) close(hFig));

% App Properties Path
fPath = fileparts(mfilename('fullpath'));
propPath = fullfile(fPath, 'AppProperties');

% Initial Load
loadFile('custom.css');

% --- Functions ---

    function loadFile(fname)
        fullP = fullfile(propPath, fname);
        if exist(fullP, 'file')
            txt = fileread(fullP);
            txtEditor.Value = strsplit(txt, '\n');
            if strcmp(fname, 'default.css') || strcmp(fname, 'dark.css')
                txtEditor.Editable = 'off'; % Protect default/dark? Or allow edit? User said Custom is custom.
                % Let's allow viewing source for copy-paste but warn on save?
                % For now, just load.
            else
                txtEditor.Editable = 'on';
            end
        else
            txtEditor.Value = {'File not found.'};
        end
    end

    function saveFile()
        fname = ddFile.Value;
        if strcmp(fname, 'default.css') || strcmp(fname, 'dark.css')
            uialert(hFig, 'You should modify custom.css instead of overwriting core themes.', 'Warning');
            % Allow overwrite if they insist? Logic: User requested custom.css be the custom one.
            % Let's restrict saving default/dark to prevent accidents.
            return;
        end

        fullP = fullfile(propPath, fname);
        try
            fid = fopen(fullP, 'w');
            if fid == -1
                error('Cannot open file for writing.');
            end
            % Join lines
            str = strjoin(txtEditor.Value, '\n');
            fprintf(fid, '%s', str);
            fclose(fid);
            uialert(hFig, 'Theme saved successfully.', 'Success');
        catch ME
            uialert(hFig, ['Error saving file: ' ME.message], 'Error');
        end
    end

end
