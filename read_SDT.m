function [data, config] = read_SDT(filename)
% READ_SDT - Bio-Formats based multi-channel reader for HILIGHTer
% v3.1: Improved Series/Channel mapping and T/Z gate detection.

% 1. Add Bio-Formats to path if needed
basePath = fileparts(mfilename('fullpath'));
bfPath = fullfile(basePath, 'legacy', 'bfmatlab');
if ~exist('bfopen', 'file')
    addpath(bfPath);
end

% Ensure Java is ready
try
    bfCheckJavaPath();
catch
    jarPath = fullfile(bfPath, 'bioformats_package.jar');
    if ~any(strcmpi(javaclasspath, jarPath)), javaaddpath(jarPath); end
end

% 2. Open full data using bfopen
bfData = bfopen(filename);
if isempty(bfData)
    error('Bio-Formats could not open the file: %s', filename);
end

numSeries = size(bfData, 1);
r = bfGetReader(filename);
meta = r.getMetadataStore();

% Default Dimensions from Series 0
nX = meta.getPixelsSizeX(0).getValue();
nY = meta.getPixelsSizeY(0).getValue();
nT = meta.getPixelsSizeT(0).getValue();
nC = meta.getPixelsSizeC(0).getValue();
nZ = meta.getPixelsSizeZ(0).getValue();

% Determine Gate and Channel structure
% If multiple series, we often find 1 channel per series
if numSeries > 1 && nC == 1
    totalC = numSeries;
else
    totalC = nC * numSeries; % Fallback
end

% If T is 1 but Z > 1, the gates are likely in Z
if nT == 1 && nZ > 1
    actualGates = nZ;
    isGatesInZ = true;
else
    actualGates = nT;
    isGatesInZ = false;
end

fprintf('SDT Structure: %d series | %d x %d | gates=%d, channels=%d\n', ...
    numSeries, nX, nY, actualGates, totalC);

% Preallocate [Y, X, T, C]
data = zeros(nY, nX, actualGates, totalC);

% Fill data from all series
currC = 1;
for s = 1:numSeries
    seriesPlanes = bfData{s, 1};
    numPlanesInSeries = size(seriesPlanes, 1);

    r.setSeries(s-1);
    sNC = r.getSizeC();
    sNT = r.getSizeT();
    sNZ = r.getSizeZ();

    % Loop through planes in this series
    for t = 1:sNT
        for c = 1:sNC
            for z = 1:sNZ
                % getIndex is 0-based
                flatIdx = r.getIndex(z-1, c-1, t-1) + 1;

                if flatIdx <= numPlanesInSeries
                    planeData = double(seriesPlanes{flatIdx, 1});

                    % Determine target gate index and channel
                    if isGatesInZ
                        targetGate = z;
                        % If it's truly a Z-stack with T-gates, we sum Z or handle differently.
                        % For SDT, usually it's just gates.
                    else
                        targetGate = t;
                    end

                    targetChan = currC + c - 1;

                    if targetGate <= actualGates && targetChan <= totalC
                        % If it's a mix (Z and T both > 1), we sum into the gate
                        if (isGatesInZ && sNT > 1 && t > 1) || (~isGatesInZ && sNZ > 1 && z > 1)
                            data(:, :, targetGate, targetChan) = data(:, :, targetGate, targetChan) + planeData;
                        else
                            data(:, :, targetGate, targetChan) = planeData;
                        end
                    end
                end
            end
        end
    end
    currC = currC + sNC;
end
r.close();

% 4. Metadata Extraction (TAC range)
try
    metaMap = bfData{1, 2};
    tac_r = 12.5e-9;
    if metaMap.containsKey('TAC range')
        val = metaMap.get('TAC range');
        if ischar(val), val = str2double(val); end
        tac_r = val;
    elseif metaMap.containsKey('TacRange')
        val = metaMap.get('TacRange');
        if ischar(val), val = str2double(val); end
        tac_r = val;
    end
    config.T = double(tac_r) * 1e9;
catch
    config.T = 12.5;
end

if config.T <= 0 || isnan(config.T), config.T = 12.5; end

config.N_gates = actualGates;
config.gate_edges = linspace(0, config.T, actualGates + 1);
config.fwhm = 0.2;
config.profile = 'Gaussian';
config.r = 0.001;
config.rise_time = 0;
config.fall_time = 0;
config.bPulseTrain = false;
config.PT_Trep = 10;
config.PT_sigma = 0.05;
config.dt = config.T / actualGates;
config.filename = filename;
config.nChannels = totalC;

fprintf('Import Successful. Final Data Dims: %dx%dx%dx%d\n', size(data));

end
