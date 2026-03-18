# HILIGHT-HORIZON: MATLAB to Python Translation Plan

This document outlines the strategic milestones for translating the HILIGHTer Digital Twin platform from MATLAB to Python, ensuring architectural decoupledness and strict physics parity.

## 🏗️ Architectural Strategy
We will transition from a monolithic MATLAB App Designer architecture to a **Modern Decoupled Stack**:
- **Backend**: Python 3.11+ (NumPy, SciPy, Numba, Core Physics).
- **Frontend**: Native Python Desktop Application (PyQt6, pyqtgraph, napari) matching the FIREFLY architecture.
- **Data Layer**: HDF5 or Zarr for hypercube storage; internal dataclasses/pydantic for state.

---

## 🚩 Milestone 1: Environment & Physics Validation Shield
**Goal**: Establish the testing framework to ensure "Same Physics" throughout the translation.
- [ ] **Data Export Utility**: Create a MATLAB script to export "Ground Truth" datasets (4D hypercubes + results) in `.json` and `.mat` for Python ingest.
- [ ] **Parity Testing Workspace**: Setup a Python environment with PyTest.
- [ ] **CI Pipeline**: Automated checks for mathematical parity (MATLAB output vs. Python output).

## 🚩 Milestone 2: Unified Data Model (The "State" Layer)
**Goal**: Replicate the MATLAB `Unified Data Model` using Pythonic structures.
- [ ] **Data Hierarchy Definition**: Port the `d.Conditions{i}.Analysis(f).Data` structure to Pydantic models.
- [ ] **File I/O Layer**: Implement `read_SDT` and FBK binary importers in Python.
- [ ] **Storage Engine**: Migrate from nested structs to a high-performance blob storage (HDF5 or Zarr).

## 🚩 Milestone 3: Mathematics & Physics Core (The "Logic" Layer)
**Goal**: Port core mathematical models while maintaining 1:1 numerical parity.
- [ ] **Phasor Engine**: Port time-to-frequency domain mapping (Universal Circle logic).
- [ ] **Fitting Engines**: 
    - Port `Grid MLE` and `Tail Fit`.
    - Implement `Iterative Reconvolution` using SciPy's optimization suite.
- [ ] **FBK Model**: Translate `FBK_Model.m` to a core Python class inheriting from a base `PhysicsModel`.
- [ ] **Numba Optimization**: Apply JIT compilation to bottleneck loops (e.g., decay convolution).

## 🚩 Milestone 4: Backend API & Analysis Workers
**Goal**: Expose the physics core via an asynchronous API.
- [ ] **FastAPI Wrapper**: Expose `getChannelData` logic as API endpoints.
- [ ] **Task Queue**: (Optional) Use Celery or BackgroundTasks for heavy fitting operations to keep the UI responsive.
- [ ] **WebSocket Sync**: Real-time context updates (e.g., channel switching updates all analysis components).

## 🚩 Milestone 5: Frontend - Desktop Design System & Master View
**Goal**: Build a premium, reactive interface mimicking the "Master View" intent using Qt.
- [ ] **UI/UX Design**: Draft layouts using PyQt6 QDockWidgets for modular, draggable panels.
- [ ] **Image Rendering**: Implement high-performance napari or pyqtgraph `RawImage` rendering for large 2D/3D datasets.
- [ ] **Unified State Management**: Use Qt Signals/Slots to sync group/channel selection across widget components.

## 🚩 Milestone 6: Analysis Worker Views (The "Specialized Widgets")
**Goal**: Port the specialized worker tabs as modular PyQt6 DockWidgets.
- [ ] **Phasor Widget**: Interactive phasor plot with ROI selection using `pyqtgraph`.
- [ ] **Fit Widget**: Parametric control panel linked to the MLE/Iterative backend using Qt input elements.
- [ ] **Decay Widget**: Real-time photon count and fit curve visualization.

## 🚩 Milestone 7: Integration & End-to-End Validation
**Goal**: Ensure the "Digital Twin" behaves identically to its progenitor.
- [ ] **Full-Stack Integration**: Connect the local Python backend engine directly to the PyQt6 frontend components.
- [ ] **Physics Recalibration**: Run the "Ground Truth" datasets through the Python stack and verify < 10^-8 error vs. MATLAB.
- [ ] **Performance Audit**: Ensure Python/Numba execution is as faster or faster than MATLAB MEX/JIT.

## 🚩 Milestone 8: Deployment & Documentation
**Goal**: Package the application for the Brunei HILIGHT-HORIZON team.
- [ ] **Dockerization**: Create a containerized version for easy deployment.
- [ ] **Complete Manual**: Update html manual for the Python-specific workflow.
- [ ] **Developer Guide**: Documentation for the decoupled architecture to facilitate future updates.

---

> [!IMPORTANT]
> **Strict Physics Rule**: No physics algorithm should be "improved" during the initial port. The goal is bit-for-bit parity first. Optimizations or model changes should follow only after parity is verified.
