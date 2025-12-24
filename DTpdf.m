
function [pdf, cdf] = DTpdf(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma, tau)
    
    % Generate excitation profile (envelope)
    excitation = DTexcitation(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma);
    IRF = excitation / sum(excitation);

    % Generate IRF-convolved exponential decay
    decay = exp(-t / tau);
    decay = decay / trapz(t, decay);  % normalize

    pdf = conv(IRF, decay, 'full');
    pdf = pdf(1:numel(decay));
    pdf = pdf / sum(pdf);  % normalize again

    cdf = cumsum(pdf);

end



