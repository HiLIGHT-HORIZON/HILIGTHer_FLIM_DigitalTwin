# HILIGHTer FBK Edition: User & Technical Manual

The **HILIGHTer FBK Edition** is a specialized version of the HILIGHTer suite designed for high-precision Fluorescence Lifetime Imaging Microscopy (FLIM) data analysis and detector characterization. It features advanced gate modeling, fractional background fitting, and hardware-aware simulation.

---

## 1. Interface Overview

The application is divided into two primary workspaces: **Gate Characterization** and **Data Analysis**.

### 1.1 Characterization & Settings (Left Panel)
*   **1. Import Sample Data**: Loads experimental multi-gate data (.sdt or .mat).
*   **Import FBK Legacy**: Loads data from the legacy FBK folder structure (4 binary files).
*   **2. IRF & Characterization**:
    *   **Import Gate Sweep**: Loads a hardware sweep CSV (multiple gate widths). 
    *   **Import Gates**: Loads the 4 exact experimental gate profiles as CSV.
    *   **Import Laser**: Loads the laser impulse response (IRF) CSV.
    *   **Distill Gate Shapes**: Analyzes hardware data to estimate internal kinetics.
    *   **Method Dropdown**:
        *   `Ideal`: Theoretical rectangular gates + manual skewness.
        *   `Experimental`: Uses loaded exact hardware profiles.
        *   `Synthetic`: Uses ideal boundaries smoothed by fitted hardware kinetics.
    *   **Gate Edges [ns]**: Set the temporal boundaries for integration. Default: `0, 1.1, 3.4, 9.0, 25.0` ns.
*   **3. Simulation Parameters**: Configure synthetic data generation (Amplitude, Background, Tau gradient, Resolution).
*   **4. Data Fitting**:
    *   **Background Mode**: Choice of `Fit` (analytical estimate), `Fix to Value` (manual count/pixel), `Gate 4` (estimate from 4th gate), or `Measurement` (external file).
    *   **Thresh (Min/Max)**: The analysis runs only on pixels where intensity is between Min/Max. Use the **Threshold On** dropdown to choose between `Total Counts` or `Gate 1` as the reference.
    *   **Run Fit**: Triggers the iterative reconvolution engine.

---

## 2. Mathematical Foundation

### 2.1 The Forward Model
The expected photons $F_j$ in gate $j$ for a lifetime $\tau$ are modeled as:
$$F_j(\tau, k) = D_{total} \left[ (1 - k) P_j(\tau) + k Q_j \right]$$

Where:
*   **$D_{total}$**: Total observed photons in the pixel.
*   **$k$**: Background fraction (fraction of total photons belonging to noise).
*   **$P_j(\tau)$**: Normalized Signal Profile. The convolution of the exponential decay with the IRF, integrated over the shape of Gate $j$.
*   **$Q_j$**: Normalized Background Profile. Represents uniform noise distributed according to the relative area of each gate.

### 2.2 Fractional Background Fitting
To maximize stability, the HILIGHTer FBK Edition uses **Fractional Fitting**. Instead of fitting amplitude and background as free parameters, it exploits the conservation of total counts. For any given lifetime $\tau$:
1.  The profiles $P_j$ and $Q_j$ are calculated.
2.  The optimal background fraction $k$ is solved **analytically** using Weighted Least Squares (WLS):
    $$ \min_k \sum w_j (Obs_j - F_j(k))^2 $$
3.  $k$ is constrained to $[0, 1]$, preventing non-physical negative results.

### 2.3 Hardware Characterization (Global Sweep Fit)
When a Gate Sweep is imported, the system characterizes the detector's electronic response using a **Global Gaussian-Rectangular** fit:
$$ S_i(t) \approx \text{Rect}(W_i) * \text{Gaussian}(\sigma) * \text{Laser}(t) $$
*   **Mirroring**: Experimental time axes are automatically mirrored to align the sweep with the physical decay direction.
*   **Global $\sigma$**: Fits a single shared smoothing kernel (jitter) across all gate widths.
*   **Individual $W_i$**: Refines the exact width of each swept gate.

---

## 3. Statistical Diagnostics

### 3.1 Standardized Residuals (Z-Scores)
Residuals are visualized on the Mixed Decay plot:
$$ Z_j = \frac{Obs_j - Pred_j}{\sqrt{\max(Pred_j, 1)}} $$
The Y-axis dynamically scales but maintains a minimum range of $[-5, 5]$ to highlight model accuracy.

### 3.2 Randomness (Runs Test)
The application automatically performs a **Runs Test** on the residuals to verify fit quality:
*   **YES (Green)**: The errors alternate signs frequently, indicating they are purely stochastic (Poisson noise).
*   **NO (Red)**: The errors show a systematic trend, indicating a mismatch between the model and the data (e.g., incorrect IRF or misaligned gates).

---

## 4. Workflows

### 4.1 Characterizing a New Detector
1.  Import your **Gate Sweep** CSV.
2.  Import your **Laser Pulse** CSV.
3.  Click **Distill Gate Shapes**. 
4.  Switch the **Method** to `Synthetic` to use the fitted kinetics for your analysis.

### 4.2 Analyzing Experimental Data
1.  Import your **Sample Data**.
2.  Set the **Threshold** (typically 10-50 photons).
3.  Click **Run Fit**.
4.  Navigate the **Fitting Maps** (Tau, A, B, Chi2) and click individual pixels to inspect the local decay and residuals.

### 4.3 Generating a Digital Twin
1.  Configure the **Simulation Parameters** (e.g., Tau 1: 1.5ns, Tau 2: 4.5ns).
2.  Click **Generate Simulated Data**.
3.  The system wipes previous results and populates the analysis window with a "ground truth" gradient, perfect for benchmarking your precision limits.

### 4.4 Loading Legacy FBK Data
1.  Click **Import FBK Legacy**.
2.  Select the folder containing the `image2D_G*.bin` files (e.g., `100x_1`).
3.   The data will be loaded, processed (cumulative subtraction), and visualized.
