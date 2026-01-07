# Simulation Configuration UI Refactor Request

## User Objective
Rationalize the Simulation Configuration Pane in HILIGHTer.

## Layout Requirements
1.  **Mode Selector** (Existing)
    *   Rename options:
        *   "FRET" -> "FRET (Donor FLIM)"
        *   "FRET 2-Channel" -> "seFRET (Donor/Acceptor FLIM)"
        *   "Anisotropy" -> "Time resolved anisotropy"
2.  **Configuration Manager** (New)
    *   Dropdown menu to save/load specific configurations.
3.  **Generate Button** (Moved)
    *   Placed immediately after Config Manager.
4.  **Size Controls**
    *   X and Y dimensions labeled.
    *   Spinners with increments in power of two (default 64).
    *   Remove "x2" and "/2" buttons.
    *   Add "1:1 aspect ratio" checkbox (default checked). Disables 2nd dimension spinner when checked.
5.  **Instrument Settings**
    *   Channel Number checkbox/spinner.
    *   Pixel Dwell Time.
    *   Dead Time.
6.  **Photon Statistics**
    *   Photons per pixel.
    *   Label: Count Rate.
    *   Label: Photons lost by pulse pile up (%).
    *   Checkbox: "Multihit" (default checked).
        *   Logic: Count multiple photons/cycle unless within deadtime.
7.  **Model Parameters**
    *   All specific model parameters follow here.
8.  **IRF & Wraparound**
    *   IRF Shift controls for *each* active channel.
    *   Checkbox: "Wrap decays" (Single control, default checked). Replaces "Wrap Channels".
    *   Checkbox: "Sync IRFs" (Default checked).
        *   Logic: When checked, only Ch1 shift is active; others follow Ch1.
9.  **Sweeping Controls**
    *   **Structure**:
        *   Checkbox: "Sweep X"
        *   Checkbox: "Sweep Y"
    *   **Per Axis**:
        *   Dropdown to select parameter to sweep (from available model params).
        *   Note: A parameter can only be swept along one direction.
        *   Start Value input.
        *   End Value input.
        *   Gradient Resolution input (Default = number of pixels in direction).
        *   Gradient Type: Linear (Default) or Non-linear.
        *   Padding Spinners (Start & End): Default 0, step 1. Adds reference data columns/rows.
    *   **Interaction**:
        *   When a parameter is selected for sweeping, its main input in "Model Parameters" is disabled.
        *   Example (2 Lifetimes): Option to sweep fractional contribution vs constant.

## Examples Provided
*   **Single Lifetime**: Sweep lifetime X left-to-right. Main lifetime input disabled.
*   **2 Lifetimes**: Sweep fractional contribution (Alpha).
    *   Padding 3 -> 3 columns Alpha=0, Gradient..., 3 columns Alpha=1.

## UI Design Note
*   Use tabbed groups if necessary for space.
