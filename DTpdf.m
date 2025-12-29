
function [pdf, cdf] = DTpdf(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, tau)

% Generate excitation profile (envelope)
excitation = DTexcitation(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma);
IRF = excitation / sum(excitation);

% Generate IRF-convolved exponential decay
decay = exp(-t / tau);
decay = decay / trapz(t, decay);  % normalize

pdf = conv(IRF, decay, 'full');
pdf = pdf(1:numel(decay));
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



