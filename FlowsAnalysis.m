classdef FlowsAnalysis < handle
    % FLOWSANALYSIS - Advanced Analysis GUI for Flows
    % Features: Split View (Controls/Exp), Multi-File Tabs, Phasor Plot, Thresholding

    properties
        Fig             % Main uifigure
        Data            % Main Data Structure

        % State
        CurrentChannel  % Index (1-based)
        CurrentMask     % Map container or struct for masks? (per file)
        IsThresholded   % Boolean
        PhasorHarmonic  % Default 1

        % UI Layouts
        GridMain        % [1 2] -> Left: Phasor, Right: Data
        LeftPanel       % Phasor Parent
        RightPanel      % Data split Parent

        % UI Components
        PhasorAxes
        TabGroupCtrl    % Top Right
        TabGroupExp     % Bottom Right
        ChannelGrp      % Radio Config

        % Opacity Labels
        lblCtrlVal
        lblExpVal

        DropdownCtrl    % Group Selector
        DropdownExp     % Group Selector

        % Helper indices
        CtrlGroupIndices
        ExpGroupIndices

        % State
        PhasorZoomMode = 'Full' % 'Full' or 'Data'
        ControlOpacity = 0.3
        ExpOpacity = 0.3
    end

    methods
        function obj = FlowsAnalysis(inputData)
            obj.Data = inputData;
            obj.CurrentChannel = 1;
            obj.IsThresholded = false;
            obj.PhasorHarmonic = 1;
            obj.CurrentMask = containers.Map(); % Key: 'GroupIdx_FileIdx'
            obj.ControlOpacity = 0.3;
            obj.ExpOpacity = 0.3;
            obj.PhasorZoomMode = 'Full';

            % Sort Indices
            obj.categorizeGroups();

            % Build
            obj.buildUI();
        end

        function delete(obj)
            if ishandle(obj.Fig), delete(obj.Fig); end
        end
    end

    methods (Access = private)
        function categorizeGroups(obj)
            obj.CtrlGroupIndices = [];
            obj.ExpGroupIndices = [];
            for i = 1:numel(obj.Data.Conditions)
                type = obj.Data.Conditions{i}.Type;
                if contains(type, 'Control', 'IgnoreCase', true)
                    obj.CtrlGroupIndices(end+1) = i;
                else
                    obj.ExpGroupIndices(end+1) = i;
                end
            end
        end

        function buildUI(obj)
            obj.Fig = uifigure('Name', 'Flows Analysis | HILIGHTer', ...
                'Position', [50 50 1400 900], ...
                'Color', [0.12 0.12 0.14], ...
                'Tag', 'FlowsAnalysisGUI');

            % Main Layout: 1 Row, 2 Cols
            obj.GridMain = uigridlayout(obj.Fig, [1 2]);
            obj.GridMain.ColumnWidth = {'1x', '1.5x'};
            obj.GridMain.Padding = [10 10 10 10];
            obj.GridMain.ColumnSpacing = 10;

            % --- LEFT: DATA SPLIT VIEW ---
            obj.RightPanel = uigridlayout(obj.GridMain, [3 1]);
            obj.RightPanel.RowHeight = {50, '1x', '1x'};
            obj.RightPanel.Layout.Column = 1;
            obj.RightPanel.Padding = [0 0 0 0];

            % -- Global Toolbar --
            toolGrid = uigridlayout(obj.RightPanel, [1 4]);
            toolGrid.Layout.Row = 1;
            toolGrid.ColumnWidth = {80, 200, '1x', 150};

            uilabel(toolGrid, 'Text', 'Channel:', 'FontColor', 'white', 'FontWeight', 'bold');

            obj.ChannelGrp = uibuttongroup(toolGrid, 'BackgroundColor', [0.12 0.12 0.14], 'BorderType', 'none', ...
                'SelectionChangedFcn', @(s,e) obj.onChannelChanged(e.NewValue));

            nCh = 1;
            try
                if ~isempty(obj.Data.Conditions) && ~isempty(obj.Data.Conditions{1}.Analysis)
                    dat = obj.Data.Conditions{1}.Analysis(1).Data;
                    if ~isempty(dat), nCh = size(dat, 4); end
                end
            catch
                nCh = 1;
            end
            if nCh < 1, nCh = 1; end

            btnW = 60; btnH = 30; spacing = 5;
            startX = 10; startY = 10;
            for i = 1:nCh
                xPos = startX + (i-1)*(btnW + spacing);
                rb = uiradiobutton(obj.ChannelGrp, 'Text', sprintf('Ch %d', i), ...
                    'FontColor', 'white', 'Tag', num2str(i), ...
                    'Position', [xPos, startY, btnW, btnH]);
                if i==1, rb.Value = true; end
            end

            uilabel(toolGrid, 'Text', '');
            uibutton(toolGrid, 'Text', 'Filtering / Threshold ⚡', ...
                'BackgroundColor', [0.6 0.2 0.8], 'FontColor', 'white', ...
                'ButtonPushedFcn', @(s,e) obj.onThresholdOptions());

            % -- TOP: CONTROLS VIEW --
            ctrlP = uipanel(obj.RightPanel, 'Title', 'CONTROLS', 'BackgroundColor', [0.2 0.25 0.2], 'ForegroundColor', 'white');
            ctrlP.Layout.Row = 2;
            cpGrid = uigridlayout(ctrlP, [1 2]);
            cpGrid.ColumnWidth = {200, '1x'};
            cSide = uigridlayout(cpGrid, [3 1]);
            cSide.RowHeight = {20, 25, '1x'};
            uilabel(cSide, 'Text', 'Select Group:', 'FontColor', 'white');
            cNames = {'None'};
            if ~isempty(obj.CtrlGroupIndices)
                cNames = cellfun(@(i) obj.Data.Conditions{i}.Name, num2cell(obj.CtrlGroupIndices), 'UniformOutput', false);
            end
            obj.DropdownCtrl = uidropdown(cSide, 'Items', cNames, 'ValueChangedFcn', @(s,e) obj.updateControlTabs());
            obj.TabGroupCtrl = uitabgroup(cpGrid);
            obj.TabGroupCtrl.Layout.Column = 2;

            % -- BOTTOM: EXPERIMENT VIEW --
            expP = uipanel(obj.RightPanel, 'Title', 'EXPERIMENTAL CONDITIONS', 'BackgroundColor', [0.2 0.2 0.25], 'ForegroundColor', 'white');
            expP.Layout.Row = 3;
            epGrid = uigridlayout(expP, [1 2]);
            epGrid.ColumnWidth = {200, '1x'};
            eSide = uigridlayout(epGrid, [2 1]);
            eSide.RowHeight = {30, '1x'};
            uilabel(eSide, 'Text', 'Select Group:', 'FontColor', 'white');
            eNames = {'None'};
            if ~isempty(obj.ExpGroupIndices)
                eNames = cellfun(@(i) obj.Data.Conditions{i}.Name, num2cell(obj.ExpGroupIndices), 'UniformOutput', false);
            end
            obj.DropdownExp = uidropdown(eSide, 'Items', eNames, 'ValueChangedFcn', @(s,e) obj.updateExperimentTabs());
            obj.TabGroupExp = uitabgroup(epGrid);
            obj.TabGroupExp.Layout.Column = 2;

            % --- RIGHT: PHASOR PANEL ---
            obj.LeftPanel = uipanel(obj.GridMain, 'Title', 'CUMULATIVE PHASOR PLOT', ...
                'FontSize', 14, 'FontWeight', 'bold', 'BackgroundColor', [0.15 0.15 0.17], 'ForegroundColor', 'white');
            obj.LeftPanel.Layout.Column = 2;
            pGrid = uigridlayout(obj.LeftPanel, [3 1]);
            pGrid.RowHeight = {'1x', 45, 55};

            obj.PhasorAxes = uiaxes(pGrid, 'BackgroundColor', 'white', 'XColor', 'black', 'YColor', 'black');
            obj.PhasorAxes.Layout.Row = 1;
            obj.PhasorAxes.Box = 'on';
            title(obj.PhasorAxes, 'Phasor Space', 'Color', 'black');
            xlabel(obj.PhasorAxes, 'G (cos)', 'Color', 'black');
            ylabel(obj.PhasorAxes, 'S (sin)', 'Color', 'black');
            axis(obj.PhasorAxes, 'equal');

            pTool = uigridlayout(pGrid, [1 3]);
            pTool.Layout.Row = 2;
            uibutton(pTool, 'Text', '⚡ Recalculate', 'ButtonPushedFcn', @(s,e) obj.forcePhasorUpdate());
            uibutton(pTool, 'Text', '🔍 Data', 'ButtonPushedFcn', @(s,e) obj.setZoom('Data'));
            uibutton(pTool, 'Text', '🔍 Full', 'ButtonPushedFcn', @(s,e) obj.setZoom('Full'));

            pOpacity = uigridlayout(pGrid, [1 6]);
            pOpacity.Layout.Row = 3;
            pOpacity.ColumnWidth = {85, '1x', 55, 85, '1x', 55};
            pOpacity.Padding = [10 0 10 5];

            uilabel(pOpacity, 'Text', 'Ctrl Opacity:', 'FontColor', [0.2 0.8 0.2], 'HorizontalAlignment', 'right', 'FontWeight', 'bold');
            sCtrl = uislider(pOpacity, 'Limits', [0 1], 'Value', obj.ControlOpacity, ...
                'ValueChangingFcn', @(s,e) obj.updateOpacity('Ctrl', e.Value), ...
                'ValueChangedFcn', @(s,e) obj.updateOpacity('Ctrl', s.Value));
            obj.lblCtrlVal = uilabel(pOpacity, 'Text', sprintf('%.0f%%', obj.ControlOpacity*100), 'FontColor', 'white');

            uilabel(pOpacity, 'Text', 'Exp Opacity:', 'FontColor', [1 0.2 0.2], 'HorizontalAlignment', 'right', 'FontWeight', 'bold');
            sExp = uislider(pOpacity, 'Limits', [0 1], 'Value', obj.ExpOpacity, ...
                'ValueChangingFcn', @(s,e) obj.updateOpacity('Exp', e.Value), ...
                'ValueChangedFcn', @(s,e) obj.updateOpacity('Exp', s.Value));
            obj.lblExpVal = uilabel(pOpacity, 'Text', sprintf('%.0f%%', obj.ExpOpacity*100), 'FontColor', 'white');

            obj.updateControlTabs();
            obj.updateExperimentTabs();
            obj.updatePhasorPlot();
        end

        function updateControlTabs(obj)
            idx = obj.getGroupIndex(obj.DropdownCtrl.Value, obj.CtrlGroupIndices);
            obj.populateTabGroup(obj.TabGroupCtrl, idx);
        end

        function updateExperimentTabs(obj)
            idx = obj.getGroupIndex(obj.DropdownExp.Value, obj.ExpGroupIndices);
            obj.populateTabGroup(obj.TabGroupExp, idx);
        end

        function idx = getGroupIndex(obj, name, listIndices)
            idx = 0; if strcmp(name, 'None'), return; end
            for i = listIndices
                if strcmp(obj.Data.Conditions{i}.Name, name), idx = i; return; end
            end
        end

        function populateTabGroup(obj, tabGroup, grpIdx)
            delete(tabGroup.Children);
            if grpIdx == 0, return; end
            filesData = obj.Data.Conditions{grpIdx}.Analysis;
            fNames = obj.Data.Conditions{grpIdx}.Files;
            for i = 1:numel(filesData)
                [~, fname, ~] = fileparts(fNames{i});
                t = uitab(tabGroup, 'Title', fname);
                tg = uigridlayout(t, [1 1]);
                ax = uiaxes(tg, 'BackgroundColor', 'black');
                rawData = filesData(i).Data;
                if ~isempty(rawData) && obj.CurrentChannel <= size(rawData, 4)
                    img = sum(rawData(:,:,:,obj.CurrentChannel), 3);
                    key = sprintf('%d_%d', grpIdx, i);
                    if obj.IsThresholded && obj.CurrentMask.isKey(key)
                        img(~obj.CurrentMask(key)) = 0;
                    end
                    imagesc(ax, img); colormap(ax, 'turbo'); colorbar(ax, 'Color', 'white');
                    axis(ax, 'image', 'off');
                else
                    title(ax, 'No Data / Missing Channel', 'Color', 'gray');
                end
            end
        end

        function onChannelChanged(obj, rButton)
            obj.CurrentChannel = str2double(rButton.Tag);
            obj.updateControlTabs(); obj.updateExperimentTabs();
            obj.updatePhasorPlot();
        end

        function updateOpacity(obj, target, val)
            if strcmp(target, 'Ctrl')
                obj.ControlOpacity = val;
                if ~isempty(obj.lblCtrlVal), obj.lblCtrlVal.Text = sprintf('%.0f%%', val*100); end
            else
                obj.ExpOpacity = val;
                if ~isempty(obj.lblExpVal), obj.lblExpVal.Text = sprintf('%.0f%%', val*100); end
            end
            objs = findobj(obj.PhasorAxes, 'Type', 'Scatter');
            for i = 1:numel(objs)
                dName = objs(i).DisplayName;
                if ~isempty(dName)
                    isCtrl = false;
                    for ic = obj.CtrlGroupIndices
                        if strcmp(obj.Data.Conditions{ic}.Name, dName), isCtrl = true; break; end
                    end
                    if isCtrl && strcmp(target, 'Ctrl')
                        objs(i).MarkerFaceAlpha = val;
                    elseif ~isCtrl && strcmp(target, 'Exp')
                        objs(i).MarkerFaceAlpha = val;
                    end
                end
            end
        end

        function forcePhasorUpdate(obj)
            title(obj.PhasorAxes, 'Recalculating...', 'Color', [0.8 0.5 0]);
            drawnow; obj.updatePhasorPlot();
            title(obj.PhasorAxes, 'Phasor Space', 'Color', 'black');
        end

        function setZoom(obj, mode)
            obj.PhasorZoomMode = mode;
            obj.updatePhasorPlot();
        end

        function updatePhasorPlot(obj)
            cla(obj.PhasorAxes); hold(obj.PhasorAxes, 'on');

            % Universal Semicircle
            gArc = linspace(0, 1, 100); sArc = sqrt(gArc .* (1 - gArc));
            plot(obj.PhasorAxes, gArc, sArc, 'k-', 'LineWidth', 1.5, 'HandleVisibility', 'off');

            refConfig = [];
            allGroups = [obj.CtrlGroupIndices, obj.ExpGroupIndices];
            for i = allGroups
                if ~isempty(obj.Data.Conditions{i}.Analysis) && isfield(obj.Data.Conditions{i}.Analysis(1), 'Config')
                    refConfig = obj.Data.Conditions{i}.Analysis(1).Config; break;
                end
            end

            if ~isempty(refConfig)
                T = refConfig.T; f = 1 / T; tau_locus = logspace(log10(0.05), log10(50), 100);
                dt = T / 200; t_vec = 0:dt:T;
                gate_profiles = DTgates(t_vec, refConfig.r, refConfig.gate_edges);
                gate_interp_fns = cell(refConfig.N_gates, 1);
                for ig = 1:refConfig.N_gates, gate_interp_fns{ig} = griddedInterpolant(t_vec, gate_profiles(ig, :), 'linear', 'nearest'); end
                P_locus = DTpmod(refConfig.N_gates, tau_locus, t_vec, gate_interp_fns, ...
                    refConfig.fwhm, refConfig.profile, refConfig.rise_time, refConfig.fall_time, ...
                    refConfig.bPulseTrain, refConfig.PT_Trep, refConfig.PT_sigma, 0);
                sumP = sum(P_locus, 1); sumP(sumP == 0) = 1e-10;
                gate_centers = 0.5 * (refConfig.gate_edges(1:end-1) + refConfig.gate_edges(2:end));
                cosT = cos(2 * pi * f * gate_centers(:)); sinT = sin(2 * pi * f * gate_centers(:));
                gTh = (cosT' * P_locus)./sumP; sTh = (sinT' * P_locus)./sumP;
                plot(obj.PhasorAxes, gTh, sTh, '--', 'Color', [0.4 0.4 0.4], 'LineWidth', 1, 'DisplayName', 'Theory');
                tau_labels = [0.1, 0.5, 1, 2, 5, 10];
                for tl = tau_labels
                    P_p = DTpmod(refConfig.N_gates, tl, t_vec, gate_interp_fns, ...
                        refConfig.fwhm, refConfig.profile, refConfig.rise_time, refConfig.fall_time, ...
                        refConfig.bPulseTrain, refConfig.PT_Trep, refConfig.PT_sigma, 0);
                    gp = (cosT' * P_p) / sum(P_p); sp = (sinT' * P_p) / sum(P_p);
                    plot(obj.PhasorAxes, gp, sp, 'ko', 'MarkerSize', 4, 'MarkerFaceColor', [0.4 0.4 0.4], 'HandleVisibility', 'off');
                    text(obj.PhasorAxes, gp, sp+0.02, sprintf('%.1gns', tl), 'Color', 'black', 'FontSize', 8, 'HorizontalAlignment', 'center');
                end
            end

            hC = obj.plotPhasorPoints(obj.CtrlGroupIndices, [0.2 0.8 0.2], obj.ControlOpacity);
            hE = obj.plotPhasorPoints(obj.ExpGroupIndices, [1 0.2 0.2], obj.ExpOpacity);

            % Update Zoom
            allX = []; allY = [];
            objs = findobj(obj.PhasorAxes, 'Type', 'Scatter');
            for io = 1:numel(objs), allX = [allX; objs(io).XData(:)]; allY = [allY; objs(io).YData(:)]; end

            if strcmp(obj.PhasorZoomMode, 'Data')
                if ~isempty(allX)
                    xR = [min(allX) max(allX)]; yR = [min(allY) max(allY)]; dx = diff(xR); dy = diff(yR);
                    if dx == 0, dx = 0.1; end; if dy == 0, dy = 0.1; end
                    xlim(obj.PhasorAxes, [xR(1)-0.1*dx, xR(2)+0.1*dx]); ylim(obj.PhasorAxes, [yR(1)-0.1*dy, yR(2)+0.1*dy]);
                end
            else
                xMin = 0; xMax = 1; yMin = 0; yMax = 0.5;
                if ~isempty(allX)
                    xMin = min([xMin; allX]); xMax = max([xMax; allX]); yMin = min([yMin; allY]); yMax = max([yMax; allY]);
                end
                dx = xMax - xMin; dy = yMax - yMin;
                xlim(obj.PhasorAxes, [xMin - 0.05*dx, xMax + 0.05*dx]); ylim(obj.PhasorAxes, [yMin - 0.05*dy, yMax + 0.05*dy]);
            end

            % Axes visibility
            grid(obj.PhasorAxes, 'on');
            xline(obj.PhasorAxes, 0, 'k-', 'LineWidth', 1.2, 'HandleVisibility', 'off');
            yline(obj.PhasorAxes, 0, 'k-', 'LineWidth', 1.2, 'HandleVisibility', 'off');
            xline(obj.PhasorAxes, 1, 'k:', 'Alpha', 0.1, 'HandleVisibility', 'off');
            yline(obj.PhasorAxes, 0.5, 'k:', 'Alpha', 0.1, 'HandleVisibility', 'off');

            legend_plots = []; legend_names = {};
            if ~isempty(hC), legend_plots(end+1) = hC; legend_names{end+1} = 'Controls'; end
            if ~isempty(hE), legend_plots(end+1) = hE; legend_names{end+1} = 'Experiment'; end
            if ~isempty(legend_plots)
                legend(obj.PhasorAxes, legend_plots, legend_names, 'TextColor', 'black', 'EdgeColor', [0.7 0.7 0.7], 'Location', 'northeast');
            end
            hold(obj.PhasorAxes, 'off');
        end

        function h = plotPhasorPoints(obj, indices, style, alpha)
            h = []; allG = []; allS = []; if nargin < 4, alpha = 0.3; end
            legendName = '';
            for iG = indices
                cond = obj.Data.Conditions{iG};
                if isempty(legendName) && ~isempty(cond.Name), legendName = cond.Name; end
                for f = 1:numel(cond.Analysis)
                    if isempty(cond.Analysis(f).Data), continue; end
                    chRaw = cond.Analysis(f).Data(:,:,:,obj.CurrentChannel);
                    [nY, nX, nT] = size(chRaw);
                    T = 12.5; if isfield(cond.Analysis(f), 'Config') && ~isempty(cond.Analysis(f).Config), T = cond.Analysis(f).Config.T; end
                    key = sprintf('%d_%d', iG, f);
                    mask = true(nY, nX); if obj.IsThresholded && obj.CurrentMask.isKey(key), mask = obj.CurrentMask(key); end
                    trace = reshape(chRaw, [], nT); trace = trace(mask(:), :);
                    if isempty(trace), continue; end
                    f_base = 1 / T;
                    if isfield(cond.Analysis(f), 'Config') && ~isempty(cond.Analysis(f).Config)
                        edges = cond.Analysis(f).Config.gate_edges; gate_centers = 0.5 * (edges(1:end-1) + edges(2:end));
                    else
                        gate_centers = linspace(T/(2*nT), T-T/(2*nT), nT);
                    end
                    [~, peakIdx] = max(sum(trace, 1)); t_peak = gate_centers(peakIdx);
                    phase = 2 * pi * f_base * (gate_centers(:) - t_peak);
                    totalI = sum(trace, 2); valid = totalI > 0; trace = trace(valid, :); totalI = totalI(valid);
                    if isempty(trace), continue; end
                    g = (trace * cos(phase)) ./ totalI; s = (trace * sin(phase)) ./ totalI;
                    allG = [allG; g(:)]; allS = [allS; s(:)];
                end
            end
            if ~isempty(allG)
                h = scatter(obj.PhasorAxes, allG, allS, 15, style, 'filled', 'MarkerFaceAlpha', alpha, 'MarkerEdgeAlpha', 0, 'DisplayName', legendName);
                if numel(allG) > 10
                    try
                        mu = [mean(allG), mean(allS)]; sigma = cov(allG, allS);
                        sCI = -2 * log(1 - 0.96); % 96% CI
                        [V, D] = eig(sigma * sCI); t = linspace(0, 2*pi, 80); xy = V * sqrt(D) * [cos(t); sin(t)];
                        plot(obj.PhasorAxes, xy(1,:) + mu(1), xy(2,:) + mu(2), '-', 'LineWidth', 2.5, 'Color', style, 'HandleVisibility', 'off');
                    catch
                    end
                end
            end
        end

        function onThresholdOptions(obj)
            d = uifigure('Name', 'Thresholding', 'Position', [obj.Fig.Position(1)+100 obj.Fig.Position(2)+100 300 200]);
            g = uigridlayout(d, [4 1]); uilabel(g, 'Text', 'Threshold Strategy:', 'FontWeight', 'bold');
            uibutton(g, 'Text', 'Automatic (Otsu + Morph)', 'ButtonPushedFcn', @(s,e) obj.applyAutoThreshold(d));
            subG = uigridlayout(g, [1 2]); ef = uieditfield(subG, 'numeric', 'Value', 10);
            uibutton(subG, 'Text', 'Manual (Count)', 'ButtonPushedFcn', @(s,e) obj.applyManualThreshold(d, ef.Value));
            uibutton(g, 'Text', 'Clear Thresholds', 'FontColor', 'red', 'ButtonPushedFcn', @(s,e) obj.clearThreshold(d));
        end

        function applyAutoThreshold(obj, dialog), close(dialog); obj.performThresholding('auto', []); end
        function applyManualThreshold(obj, dialog, val), close(dialog); obj.performThresholding('manual', val); end
        function clearThreshold(obj, dialog)
            close(dialog); obj.IsThresholded = false; obj.CurrentMask = containers.Map();
            obj.updateControlTabs(); obj.updateExperimentTabs(); obj.updatePhasorPlot();
        end

        function performThresholding(obj, mode, val)
            hThreshold = uiprogressdlg(obj.Fig, 'Message', 'Computing Masks...', 'Indeterminate', 'on');
            allConds = [obj.CtrlGroupIndices, obj.ExpGroupIndices];
            for iT = allConds
                cond = obj.Data.Conditions{iT};
                for fT = 1:numel(cond.Analysis)
                    dat = cond.Analysis(fT).Data; if obj.CurrentChannel > size(dat, 4), continue; end
                    img = sum(dat(:,:,:,obj.CurrentChannel), 3);
                    if strcmp(mode, 'auto'), lvl = graythresh(mat2gray(img)); mask = imbinarize(mat2gray(img), lvl);
                    else, mask = img > val; end
                    se2 = strel('square', 5); mask = imerode(mask, se2); mask = imdilate(mask, se2);
                    obj.CurrentMask(sprintf('%d_%d', iT, fT)) = mask;
                end
            end
            obj.IsThresholded = true; close(hThreshold);
            obj.updateControlTabs(); obj.updateExperimentTabs(); obj.updatePhasorPlot();
            uialert(obj.Fig, 'Thresholding applied to all files.', 'Success');
        end
    end
end
