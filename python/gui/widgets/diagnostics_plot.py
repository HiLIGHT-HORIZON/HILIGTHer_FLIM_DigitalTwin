import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QScrollArea, QCheckBox, QFrame, QLabel, QPushButton)
from PyQt6.QtCore import Qt, QTimer

class DiagnosticsWidget(QWidget):
    """
    Visualizes the raw physics of the instrument:
    - Gate Shapes (Time-gating profiles)
    - IRF (Laser Pulse / Electronic response)
    - PDF (Theoretical Decay for a reference lifetime)
    
    Includes a master toggle for gates rather than individual selection.
    """
    def __init__(self):
        super().__init__()
        root_layout = QVBoxLayout(self)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Prev")
        self.btn_prev.clicked.connect(lambda: self.step_frame(-1))
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(lambda: self.step_frame(1))
        self.lbl_frame = QLabel("Instrument snapshot")
        self.chk_autoplay = QCheckBox("Auto-play")
        self.chk_autoplay.setChecked(True)
        self.chk_autoplay.stateChanged.connect(self._on_autoplay_changed)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.lbl_frame, 1)
        nav_layout.addWidget(self.chk_autoplay)
        root_layout.addLayout(nav_layout)

        main_layout = QHBoxLayout()
        root_layout.addLayout(main_layout)
        
        # 1. Plot Area
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('k')
        self.plot_widget.setLabel('bottom', 'Time (ns)')
        self.plot_widget.setLabel('left', 'Relative Amplitude')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        main_layout.addWidget(self.plot_widget, stretch=4)
        
        # 2. Controls / Legend Panel (Right)
        self.controls_panel = QFrame()
        self.controls_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.controls_panel.setMinimumWidth(160)
        self.controls_layout = QVBoxLayout(self.controls_panel)
        self.controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.controls_panel)
        main_layout.addWidget(scroll, stretch=1)
        
        # Master Controls
        self.controls_layout.addWidget(QLabel("<b>Display Options</b>"))
        
        self.irf_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#22d3ee', width=2),
            name="Excitation (IRF)"
        )
        self.chk_irf = self._add_master_toggle("Show IRF", self.irf_curve, "#22d3ee")
        
        self.pdf_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='w', width=3, style=Qt.PenStyle.DashLine),
            name="Theoretical Reference"
        )
        self.chk_pdf = self._add_master_toggle("Show Ref PDF", self.pdf_curve, "white")
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        self.controls_layout.addWidget(line)
        
        # The Master Gate Toggle
        self.chk_gates = QCheckBox("Show Time Gates")
        self.chk_gates.setChecked(True)
        self.chk_gates.setStyleSheet("font-weight: bold; color: #3b82f6;")
        self.chk_gates.stateChanged.connect(self._on_gates_toggle)
        self.controls_layout.addWidget(self.chk_gates)
        
        # Registry for dynamic gate curves
        self.gate_curves = []
        self.frames = []
        self.current_frame_index = -1
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(1000)
        self._playback_timer.timeout.connect(lambda: self.step_frame(1))
        self._update_nav_enabled()

    def _add_master_toggle(self, label, curve, color=None):
        chk = QCheckBox(label)
        chk.setChecked(True)
        if color:
            chk.setStyleSheet(f"color: {color}; font-weight: bold;")
        chk.stateChanged.connect(lambda state: curve.setVisible(state == Qt.CheckState.Checked.value))
        self.controls_layout.addWidget(chk)
        return chk

    def _on_gates_toggle(self, state):
        visible = (state == Qt.CheckState.Checked.value)
        for c in self.gate_curves:
            c.setVisible(visible)

    def update_plot(self, time_vec, gate_shapes, irf=None, pdf=None, label=None):
        """Updates the diagnostic view with master gate control."""
        # Clear old gates
        for c in self.gate_curves:
            self.plot_widget.removeItem(c)
        self.gate_curves = []
        
        # Plot Gate Shapes
        colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4']
        num_gates = gate_shapes.shape[0]
        
        gates_visible = self.chk_gates.isChecked()
        
        for i in range(num_gates):
            color = colors[i % len(colors)]
            c = self.plot_widget.plot(
                time_vec, gate_shapes[i, :],
                pen=pg.mkPen(color=color, width=1.5),
                fillLevel=0,
                brush=pg.mkBrush(color=color + '44')
            )
            c.setVisible(gates_visible)
            self.gate_curves.append(c)
            
        # Update Static Data
        if irf is not None:
            irf_norm = irf / np.max(irf) if np.max(irf) > 0 else irf
            self.irf_curve.setData(time_vec, irf_norm)
        
        if pdf is not None:
            pdf_norm = pdf / np.max(pdf) if np.max(pdf) > 0 else pdf
            self.pdf_curve.setData(time_vec, pdf_norm)
        if label:
            self.lbl_frame.setText(label)

    def clear_frames(self):
        self.frames = []
        self.current_frame_index = -1
        self._playback_timer.stop()
        self.lbl_frame.setText("Instrument snapshot")
        self._update_nav_enabled()

    def set_sweep_frames(self, frames):
        self.frames = list(frames)
        if self.frames:
            self.set_frame(0)
        else:
            self.clear_frames()
        self._update_nav_enabled()
        self._on_autoplay_changed()

    def append_frame(self, frame, focus=True):
        self.frames.append(frame)
        self._update_nav_enabled()
        if focus:
            self.set_frame(len(self.frames) - 1)

    def set_frame(self, index):
        if not self.frames:
            return
        self.current_frame_index = index % len(self.frames)
        frame = self.frames[self.current_frame_index]
        self.update_plot(
            frame["time_vec"],
            frame["gate_shapes"],
            irf=frame.get("irf"),
            pdf=frame.get("pdf"),
            label=frame.get("label"),
        )
        self._update_nav_enabled()

    def update_current_frame(self, frame):
        if not self.frames:
            self.frames = [frame]
            self.current_frame_index = 0
        elif self.current_frame_index < 0:
            self.frames.append(frame)
            self.current_frame_index = len(self.frames) - 1
        else:
            if self.current_frame_index >= len(self.frames):
                self.frames.append(frame)
                self.current_frame_index = len(self.frames) - 1
            else:
                self.frames[self.current_frame_index] = frame
        self.set_frame(self.current_frame_index)

    def pause_playback(self):
        self._playback_timer.stop()

    def resume_playback(self):
        self._on_autoplay_changed()

    def step_frame(self, step):
        if not self.frames:
            return
        self.set_frame(self.current_frame_index + step)

    def _update_nav_enabled(self):
        enabled = len(self.frames) > 1
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.chk_autoplay.setEnabled(enabled)

    def _on_autoplay_changed(self, *_):
        if self.chk_autoplay.isChecked() and len(self.frames) > 1:
            self._playback_timer.start()
        else:
            self._playback_timer.stop()
