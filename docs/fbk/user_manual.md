# User Manual: HILIGHTer FBK Edition

## Workflows

### Characterizing Gate Shapes
1. Open the app using `HILIGHTer_FBK_edition`.
2. Click **Import Gate Measurement** and select your `min_gate_measurement.csv`.
3. Click **Import Laser Pulse** and select `laser_236mW.csv`.
4. Choose **Experimental** or **Synthetic** from the **Gate Shape Method** dropdown to distill the shapes.
5. The **Gate Shapes** plot will update to show the 4 characterize gates.

### Performing Lifetime Analysis
1. Click **Import Sample Data** to load your image stack (SDT or MAT).
2. Set the **Threshold** (e.g., 50 counts) to ignore background pixels.
3. Click **Run Iterative Fit**.
4. Switch to the **Lifetime Maps** tab to view A, Tau, B, and Chi2 results.

## Technical Reference

- **Model**: $A \exp(-t/\tau) + B$.
- **Reconvolution**: Every gate count is predicted by numerically integrating the decay model over the specific time-domain profile of that gate.
- **Deconvolution**: Gate profiles are extracted by solving $(L * G = C)$ via regularized matrix inversion, where $L$ is the laser pulse and $C$ is the gate sweep measurement.
- **Fitting Algorithm**: 1D Golden Section search for $\tau$, with embedded linear regression for $A$ and $B$.
