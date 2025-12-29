function InstrumentWizard()
% INSTRUMENTWIZARD - Wizard to create a new instrument JSON
% Scrapes values from the active DigitalTwin GUI if possible.

% 1. Check if Digital Twin is open
dtFig = findall(0, 'Name', 'HILIGHT FLIM Digital Twin');

if isempty(dtFig)
    % ALERT if not open
    uialert(uifigure, 'Digital Twin GUI must be open to capture instrument settings. Please launch Digital Twin and configure your settings first.', 'Digital Twin Not Found');
    return;
end

% Scrape parameters immediately
scrapedData = scrapeDigitalTwin(dtFig(1));

% 2. Open Dialog
d = uifigure('Name', 'New Instrument', 'Position', [300 300 450 320], ...
    'WindowStyle', 'modal', 'Resize', 'off', 'Color', [1 1 1]);

% Main Layout
g = uigridlayout(d, [4, 2]);
g.RowHeight = {40, '1x', 40, 50}; % Header, Body/Desc, Input, Buttons
g.ColumnWidth = {'1x', '2x'};
g.Padding = [20 20 20 20];
g.RowSpacing = 15;
g.ColumnSpacing = 10;

% Header
lblHeading = uilabel(g, 'Text', 'Save Instrument Profile');
lblHeading.FontName = 'Segoe UI';
lblHeading.FontSize = 18;
lblHeading.FontWeight = 'bold';
lblHeading.FontColor = [0.2 0.2 0.2];
lblHeading.Layout.Column = [1 2];

% Description
descText = sprintf('This will capture the current excitation, timing, and gate settings from the active Digital Twin window and save them as a new reusable instrument profile.');
lblDesc = uilabel(g, 'Text', descText);
lblDesc.WordWrap = 'on';
lblDesc.FontName = 'Segoe UI';
lblDesc.FontSize = 12;
lblDesc.FontColor = [0.4 0.4 0.4];
lblDesc.Layout.Column = [1 2];
lblDesc.VerticalAlignment = 'top';

% Name Input
lblInput = uilabel(g, 'Text', 'Instrument Name:');
lblInput.HorizontalAlignment = 'right';
lblInput.FontWeight = 'bold';
lblInput.FontSize = 13;

nameField = uieditfield(g, 'text', 'Value', 'MyNewInstrument');
nameField.FontSize = 13;

% Button Container (Nested Grid for alignment)
btnGrid = uigridlayout(g, [1, 2]);
btnGrid.Layout.Column = [1 2];
btnGrid.Layout.Row = 4;
btnGrid.Padding = [0 0 0 0];
btnGrid.ColumnSpacing = 10;

btnCancel = uibutton(btnGrid, 'Text', 'Cancel', ...
    'BackgroundColor', [0.95 0.95 0.95], 'FontColor', [0.2 0.2 0.2], ...
    'FontSize', 12, 'ButtonPushedFcn', @(btn,ev) close(d));

btnSave = uibutton(btnGrid, 'Text', 'Save Profile', ...
    'BackgroundColor', [0 0.45 0.74], 'FontColor', [1 1 1], 'FontWeight', 'bold', ...
    'FontSize', 12, 'ButtonPushedFcn', @(btn,ev) saveInstrument());

% Pre-calculate path
fPath = fileparts(mfilename('fullpath'));
instFolder = fullfile(fPath, 'instruments');

    function saveInstrument()
        instName = strtrim(nameField.Value);
        if isempty(instName)
            uialert(d, 'Please enter a valid instrument name.', 'Error');
            return;
        end

        % Serialize Name (remove invalid chars for filenames)
        instNameClean = regexprep(instName, '[^a-zA-Z0-9_\-\. ]', '');
        if isempty(instNameClean)
            uialert(d, 'Instrument name contains no valid characters.', 'Error');
            return;
        end

        % Finalize Data
        scrapedData.name = instNameClean;

        % Ensure folder exists
        if ~exist(instFolder, 'dir')
            [status, msg] = mkdir(instFolder);
            if ~status
                uialert(d, sprintf('Cannot create folder: %s\n%s', instFolder, msg), 'Folder Error');
                return;
            end
        end

        fname = [instNameClean '.json'];
        fullPath = fullfile(instFolder, fname);

        if exist(fullPath, 'file')
            choice = uiconfirm(d, 'An instrument with this name already exists. Overwrite?', 'Confirm Overwrite');
            if ~strcmp(choice, 'OK'), return; end
        end

        try
            jsonStr = jsonencode(scrapedData, 'PrettyPrint', true);
            fid = fopen(fullPath, 'w');
            if fid == -1
                % Detailed error via ferror? ferror requires fid, but fid is -1.
                % Just show path.
                uialert(d, sprintf('Cannot create file at:\n%s\nCheck permissions or invalid characters.', fullPath), 'File Error');
                return;
            end
            fprintf(fid, '%s', jsonStr);
            fclose(fid);

            % Success msg and close
            uialert(d, sprintf('Instrument "%s" saved successfully.', instNameClean), 'Success', ...
                'CloseFcn', @(src,ev) closeAndRefresh(d));

        catch ME
            uialert(d, ['Error saving instrument: ' ME.message], 'Error');
        end
    end

    function closeAndRefresh(d)
        delete(d);
        % Also refresh the Main Menu
        dtFig = findall(0, 'Name', 'HILIGHT FLIM Digital Twin');
        if ~isempty(dtFig)
            refreshInstrumentsMenu(dtFig(1));
        end
    end

end

function s = scrapeDigitalTwin(fig)
s = struct();

% Helper to safely get value by Tag
    function val = getByTag(t, defaultVal)
        val = defaultVal;
        obj = findobj(fig, 'Tag', t);
        if ~isempty(obj)
            v = obj.Value;
            % Convert text to number if needed
            if isnumeric(defaultVal) && ischar(v)
                val = str2double(v);
            else
                val = v;
            end
        end
    end

s.T = getByTag('TField', 50);
s.fwhm = getByTag('fwhmField', 5);
s.profile = getByTag('profileDropdown', 'Rectangular');
s.toff = getByTag('toffField', 18);
s.rise_time = getByTag('riseField', 0);
s.fall_time = getByTag('fallField', 0);
s.bPulseTrain = getByTag('PTCheck', false);
s.PT_Trep = getByTag('PTTField', 0.1);
s.PT_sigma = getByTag('PTSField', 0.05);
s.gate_type = getByTag('gateDropdown', 'Equal');
s.N_gates = getByTag('NGateField', 4);
s.r = getByTag('rField', 0.001);
s.N_photons = getByTag('NPhotonsField', 1e4);
s.M = getByTag('MField', 400);
s.dt = getByTag('dtField', 0.01);

% Custom Gates
if s.N_gates > 0 && s.N_gates <= 8
    gw = zeros(1, s.N_gates);
    for k=1:s.N_gates
        gw(k) = getByTag(sprintf('gField%d', k), 2);
    end
    s.gate_widths = gw;
else
    s.gate_widths = [];
end
end
