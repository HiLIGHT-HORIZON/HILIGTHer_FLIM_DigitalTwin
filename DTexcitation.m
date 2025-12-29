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
        % Ensure t_rise and fall_time have safe minimums for the exponential model
        % or use a pure step if they are very small.
        tr = max(rise_time, 1e-6);
        tf = max(fall_time, 1e-6);

        % Use fwhm as the "on" duration
        excitation = zeros(size(t));
        idx_rise = find(t < fwhm);
        if ~isempty(idx_rise)
            % Growth towards 1
            excitation(idx_rise) = 1 - exp(-t(idx_rise)/tr);
            % Ensure it actually reaches 1 if fwhm is long enough,
            % or at least has a peak value at the switch point.
            peak_val = 1 - exp(-fwhm/tr);

            % Fall from the switch point
            idx_fall = t >= fwhm;
            excitation(idx_fall) = peak_val * exp(-(t(idx_fall) - fwhm)/tf);
        else
            % If fwhm is extremely small (sub-dt), at least set the first point
            excitation(1) = 1.0;
        end

        % Robustness check: if all zeros (due to sampling), force at least the start
        if all(excitation == 0), excitation(1) = 1.0; end

    case 'gaussian'
        mu = fwhm / 2;
        sigma = fwhm / (2 * sqrt(2 * log(2)));
        if sigma < 1e-6, sigma = 1e-6; end
        excitation = exp(-((t - mu).^2) / (2 * sigma^2));

    otherwise
        error('Unsupported excitation profile: %s', profile);
end

%%%
if bPulseTrain
    pulse_train = zeros(size(t));
    % Center pulses at 0, Trep, 2*Trep...
    % Trep must be positive
    Trep = max(PT_Trep, 1e-3);
    for center = 0:Trep:max(t)
        pulse_train = pulse_train + exp(-((t - center).^2) / (2*max(PT_sigma, 1e-6)^2));
    end
else
    pulse_train = ones(size(t));
end

%%%

% Normalize excitation to unit area (optional here, but keeping raw magnitude)
excitation = excitation .* pulse_train;

end
