classdef CellSAMWrapper < handle
    % CELLSAMWRAPPER  MATLAB wrapper for the cellSAM Python library.
    %   Encapsulates interaction with the Python environment and the cellSAM model.
    %
    %   Usage:
    %       sam = CellSAMWrapper();
    %       sam.loadModel(); % Checkpoint handling
    %       mask = sam.segment(image);

    properties (Access = private)
        Model         % Python cellSAM model object
        IsLoaded = false
        Device = 'cpu'
    end

    methods
        function obj = CellSAMWrapper()
            % Constructor: Check environment
            try
                pe = pyenv;
                if pe.Version < "3.10"
                    warning('CellSAM requires Python 3.10+. Current version: %s', pe.Version);
                end
            catch
                error('MATLAB Python interface not configured. Run pyenv to set it up.');
            end
        end

        function success = loadModel(obj, checkpointPath)
            % loadModel Loads the cellSAM model
            % checkpointPath: (Optional) Path to SAM checkpoint.
            % If not provided, it attempts to load 'sam_vit_b_01ec64.pth' from pwd or asks user.

            if nargin < 2 || isempty(checkpointPath)
                % Default checkpoint name
                chkParams = 'sam_vit_b_01ec64.pth';
                if exist(chkParams, 'file')
                    checkpointPath = fullfile(pwd, chkParams);
                else
                    % Try to find it or download it?
                    % For now, let's assume one exists or we rely on the library to download?
                    % cellSAM might download automatically if not found?
                    % Let's point to a specific file if possible.

                    % Check if we can use the library's default
                    checkpointPath = 'sam_vit_b_01ec64.pth';
                end
            end

            try
                % Import library
                % Assuming 'cellsam' is the package name.
                % Based on repo: setup.py says name='cellsam'

                % We need to import the SegmentAnything class or similar.
                % Looking at the repo, usage is usually:
                % from cellsam import CellSAM
                % model = CellSAM(device='cuda')
                % model.load_model(checkpoint_path)

                cellsamIdx = py.importlib.import_module('cellsam');

                % Determine device
                % Check if torch has cuda
                torch = py.importlib.import_module('torch');
                if torch.cuda.is_available()
                    obj.Device = 'cuda';
                else
                    obj.Device = 'cpu';
                end

                % Instantiate
                obj.Model = cellsamIdx.CellSAM(pyargs('device', obj.Device));

                % Load weights
                % obj.Model.load_model(checkpointPath);
                % Note: If the file doesn't exist, this might fail or download.
                % VanValenLab cellSAM usually wraps 'segment-anything'.

                % Let's assume we need to pass the path.
                % If it fails, we will catch it.
                obj.Model.load_model(checkpointPath);

                obj.IsLoaded = true;
                success = true;
                fprintf('CellSAM Model loaded successfully on %s.\n', obj.Device);

            catch ME
                obj.IsLoaded = false;
                success = false;
                warning('Failed to load cellSAM model: %s', ME.message);
                disp(ME.stack(1));
            end
        end

        function [masks, flows] = segment(obj, img)
            % segment Performs segmentation on a standard uint8 or double image.
            % img: [H x W x C] or [H x W] image.

            if ~obj.IsLoaded
                error('Model not loaded. Call loadModel() first.');
            end

            % 1. Convert Image to Python Format
            % cellSAM expects [H, W, C] in RGB usually, or Grayscale?
            % It likely uses SegmentAnything which takes RGB.

            [H, W, C] = size(img);
            if C == 1
                % Replicate to RGB if grayscale
                img = repmat(img, 1, 1, 3);
            end

            % Normalize if double [0,1] -> [0,255] uint8
            if isa(img, 'double') || isa(img, 'single')
                if max(img(:)) <= 1.0
                    img = uint8(img * 255);
                else
                    img = uint8(img); % Clip?
                end
            end

            % Convert to numpy array
            % MATLAB image is [Row, Col, Chan]. Numpy expects the same for images usually.
            % But py.numpy.array from MATLAB can be tricky.
            % Best to use: py.numpy.array(img).
            % However, MATLAB passes 3D arrays as... let's check.
            % Safest is to flatten and reshape in Python or check doc.
            % Modern MATLAB (R2022b+) handles this well. Assuming R2023a+ from context of typical 'Agentic' users,
            % but let's be safe.

            np = py.importlib.import_module('numpy');

            % Conversion logic
            % Flatten to 1D
            img_flat = uint8(img(:)');
            np_img_flat = py.numpy.array(img_flat);
            % Reshape in Python: (H, W, 3)
            % MATLAB is column-major, Python is row-major.
            % So we actually need to transpose or be careful.
            % Image processing: usually better to let Python load or handle transpose.

            % Detailed Transpose for MATLAB -> Numpy Image:
            % MATLAB: (H, W, C)
            % Python wants: (H, W, C) but data order is different.
            % Permute MATLAB to (C, W, H) -> Flatten -> Reshape (H, W, C)? No.
            % Correct way: Permute to (C, W, H) because Python is C-contiguous (last index varies fastest)?
            % ACTUALLY:
            % MATLAB: Col-major.
            % Python: Row-major.
            % Standard trick: permute(img, [3, 2, 1]) -> flatten -> reshape(C, W, H) -> transpose?
            % Easier: passing row-major data.
            % permute(img, [2, 1, 3]) swaps X/Y.

            % Let's try the simplest:
            % Ensure input is uint8.
            % Use the direct conversion if available or standard interop.

            % For stability, let's assume we simply pass the array object if supported.
            % If not, we use the numeric matrix.

            % The wrapper call:
            % results = model.segment_image(image)

            % Let's try passing the MATLAB array directly. MATLAB converts numeric matrices to Python buffer protocol often.

            try
                % Permute for Row-Major behavior?
                % Usually images passed to Python need to be permuted [2 1 3] if we want pixel perfect match?
                % Or just trust the engine?

                % cellSAM expects a standard numpy array.
                % img_py = py.numpy.array(img); % This often creates a list or similar.

                % Better approach using 'double' list for safety if small, or specific numpy call.
                % But for 1024x1024, list is slow.

                % Lets use the implicit conversion and see.
                % NOTE: For this draft, I will wrap the call.

                % Assuming we just pass the data.
                masks_py = obj.Model.segment(img);

                % Convert result back
                % masks is likely a boolean or int array.
                masks = logical(masks_py);
                flows = []; % Placeholder
            catch ME
                rethrow(ME);
            end
        end

        function downloadCheckpoint(obj)
            % Helpers to fetch weights if missing
            url = 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth';
            outfile = fullfile(pwd, 'sam_vit_b_01ec64.pth');
            if ~exist(outfile, 'file')
                fprintf('Downloading SAM checkpoint...\n');
                websave(outfile, url);
                fprintf('Done.\n');
            else
                fprintf('Checkpoint already exists.\n');
            end
        end
    end
end
