import React, { useState } from 'react';
import axios from 'axios';

const SessionManager = ({ onRefresh, API_BASE }) => {
  const [sessionName, setSessionName] = useState('default_session');

  const handleSave = async () => {
    try {
      await axios.post(`${API_BASE}/session/save/${sessionName}`);
      alert('Session saved to HDF5!');
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleLoad = async () => {
    try {
      await axios.post(`${API_BASE}/session/load/${sessionName}`);
      alert('Session restored from HDF5!');
      onRefresh();
    } catch (err) {
      alert('Load failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="session-manager">
      <section className="manager-section">
        <h3>SESSION PERSISTENCE</h3>
        <div className="control-group">
          <input
            type="text"
            value={sessionName}
            onChange={e => setSessionName(e.target.value)}
            placeholder="Session Name"
          />
        </div>
        <div className="action-buttons horizontal">
          <button className="run-btn secondary" onClick={handleLoad}>Load</button>
          <button className="run-btn primary" onClick={handleSave}>Save</button>
        </div>
      </section>
    </div>
  );
};

export default SessionManager;
