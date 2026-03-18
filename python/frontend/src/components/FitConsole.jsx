import React from 'react';

const FitConsole = ({ simParams, setSimParams, onMethodChange }) => {
  return (
    <section className="control-section fitting-section">
      <h3>Fitting Strategy</h3>
      <div className="control-group">
        <label>Method:</label>
        <select 
            value={simParams.fit_method} 
            onChange={e => {
                setSimParams({...simParams, fit_method: e.target.value});
                if(onMethodChange) onMethodChange(e.target.value);
            }}
        >
          <option value="mle">Iterative Recon (MLE)</option>
          <option value="tail">Rapid Tail Fit (Log-Linear)</option>
          <option value="phasor" disabled>Phasor Mapping (G/S)</option>
        </select>
      </div>
      
      <div className="method-info">
          {simParams.fit_method === 'mle' ? (
              <small>🔍 Uses numerical convolution with IRF. Accurate but slower.</small>
          ) : (
              <small>⚡ Fits the decay tail after IRF. Near-instantaneous.</small>
          )}
      </div>
    </section>
  );
};

export default FitConsole;
