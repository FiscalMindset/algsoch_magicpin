import React from 'react';
import Card from '../components/Card';
import './Analytics.css';

function Analytics() {
  const metrics = [
    { name: 'Total Messages', value: '0', unit: 'messages' },
    { name: 'Avg Response Time', value: '0', unit: 'ms' },
    { name: 'Success Rate', value: '0', unit: '%' },
    { name: 'Auto-reply Detection', value: '0', unit: 'instances' },
  ];

  return (
    <div className="analytics">
      <div className="analytics-header">
        <h2>📊 Performance Insights</h2>
        <p>How your Vera assistant is doing</p>
      </div>

      <div className="metrics-grid">
        {metrics.map((metric, idx) => (
          <Card key={idx} className="metric-card">
            <div className="metric-content">
              <h4>{metric.name}</h4>
              <div className="metric-value">
                {metric.value}
                <span className="metric-unit">{metric.unit}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card title="Engagement Timeline" subtitle="Last 7 days">
        <div className="timeline-placeholder">
          <p>📊 Timeline chart coming soon...</p>
        </div>
      </Card>
    </div>
  );
}

export default Analytics;
