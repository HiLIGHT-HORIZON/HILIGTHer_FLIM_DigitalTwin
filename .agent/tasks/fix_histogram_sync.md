---
description: Fix proper bidirectional synchronization between histogram draggable lines and numeric spinners
---

The bidirectional synchronization between the draggable lines on the intensity histogram (`Min`, `Max`, `Thresh`) and the numeric spinners is currently one-way or flaky.

- Spinner to line: works.
- Line to spinner: fails or is inconsistent.

Previous attempts involving listener wiring, ancestor lookup, and passing explicit tab handles did not fully resolve the issue.

Goal:

Debug and fix the event handling and component reference logic so that dragging a vertical line strictly and immediately updates the corresponding numeric input field.
