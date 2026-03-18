import React from 'react';

const Widget = ({ title, children, className = '', actions = null }) => {
  return (
    <div className={`widget-card ${className}`}>
      <div className="widget-header">
        <h3 className="widget-title">{title}</h3>
        {actions && <div className="widget-actions">{actions}</div>}
      </div>
      <div className="widget-content">
        {children}
      </div>
    </div>
  );
};

export default Widget;
