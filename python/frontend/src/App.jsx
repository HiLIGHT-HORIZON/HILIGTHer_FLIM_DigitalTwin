import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import Widget from './components/Widget';
import PhasorPlot from './components/PhasorPlot';
import ImageView from './components/ImageView';
import DecayPlot from './components/DecayPlot';
import FisherPlot from './components/FisherPlot';
import SessionManager from './components/SessionManager';
import FitConsole from './components/FitConsole';

// This browser client still talks to the backend through a mix of current and
// compatibility endpoints. Keep it aligned with `python/backend/main.py`.
const API_BASE = 'http://localhost:8000';

function App() {
  console.log("App Initializing...");
  const [activeTab, setActiveTab] = useState('simulate');
  const [tauMap, setTauMap] = useState(null);
  const [phasorData, setPhasorData] = useState({ g: [], s: [] });
  const [locus, setLocus] = useState({ g: [], s: [] });
  const [fisherData, setFisherData] = useState(null);
  const [pixelAnalysis, setPixelAnalysis] = useState(null);
  const [selectedPixel, setSelectedPixel] = useState(null);
  const [loading, setLoading] = useState(false);
  const [simParams, setSimParams] = useState({ a: 2000, tau1: 1.0, tau2: 5.0, b: 25, res: 64 });
  const [instParams, setInstParams] = useState({ 
    timing_jitter: 0, 
    dnl_level: 0,
    detector_deadtime: 0,
    b_multihit_mode: true
  });
  const [roiMask, setRoiMask] = useState(null);
  const [simState, setSimState] = useState({ ...simParams, fit_method: 'mle' });

  useEffect(() => {
    fetchTheory();
    fetchFisher();
    onDataUpdate();
  }, []);

  const fetchTheory = async () => {
    try {
      const res = await axios.get(`${API_BASE}/theory/locus`);
      setLocus(res.data);
    } catch (err) {
      console.error("Failed to fetch theory", err);
    }
  };

  const fetchFisher = async () => {
    try {
      const res = await axios.get(`${API_BASE}/results/fisher/${simParams.a}`);
      setFisherData(res.data);
    } catch (err) {
      console.error("Failed to fetch fisher info", err);
    }
  };

  const onDataUpdate = async () => {
    try {
        const resTau = await axios.get(`${API_BASE}/results/tau`);
        const resPhasor = await axios.get(`${API_BASE}/results/phasor`);
        setTauMap(resTau.data.data);
        setPhasorData(resPhasor.data);
        setPixelAnalysis(null);
        setSelectedPixel(null);
    } catch (err) {
        // Data might not be available yet
    }
  };

  const handlePixelSelect = async (pixel) => {
    setSelectedPixel(pixel);
    try {
        const res = await axios.get(`${API_BASE}/results/pixel/${pixel.y}/${pixel.x}`);
        setPixelAnalysis(res.data);
    } catch (err) {
        console.error("Failed to fetch pixel analysis", err);
    }
  };

  const updateInstrumentConfig = async () => {
    await axios.post(`${API_BASE}/config/update`, {
        ...instParams,
        gate_edges: [0.0, 1.1, 3.4, 9.0, 25.0], // Sync defaults
        dt_input: 0.05
    });
  };

  const runSimulation = async (mode = 'basic') => {
    setLoading(true);
    try {
      const payload = { ...simParams, fit_method: simState.fit_method };
      if (mode === 'advanced') {
          await updateInstrumentConfig();
          await axios.post(`${API_BASE}/simulate/advanced`, payload);
      } else {
          await axios.post(`${API_BASE}/simulate`, payload);
      }
      onDataUpdate();
      fetchFisher();
    } catch (err) {
      console.error("Simulation failed", err);
    } finally {
      setLoading(false);
    }
  };

  const handleROIChange = async (roi) => {
      if (!roi) {
          setRoiMask(null);
          return;
      }
      try {
          const res = await axios.post(`${API_BASE}/results/roi`, roi);
          setRoiMask(res.data.mask);
      } catch (err) {
          console.error("ROI filtering failed", err);
      }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
            <h1>HILIGHTer Digital Twin | Python Ecosystem</h1>
            <nav className="header-tabs">
                <button 
                    className={`tab-btn ${activeTab === 'simulate' ? 'active' : ''}`}
                    onClick={() => setActiveTab('simulate')}
                >Simulator</button>
                <button 
                    className={`tab-btn ${activeTab === 'sessions' ? 'active' : ''}`}
                    onClick={() => setActiveTab('sessions')}
                >Sessions</button>
                <a 
                    href="/manual.html" 
                    target="_blank" 
                    className="tab-btn manual-link"
                    style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}
                >📖 Manual</a>
            </nav>
            <span className="status-badge">FPGA Emulator: Online</span>
        </div>
      </header>

      <main className="main-content">
        <aside className="controls-panel panel-glass">
          {activeTab === 'simulate' ? (
            <>
              <Widget title="Photon Statistics">
                <div className="control-group">
                    <label>Average Photons (A):</label>
                    <input type="number" value={simParams.a} 
                        onChange={e => setSimParams({...simParams, a: Number(e.target.value)})} />
                </div>
                <div className="control-group">
                    <label>Background (B):</label>
                    <input type="number" value={simParams.b} 
                        onChange={e => setSimParams({...simParams, b: Number(e.target.value)})} />
                </div>
                <div className="control-group">
                  <label>Lifetime Range (ns):</label>
                  <div className="input-row" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <input type="number" style={{ width: '60px' }} value={simParams.tau1} 
                      onChange={e => setSimParams({...simParams, tau1: Number(e.target.value)})} />
                    <span style={{ color: 'var(--text-muted)' }}>-</span>
                    <input type="number" style={{ width: '60px' }} value={simParams.tau2} 
                      onChange={e => setSimParams({...simParams, tau2: Number(e.target.value)})} />
                  </div>
                </div>
              </Widget>

              <Widget title="Analysis Mode">
                <FitConsole 
                    simParams={simState} 
                    setSimParams={setSimState} 
                />
              </Widget>

              <Widget title="Instrument Hardware">
                <div className="control-group">
                    <label>Jitter (RMS ps):</label>
                    <input type="number" value={instParams.timing_jitter} 
                        onChange={e => setInstParams({...instParams, timing_jitter: Number(e.target.value)})} />
                </div>
                <div className="control-group">
                    <label>DNL Level (%):</label>
                    <input type="number" value={instParams.dnl_level} 
                        onChange={e => setInstParams({...instParams, dnl_level: Number(e.target.value)})} />
                </div>
                <div className="control-group">
                    <label>Deadtime (ns):</label>
                    <input type="number" step="0.1" value={instParams.detector_deadtime} 
                        onChange={e => setInstParams({...instParams, detector_deadtime: Number(e.target.value)})} />
                </div>
                <div className="control-group checkbox-group">
                    <input type="checkbox" id="multihit" checked={instParams.b_multihit_mode} 
                        onChange={e => setInstParams({...instParams, b_multihit_mode: e.target.checked})} />
                    <label htmlFor="multihit">Multihit Support</label>
                </div>
              </Widget>

              <div className="action-buttons">
                <button className="run-btn secondary" onClick={() => runSimulation('basic')} disabled={loading}>
                  Monte Carlo (Ideal)
                </button>
                <button className="run-btn primary" onClick={() => runSimulation('advanced')} disabled={loading}>
                  ⚡ Instrument Sim
                </button>
              </div>
            </>
          ) : (
            <Widget title="Session Manager">
                <SessionManager 
                    API_BASE={API_BASE} 
                    onRefresh={onDataUpdate} 
                />
            </Widget>
          )}

          {pixelAnalysis && (
            <Widget title={`Pixel [${selectedPixel?.x}, ${selectedPixel?.y}]`} className="pixel-overlay-section">
                <DecayPlot data={pixelAnalysis} />
            </Widget>
          )}
        </aside>

        <section className="analysis-panel">
          <div className="plots-grid">
            <div className="plot-card">
               <FisherPlot data={fisherData} />
            </div>
            <div className="plot-card">
              <ImageView 
                data={tauMap} 
                title="Lifetime Gradient Map" 
                onPixelSelect={handlePixelSelect}
                selectedPixel={selectedPixel}
                roiMask={roiMask}
              />
            </div>
            <div className="plot-card wide-card">
              <PhasorPlot 
                g_data={phasorData.g} 
                s_data={phasorData.s} 
                locus_g={locus.g} 
                locus_s={locus.s} 
                onROIChange={handleROIChange}
              />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
