function [newMask, userCancelled] = MaskEditor(imgData, initialMask)
% MASKEDITOR Modal dialog for morphological mask editing
% imgData: 2D intensity image (for visualization)
% initialMask: Logical 2D mask (true = masked/background, false = ROI) -> Wait, let's clarify conventions.
% HILIGHTer Convention:
%   BackgroundMask Tag used 'red' overlay.
%   alphaMap = double(projXY <= tVal); -> 1 (Red) where data IS background (low intensity).
%   So input 'initialMask' should be TRUE for Background, FALSE for Foreground.
%
% Returns:
%   newMask: Modified logical mask
%   userCancelled: Boolean flag

newMask = initialMask;
userCancelled = true;

% Create Modal Figure
hFig = uifigure('Name', 'Mask Editor', 'WindowStyle', 'modal', ...
    'Position', [100 100 800 600]);

% Layout
g = uigridlayout(hFig, [1, 2]);
g.ColumnWidth = {'1x', 250};

% Panel 1: Image Display
pnlDisp = uipanel(g);
ax = uiaxes(pnlDisp, 'Position', [10 10 500 550]); % Approximate, will adjust with resize
ax.Layout.Row = 1; ax.Layout.Column = 1;

% Panel 2: Controls
pnlCtrl = uipanel(g);
pnlCtrl.Layout.Row = 1; pnlCtrl.Layout.Column = 2;

% --- Visualization ---
% Show Image
imagesc(ax, imgData);
colormap(ax, 'gray');
axis(ax, 'image');
set(ax, 'XTick', [], 'YTick', []);

% Show Overlay
hold(ax, 'on');
sz = size(imgData);
redImg = cat(3, ones(sz), zeros(sz), zeros(sz));
hMask = image(ax, redImg);
hMask.AlphaData = double(newMask) * 0.5; % Semi-transparent red for mask

% --- Controls ---
lblH = 22; pad = 10;
currY = 550;

uilabel(pnlCtrl, 'Text', 'Morphological Operations', 'FontWeight', 'bold', ...
    'Position', [10 currY 200 lblH]);

currY = currY - 30;
uilabel(pnlCtrl, 'Text', 'Operation:', 'Position', [10 currY 80 lblH]);
ddOp = uidropdown(pnlCtrl, 'Items', {'Dilate', 'Erode', 'Open', 'Close'}, ...
    'Position', [80 currY 140 lblH]);

currY = currY - 30;
uilabel(pnlCtrl, 'Text', 'Radius (px):', 'Position', [10 currY 80 lblH]);
spnRad = uispinner(pnlCtrl, 'Limits', [1 50], 'Value', 1, ...
    'Position', [80 currY 80 lblH]);

currY = currY - 30;
uilabel(pnlCtrl, 'Text', 'Target:', 'Position', [10 currY 80 lblH]);
% "Foreground" usually means the White parts (1).
% In our convention, Mask=1 (Red/Background).
% So if user wants to Dilate the "Cell" (Foreground/0), they affect the 0 regions.
% To match user request "apply to Foreground OR Background":
% List items: "Background (Red Mask)", "Foreground (Data)"
ddTarget = uidropdown(pnlCtrl, 'Items', {'Background (Red)', 'Foreground (Data)'}, ...
    'Position', [80 currY 140 lblH]);

currY = currY - 40;
uibutton(pnlCtrl, 'Text', 'APPLY OPERATION', 'FontWeight', 'bold', ...
    'BackgroundColor', [0.9 0.9 0.9], ...
    'Position', [10 currY 210 30], ...
    'ButtonPushedFcn', @onApply);

currY = currY - 50;
uibutton(pnlCtrl, 'Text', 'Undo Last', 'Enable', 'off', ...
    'Position', [10 currY 100 30], 'Tag', 'btnUndo', ...
    'ButtonPushedFcn', @onUndo);

uibutton(pnlCtrl, 'Text', 'Reset All', ...
    'Position', [120 currY 100 30], ...
    'ButtonPushedFcn', @onReset);

% Final Buttons
uibutton(pnlCtrl, 'Text', 'OK', 'FontWeight', 'bold', ...
    'BackgroundColor', [0 0.447 0.741], 'FontColor', 'w', ...
    'Position', [10 60 100 30], ...
    'ButtonPushedFcn', @onOK);

uibutton(pnlCtrl, 'Text', 'Cancel', ...
    'Position', [120 60 100 30], ...
    'ButtonPushedFcn', @onCancel);

% State
history = {initialMask};

% Wait for user interaction
uiwait(hFig);

% --- Callbacks ---

    function onApply(~,~)
        op = ddOp.Value;
        rad = spnRad.Value;
        target = ddTarget.Value;

        currentBW = history{end};
        se = strel('disk', rad);

        % Mapping:
        % Our `currentBW` is 1 for Background (Red), 0 for Foreground.
        % Morph functions (imdilate, etc) operate on 1s.

        bwToProcess = currentBW;

        if strcmp(target, 'Foreground (Data)')
            % We want to process the Foreground.
            % Foreground is 0 in currentBW.
            % Invert so Foreground is 1.
            bwToProcess = ~currentBW;
        end

        % Apply Op
        switch op
            case 'Dilate', res = imdilate(bwToProcess, se);
            case 'Erode',  res = imerode(bwToProcess, se);
            case 'Open',   res = imopen(bwToProcess, se);
            case 'Close',  res = imclose(bwToProcess, se);
        end

        if strcmp(target, 'Foreground (Data)')
            % Invert back so Background is 1 again
            res = ~res;
        end

        % Update
        history{end+1} = res;
        updateView();
    end

    function onUndo(~,~)
        if numel(history) > 1
            history(end) = [];
            updateView();
        end
    end

    function onReset(~,~)
        history = {initialMask};
        updateView();
    end

    function updateView()
        newMask = history{end};
        hMask.AlphaData = double(newMask) * 0.5;

        btnUndo = findobj(pnlCtrl, 'Tag', 'btnUndo');
        if numel(history) > 1
            btnUndo.Enable = 'on';
        else
            btnUndo.Enable = 'off';
        end
    end

    function onOK(~,~)
        newMask = history{end};
        userCancelled = false;
        close(hFig);
    end

    function onCancel(~,~)
        userCancelled = true;
        close(hFig);
    end

end
