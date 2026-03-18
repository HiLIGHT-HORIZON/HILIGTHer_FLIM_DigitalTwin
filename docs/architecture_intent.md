# Architecture Intent Map: HILIGHTer


## Core Design Philosophy: Unified Data Flow
The application has transitioned from a simulation-only tool to a dual-mode platform. All data (Synthetic and Experimental) is channeled through the **Unified Data Model**.

| Component | Intention | Responsible Function(s) |
| :--- | :--- | :--- |
| **Unified State** | Provides a single source of truth for the app's state, preventing "context drift." | `flows_getData`, `flows_setData` |
| **Image Tab** | The "Master View." It handles navigation across groups, files, and channels. It DOES NOT perform analysis; it triggers it. | `createImageTabInterface`, `refreshUnifiedPlots` |
| **Analysis Tabs** | Specialized "Worker Views." They perform mathematical operations on slices of data provided by the Image Tab context. | `createNewFitTab`, `createNewPhasorTab`, `createNewLimaTab` |
| **Context Sync** | Ensures that switching a channel in the Image Tab updates the internal state of all background Analysis tabs. | `updateAnalysisContext`, `navChannel` |

## Core Design Philosophy: Precision-First Logic
The Digital Twin has evolved from a simple Monte Carlo simulator to a target-oriented **Optimality Profiler**.

| Component | Intention | Logic |
| :--- | :--- | :--- |
| **Precision Analysis** | Evaluation of the **Cramér-Rao Lower Bound (CRLB)**. | Theoretical Fisher Matrix inversion based on model derivatives. |
| **Target Parameter** | the X-axis of our benchmarks. | One model parameter (e.g. \(\tau_1\)) is swept while others are fixed. |
| **Batch Instrumentation**| Evaluating hardware impact. | Sweeping instrument non-idealities (e.g. Jitter) to generate multiple precision curves. |
| **Synthetic Imaging** | Monte Carlo verification. | Generates repeated gated photon-count experiments and compares the recovered precision against the CRLB/F-value curve. |

## 1. Unified State & Models
All components share a pydantic `PhysicsConfig` state.
*   **Fix Flags**: Determines which parameters the inverse problem (MLE) treats as constants.
*   **F-Value Axis**: Selective targeting of which physical dimension is evaluated for precision.
*   **Decay wrapping**: A mathematical logic representing the pulse-train excitation. Signal tails from previous periods wrap into the current window. Default: **ON**.
*   **Measurement Period (\(T_{rep}\))**: The fundamental temporal window of the experiment (Standard: **50 ns / 20 MHz**). All simulations and visualizations are confined to this range.
*   **Sensor Dead-time / Read-out**: A predefined period where detection is inactive (Standard: **18 ns**).
*   **Burst Excitation**: A secondary high-frequency sub-structure. If active, the standard IRF (Gaussian/Rect) acts as a slow temporal envelope for a burst of ultra-fast pulses (Sweet spot: **5-7.5 ns**).
*   **Precision Workspace**: The desktop `RUN PRECISION` flow now acts as a combined theory-and-validation runner. It can:
    * compute the ideal reference and theoretical F-value curves,
    * optionally run Monte Carlo validation for single-exponential `tau1` sweeps,
    * update the precision plot incrementally while points are being computed,
    * update and cache instrument-diagnostics frames for each sweep configuration,
    * export the last completed precision session as an interactive HTML report.

## 2. Performance Benchmarks (Parity Targets)
Based on Deliverable 6.1 (T6.2), the system must validate against these "Gold Standard" configurations:

| configuration | Gate Edges (ns) | Target Performance |
| :--- | :--- | :--- |
| **8-Gate Reference** | Evenly spaced over 32 ns | Peak efficiency ~75% @ 4ns |
| **4-Gate Baseline** | Edges: [0, 8, 16, 24, 32] | ~40% efficiency @ 2ns |
| **4-Gate Optimized** | Edges: [0, 2.8, 7.5, 12.5, 32] | **~50% efficiency @ 2ns** |
*   **IRF Morphing**: Adaptive control over IRF geometry.
    *   **Gaussian**: Control over the **Center** of the peak.
    *   **Rectangular**: Control over the **Start** of the wave, with optional asymmetric Rise/Fall transitions.

## Frame Intentions & UIDs

### UID_Image_PlotArea
*   **Intent**: Visual identification of raw vs processed data.
*   **Interaction**: Click on the XY projection to trigger "Pixel Analysis" (visualizing the decay at that specific coordinate).

### UID_Phasor_Settings
*   **Intent**: Controls for the Phasor plot visualization (Harmonics, ROIs, Zoom).
*   **Physics Logic**: Maps time-domain decays to the complex unit circle.

### UID_Fit_ParamPanel
*   **Intent**: Configuration of numerical fitting engines.
*   **Mathematics**: Supports Grid MLE, Tail Fitting, and Iterative Reconvolution.

## Data Hierarchy & Retrieval Protocol
**CRITICAL**: All analysis functions must NOT inspect `fig.UserData` directly. They MUST use `getChannelData(fig, chanIdx)` to guarantee they are analyzing the data visible to the user.

### 1. Data Structure (The "Database")
Experimental and imported data resides in a nested structure within `fig.UserData`:
*   `d.Conditions{group_index}`: A cell array representing logical groups (Conditions).
*   `.Analysis(file_index)`: An array of structs representing individual files within a group.
*   `.Data`: **The Primary Data Blob**. This contains the 4D hypercube `[Y, X, T, Channels]`.
    *   **Access Path**: `d.Conditions{i}.Analysis(f).Data`.

### 2. Retrieval Logic (`getChannelData`)
The `getChannelData` function acts as the "Gatekeeper". It prioritizes data sources in this order:
1.  **Dynamic Lookup**: Uses `navGroup` and `navFile` indices to fetch `d.Conditions{navGroup}.Analysis(navFile).Data`.
2.  **Cached View**: `d.currentData` (The slice currently shown in the Image Tab).
3.  **Legacy/Simulation**: `d.RawData` (Output from the internal simulator).







