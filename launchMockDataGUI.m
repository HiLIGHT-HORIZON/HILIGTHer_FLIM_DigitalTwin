function launchMockDataGUI(TField, fwhmField, profileDropdown, toffField, rField, NGateField, ...
    NPhotonsField, MField, dtField, riseField, fallField, ...
    PTCheck, PTSField, PTTField, gFields, gateDropdown)

% Collect all settings into a struct
config.T            = TField.Value;
config.fwhm         = str2double(fwhmField.Value);
config.profile      = profileDropdown.Value;
config.toff         = toffField.Value;
config.r            = str2double(rField.Value);
config.N_gates      = str2double(NGateField.Value);
config.N_photons    = NPhotonsField.Value;
config.M            = MField.Value;
config.dt           = dtField.Value;
config.rise_time    = str2double(riseField.Value);
config.fall_time    = fallField.Value;
config.bPulseTrain  = PTCheck.Value;
config.PT_sigma     = PTSField.Value;
config.PT_Trep      = PTTField.Value;
config.gate_type    = gateDropdown.Value;

% Handle custom gates
if strcmp(config.gate_type, 'Custom (max 8)')
    % Reconstruct gate edges from widths
    % Custom: reconstruct from widths
    % The fields contain WIDTHS, so we cumsum them starting from 0.
    widths = [];
    count = min(8, config.N_gates);
    for i = 1:count
        widths = [widths, gFields(i).Value];
    end
    config.gate_edges = [0, cumsum(widths)];
else
    % Equal gates: explicitly generate them here to pass consistent 'gate_edges' to GUI
    % Equal gates fill the space from 0 to toff (Last gate edge)
    config.gate_edges = linspace(0, config.toff, config.N_gates + 1);
end

% Launch the new GUI
MockData_GUI(config);
end
