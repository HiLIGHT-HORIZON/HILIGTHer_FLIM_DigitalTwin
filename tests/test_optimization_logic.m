% test_optimization_logic.m
% Simple test script to verify DToptimizeGates runs and outputs valid gates

clc; clear;

% Defines params
N_gates = 4;
T_max = 50;
tau_range = [0.5, 5];
irf.fwhm = 5;
irf.profile = 'Rectangular';
irf.rise_time = 0;
irf.fall_time = 0;
irf.bPulseTrain = false;
irf.PT_Trep = 10;
irf.PT_sigma = 1;

gate.rise_time = 0.001;

opt.n_restarts = 5; % Keep low for quick test

fprintf('Running optimization test...\n');

try
    [best_edges, best_J, info] = DToptimizeGates(N_gates, T_max, tau_range, irf, gate, opt);
    
    fprintf('Success!\n');
    fprintf('Best Objective: %f\n', best_J);
    fprintf('Edges: %s\n', mat2str(best_edges, 4));
    
    % Validation checks
    if length(best_edges) ~= N_gates + 1
        error('Wrong number of edges returned.');
    end
    
    if any(diff(best_edges) < 0)
        error('Gate edges are not monotonic.');
    end
    
    if best_edges(1) < 0 || best_edges(end) > T_max
        error('Gate edges out of bounds [0, T_max].');
    end
    
    fprintf('Validation passed: Gates are monotonic and within bounds.\n');
    
    % Check Fisher Info
    if any(info.fisher_info < 0) || any(isnan(info.fisher_info))
        error('Fisher Information contains negative or NaN values.');
    end
    fprintf('Fisher Information seems valid (non-negative).\n');
    
catch ME
    fprintf('Error during test: %s\n', ME.message);
    rethrow(ME);
end
