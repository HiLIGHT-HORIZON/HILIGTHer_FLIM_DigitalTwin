
function setElapsedAndRemaining(elapsedLabel, remainingLabel, current, total, elapsed)
    % Calculate progress
    progress = current / total;

    % Estimate remaining time
    if progress > 0
        eta = (elapsed / progress) - elapsed;
    else
        eta = NaN;
    end

    % Update GUI labels
    elapsedLabel.Text = sprintf('Elapsed time: %.1f s', elapsed);
    if isnan(eta)
        remainingLabel.Text = 'Remaining time: calculating...';
    else
        remainingLabel.Text = sprintf('Remaining time: %.1f s', max(0, eta));
    end

    drawnow limitrate;
end
