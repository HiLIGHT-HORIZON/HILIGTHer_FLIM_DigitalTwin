function excitation = DTexcitation(t, fwhm, profile, rise_time, fall_time, bPulseTrain, PT_Trep, PT_sigma)
% DTEXCITATION - Generate excitation profile
%
% Inputs:
%   t           : time vector
%   fwhm        : Width parameter
%   profile     : 'Rectangular' or 'Gaussian'
%   rise_time   : Rise time (for Rectangular)
%   fall_time   : Fall time (for Rectangular)
%   bPulseTrain : Boolean, enable pulse train
%   PT_Trep     : Pulse train repetition period
%   PT_sigma    : Pulse train peak width

    % Generate excitation profile (envelope)
    switch lower(profile)
        case 'rectangular'

            % Segment durations
            t_rise      = fwhm;
            excitation  = zeros(size(t));
            
            % Exponential rise
            idx_rise = find(t < t_rise);
            excitation(idx_rise) = 1 - exp(-(t(idx_rise)/max(rise_time,eps)));
    
            % Exponential fall
            idx_fall = t >= t_rise;
            excitation(idx_fall) = excitation(idx_rise(end)) * exp(-(t(idx_fall) - t_rise) / max(fall_time, eps));

        case 'gaussian'
            sigma = fwhm / (2 * sqrt(2 * log(2)));
            excitation = exp(-((t - fwhm / 2).^2) / (2 * sigma^2));
        otherwise
            error('Unsupported excitation profile: %s', profile);
    end

    %%%
    if bPulseTrain

        pulse_train = zeros(size(t));
        center = 0;
        while center < max(t) 
            center = center + PT_Trep;
            pulse_train = pulse_train + exp(-((t - center).^2) / (2*PT_sigma^2));
        end
    else
        pulse_train = ones(size(t));
    end

    %%%

    % Normalize excitation to unit area (optional here, but keeping raw magnitude)
    excitation = excitation .* pulse_train;
    
end
