import React from 'react';
import './StatBox.css';

function StatBox({ label, value, icon: Icon, trend, color = 'blue' }) {
  return (
    <div className={`stat-box stat-box-${color}`}>
      <div className="stat-header">
        {Icon && <Icon className="stat-icon" size={24} />}
        <span className="stat-label">{label}</span>
      </div>
      <div className="stat-value">{value}</div>
      {trend && <div className={`stat-trend trend-${trend.direction}`}>{trend.text}</div>}
    </div>
  );
}

export default StatBox;
