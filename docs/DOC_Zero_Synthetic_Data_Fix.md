# Issue: Synthetic Data Generation Resulting in Zeros

## Symptoms
After changing instrument profiles in HILIGHTer (especially when switching to high-bins TCSPC or Custom Gating profiles), clicking the **GENERATE** button resulted in the synthetic data being entirely populated by zeros.

## Root Causes

### 1. Excitation Profile Sub-sampling (Primary Cause)
The `DTexcitation.m` function's implementation of the "Rectangular" profile was mathematically correct but numerically fragile. When the simulation time-step (`dt`) was large compared to the pulse width (`FWHM`) or the rise/fall times, the logic failed to find any time indices where the pulse was active. This caused the excitation signal to be all zeros, and since the simulation is a convolution of this signal with a decay, the result was always zero.

### 2. Custom Gate Type Detection
The instrument loading logic in `applyInstrumentToDT.m` used a strict `strcmpi(..., 'Custom')` check. Many saved instrument profiles used labels like "Custom (max 8)", which caused the application to ignore the custom gate widths. This led to a mismatch between the expected number of gates and the actual data structure.

### 3. Numerical Instability in Normalization
In `DTpdf.m`, the convolution of the IRF and the decay was normalized by dividing by the sum. If the IRF was zeroed out (as per cause #1), the sum would be zero, resulting in `NaN` or zero-filled data.

---

## Solutions Adopted

### 1. Robust Excitation Logic (`DTexcitation.m`)
*   **Minimum Duration Guard**: Added a fallback that if `FWHM` is smaller than the simulation resolution, it forces at least the first frame to be active (`excitation(1) = 1.0`).
*   **Safe Parameters**: Clamped `rise_time` and `fall_time` to a minimum of `1e-6` to avoid division-by-zero or infinite slopes.
*   **Pulse Train Alignment**: Corrected the pulse train logic to ensure it starts exactly at `t=0`, which is critical for periodic excitation consistency.

### 2. Fuzzy Gate Detection (`applyInstrumentToDT.m`)
*   Changed the gate type check to `contains(lower(...), 'custom')`. This ensures that any instrument profile labeled with "custom" (regardless of sub-text) correctly loads its specific gate widths.
*   Added automatic synchronization of `N_gates` based on the number of widths provided in the JSON profile.

### 3. Normalization Safeties (`DTpdf.m`)
*   Added a check `if sum(pdf) > 0` before normalization.
*   If the sum is zero (indicating a failure in the model calculation), it defaults to a delta function at the first bin rather than allowing `NaN` values to propagate.

### 4. Simulator UI Robustness (`HILIGHTer.m`)
*   **Lifetime Clamping**: Added `max(Value, 1)` to the ps-to-ns conversion in `onGenerate` to prevent zero or negative lifetimes from entering the mathematical models.
*   **Progress Feedback**: Integrated `uiprogressdlg` to provide visual feedback during the simulation process.
*   **Configuration Sync**: Added a final check in `onGenerate` to ensure `config.N_gates` is always in sync with the actual data dimensions produced by the instrument model.

## How to Revert or Verify
If this issue re-occurs:
1.  Check `DTexcitation(t, ...)` and ensure it returns a non-zero signal.
2.  Verify that `data.config.gate_edges` is populated correctly in the `HILIGHTer` figure's `UserData`.
3.  Ensure the chosen instrument's `gate_type` is correctly identified as 'custom' in `applyInstrumentToDT.m`.
