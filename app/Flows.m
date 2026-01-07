function Flows()
% FLOWS - A visually stunning graphical user interface to guide non-experts in data analysis.
% Part of the HILIGHTer suite.

% Add AppProperties to path to ensure shared utilities are available
rootPath = fileparts(mfilename('fullpath'));
addpath(fullfile(rootPath, 'AppProperties'));

% --- Create Figure ---
fig = uifigure('Name', 'HILIGHTer | Flows', ...
    'Position', [100 100 450 1000], ... % Taller window (1000px)
    'Color', [0.12 0.12 0.14], ... % Sleek dark background
    'Tag', 'FlowsGUI');

% Apply standard HILIGHTer properties and theme
setupAppProperties(fig);
applyAppTheme(fig, 'dark.css'); % Force dark theme for premium feel

% --- Main Layout ---
gl = uigridlayout(fig, [4 1]);
gl.ColumnWidth = {'1x'};
gl.RowHeight = {'1x', '1.5x', 80, 70}; % Conditions, Files, Pre-Process, Run
gl.Padding = [15 15 15 15];
gl.RowSpacing = 15;

% --- Panel 1: Experimental Conditions (Top) ---
condPanel = uipanel(gl, 'Title', 'EXPERIMENTAL CONDITIONS', 'FontWeight', 'bold', 'FontSize', 15, ...
    'BackgroundColor', [0.18 0.18 0.20], 'ForegroundColor', [0.9 0.9 0.9]);
condPanel.Layout.Row = 1; condPanel.Layout.Column = 1;

cpOuter = uigridlayout(condPanel, [2 1]);
cpOuter.RowHeight = {50, '1x', 60}; % Taller top/bottom toolbars for larger icons

% Create Condition Toolbar (Top)
createBox = uigridlayout(cpOuter, [1 2]);
createBox.Layout.Row = 1; createBox.ColumnSpacing = 5; createBox.Padding = [0 0 0 5];

uibutton(createBox, 'Text', 'New from Files 📄', 'BackgroundColor', [0.2 0.35 0.5], 'FontColor', [1 1 1], 'FontWeight', 'bold', 'FontSize', 14, ...
    'ButtonPushedFcn', @(s,e) createConditionFromFiles(), 'Tooltip', 'Create a new Experimental Condition group by selecting files.');
uibutton(createBox, 'Text', 'New from Folder 📁', 'BackgroundColor', [0.2 0.35 0.5], 'FontColor', [1 1 1], 'FontWeight', 'bold', 'FontSize', 14, ...
    'ButtonPushedFcn', @(s,e) createConditionFromFolder(), 'Tooltip', 'Create a new Experimental Condition group by importing a folder.');

% Condition List
condListBox = uilistbox(cpOuter, 'Tag', 'condListBox', 'BackgroundColor', [0.12 0.12 0.14], ...
    'FontColor', [0.9 0.9 0.9], 'Items', {}, 'Tooltip', 'List of defined experimental conditions (Groups)');
condListBox.Layout.Row = 2;
condListBox.ValueChangedFcn = @(s,e) updateFileDisplay();

% Condition Management Toolbar (Bottom)
toolBox = uigridlayout(cpOuter, [1 5]);
toolBox.Layout.Row = 3;
toolBox.ColumnSpacing = 2; toolBox.Padding = [0 5 0 0];

uibutton(toolBox, 'Text', '✎', 'FontSize', 32, 'ButtonPushedFcn', @(s,e) renameCondition(), ...
    'Tooltip', 'Rename: Change the name of the selected condition group.');
uibutton(toolBox, 'Text', '±', 'FontSize', 32, 'ButtonPushedFcn', @(s,e) flagCondition(), ...
    'Tooltip', 'Set Type: Cycle this condition between Experimental, Positive Control, and Negative Control.');
uibutton(toolBox, 'Text', '🗑', 'FontSize', 32, 'FontColor', [0.8 0.3 0.3], 'ButtonPushedFcn', @(s,e) deleteCondition(), ...
    'Tooltip', 'Delete: Permanently remove the selected condition group.');
uibutton(toolBox, 'Text', '🔗', 'FontSize', 32, 'ButtonPushedFcn', @(s,e) mergeConditions(), ...
    'Tooltip', 'Merge: Combine two or more selected conditions into a single group.');
uibutton(toolBox, 'Text', '❐', 'FontSize', 32, 'ButtonPushedFcn', @(s,e) duplicateCondition(), ...
    'Tooltip', 'Duplicate: Create a copy of the selected condition group.');


% --- Panel 2: Associated File Stream (Bottom) ---
filePanel = uipanel(gl, 'Title', 'ASSOCIATED FILE STREAM', 'FontWeight', 'bold', 'FontSize', 15, ...
    'BackgroundColor', [0.18 0.18 0.20], 'ForegroundColor', [0.9 0.9 0.9]);
filePanel.Layout.Row = 2; filePanel.Layout.Column = 1;

fpGrid = uigridlayout(filePanel, [2 1]);
fpGrid.RowHeight = {'1x', 60}; % Taller bottom toolbar

fileListBox = uilistbox(fpGrid, 'Multiselect', 'on', 'Tag', 'fileListBox', ...
    'BackgroundColor', [0.12 0.12 0.14], 'FontColor', [0.9 0.9 0.9], 'Items', {}, ...
    'Tooltip', 'Files associated with the currently selected condition');
fileListBox.Layout.Row = 1;

% File Management Toolbar
fToolBox = uigridlayout(fpGrid, [1 4]); % Horizontal strip
fToolBox.Layout.Row = 2;
fToolBox.ColumnWidth = {'1x', 60, 60, 60}; % Wider buttons for larger icons
fToolBox.Padding = [0 5 0 0]; fToolBox.ColumnSpacing = 5;

% Move generic "Add" buttons here as requested (consolidated)
uibutton(fToolBox, 'Text', 'Add Content Here...', 'FontSize', 14, 'ButtonPushedFcn', @(s,e) importFilesToCondition(), ...
    'Tooltip', 'Add more files or content directly to the selected condition.', 'BackgroundColor', [0.25 0.25 0.28], 'FontColor', [1 1 1]);

uibutton(fToolBox, 'Text', '🗑', 'FontSize', 32, 'FontColor', [0.8 0.3 0.3], 'ButtonPushedFcn', @(s,e) removeSelectedFiles(), ...
    'Tooltip', 'Remove Files: Delete selected file(s) from this condition list.');

uibutton(fToolBox, 'Text', '➡', 'FontSize', 32, 'ButtonPushedFcn', @(s,e) moveFilesToCondition(), ...
    'Tooltip', 'Move: Move selected files to a different condition group.');


% --- Panel 3: Pre-Processing (New) ---
prePanel = uipanel(gl, 'Title', 'DATA PRE-PROCESSING', 'FontWeight', 'bold', 'FontSize', 15, ...
    'BackgroundColor', [0.18 0.18 0.20], 'ForegroundColor', [0.9 0.9 0.9]);
prePanel.Layout.Row = 3; prePanel.Layout.Column = 1;

ppGrid = uigridlayout(prePanel, [1 3]);
ppGrid.ColumnWidth = {80, 150, 150};
ppGrid.Padding = [10 10 10 10];

uilabel(ppGrid, 'Text', 'Method:', 'FontColor', [0.9 0.9 0.9], 'FontWeight', 'bold');
binTypeDrop = uidropdown(ppGrid, 'Items', {'None', 'Simple Binning', 'Gaussian Filter'}, ...
    'Value', 'None', 'BackgroundColor', [0.25 0.25 0.25], 'FontColor', 'white');

binSpinner = uispinner(ppGrid, 'Limits', [0 0], 'Value', 0, 'Enable', 'off', ...
    'Tooltip', 'Parameter (Bin Size or Sigma)');

% Callback to update spinner based on Type
binTypeDrop.ValueChangedFcn = @(s,e) onBinTypeChange(binSpinner, s.Value);

% --- Run Analysis Button (Footer) ---
runBtn = uibutton(gl, 'Text', 'RUN ANALYSIS 🚀', 'FontSize', 20, 'FontWeight', 'bold', ...
    'BackgroundColor', [0.2 0.6 0.3], 'FontColor', [1 1 1], ...
    'ButtonPushedFcn', @(s,e) runFullAnalysis(), 'Tooltip', 'Proceed to the Analysis Step');
runBtn.Layout.Row = 4;

% --- App State ---
appData = struct();
appData.Conditions = {}; % Array of structs: {Name, Type, Files}
appData.binSpinner = binSpinner; % Store handle
appData.binTypeDrop = binTypeDrop;
fig.UserData = appData;

% --- Callback Functions ---

    function createConditionFromFiles()
        [files, path] = uigetfile({'*.sdt;*.SDT', 'Becker & Hickl Files (*.sdt)'}, 'Select Files for Condition', 'MultiSelect', 'on');
        if isequal(files, 0), return; end
        if ischar(files), files = {files}; end
        fullPaths = cellfun(@(f) fullfile(path, f), files, 'UniformOutput', false);

        % Create Buffer -> Then Create Condition
        promptConditionName(fullPaths);
    end

    function createConditionFromFolder()
        folder = uigetdir(pwd, 'Select Folder for Condition');
        if isequal(folder, 0), return; end

        allFiles = {};
        d = dir(fullfile(folder, '**', '*.*'));
        d = d(~[d.isdir]);
        paths = arrayfun(@(x) fullfile(x.folder, x.name), d, 'UniformOutput', false);
        allFiles = [allFiles; paths(:)];

        if isempty(allFiles), return; end
        promptConditionName(allFiles);
    end

    function promptConditionName(newFiles)
        data = fig.UserData;
        newName = char(inputdlg('Enter Name for New Condition:', 'Create Condition', [1 50], {['Group_' datestr(now, 'HHMMSS')]}));
        if isempty(newName), return; end

        newCond = struct('Name', newName, 'Type', 'Experimental', 'Files', {newFiles(:)});
        data.Conditions{end+1} = newCond;
        fig.UserData = data;
        refreshCondList();

        % Auto-Select the new condition
        condListBox.Value = condListBox.Items{end};
        updateFileDisplay();
    end

    function refreshCondList()
        data = fig.UserData;
        items = {};
        for i = 1:numel(data.Conditions)
            prefix = "";
            if strcmp(data.Conditions{i}.Type, 'Positive Control'), prefix = "✓ [P] ";
            elseif strcmp(data.Conditions{i}.Type, 'Negative Control'), prefix = "✗ [N] ";
            else, prefix = "○ [E] ";
            end
            items{end+1} = sprintf('%s%s (%d)', prefix, data.Conditions{i}.Name, numel(data.Conditions{i}.Files));
        end
        condListBox.Items = items;
    end

    function idx = getSelectedCondIndex()
        val = condListBox.Value;
        if isempty(val), idx = []; return; end
        idx = find(strcmp(condListBox.Items, val));
    end

    function updateFileDisplay()
        idx = getSelectedCondIndex();
        if isempty(idx)
            fileListBox.Items = {};
            return;
        end
        data = fig.UserData;
        files = data.Conditions{idx}.Files;
        dispFiles = {};
        for i = 1:numel(files)
            [p, n, e] = fileparts(files{i});
            [~, parent] = fileparts(p);
            dispFiles{end+1} = sprintf('[%s] %s%s', parent, n, e);
        end
        fileListBox.Items = dispFiles;
        fileListBox.UserData = files;
    end

% --- Toolbar Logic ---
    function renameCondition()
        idx = getSelectedCondIndex(); if isempty(idx), return; end
        data = fig.UserData;
        answer = inputdlg('Rename Condition:', 'Manage', [1 50], {data.Conditions{idx}.Name});
        if ~isempty(answer)
            data.Conditions{idx}.Name = char(answer);
            fig.UserData = data; refreshCondList();
        end
    end

    function flagCondition()
        idx = getSelectedCondIndex(); if isempty(idx), return; end
        data = fig.UserData;
        types = {'Experimental', 'Positive Control', 'Negative Control'};
        % Handle cases where type might be 'Experimental Condition' vs just 'Experimental'
        currType = data.Conditions{idx}.Type;
        if contains(currType, 'Experimental'), currType = 'Experimental'; end

        cIdx = find(strcmp(types, currType));
        if isempty(cIdx), cIdx = 1; end % Default to Experimental if unknown

        data.Conditions{idx}.Type = types{mod(cIdx, 3)+1};
        fig.UserData = data; refreshCondList();
    end

    function deleteCondition()
        idx = getSelectedCondIndex(); if isempty(idx), return; end
        data = fig.UserData; data.Conditions(idx) = [];
        fig.UserData = data; refreshCondList(); updateFileDisplay();
    end

    function mergeConditions()
        if numel(condListBox.Items) < 2, return; end
        [sel, ok] = listdlg('ListString', condListBox.Items, 'PromptString', 'Select to merge:', 'Name', 'Merge');
        if ~ok || numel(sel) < 2, return; end
        data = fig.UserData;
        for i = 2:numel(sel)
            data.Conditions{sel(1)}.Files = unique([data.Conditions{sel(1)}.Files; data.Conditions{sel(i)}.Files]);
        end
        data.Conditions(sel(2:end)) = [];
        fig.UserData = data; refreshCondList(); updateFileDisplay();
    end

    function duplicateCondition()
        idx = getSelectedCondIndex(); if isempty(idx), return; end
        data = fig.UserData; newC = data.Conditions{idx};
        newC.Name = [newC.Name '_Copy'];
        data.Conditions{end+1} = newC;
        fig.UserData = data; refreshCondList();
    end

    function removeSelectedFiles()
        cIdx = getSelectedCondIndex(); if isempty(cIdx), return; end
        sel = fileListBox.Value; if isempty(sel), return; end
        if ischar(sel), sel = {sel}; end
        data = fig.UserData; uPaths = fileListBox.UserData;
        pathsToRemove = {};
        for i = 1:numel(sel)
            m = find(strcmp(fileListBox.Items, sel{i}));
            pathsToRemove = [pathsToRemove; uPaths(m)];
        end
        data.Conditions{cIdx}.Files = setdiff(data.Conditions{cIdx}.Files, pathsToRemove);
        fig.UserData = data; updateFileDisplay(); refreshCondList();
    end

    function importFilesToCondition()
        cIdx = getSelectedCondIndex(); if isempty(cIdx), return; end
        [f, p] = uigetfile({'*.sdt;*.SDT', 'Becker & Hickl Files (*.sdt)'}, 'Import', 'MultiSelect', 'on');
        if isequal(f,0), return; end
        if ischar(f), f = {f}; end
        data = fig.UserData;
        data.Conditions{cIdx}.Files = unique([data.Conditions{cIdx}.Files; fullfile(p, f(:))]);
        fig.UserData = data; updateFileDisplay(); refreshCondList();
    end

    function moveFilesToCondition()
        cIdx = getSelectedCondIndex(); if isempty(cIdx), return; end
        sel = fileListBox.Value; if isempty(sel), return; end
        data = fig.UserData;
        names = cellfun(@(c) c.Name, data.Conditions, 'UniformOutput', false);
        [dIdx, ok] = listdlg('ListString', names, 'SelectionMode', 'single', 'PromptString', 'Move to:');
        if ~ok || isequal(dIdx, cIdx), return; end
        uPaths = fileListBox.UserData;
        pathsToMove = {};
        if ischar(sel), sel = {sel}; end
        for i = 1:numel(sel)
            m = find(strcmp(fileListBox.Items, sel{i}));
            pathsToMove = [pathsToMove; uPaths(m)];
        end
        data.Conditions{cIdx}.Files = setdiff(data.Conditions{cIdx}.Files, pathsToMove);
        data.Conditions{dIdx}.Files = unique([data.Conditions{dIdx}.Files; pathsToMove(:)]);
        fig.UserData = data; updateFileDisplay(); refreshCondList();
    end

% --- Analysis Logic ---
    function runFullAnalysis()
        % 1. Validation
        data = fig.UserData;
        if isempty(data.Conditions)
            uialert(fig, 'No conditions defined!', 'Cannot Run');
            return;
        end

        % Check if Analysis Data Exists
        dataLoaded = false;
        if isfield(data.Conditions{1}, 'Analysis') && ~isempty(data.Conditions{1}.Analysis)
            dataLoaded = true;
        end

        if dataLoaded
            ans = uiconfirm(fig, 'Data is already loaded. Do you want to reload files from disk?', 'Run Analysis', ...
                'Options', {'Yes (Reload)', 'No (Open GUI)'}, 'DefaultOption', 'No (Open GUI)', 'Icon', 'question');

            if strcmp(ans, 'No (Open GUI)')
                % Just Open
                FlowsAnalysis(data);
                return;
            end
            % Else proceed to reload
        end

        % Capture Pre-Processing Settings
        binVal = 0;
        binType = 'None';
        if isfield(data, 'binSpinner') && isvalid(data.binSpinner)
            binVal = data.binSpinner.Value;
        end
        if isfield(data, 'binTypeDrop') && isvalid(data.binTypeDrop)
            binType = data.binTypeDrop.Value;
        end
        data.config.spatialBinning = binVal;
        data.config.binType = binType;

        % 2. Count Total Files for Progress Bar
        totalFiles = 0;
        for i = 1:numel(data.Conditions)
            totalFiles = totalFiles + numel(data.Conditions{i}.Files);
        end

        if totalFiles == 0
            uialert(fig, 'No files found in any condition!', 'Cannot Run');
            return;
        end

        % 3. Initialize Progress & Processing
        prog = uiprogressdlg(fig, 'Title', 'Ingesting Data', ...
            'Message', 'Allocating Memory...', 'Cancelable', true);

        try
            fileCount = 0;

            % Get Total Memory once (approximate)
            try
                [userMem, sysMem] = memory;
                totalRam = sysMem.PhysicalMemory.Total;
            catch
                totalRam = 16e9; % Assume 16GB if query fails
            end

            % Loop Conditions
            for i = 1:numel(data.Conditions)
                files = data.Conditions{i}.Files;
                data.Conditions{i}.Analysis = struct(); % Init Analysis Storage

                for f = 1:numel(files)
                    try
                        % Check Cancel
                        if prog.CancelRequested
                            error('UserCancelled');
                        end

                        fileCount = fileCount + 1;
                        [~, name, ~] = fileparts(files{f});

                        % --- MEMORY CHECK ---
                        try
                            [~, sys] = memory;
                            avail = sys.PhysicalMemory.Available;
                            if avail < 1.5e9
                                error('LowMemory:Stopping', 'Available Memory Critical (<1.5GB). Analysis stopped to prevent crash.');
                            end
                            memPercent = 100 * (1 - (avail / totalRam));
                        catch ME
                            if strcmp(ME.identifier, 'LowMemory:Stopping'), rethrow(ME); end
                            memPercent = 0;
                        end

                        prog.Message = sprintf('Loading %s\nMemory Usage: %.1f%%', name, memPercent);
                        prog.Value = fileCount / totalFiles;

                        % Load
                        [sdt, cfg] = read_SDT(files{f});

                        % Store Config
                        data.Conditions{i}.Analysis(f).Config = cfg;

                        % --- APPLY PRE-PROCESSING ---
                        if ~strcmp(data.config.binType, 'None') && data.config.spatialBinning > 0
                            param = data.config.spatialBinning;
                            [nY, nX, nT, nC] = size(sdt);

                            if strcmp(data.config.binType, 'Simple Binning')
                                scale = 1/param;
                                tmp = imresize(sdt(:,:,1,1), scale, 'box');
                                [newY, newX] = size(tmp);
                                newSDT = zeros(newY, newX, nT, nC, 'like', sdt);

                                for c = 1:nC
                                    for t = 1:nT
                                        newSDT(:,:,t,c) = imresize(sdt(:,:,t,c), scale, 'box') * (param^2);
                                    end
                                end
                                sdt = newSDT;

                            elseif strcmp(data.config.binType, 'Gaussian Filter')
                                for c = 1:nC
                                    for t = 1:nT
                                        sdt(:,:,t,c) = imgaussfilt(sdt(:,:,t,c), param);
                                    end
                                end
                            end
                        end

                        data.Conditions{i}.Analysis(f).Data = sdt;

                        % Create Preview Image (Sum over Time & Channels)
                        img = sum(sdt, [3 4]);
                        data.Conditions{i}.Analysis(f).IntensityImage = img;

                    catch readErr
                        warning('Failed to load file %s: %s', name, readErr.message);
                        data.Conditions{i}.Analysis(f).Data = [];
                        data.Conditions{i}.Analysis(f).IntensityImage = zeros(50,50); % dummy
                    end
                end
            end

            % 4. Launch New GUI
            fig.UserData = data; % Update store
            close(prog);

            % LAUNCH ANALYSIS
            FlowsAnalysis(data);

        catch ME
            close(prog);
            if strcmp(ME.message, 'UserCancelled')
                return;
            else
                uialert(fig, sprintf('Analysis Failed:\n%s', ME.message), 'Error');
            end
        end
    end

    function onBinTypeChange(spinner, type)
        switch type
            case 'Simple Binning'
                spinner.Limits = [1 10];
                spinner.Value = 1;
                spinner.Enable = 'on';
                spinner.Tooltip = 'Binning Factor (1=No change, 2=2x2, etc.)';
            case 'Gaussian Filter'
                spinner.Limits = [0.1 10];
                spinner.Value = 1.0;
                spinner.Step = 0.1;
                spinner.Enable = 'on';
                spinner.Tooltip = 'Gaussian Sigma (Standard Deviation)';
            otherwise
                spinner.Enable = 'off';
                spinner.Value = 0;
        end
    end

end
