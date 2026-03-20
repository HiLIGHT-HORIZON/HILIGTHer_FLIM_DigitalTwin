function refreshThemesMenu(fig)
% refreshThemesMenu - Rebuilds the 'Select' theme menu in the main figure
% Assumes the menu exists as 'menuSelectTheme' tag (we'll add this tag)

mSelect = findobj(fig, 'Tag', 'menuSelectTheme');
if isempty(mSelect), return; end

% Clear existing
delete(mSelect.Children);

% --- Dynamic Items ---
fPath = fileparts(mfilename('fullpath'));
% themes are .css files in AppProperties
files = dir(fullfile(fPath, '*.css'));

if isempty(files)
    uimenu(mSelect, 'Text', '(No themes found)', 'Enable', 'off');
else
    for k = 1:length(files)
        fname = files(k).name;
        [~, name, ~] = fileparts(fname);

        mItem = uimenu(mSelect);
        mItem.Text = name;
        mItem.MenuSelectedFcn = @(src, ev) applyAppTheme(fig, fname);
    end
end
end
