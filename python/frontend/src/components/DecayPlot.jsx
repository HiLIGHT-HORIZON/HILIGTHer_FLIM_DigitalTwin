import React from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

const DecayPlot = ({ data, title }) => {
  const factory = (createPlotlyComponent && createPlotlyComponent.default) || createPlotlyComponent;
  if (!factory || typeof factory !== 'function') {
      return <div className="widget-error">Plotly Factory Initialization Failed</div>;
  }
  const Plot = factory(Plotly);
  
  if (!data || !data.decay) {
    return (
      <div className="decay-placeholder">
        <p>Click on a pixel to view decay analysis</p>
      </div>
    );
  }

  const { centers, decay, fit, tau } = data;

  return (
    <div className="decay-container" style={{ width: '100%', height: '300px' }}>
      <Plot
        data={[
          {
            x: centers,
            y: decay,
            type: 'scatter',
            mode: 'markers+lines',
            name: 'Raw Counts',
            marker: { color: '#fbbf24', size: 8 },
            line: { color: '#fbbf24', width: 1 },
          },
          fit ? {
            x: centers,
            y: fit,
            type: 'scatter',
            mode: 'lines',
            name: 'Iterative Fit',
            line: { color: '#ef4444', width: 3 },
          } : null,
        ].filter(Boolean)}
        layout={{
          title: `Pixel Decay | τ: ${tau ? tau.toFixed(2) : 'N/A'} ns`,
          xaxis: { title: 'Time (ns)', gridcolor: '#334155' },
          yaxis: { title: 'Counts', gridcolor: '#334155', type: 'log' },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#94a3b8' },
          margin: { l: 50, r: 10, t: 40, b: 40 },
          legend: { orientation: 'h', y: -0.2 },
        }}
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

export default DecayPlot;
