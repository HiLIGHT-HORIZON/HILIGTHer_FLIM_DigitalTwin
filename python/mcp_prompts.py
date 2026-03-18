PROMPTS = {
    "precision-audit": {
        "name": "precision-audit",
        "description": "Audit theory vs Monte Carlo precision and identify incompatible MC regions.",
        "template": (
            "You are controlling the HILIGHTer Digital Twin. "
            "First inspect backend status and current config. "
            "Then run the precision workflow, compare theory and Monte Carlo, "
            "and explicitly report any Monte Carlo points marked incompatible at the configured estimator-accuracy p-value threshold. "
            "Recommend instrument changes that improve compatibility and F-value together."
        ),
    },
    "instrument-design": {
        "name": "instrument-design",
        "description": "Optimize excitation, detection, and gating parameters for a requested lifetime regime.",
        "template": (
            "Use the Digital Twin as an instrument-design copilot. "
            "Read the GUI schema and current config, identify the active target parameter, "
            "and propose a batch sweep plan spanning excitation, detection, and gating. "
            "After running precision, summarize tradeoffs and the most robust architecture."
        ),
    },
    "data-inspection": {
        "name": "data-inspection",
        "description": "Inspect imported or simulated data products and explain what they mean.",
        "template": (
            "Use the Digital Twin data APIs to inspect the current dataset. "
            "Retrieve the data summary, tau map, phasor map, diagnostics snapshot, and one representative pixel. "
            "Explain what each artifact says about instrument behavior and estimator quality."
        ),
    },
}


def get_prompts():
    return PROMPTS
