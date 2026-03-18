import React, { useEffect, useRef } from 'react';

const ImageView = ({ data, title, onPixelSelect, selectedPixel, roiMask }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!data || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const height = data.length;
    const width = data[0].length;

    canvas.width = width;
    canvas.height = height;

    const imageData = ctx.createImageData(width, height);
    
    const flatData = data.flat();
    const flatMask = roiMask ? roiMask.flat() : null;
    
    // Robust min/max calculation for large arrays
    let minVal = Infinity;
    let maxVal = -Infinity;
    for (let i = 0; i < flatData.length; i++) {
        const v = flatData[i];
        if (!isNaN(v) && v !== 0) {
            if (v < minVal) minVal = v;
            if (v > maxVal) maxVal = v;
        }
    }
    
    if (minVal === Infinity) { minVal = 0; maxVal = 1; }
    const range = maxVal - minVal || 1;

    for (let i = 0; i < flatData.length; i++) {
        const val = flatData[i];
        if (isNaN(val) || val === 0) {
            imageData.data[i * 4 + 3] = 0;
            continue;
        }
        const norm = (val - minVal) / range;
        
        imageData.data[i * 4] = norm * 255;
        imageData.data[i * 4 + 1] = norm * 200;
        imageData.data[i * 4 + 2] = 255 - norm * 255;
        
        if (flatMask && !flatMask[i]) {
            imageData.data[i * 4 + 3] = 40;
        } else {
            imageData.data[i * 4 + 3] = 255;
        }
    }

    ctx.putImageData(imageData, 0, 0);

    if (selectedPixel) {
        ctx.strokeStyle = '#f8fafc';
        ctx.lineWidth = 1;
        ctx.strokeRect(selectedPixel.x, selectedPixel.y, 1, 1);
    }
  }, [data, selectedPixel, roiMask]);

  const handleCanvasClick = (e) => {
    if (!canvasRef.current || !onPixelSelect) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * canvasRef.current.width);
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * canvasRef.current.height);
    onPixelSelect({ x, y });
  };

  return (
    <div className="image-view-card">
      <div className="card-header">
        <h3>{title}</h3>
      </div>
      <canvas 
        ref={canvasRef} 
        onClick={handleCanvasClick}
        style={{ 
          width: '100%', 
          aspectRatio: '1/1', 
          imageRendering: 'pixelated',
          border: '1px solid #334155',
          cursor: 'crosshair',
          borderRadius: '4px'
        }} 
      />
    </div>
  );
};

export default ImageView;
