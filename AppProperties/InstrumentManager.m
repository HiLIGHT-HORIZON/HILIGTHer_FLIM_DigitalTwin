function InstrumentManager(fig)
% INSTRUMENTMANAGER - GUI to create and manage instruments
% Stores instruments as JSON files in AppProperties/instruments

% === Layout ===
d = uifigure('Name', 'Instrument Manager', 'Position', [150 150 750 400], 'WindowStyle', 'modal', 'Resize', 'off');
g = uigridlayout(d, [2, 5]);
g.RowHeight = {'1x', 40};
g.ColumnWidth = {'1x', '1x', '1x', '1x', '1.5x'}; % Apply button slightly wider
g.Padding = [10 10 10 10];
g.ColumnSpacing = 8;

% List Box (Left)
lbInst = uilistbox(g);
lbInst.Layout.Column = [1 5];

% Buttons
uibutton(g, 'Text', 'New...', 'ButtonPushedFcn', @(btn,ev) createWizard(d));
uibutton(g, 'Text', 'View', 'ButtonPushedFcn', @(btn,ev) viewSelected(d, lbInst));
uibutton(g, 'Text', 'Rename', 'ButtonPushedFcn', @(btn,ev) renameSelected(d, lbInst));
uibutton(g, 'Text', 'Delete', 'ButtonPushedFcn', @(btn,ev) deleteSelected(d, lbInst), 'FontColor', [0.7 0 0]);
uibutton(g, 'Text', 'Apply Selected', 'BackgroundColor', [0.2 0.6 0.8], 'FontWeight', 'bold', 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(btn,ev) applySelected(d, lbInst));

refreshList(lbInst);

% --- Helpers ---
    function refreshList(lb)
        fPath = fileparts(mfilename('fullpath'));
        instFolder = fullfile(fPath, 'instruments');
        if ~exist(instFolder, 'dir'), mkdir(instFolder); end

        files = dir(fullfile(instFolder, '*.json'));
        items = {files.name};
        lb.Items = items;

        % Also refresh the Main Menu if Digital Twin is open
        dtFig = findall(0, 'Name', 'HILIGHT FLIM Digital Twin');
        if ~isempty(dtFig)
            refreshInstrumentsMenu(dtFig(1));
        end
    end

    function deleteSelected(d, lb)
        val = lb.Value;
        if isempty(val), return; end

        selection = uiconfirm(d, ['Delete ' val '?'], 'Confirm Delete', 'Icon', 'warning');
        if strcmp(selection, 'OK')
            instFolder = fullfile(fileparts(mfilename('fullpath')), 'instruments');
            delete(fullfile(instFolder, val));
            refreshList(lb);
        end
    end

    function viewSelected(d, lb)
        val = lb.Value;
        if isempty(val), return; end

        instFolder = fullfile(fileparts(mfilename('fullpath')), 'instruments');
        fpath = fullfile(instFolder, val);
        try
            txt = fileread(fpath);
            prettyTxt = jsonencode(jsondecode(txt), 'PrettyPrint', true); % Re-format nicely

            % View Dialog
            vd = uifigure('Name', ['View ' val], 'Position', [200 200 400 500], 'WindowStyle', 'modal', 'Resize', 'off');
            vg = uigridlayout(vd, [2, 1]);
            vg.RowHeight = {'1x', 40};

            uitextarea(vg, 'Value', cellstr(splitlines(prettyTxt)), 'Editable', 'off', 'FontName', 'Consolas');
            uibutton(vg, 'Text', 'Close', 'ButtonPushedFcn', @(btn,ev) close(vd));

        catch ME
            uialert(d, ['Error reading file: ' ME.message], 'Error');
        end
    end

    function renameSelected(d, lb)
        val = lb.Value;
        if isempty(val), return; end

        [~, oldName, ext] = fileparts(val);

        % Simple Input Dialog
        inputFig = uifigure('Name', 'Rename Instrument', 'Position', [d.Position(1)+100 d.Position(2)+100 300 150], ...
            'WindowStyle', 'modal', 'Resize', 'off');
        ig = uigridlayout(inputFig, [3, 2]);
        ig.RowHeight = {30, 30, 40};

        uilabel(ig, 'Text', 'New Name:', 'Layout.Column', [1 2]);
        nf = uieditfield(ig, 'text', 'Value', oldName, 'Layout.Column', [1 2]);

        uibutton(ig, 'Text', 'Cancel', 'ButtonPushedFcn', @(btn,ev) close(inputFig));
        uibutton(ig, 'Text', 'Rename', 'BackgroundColor', [0.2 0.6 0.8], 'FontColor', 'white', ...
            'ButtonPushedFcn', @(btn,ev) doRename(nf.Value));

        function doRename(newName)
            newName = strtrim(newName);
            % Sanitize (Alphanumeric, underscore, dash, dot, space)
            newNameClean = regexprep(newName, '[^a-zA-Z0-9_\-\. ]', '');
            if isempty(newNameClean)
                uialert(inputFig, 'Invalid name.', 'Error');
                return;
            end

            % Paths
            instFolder = fullfile(fileparts(mfilename('fullpath')), 'instruments');
            oldPath = fullfile(instFolder, val);
            newPath = fullfile(instFolder, [newNameClean ext]);

            if strcmpi(oldPath, newPath)
                close(inputFig); return;
            end

            if exist(newPath, 'file')
                uialert(inputFig, 'File already exists.', 'Error');
                return;
            end

            try
                % Update internal name in JSON
                txt = fileread(oldPath);
                data = jsondecode(txt);
                data.name = newNameClean;

                % Write New File
                fid = fopen(newPath, 'w');
                if fid == -1
                    error('Cannot create new file.');
                end
                cleanObj = onCleanup(@() fclose(fid)); % Ensure close
                fprintf(fid, '%s', jsonencode(data, 'PrettyPrint', true));
                clear cleanObj; % Force close

                % Delete Old File
                delete(oldPath);

                close(inputFig);
                refreshList(lb);
            catch ME
                uialert(inputFig, ['Rename failed: ' ME.message], 'Error');
            end
        end
    end

    function applySelected(d, lb)
        val = lb.Value;
        if isempty(val)
            uialert(d, 'Please select an instrument to apply.', 'No Selection');
            return;
        end

        instFolder = fullfile(fileparts(mfilename('fullpath')), 'instruments');
        fpath = fullfile(instFolder, val);
        try
            txt = fileread(fpath);
            data = jsondecode(txt);

            % Use shared helper
            applyInstrumentToDT(data);

            uialert(d, sprintf('Settings from "%s" applied successfully.', data.name), 'Success');

        catch ME
            uialert(d, ['Error applying instrument: ' ME.message], 'Error');
        end
    end

    function createWizard(parentFig)
        InstrumentWizard();
        refreshList(lbInst);
    end

end
