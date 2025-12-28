# HILIGHTer Future Tasks

## Mask Editor Integration
- **Status**: Partially Implemented, currently disabled.
- **Description**: Enable the "Edit Mask" button in the Data tab to allow users to manually refine the background mask using morphological operations.
- **Current State**:
    - `MaskEditor.m` file exists and is functional (modal GUI for dilation, erosion, etc.).
    - `onEditMask` callback exists in `HILIGHTer.m`.
    - `CustomMask` logic is implemented in `refreshAllPlots` and `onThresholdAction`.
- **Issue**: The callback does not seem to trigger reliably in the current environment, possibly due to persistent state or callback wiring issues.
- **Steps to Complete**:
    1. Verify callback wiring in `createDataTab`.
    2. Debug the execution flow from Button -> `onEditMask` -> `MaskEditor`.
    3. Enable the button in `createDataTab`.
