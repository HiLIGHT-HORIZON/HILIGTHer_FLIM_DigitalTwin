import React, { useState } from 'react';
import axios from 'axios';

const DatasetManager = ({ onImportComplete, API_BASE }) => {
  const [sessionName, setSessionName] = useState('default_session');
  const [uploading, setUploading] = useState(false);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      const res = await axios.post(`${API_BASE}/upload/sdt`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert('SDT Imported Successfully!');
      onImportComplete();
    } catch (err) {
      console.error('Import failed', err);
      alert('Import failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
    }
  };

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
      onImportComplete();
    } catch (err) {
      alert('Load failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="dataset-manager">
      <section className="manager-section">
        <h3>BECKER & HICKL IMPORT</h3>
        <label className="file-input-label">
          {uploading ? 'Uploading...' : '📁 Select SDT File'}
          <input type="file" accept=".sdt" onChange={handleFileUpload} disabled={uploading} style={{ display: 'none' }} />
        </label>
      </section>

      <section className="manager-section">
        <h3>HDF5 SESSION PERSISTENCE</h3>
        <div className="control-group">
            <input 
                type="text" 
                value={sessionName} 
                onChange={e => setSessionName(e.target.value)}
                placeholder="Session Name" 
            />
        </div>
        <div className="action-buttons horizontal">
            <button className="run-btn secondary" onClick={handleLoad}>📂 Load</button>
            <button className="run-btn primary" onClick={handleSave}>💾 Save</button>
        </div>
      </section>
    </div>
  );
};

export default DatasetManager;
