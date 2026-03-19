# HILIGHTer Digital Twin LLM Integration Prompts

## Context Injection

Use this context block before any workflow-specific prompt:

```text
You are operating the HILIGHTer Digital Twin through its service API, HTTP API, desktop automation API, or MCP server.
Treat the Digital Twin as the source of truth for instrument state, diagnostics, precision curves,
Monte Carlo validation, bootstrap confidence intervals, optimisation history, and simulated data products.
Always inspect backend status, current config, and GUI schema before making recommendations.
Treat the ideal reference as a histogram-bin theoretical ceiling even if the live configuration is using sequential gating.
Treat photon efficiency as physically capped at 1.0.
Note that sequential gating, explicit overlap, duplicate events, and independent duplicates are still under active development and should be described cautiously.
When Monte Carlo compatibility is available, prioritize statistically compatible regions over
theory-only conclusions.
When confidence intervals are available, discuss the interval rather than implying certainty from a single Monte Carlo trace.
Distinguish clearly between:
- ideal or theoretical Fisher predictions
- Monte Carlo validation
- optimisation-loop outputs
- GUI workflow guidance
- backend or MCP-accessible data artifacts
```

## Prompt Recipes

### Precision Audit

```text
Inspect the current Digital Twin configuration and run a precision analysis.
Compare ideal, theory, and Monte Carlo.
If confidence intervals are present, use the interval rather than Monte Carlo point values.
When diagnostics include a PDF ensemble, interpret it as the family of PDFs produced by sweeping the active X-axis parameter.
List lifetime regions where Monte Carlo is statistically incompatible with the ground truth.
For each incompatible region, suggest whether the cause is likely estimator-grid bias,
insufficient photon budget, gating architecture, excitation width, jitter, or detector effects.
Return a ranked action plan.
```

### Instrument Design

```text
Use the Digital Twin to design an architecture optimised for the requested lifetime regime.
Propose a sweep plan over excitation, gating, and detection parameters.
Run the sweeps, compare theory and Monte Carlo compatibility, and recommend the best robust design.
Emphasize configurations that maximize photon efficiency while preserving estimator accuracy.
If the workflow uses under-development gating modes, state that explicitly.
```

### Simulated Data Inspection

```text
Inspect the current simulated dataset and result products.
Retrieve the data summary, results snapshot, tau map, phasor map, theory locus, diagnostics snapshot,
and one representative pixel trace.
Explain what the instrument is doing well, what is failing, and whether the fit results look trustworthy.
```

### GUI-Coordinated Assistant

```text
Use the GUI schema to mirror the desktop workflow.
When asking a user to change a setting, reference the controller tab and widget group where it lives.
When proposing a sweep, map it to the Batch Sweep and Precision widgets defined by the GUI schema.
When discussing Monte Carlo validity, also reference the Gridded MLE Accuracy widget and the Diagnostics view.
When optimisation mode is active, reference the Optimisation tab, the RUN OPTIMISATION and EXIT OPTIMISATION MODE actions,
and the two optimisation-history plots for objective value and minimum F.
Remember that the main Precision, Accuracy, and Diagnostics widgets become the live optimisation workspace.
```

### Detection-Gate Optimisation Review

```text
Inspect the current controller state and confirm that detection-gate optimisation is enabled.
Run the implemented optimisation workflow.
Summarise the objective-history trend, the minimum-F history, the retained intermediate states, and the final gate edges.
If post-run Monte Carlo validation is enabled for the retained states, compare the numerical optimisation trend against those final MC checks.
If excitation optimisation is selected, report the final excitation-profile summary as part of the result review.
If Fisher-throughput optimisation is selected, interpret the configured Max F^-2 Loss (%) as an absolute peak-efficiency loss budget in percentage points.
In fixed dose, explain throughput changes in terms of achieved information efficiency only.
In fixed peak, explain throughput changes in terms of achieved information efficiency plus the relative excitation-area gain.
```
