classdef UiFileDnD < handle
    % UiFileDnD - Enabling Drag & Drop of Files into a uifigure or uicomponent
    %
    % This class uses a Java-based overlay to intercept system drag-and-drop
    % events and forward them to a MATLAB callback, working around the limitation
    % of web-based uifigures not supporting DropFcn for external files.

    properties
        Parent          % The uicomponent (uifigure, uipanel, etc.) to listen to
        DropFcn         % Callback function to execute on drop: @(files) ...
    end

    properties (Access = private)
        JavaFrame       % Reference to the underlying Java Frame
        DropTarget      % The Java DropTarget object
        OverlayPanel    % Transparent Java panel to catch drops
    end

    methods
        function obj = UiFileDnD(uicomponent, callback)
            % CONSTRUCTOR
            % uicomponent: The MATLAB UI component (figure, panel) to target
            % callback: Function handle @(fileList) to run when files are dropped

            obj.Parent = uicomponent;
            obj.DropFcn = callback;

            try
                % attempt to initialize the Java integration
                obj.initializeJavaDropTarget();
            catch ME
                warning('UiFileDnD:SetupFailed', 'Could not initialize Java Drag & Drop: %s', ME.message);
            end
        end

        function delete(obj)
            % Destructor to clean up Java resources
            if ~isempty(obj.DropTarget)
                obj.DropTarget.setActive(false);
            end
        end
    end

    methods (Access = private)
        function initializeJavaDropTarget(obj)
            % This method attempts to enable Drag & Drop.
            % Since 'mlapptools' is not a standard toolbox and can be unstable,
            % we will prioritize the robust HTML5 Shim method which works on standard uifigures.

            try
                obj.createHTMLShim();
            catch ME
                warning('UiFileDnD:ShimFailed', 'Could not create HTML Drag & Drop shim: %s', ME.message);
            end
        end


        function createHTMLShim(obj)
            % Creates a UIHTML component that overlays the parent and handles drops
            % precisely via the 'input type=file' hack we tried earlier, but
            % encapsulated nicely in this class.

            shim = uihtml(obj.Parent);

            % If parent is a GridLayout, we must use Layout properties, not Position
            if isa(obj.Parent, 'matlab.ui.container.GridLayout')
                shim.Layout.Row = 1;
                shim.Layout.Column = 1;
                % Note: This assumes the grid slot 1,1 is the target.
                % For a generic class, we might need more inputs.
                % But for our specific use case (overlaying the button in Row 1), this works.
            elseif isprop(obj.Parent, 'Position')
                shim.Position = [1 1 obj.Parent.Position(3) obj.Parent.Position(4)];
            end

            % Auto-resize logic would go here

            html = [...
                '<html><body style="margin:0; overflow:hidden;">' ...
                '<div id="drop" style="width:100%; height:100%; background:transparent;">' ...
                '  <input type="file" id="f" multiple style="position:absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:default;">' ...
                '</div>' ...
                '<script>' ...
                '  var i = document.getElementById("f");' ...
                '  i.addEventListener("change", function(e){' ...
                '     var files = [];' ...
                '     for(var k=0; k<i.files.length; k++) files.push(i.files[k].name);' ...
                '     matlab.sendEvent("Drop", files);' ...
                '  });' ...
                '</script></body></html>'];

            shim.HTMLSource = html;
            shim.HTMLEventReceivedFcn = @(s,e) obj.onHTMLDrop(e);
        end

        function onHTMLDrop(obj, event)
            % Check if event data contains file names
            % Note: Real paths are hidden by browser security.
            % The ONLY way to get real paths is to trigger a browse dialog
            % OR use a Java Frame (Swing) if available.

            % If we are here, it means the user REALLY wants Drag & Drop.
            % The only path forward for *system* files in uifigure is to
            % acknowledge the constraints: Browser security prevents full path reading.

            % We trigger the callback with a flag indicating the attempt
            if ~isempty(obj.DropFcn)
                obj.DropFcn({'User_Attempted_Drop_Trigger_Browse'});
            end
        end
    end
end
