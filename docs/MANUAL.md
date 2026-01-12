# HILIGHT FLIM Digital Twin: Comprehensive Manual

The **HILIGHT FLIM Digital Twin** is an agentic modeling suite for Fluorescence Lifetime Imaging Microscopy (FLIM). It provides a full "Digital Twin" of the hardware acquisition process, enabling the optimization of instrument parameters and the benchmarking of analysis algorithms.

---

## 1. Core Architecture

The project is divided into three functional layers:

### A. The Forward Model (Simulation)
These functions define the physics of the system:
*   `DTexcitation.m`: Generates the Instrument Response Function (IRF).
*   `DTpdf.m`: Convolves the IRF with an exponential decay.
*   `DTgates.m`: Defines the integration windows of the detector.
*   `DTpmod.m`: Combines the PDF and Gates to calculate discrete detection probabilities.

### B. The Inverse Problem (Analysis)
These algorithms retrieve the lifetime from the simulated data:
*   `DTmle.m`: **Maximum Likelihood Estimation**. Uses grid search against a library of `DTpmod` results.
*   `DTiterative.m`: **Iterative Reconvolution**. Pixel-wise least-squares fitting.

### C. Optimization & Evaluation
Tools for hardware design and system evaluation:
*   `DTcomputeFisherInfo.m`: Computes the **Fisher Information** matrix and **Cramér-Rao Lower Bound (CRLB)**—the absolute physical limit of precision ($1/\sqrt{I}$).

---

## 2. Simulation Modes (MockData_GUI)

The simulator allows benchmarking algorithms under two primary biological scenarios:

### Lifetime Gradient
*   **Description**: Simulates a linear gradient of a single fluorescent species.
*   **Behavior**: Each column of the image has the same lifetime. The lifetime varies linearly from **Lifetime 1** to **Lifetime 2** across the X-axis.
*   **Use Case**: Benchmarking estimator linearity and precision across a wide range of lifetimes.

### Lifetime Mix
*   **Description**: Simulates a mixture of two fluorescent species with distinct lifetimes.
*   **Behavior**: **Lifetime 1** and **Lifetime 2** are held constant. Their relative fractional contribution (amplitudes) varies linearly from 0% to 100% across the X-axis.
*   **Ground Truth**: For single-exponential fits, the ground truth is calculated as the intensity-weighted mean lifetime.
*   **Use Case**: Evaluating how single-exponential estimators handle complex multi-component decays.

---

## 3. High-Level Performance Metrics

### Background (Dark Counts)
*   You can specify a constant background level (Dark Counts) added to every gate. 
*   This simulates realistic detector noise floors and allows testing the robustness of estimators to non-signal photons.

### Standardized Residuals (Z)
*   **Definition**: $Z = (\tau_{estimated} - \tau_{true}) / \sigma_{theoretical}$.
*   $\sigma_{theoretical}$ is the CRLB calculated from the Fisher Information.

### 1 / Efficiency (Reduced $\chi^2$)
*   **$\chi^2_{red} \approx 1$**: The algorithm is perfectly **Efficient** (reaches the physical limit).
*   **$\chi^2_{red} > 1$**: The algorithm is sub-optimal or there is a mismatch in the model parameters.

### Randomness (Runs Test)
*   This evaluates the **Bias Trend** across the lifetime range.
*   **YES**: The estimation errors are purely stochastic.
*   **NO**: Errors show a systematic trend (Bias).

---

## 4. Interactive Pixel Analysis

The **MockData_GUI** includes a diagnostic tool for pixel-level inspection:
*   **Crosshair**: After clicking **ANALYSE**, you can click any pixel on the **Estimated Lifetime** map. A white crosshair will appear to mark your selection.
*   **Pixel Decay Plot**: A new plot appears at the bottom right showing:
    *   **Data (Blue Circles)**: The actual photon counts per gate for that specific pixel.
    *   **Fit (Black Line)**: The theoretical gated decay based on the estimated lifetime.
    *   **IRF (Grey Area)**: The normalized Instrument Response Function for timing reference.

---

## 5. Workflows (Experimental Analysis)

### Importing Data
1. Open the **Data > Groups** tab.
2. Click **Create Group** to select one or more FLIM files.
3. Click **Analyse** (Red Button) to load and process the data.
4. Data will appear in the **Data > Image** tab.

### Unified Navigation
1. Use the **Group** and **File** dropdowns in the **Image** tab to select your dataset.
2. Use the **Channel Navigation Bar** (bottom of Image tab) to cycle through spectral or polarization channels.
3. Switching channels automatically updates the context for all active **Analysis Tabs** (Phasor, Fit, etc.).

## 6. Technical Reference

| GUI Element | Tag | Algorithm / Reference |
| :--- | :--- | :--- |
| **Spectral Maps** | `dataPlotArea` | Displays projections (XY, XT) of the 4D hypercube $(x, y, t, c)$. |
| **Phasor Plot** | `axPhasorRun` | Harmonics $\mathcal{G}$ and $\mathcal{S}$ calculation. Uses `refreshPhasorPlot`. |
| **Grid MLE** | `pnlParams` | Brute-force lookup in `DTpmod` library. Optimal for low-count data. |
| **LiMA moments** | `axMu` | Non-parametric lifetime estimation via statistical moments. |
| **Fisher Maps** | `mapTg_Fisher` | Statistical optimality mapping ($1/\sqrt{I}$). |

---

## 7. Getting Started
1. Run `startup.m` to ensure all library paths are set.
2. Run `HILIGHTer.m` to launch the main application.
3. Use the **Simulator** tab for benchmarking and the **Data** tab for experimental analysis.
