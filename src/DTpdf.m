function [pdf, cdf] = DTpdf(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, tau, irf_shift, bWrap, dead_time, irf_custom)
% Default values for new parameters
if nargin < 10, irf_shift = 0; end
if nargin < 11, bWrap = false; end
if nargin < 12, dead_time = 0; end
if nargin < 13, irf_custom = []; end

if ~isempty(irf_custom)
    % Use custom IRF
    IRF = irf_custom(:)';
    if numel(IRF) ~= numel(t)
        IRF = interp1(linspace(t(1), t(end), numel(IRF)), IRF, t, 'linear', 0);
    end
else
    % Generate excitation profile (envelope)
    excitation = DTexcitation(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma);

    % Apply IRF Shift (irf_shift in ps)
    if irf_shift ~= 0
        dt_step = t(2) - t(1);
        shift_bins = round((irf_shift/1000) / dt_step);
        excitation = circshift(excitation, [0, shift_bins]);
        if shift_bins > 0
            excitation(1:min(shift_bins, end)) = 0;
        elseif shift_bins < 0
            excitation(max(1, end+shift_bins):end) = 0;
        end
    end
    IRF = excitation;
end

IRF = IRF / sum(IRF);

% Generate IRF-convolved exponential decay
decay = exp(-t / tau);

% Apply Dead Time (blind period at start, dead_time in ps)
if dead_time > 0
    decay(t < (dead_time/1000)) = 0;
end

decay = decay / trapz(t, decay);  % normalize

% Convolve
full_pdf = conv(IRF, decay, 'full');
N = numel(t);

if bWrap
    % Wrap around tails (Pulse train effect)
    pdf = zeros(size(t));
    for i = 1:N
        % Sum every N bins to wrap tails from subsequent "virtual" periods
        idx = i:N:numel(full_pdf);
        pdf(i) = sum(full_pdf(idx));
    end
else
    pdf = full_pdf(1:N);
end

s = sum(pdf);
if s > 0
    pdf = pdf / s;  % normalize again
else
    % Fallback if something went wrong: set first bin to 1
    pdf = zeros(size(pdf));
    pdf(1) = 1;
end

cdf = cumsum(pdf);

end



