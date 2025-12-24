function gate_profiles = DTgates(t, r, gate_edges)
% DTGATES - Generate time-dependent gate profiles using sigmoid transitions
% Inputs:
%   t - time vector
%   r - rise/decay time (ns)
%   gate_edges - array of gate edges (ns)

    N_gates = numel(gate_edges)-1;
    sigmoid = @(x) 1 ./ (1 + exp(-x));
    gate_profiles = zeros(N_gates, length(t));

    for i = 1:N_gates
        a = gate_edges(i);
        b = gate_edges(i+1);
        gate_start = sigmoid((t - a) / r);
        gate_end   = sigmoid((t - b) / r);
        gate_profiles(i, :) = gate_start .* (1 - gate_end);
    end
end