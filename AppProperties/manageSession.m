function manageSession(fig, appName, action)
% manageSession - Handles saving and resuming of application sessions
% appName: 'HILIGHTer' or 'DigitalTwin'
% action: 'check' or 'closing'

fPath = fileparts(mfilename('fullpath'));
sessionFile = fullfile(fPath, [appName '_session.mat']);

switch action
    case 'check'
        if exist(sessionFile, 'file')
            % Check if the file is valid and not too old? (Optional)
            res = uiconfirm(fig, 'A previous session was found. Do you want to resume it?', ...
                'Resume Session', 'Options', {'Resume', 'Start Fresh'}, ...
                'DefaultOption', 1, 'CancelOption', 2);

            if strcmp(res, 'Resume')
                loadSession(fig, sessionFile);
            else
                % Backup the old session just in case, or just delete
                % movefile(sessionFile, [sessionFile '.bak']);
                delete(sessionFile);
            end
        end

    case 'closing'
        res = uiconfirm(fig, 'Do you want to save the current session before closing?', ...
            'Save Session', 'Options', {'Save', 'Don''t Save', 'Cancel'}, ...
            'DefaultOption', 1, 'CancelOption', 3);

        if strcmp(res, 'Save')
            try
                saveSession(fig, sessionFile);
                delete(fig);
            catch ME
                uialert(fig, ['Error saving session: ' ME.message], 'Error');
            end
        elseif strcmp(res, 'Don''t Save')
            if exist(sessionFile, 'file'), delete(sessionFile); end
            delete(fig);
        end
end
end

function saveSession(fig, sessionFile)
% Persist UserData
session.UserData = fig.UserData;

% Collect all UI states
% We look for any component with a Tag and a Value property
allComps = findall(fig, '-property', 'Tag');
session.UIStates = struct();
for i = 1:length(allComps)
    tag = allComps(i).Tag;
    if ~isempty(tag)
        if isprop(allComps(i), 'Value')
            session.UIStates.(tag) = allComps(i).Value;
        elseif isprop(allComps(i), 'Checked')
            session.UIStates.(tag) = allComps(i).Checked;
        end
    end
end

save(sessionFile, 'session');
end

function loadSession(fig, sessionFile)
if ~exist(sessionFile, 'file'), return; end
data = load(sessionFile);
if ~isfield(data, 'session'), return; end
session = data.session;

% 1. Restore UserData
if isfield(session, 'UserData')
    fig.UserData = session.UserData;
end

% 2. Restore UI component values
if isfield(session, 'UIStates')
    tags = fieldnames(session.UIStates);
    for i = 1:length(tags)
        tag = tags{i};
        val = session.UIStates.(tag);
        comp = findobj(fig, 'Tag', tag);
        if ~isempty(comp)
            if isprop(comp, 'Value')
                try
                    comp.Value = val;
                    % Trigger ValueChanged manually if needed?
                    % Usually it's better to let the app refresh explicitly
                catch
                end
            elseif isprop(comp, 'Checked')
                comp.Checked = val;
            end
        end
    end
end

% 3. App-Specific Logic
if contains(fig.Name, 'Digital Twin', 'IgnoreCase', true)
    % Trigger any necessary UI updates for Digital Twin
    % (Most are static or updated on 'Run')
else
    % HILIGHTer - Refresh plots and tabs
    try
        % Data tabs might need to be recreated if nC changed
        if isfield(fig.UserData, 'RawData') && ~isempty(fig.UserData.RawData)
            [~,~,~,nC] = size(fig.UserData.RawData);
            % Call setupDataTabs if needed (though it's called in refreshAllPlots)
            feval('refreshAllPlots', fig);
            % We might also need to sync analysis tabs
            feval('syncAnalysisTabsWithConfig', fig);
        end
    catch
    end
end
end
