function updatePixelAnalysis(fig, point)
data = fig.UserData;
if isempty(data.RawData) || ~isfield(data, 'TauMap'), return; end

% Round to pixel coordinates
px = round(point(1));
py = round(point(2));
[nY, nX, nGates] = size(data.RawData);

if px < 1 || px > nX || py < 1 || py > nY, return; end

% Update Crosshair
hV = findobj(fig, 'Tag', 'crossV');
hH = findobj(fig, 'Tag', 'crossH');
if ~isempty(hV), set(hV, 'Value', px, 'Visible', 'on'); end
if ~isempty(hH), set(hH, 'Value', py, 'Visible', 'on'); end

% Extract Pixel Data
pixelCounts = squeeze(data.RawData(py, px, :));
estTau = data.TauMap(py, px);
config = data.config;

axPixel = findobj(fig, 'Tag', 'axPixel');
cla(axPixel); hold(axPixel, 'on');

% 1. Time Vector and Gate Centers
t = 0:config.dt:config.T;
gate_edges = config.gate_edges;
gate_centers = 0.5 * (gate_edges(1:end-1) + gate_edges(2:end));

% 2. Calculate Fitted Model Gate Counts
n_det = sum(pixelCounts);
P_pixel = DTpmod(nGates, estTau, t, data.gate_interp_fns, ...
    config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);
P_pixel = P_pixel ./ sum(P_pixel); % Normalize
fittedCounts = P_pixel * n_det;

% 3. Calculate Smooth Decay Curve for Visualization
[decay_smooth, ~] = DTpdf(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma, estTau);
decay_smooth = decay_smooth * (sum(fittedCounts) / sum(decay_smooth));

% IRF for background
irf = DTexcitation(t, config.fwhm, config.profile, config.rise_time, config.fall_time, ...
    config.bPulseTrain, config.PT_Trep, config.PT_sigma);

% 4. Plot
% IRF (Normalized and scaled - Red Line)
plot(axPixel, t, (irf/max(irf)) * max(pixelCounts) * 0.5, 'r-', 'LineWidth', 1, 'DisplayName', 'IRF');

% Fitted Curve (Smooth - Solid Black Line)
plot(axPixel, t, decay_smooth, 'k-', 'LineWidth', 1.5, 'DisplayName', sprintf('Fit (%.2fns)', estTau));

% Discrete Fitted Gate Counts (Line connecting)
plot(axPixel, gate_centers(:), fittedCounts(:), 'k--', 'LineWidth', 0.5, 'HandleVisibility', 'off');

% Experimental Data (Blue Circles)
plot(axPixel, gate_centers(:), pixelCounts(:), 'bo', 'MarkerSize', 6, 'LineWidth', 1.5, 'DisplayName', 'Data');
hold(axPixel, 'off');
legend(axPixel, 'Location', 'northeast', 'FontSize', 8);
grid(axPixel, 'on');

% Update Pixel Info Labels
hPixPos = findobj(fig, 'Tag', 'lblPixPos');
hPixTauVal = findobj(fig, 'Tag', 'lblPixTauVal');
if ~isempty(hPixPos), hPixPos.Text = sprintf('Pos: %d, %d', px, py); end
if ~isempty(hPixTauVal), hPixTauVal.Text = sprintf('\\tau: %.2f ns', estTau); end

% == Update Pixel Residuals Plot ==
axPixelRes = findobj(fig, 'Tag', 'axPixelRes');
cla(axPixelRes); hold(axPixelRes, 'on');

% Standardized residuals for Poisson data: (Data - Model) / sqrt(Model)
z_pixel = (pixelCounts(:) - fittedCounts(:)) ./ sqrt(fittedCounts(:) + 1e-10);

% Plot against gate_centers for same horizontal scale as axPixel
stem(axPixelRes, gate_centers(:), z_pixel, 'Marker', 'o', 'MarkerSize', 4, 'LineWidth', 1.5, 'Color', [0.4 0.4 0.4]);
yline(axPixelRes, 0, 'k-');
yline(axPixelRes, [1.96, -1.96], 'r--'); % 95% confidence bounds

grid(axPixelRes, 'on');
xlim(axPixelRes, [min(t) max(t)]); % Synchronize X-axis with decay plot
set(axPixelRes, 'XTickLabel', []); % Remove X-tick labels as requested
xlabel(axPixelRes, '');

% == Update Pixel-Level Metrics ==
lblPixChi2 = findobj(fig, 'Tag', 'lblPixChi2');
lblPixRE = findobj(fig, 'Tag', 'lblPixRE');
lblPixRND = findobj(fig, 'Tag', 'lblPixRND');

pix_chi2 = mean(z_pixel.^2);
if ~isempty(lblPixChi2), lblPixChi2.Text = sprintf('%c%c%c: %.3f', 967, 178, 7523, pix_chi2); end
if ~isempty(lblPixRE), lblPixRE.Text = sprintf('R.E.: %.1f%%', (1/pix_chi2)*100); end

% Runs test
if ~isempty(lblPixRND)
    s_pix = sign(z_pixel);
    s_pix(s_pix==0) = 1;
    r_pix = 1 + sum(diff(s_pix)~=0);
    n1 = sum(s_pix>0); n2 = sum(s_pix<0);
    if n1==0 || n2==0
        lblPixRND.Text = 'RND: NO (Bias)';
        lblPixRND.FontColor = [0.8 0 0];
    else
        mu_r = 1 + (2*n1*n2)/(n1+n2);
        s_r = sqrt((2*n1*n2*(2*n1*n2-n1-n2))/((n1+n2)^2 * (n1+n2-1)));
        z_r = (r_pix - mu_r)/s_r;
        if z_r < -1.645
            lblPixRND.Text = sprintf('RND: NO (Z=%.1f)', z_r);
            lblPixRND.FontColor = [0.8 0 0];
        else
            lblPixRND.Text = sprintf('RND: YES (Z=%.1f)', z_r);
            lblPixRND.FontColor = [0 0.6 0];
        end
    end
end
end
