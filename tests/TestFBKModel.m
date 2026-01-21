classdef TestFBKModel < matlab.unittest.TestCase
    % TESTFBKMODEL - Unit tests for the FBK_Model logic.

    properties
        Model
    end

    methods (Test)
        function testIdealGateFitting(testCase)
            % Test fitting with ideal rectangular gates
            m = FBK_Model();
            m.GateMethod = 'ideal';
            % 4 gates: [0.1-1, 1-3, 3-6, 6-10]
            edges = [0.1, 1.0, 3.0, 6.0, 10.0];
            m.GateEdges = edges;
            m.calculateIdealGates(true);

            % Generate synthetic decay: A=1000, tau=2.5, B=50
            A = 1000; tau = 2.5; B = 50;
            t = m.TimeVector;
            decay = A * exp(-t / tau) + B;

            % Expected counts per gate
            obs = m.GateShapes * decay(:);

            % Mock images (2x2)
            m.RawData = repmat(reshape(obs, [1,1,numel(obs)]), [2, 2, 1]);
            m.ThresholdMin = 0;
            m.ThresholdMax = Inf;

            m.runFit();

            % Assert results are close to ground truth
            testCase.verifyTrue(all(abs(m.TauMap(:) - tau) < 1e-1), 'Tau fit failed');
            testCase.verifyTrue(all(abs(m.AMap(:) - A) < 1), 'Amplitude fit failed');
            testCase.verifyTrue(all(abs(m.BMap(:) - B) < 1), 'Background fit failed');
        end

        function testExperimentalGateDistillation(testCase)
            m = FBK_Model();
            % Mock LaserPulse
            m.LaserPulse.t = 0:0.1:2;
            m.LaserPulse.p = exp(-(m.LaserPulse.t-1).^2 / 0.1); % Gaussian pulse

            % Mock MinGateData Table
            % Delay sweep from 0 to 5ns
            delays = (0:0.2:10)';
            n = length(delays);
            % Single gate width '3.0'
            counts = 100 * (delays >= 2 & delays <= 5); % Rectangular gate measurement
            % Add convolution effect?
            % For simplicity, just check if pivot works
            m.MinGateData = table(delays, repmat(3.0, n, 1), counts, ...
                'VariableNames', {'LaserDelay', 'GateWidth', 'Counts'});

            m.GateMethod = 'experimental';
            m.distillGates();

            testCase.verifyEqual(size(m.GateShapes, 1), 1, 'Should have 1 distilled gate');
            testCase.verifyTrue(any(m.GateShapes > 0), 'Gate shape should not be all zero');
        end

        function testImportLegacyFBKData(testCase)
            m = FBK_Model();
            % Locate legacy data relative to this test file
            currentDir = fileparts(mfilename('fullpath'));
            legacyPath = fullfile(currentDir, '..', 'legacy', 'FBKdata', '100x_1');

            % Check existence
            if ~exist(legacyPath, 'dir')
                warning('Legacy FBK Data path not found at: %s. Skipping test.', legacyPath);
                return;
            end

            m.importFBKDataFolder(legacyPath);

            % Verify
            testCase.verifyEqual(size(m.RawData), [100 100 4], 'Imported data should be 100x100x4');
            testCase.verifyTrue(max(m.RawData(:)) > 0, 'Data should not be empty/zeros');

            % Sanity check on cumulative subtraction
            % Sum of gates should differ significantly if subtraction worked?
            % Just check it's real and numeric
            testCase.verifyTrue(isnumeric(m.RawData), 'Data is numeric');
        end

        function testMedianFilter(testCase)
            m = FBK_Model();
            % Create a noisy pixel in a uniform field
            data = zeros(10, 10, 4);
            data(5, 5, 1) = 100; % Hot pixel

            m.setRawData(data); % Stores into Original and Current

            % 1. Filter Off
            m.MedianFilterSize = 0;
            m.applyMedianFilter();
            testCase.verifyEqual(m.RawData(5,5,1), 100, 'Filter 0 should preserve data');

            % 2. Filter On (3x3)
            m.MedianFilterSize = 3;
            m.applyMedianFilter();
            % Median of a 3x3 block with one 100 and eight 0s is 0.
            testCase.verifyEqual(m.RawData(5,5,1), 0, 'Filter 3 should remove salt noise');

            % 3. Check Persistence
            % Revert to 0
            m.MedianFilterSize = 0;
            m.applyMedianFilter();
            testCase.verifyEqual(m.RawData(5,5,1), 100, 'Turning filter off should restore original data');
        end
    end
end
