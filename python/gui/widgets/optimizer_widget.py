import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
                             QPushButton, QLabel, QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from typing import Optional, Tuple

class OptimizationWorker(QThread):
    """Worker thread to run the optimization without freezing the UI."""
    finished = pyqtSignal(tuple)
    progress = pyqtSignal(float)
    
    def __init__(self, engine, n_gates, t_max, tau_range, n_restarts):
        super().__init__()
        self.engine = engine
        self.n_gates = n_gates
        self.t_max = t_max
        self.tau_range = tau_range
        self.n_restarts = n_restarts
        
    def run(self):
        try:
            results = self.engine.optimize_gates(
                n_gates=self.n_gates,
                t_max=self.t_max,
                tau_range=self.tau_range,
                n_restarts=self.n_restarts,
                callback=self.progress.emit
            )
            self.finished.emit(results)
        except Exception as e:
            print(f"Optimization Thread Error: {e}")
            self.finished.emit((None, 0.0, {}))

class OptimizerWidget(QWidget):
    """
    Ported Gate Optimizer Widget.
    Provides UI for finding ideal gate edges using numerical optimization.
    """
    gates_optimized = pyqtSignal(list) # Emitted when user clicks 'Export'

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("HILIGHT Detection Gate Optimizer")
        self.resize(1100, 750)
        
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- LEFT: Control Panel ---
        self.ctrl_panel = QWidget()
        ctrl_layout = QVBoxLayout(self.ctrl_panel)
        
        settings_group = QGroupBox("Optimization Settings")
        form_layout = QFormLayout(settings_group)
        
        self.spin_n_gates = QSpinBox()
        self.spin_n_gates.setRange(2, 512)
        self.spin_n_gates.setValue(4)
        form_layout.addRow("Number of Gates:", self.spin_n_gates)
        
        self.spin_t_max = QDoubleSpinBox()
        self.spin_t_max.setRange(1.0, 1000.0)
        self.spin_t_max.setValue(12.5)
        form_layout.addRow("Max Time (ns):", self.spin_t_max)
        
        self.spin_tau_min = QDoubleSpinBox()
        self.spin_tau_min.setRange(0.01, 100.0)
        self.spin_tau_min.setValue(0.5)
        form_layout.addRow("Tau Min (ns):", self.spin_tau_min)
        
        self.spin_tau_max = QDoubleSpinBox()
        self.spin_tau_max.setRange(0.1, 1000.0)
        self.spin_tau_max.setValue(5.0)
        form_layout.addRow("Tau Max (ns):", self.spin_tau_max)
        
        self.spin_restarts = QSpinBox()
        self.spin_restarts.setRange(1, 100)
        self.spin_restarts.setValue(10)
        form_layout.addRow("Restarts:", self.spin_restarts)
        
        ctrl_layout.addWidget(settings_group)
        
        self.btn_optimize = QPushButton("🚀 RUN OPTIMIZER")
        self.btn_optimize.setHeight = 40
        self.btn_optimize.setStyleSheet("font-weight: bold; height: 35px; background-color: #065f46; color: white;")
        self.btn_optimize.clicked.connect(self.run_optimization)
        ctrl_layout.addWidget(self.btn_optimize)
        
        self.btn_export = QPushButton("📤 Export to Main GUI")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_results)
        ctrl_layout.addWidget(self.btn_export)
        
        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setPlaceholderText("Results will appear here...")
        ctrl_layout.addWidget(self.txt_output)
        
        splitter.addWidget(self.ctrl_panel)
        
        # --- RIGHT: Plots ---
        self.plot_panel = QWidget()
        plot_layout = QVBoxLayout(self.plot_panel)
        
        # Gate Plot
        self.gate_plot = pg.PlotWidget(title="Optimized Gates & IRF")
        self.gate_plot.setBackground('k')
        self.gate_plot.setLabel('bottom', "Time [ns]")
        self.gate_plot.showGrid(x=True, y=True, alpha=0.3)
        plot_layout.addWidget(self.gate_plot)
        
        # Metric Plot
        self.metric_plot = pg.PlotWidget(title="Performance Comparison")
        self.metric_plot.setBackground('k')
        self.metric_plot.setLabel('left', "F-Value (Precison)")
        self.metric_plot.setLabel('bottom', "Tau [ns]")
        self.metric_plot.setLogMode(x=True, y=False)
        self.metric_plot.showGrid(x=True, y=True, alpha=0.3)
        plot_layout.addWidget(self.metric_plot)
        
        splitter.addWidget(self.plot_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        
        self.best_edges = None
        self.worker = None

    def run_optimization(self):
        """Prepares and starts the optimization worker thread."""
        self.btn_optimize.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.txt_output.setText("Optimization started...\n")
        
        n_gates = self.spin_n_gates.value()
        t_max = self.spin_t_max.value()
        tau_range = (self.spin_tau_min.value(), self.spin_tau_max.value())
        n_restarts = self.spin_restarts.value()
        
        self.worker = OptimizationWorker(self.engine, n_gates, t_max, tau_range, n_restarts)
        self.worker.progress.connect(lambda j: self.txt_output.append(f"Current J: {j:.6f}"))
        self.worker.finished.connect(self.on_optimization_finished)
        self.worker.start()

    def on_optimization_finished(self, results):
        self.btn_optimize.setEnabled(True)
        edges, j_val, info = results
        
        if edges is None:
            self.txt_output.append("\n❌ Optimization Failed.")
            return
            
        self.best_edges = edges.tolist()
        self.btn_export.setEnabled(True)
        
        # Print Summary
        out = f"\n✅ Optimization Complete.\nObjective J: {j_val:.6f}\n\nOptimal Edges (ns):\n"
        out += ", ".join([f"{e:.3f}" for e in edges])
        self.txt_output.append(out)
        
        self.update_plots(info)

    def update_plots(self, info):
        """Refreshes the visuals with optimization results."""
        self.gate_plot.clear()
        self.metric_plot.clear()
        
        t = info['t']
        profiles = info['gate_profiles']
        
        # Plot individual gates
        for i in range(profiles.shape[0]):
            color = pg.intColor(i, profiles.shape[0])
            self.gate_plot.plot(t, profiles[i, :], pen=pg.mkPen(color=color, width=2))
            
        # Plot F-Values
        tau_grid = info['tau_grid']
        f_val = info['f_val']
        self.metric_plot.plot(tau_grid, f_val, pen=pg.mkPen(color='#34d399', width=3), name="Optimized")
        
        # Add a baseline reference (y=1.0)
        self.metric_plot.addLine(y=1.0, pen=pg.mkPen(color='w', style=Qt.PenStyle.DashLine))

    def export_results(self):
        """Sends the optimized edges back to the main GUI."""
        if self.best_edges:
            self.gates_optimized.emit(self.best_edges)
            self.txt_output.append("\n✅ Gates exported successfully.")
