# Architecture & Intent: HILIGHTer FBK Edition

## Intention
The `HILIGHTer_FBK_edition` is a specialized branch of the HILIGHTer project designed for the FBK partner institution. Its primary goal is to perform high-precision lifetime fitting using **experimental gate shapes** and **iterative reconvolution**. Unlike the main HILIGHTer application, this edition focuses on a specific 4-gate hardware setup and provides advanced "gate distillation" tools to model synthetic gate shapes from laboratory measurements.

## Architectural Boundaries (MVC)

### Model (`src/FBK_Model.m`)
- **Responsibility**: Holds all mathematical state, loaded CSV data, and fitting logic.
- **Independence**: Must be testable without the GUI. No `app` object references allowed here.

### View (`app/HILIGHTer_FBK_edition.mlapp`)
- **Responsibility**: Visualization of gates, fits, and result maps (A, Tau, B, Chi2).
- **Thinness**: Callbacks must only invoke methods on the `FBK_Model`.

### Logic Layer
- Reuses `DTiterative.m` mechanisms but adapts them for the $A \exp(-t/\tau) + B$ model where $B$ can be either a fitted parameter or a pre-determined background.

## Technical Goals
- **Gate Distillation**: Converting raw gate sweep measurements (counts vs. laser delay) into time-domain gate profiles.
- **Iterative Reconvolution**: Calculating the expected gate counts by convolving the model decay with the experimental IRF and integrating over the gate shape.
- **Persistence**: Saving the hardware-specific gate characterization to avoid re-importing on every session.
