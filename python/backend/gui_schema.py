GUI_SCHEMA = {
    "workspace": {
        "id": "hilighter_desktop",
        "title": "HILIGHTer Digital Twin Desktop Workspace",
        "regions": [
            {
                "id": "controller_column",
                "title": "Digital Twin Controller",
                "elements": [
                    {"id": "tab_decay_model", "type": "controller_tab", "label": "Decay Model"},
                    {"id": "tab_images", "type": "controller_tab", "label": "Images"},
                    {"id": "tab_excitation", "type": "controller_tab", "label": "Excitation"},
                    {"id": "tab_detection", "type": "controller_tab", "label": "Detection"},
                    {"id": "tab_optimization", "type": "controller_tab", "label": "Optimisation"},
                    {"id": "tab_batch_sweep", "type": "controller_tab", "label": "Batch Sweep"},
                    {"id": "action_optimise_run", "type": "action_button", "label": "RUN OPTIMISATION"},
                    {"id": "action_optimise_exit", "type": "action_button", "label": "EXIT OPTIMISATION MODE"},
                    {"id": "action_profiles", "type": "action_button", "label": "Profiles"},
                    {"id": "action_run", "type": "action_button", "label": "RUN"},
                    {"id": "action_interrupt", "type": "action_button", "label": "Interrupt"},
                    {"id": "action_export", "type": "action_button", "label": "SAVE AS"},
                    {"id": "action_test", "type": "action_button", "label": "TEST"},
                ],
            },
            {
                "id": "analysis_stack",
                "title": "Analysis Stack",
                "elements": [
                    {"id": "widget_precision", "type": "plot", "label": "Precision (Fisher Info)"},
                    {"id": "widget_accuracy", "type": "plot", "label": "Gridded MLE Accuracy"},
                    {"id": "widget_diagnostics", "type": "plot", "label": "Instrument Diagnostics"},
                    {"id": "widget_optimisation_objective", "type": "plot", "label": "Optimisation Objective History"},
                    {"id": "widget_optimisation_min_f", "type": "plot", "label": "Optimisation Minimum F History"},
                ],
            },
            {
                "id": "bottom_row",
                "title": "Imaging and Pixel Analysis",
                "elements": [
                    {"id": "widget_map", "type": "image", "label": "Lifetime Gradient Map"},
                    {"id": "widget_decay", "type": "plot", "label": "Single Pixel Decay / Fit"},
                    {"id": "widget_phasor", "type": "plot", "label": "Phasor Space (G vs S)"},
                ],
            },
        ],
    }
}


def get_gui_schema():
    return GUI_SCHEMA
