import React, { useState, useCallback } from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';
import Widget from './Widget';

const FisherPlot = ({ data }) => {
  const [logX, setLogX] = useState(false);
  const [logY, setLogY] = useState(false);
  const [revision, setRevision] = useState(0);

  const factory = (createPlotlyComponent && createPlotlyComponent.default) || createPlotlyComponent;
  if (!factory || typeof factory !== 'function') {
      return <div className="widget-error">Plotly Factory Initialization Failed</div>;
  }
  const Plot = factory(Plotly);
  
  const resetAxes = useCallback(() => {
    setRevision(prev => prev + 1);
  }, []);

  if (!data || !data.tau) {
    return (
      <Widget title="Instrument Precision (F-Value)">
        <div className="placeholder">Loading Fisher Analysis...</div>
      </Widget>
    );
  }

  const actions = (
    <div className="fisher-actions" style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
      <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
        <input type="checkbox" checked={logX} onChange={e => setLogX(e.target.checked)} /> Log X
      </label>
      <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
        <input type="checkbox" checked={logY} onChange={e => setLogY(e.target.checked)} /> Log Y
      </label>
      <button 
        onClick={resetAxes}
        style={{ 
          background: 'rgba(59, 130, 246, 0.2)', 
          border: '1px solid var(--accent)', 
          color: 'var(--accent-vibrant)',
          borderRadius: '4px',
          padding: '2px 8px',
          fontSize: '0.7rem',
          cursor: 'pointer'
        }}
      >
        Reset
      </button>
    </div>
  );

  return (
    <Widget title="Instrument Precision (F-Value)" actions={actions}>
      <div className="fisher-container" style={{ width: '100%', height: '350px' }}>
        <Plot
          data={[
            {
              x: data.tau,
              y: data.f_value,
              type: 'scatter',
              mode: 'lines+markers',
              name: 'F-Value (Precision)',
              line: { color: '#8b5cf6', width: 3, shape: 'hv' },
              marker: { size: 4, color: '#c084fc' },
              fill: 'tozeroy',
              fillcolor: 'rgba(139, 92, 246, 0.1)'
            }
          ]}
          layout={{
            xaxis: { 
              title: { text: 'Lifetime (ns)', font: { size: 12 } },
              type: logX ? 'log' : 'linear', 
              gridcolor: '#1e293b',
              zerolinecolor: '#334155',
              autorange: true
            },
            yaxis: { 
              title: { text: 'F-Value', font: { size: 12 } },
              type: logY ? 'log' : 'linear',
              gridcolor: '#1e293b',
              zerolinecolor: '#334155',
              autorange: true
            },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#94a3b8', family: 'Inter' },
            margin: { l: 45, r: 10, t: 10, b: 40 },
            datarevision: revision,
            autosize: true
          }}
          config={{
            displayModeBar: false,
            responsive: true
          }}
          useResizeHandler={true}
          style={{ width: '100%', height: '100%' }}
        />
      </div>
    </Widget>
  );
};

export default FisherPlot;
