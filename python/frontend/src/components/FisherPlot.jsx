import React from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

const FisherPlot = ({ data }) => {
  const factory = (createPlotlyComponent && createPlotlyComponent.default) || createPlotlyComponent;
  if (!factory || typeof factory !== 'function') {
      return <div className="widget-error">Plotly Factory Initialization Failed</div>;
  }
  const Plot = factory(Plotly);
  
  if (!data || !data.tau) {
    return <div className="placeholder">Loading Fisher Analysis...</div>;
  }

  return (
    <div className="fisher-container" style={{ width: '100%', height: '400px' }}>
      <Plot
        data={[
          {
            x: data.tau,
            y: data.f_value,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'F-Value (Precision)',
            line: { color: '#8b5cf6', width: 3 },
            marker: { size: 6 }
          }
        ]}
        layout={{
          title: 'Instrument Precision (F-Value)',
          xaxis: { title: 'Lifetime (ns)', type: 'log', gridcolor: '#334155' },
          yaxis: { title: 'F-Value', gridcolor: '#334155' },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#94a3b8' },
          margin: { l: 50, r: 10, t: 40, b: 40 },
        }}
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

export default FisherPlot;
