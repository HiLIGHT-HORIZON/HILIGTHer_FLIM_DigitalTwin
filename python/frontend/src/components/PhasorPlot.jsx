import React from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

const PhasorPlot = ({ g_data, s_data, locus_g, locus_s, onROIChange }) => {
  const factory = (createPlotlyComponent && createPlotlyComponent.default) || createPlotlyComponent;
  if (!factory || typeof factory !== 'function') {
      return <div className="widget-error">Plotly Factory Initialization Failed</div>;
  }
  const Plot = factory(Plotly);
  
  const handleSelected = (event) => {
    if (event && event.range) {
      const { x, y } = event.range;
      onROIChange({
        g_min: x[0],
        g_max: x[1],
        s_min: y[0],
        s_max: y[1],
      });
    } else {
      onROIChange(null);
    }
  };

  return (
    <div className="phasor-container" style={{ width: '100%', height: '500px' }}>
      <Plot
        data={[
          {
            x: locus_g,
            y: locus_s,
            type: 'scatter',
            mode: 'lines',
            name: 'Universal Circle',
            line: { color: 'white', width: 2, dash: 'dash' },
          },
          {
            x: g_data.flat(),
            y: s_data.flat(),
            type: 'scattergl',
            mode: 'markers',
            name: 'Data Points',
            marker: { color: '#3b82f6', size: 3, opacity: 0.3 },
          },
        ]}
        layout={{
          title: { text: 'Phasor Space (G vs S)', font: { color: '#94a3b8' } },
          xaxis: { 
            title: 'G (cos)', 
            range: [-0.05, 1.05], 
            scaleanchor: 'y',
            gridcolor: '#1e293b',
            tickfont: { color: '#94a3b8' }
          },
          yaxis: { 
            title: 'S (sin)', 
            range: [-0.05, 0.55],
            gridcolor: '#1e293b',
            tickfont: { color: '#94a3b8' }
          },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          margin: { l: 40, r: 10, t: 40, b: 40 },
          dragmode: 'select',
          selectdirection: 'any',
        }}
        onSelected={handleSelected}
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

export default PhasorPlot;
