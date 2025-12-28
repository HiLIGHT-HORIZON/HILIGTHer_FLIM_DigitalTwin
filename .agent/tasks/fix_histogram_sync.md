---
description: Fix proper bidirectional synchronization between histogram draggable lines and numeric spinners
---
The bidirectional synchronization between the draggable lines on the intensity histogram (Min, Max, Thresh) and the numeric spinners is currently one-way or flaky. 
- Spinner -> Line: Works (updating spinner moves line).
- Line -> Spinner: Fails or is inconsistent (dragging line does not consistently update spinner value).

Previous attempts involving `addlistener`, `ancestor` lookup, and passing explicit tab handles have not fully resolved the issue.

**Goal:**
Debug and fix the event handling and component reference logic to ensure that dragging a vertical line strictly and immediately updates the corresponding numeric input field.
