PROMPTS = {
    "precision-audit": {
        "name": "precision-audit",
        "description": "Audit theory, Monte Carlo validation, and bootstrap confidence intervals for the active precision sweep.",
        "template": (
            "You are controlling the HILIGHTer Digital Twin through MCP. "
            "Start by reading backend status, current config, and GUI schema. "
            "Run the precision workflow. "
            "Compare ideal, theory, and Monte Carlo outputs. "
            "If confidence intervals are present, use them instead of pointwise Monte Carlo values. "
            "Explicitly report regions where Monte Carlo compatibility is false at the configured estimator-accuracy threshold, "
            "and distinguish theory-only conclusions from statistically validated conclusions."
        ),
    },
    "instrument-design": {
        "name": "instrument-design",
        "description": "Design or refine an excitation, detection, and gating architecture for a target lifetime regime.",
        "template": (
            "Use the Digital Twin as an instrument-design copilot. "
            "Inspect the current configuration, GUI schema, and diagnostics. "
            "Identify the active target parameter and propose a sweep plan spanning excitation, detection, and gate settings. "
            "Run precision analysis, compare theory and Monte Carlo, and recommend the most robust design. "
            "Prioritize configurations that improve F-value while preserving Monte Carlo compatibility."
        ),
    },
    "data-inspection": {
        "name": "data-inspection",
        "description": "Inspect simulated data products, maps, diagnostics, and representative pixels.",
        "template": (
            "Use the Digital Twin data interfaces to inspect the current simulated state. "
            "Retrieve the data summary, full results snapshot, tau map, phasor map, theory locus, diagnostics snapshot, and one representative pixel analysis. "
            "Explain what these artifacts say about estimator behavior, instrument performance, and likely failure modes."
        ),
    },
    "workspace-navigation": {
        "name": "workspace-navigation",
        "description": "Guide a user or agent through the desktop workspace using the GUI schema and action identifiers.",
        "template": (
            "Use the GUI schema as the source of truth for the desktop workspace. "
            "When referencing controls, name the controller tab, action button, or plot region explicitly by its schema label and identifier. "
            "When proposing a workflow, map each step to concrete GUI elements such as RUN, EXPORT, TEST, or the Precision and Diagnostics widgets."
        ),
    },
}


def get_prompts():
    return PROMPTS
