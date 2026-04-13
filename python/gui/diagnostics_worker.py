import copy
from typing import Any, Dict, Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig


class DiagnosticsRefreshWorker(QThread):
    result_ready = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, config: PhysicsConfig, request_id: int, label: str = "Instrument snapshot"):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.request_id = int(request_id)
        self.label = str(label)

    def run(self):
        try:
            frame = self._build_frame(self.config, self.label)
            self.result_ready.emit(self.request_id, frame)
        except Exception as exc:
            self.failed.emit(self.request_id, str(exc))

    @staticmethod
    def _build_frame(config: PhysicsConfig, label: str) -> Dict[str, Any]:
        engine = TwinEngine(copy.deepcopy(config))
        engine.invalidate_grid()
        engine.distill_gates()
        tau_ref = engine.config.taus[0] if engine.config.taus else 2.5
        photon_budget = float(
            max(
                getattr(engine.config, "a_photons", 0.0)
                or getattr(engine.config, "precision_photons", 0.0)
                or 1000.0,
                1.0,
            )
        )
        latent_pdf_ref = engine.dt_pdf(engine.time_vector, tau_ref)
        pdf_ref = engine._effective_detected_pdf(
            latent_pdf_ref,
            photon_budget,
            engine.config,
        )
        histogram_diag = engine.build_deadtime_histogram_diagnostics(
            tau_ref,
            n_photons=photon_budget,
            correction_method=getattr(engine.config, "deadtime_correction_method", "none"),
            reference_pdf=latent_pdf_ref,
        )
        observed_hist_label: Optional[str] = None
        corrected_hist_label: Optional[str] = None
        if histogram_diag.get("observed_time_hist") is not None:
            observed_hist_label = "Observed Histogram"
            corrected_hist_label = None
            method = str(getattr(engine.config, "deadtime_correction_method", "none")).lower()
            if method == "isbaner_histogram":
                corrected_hist_label = "Corrected Histogram (Isbaner-lite)"
            elif method == "rapp_mchc":
                corrected_hist_label = "Corrected Histogram (Rapp (MCHC-lite))"
            elif method == "rapp_mchc_full":
                corrected_hist_label = "Corrected Histogram (Rapp (MCHC-full))"

        irf_cfg = copy.deepcopy(engine.config)
        irf_cfg.simulation_mode_preference = "ideal_poisson"
        irf_cfg.background_level = 0.0
        irf_cfg.decay_model = "exponential"
        irf_cfg.n_components = 1
        irf_cfg.taus = [1e-9]
        irf_cfg.amplitudes = [1.0]
        engine.config = irf_cfg
        irf_ref = engine.dt_pdf(engine.time_vector, tau=1e-9)
        return {
            "time_vec": np.array(engine.time_vector, copy=True),
            "gate_shapes": np.array(engine.gate_shapes, copy=True),
            "irf": np.array(irf_ref, copy=True),
            "pdf": np.array(pdf_ref, copy=True),
            "observed_hist": None
            if histogram_diag.get("observed_time_hist") is None
            else np.array(histogram_diag["observed_time_hist"], copy=True),
            "corrected_hist": None
            if histogram_diag.get("corrected_time_hist") is None
            else np.array(histogram_diag["corrected_time_hist"], copy=True),
            "observed_hist_label": observed_hist_label,
            "corrected_hist_label": corrected_hist_label,
            "label": label,
        }
