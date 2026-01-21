# Architecture Intent Map: HILIGHTer

This document defines the architectural intent of the HILIGHTer application components, as required by Rule 23.

## Core Design Philosophy: Unified Data Flow
The application has transitioned from a simulation-only tool to a dual-mode platform. All data (Synthetic and Experimental) is channeled through the **Unified Data Model**.

| Component | Intention | Responsible Function(s) |
| :--- | :--- | :--- |
| **Unified State** | Provides a single source of truth for the app's state, preventing "context drift." | `flows_getData`, `flows_setData` |
| **Image Tab** | The "Master View." It handles navigation across groups, files, and channels. It DOES NOT perform analysis; it triggers it. | `createImageTabInterface`, `refreshUnifiedPlots` |
| **Analysis Tabs** | Specialized "Worker Views." They perform mathematical operations on slices of data provided by the Image Tab context. | `createNewFitTab`, `createNewPhasorTab`, `createNewLimaTab` |
| **Context Sync** | Ensures that switching a channel in the Image Tab updates the internal state of all background Analysis tabs. | `updateAnalysisContext`, `navChannel` |

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







## FBK Edition Specifics (HILIGHTer_FBK_edition)
| Component | Intention | Responsible Function(s) |
| :--- | :--- | :--- |
| **FBK_Model** | Domain model for FBK-specific physics (Gate fitting, fractional background). Inherits `handle` for reference semantics. | `src/FBK_Model.m` |
| **Legacy Import** | Translates proprietary FBK binary format (cumulative gates) into standard `(Y,X,Gate)` histograms. | `importFBKDataFolder` |
