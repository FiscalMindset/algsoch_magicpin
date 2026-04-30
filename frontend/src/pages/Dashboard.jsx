import React from 'react';
import { Activity, MessageSquare, TrendingUp, Clock } from 'lucide-react';
import Card from '../components/Card';
import StatBox from '../components/StatBox';
import './Dashboard.css';

function Dashboard({ health, metadata }) {
  const stats = [
    {
      label: 'Contexts Loaded',
      value: health?.contexts_loaded?.merchant || 0,
      icon: Activity,
      color: 'blue',
    },
    {
      label: 'Conversations',
      value: '0',
      icon: MessageSquare,
      color: 'green',
      trend: { direction: 'up', text: '+0% this week' },
    },
    {
      label: 'Engagement Rate',
      value: '0%',
      icon: TrendingUp,
      color: 'orange',
    },
    {
      label: 'Uptime',
      value: health?.uptime_seconds ? Math.floor(health.uptime_seconds / 60) + 'm' : '0m',
      icon: Clock,
      color: 'purple',
    },
  ];

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Your Vera Assistant</h2>
        <p>✨ See what's happening right now</p>
      </div>

      <div className="stats-grid">
        {stats.map((stat, idx) => (
          <StatBox key={idx} {...stat} />
        ))}
      </div>

      <div className="dashboard-content">
        <Card title="🚀 Live Status" subtitle="Everything running smoothly">
          <div className="status-details">
            <div className="status-item">
              <span className="status-label">Status:</span>
              <div className="status-value">
                <div className="status-indicator-live"></div>
                {health?.status === 'ok' ? 'Online' : 'Offline'}
              </div>
            </div>
            <div className="status-item">
              <span className="status-label">Model:</span>
              <span className="status-value">{metadata?.model || 'Loading...'}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Team:</span>
              <span className="status-value">{metadata?.team_name || 'Loading...'}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Approach:</span>
              <span className="status-value text-small">{metadata?.approach || 'Loading...'}</span>
            </div>
          </div>
        </Card>

        <Card title="📚 Smart Data Loaded" subtitle="Ready to help merchants">
          <div className="context-breakdown">
            {health?.contexts_loaded && Object.entries(health.contexts_loaded).map(([key, count]) => (
              <div key={key} className="context-item">
                <span className="context-name">{key.charAt(0).toUpperCase() + key.slice(1)}</span>
                <span className="context-count">{count}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="⚡ What's Happening" subtitle="Real-time activity">
          <div className="activity-list">
            <div className="activity-item">
              <div className="activity-badge">🎯</div>
              <div className="activity-content">
                <div className="activity-title">Ready to assist merchants</div>
                <div className="activity-time">Right now</div>
              </div>
            </div>
            <div className="activity-item">
              <div className="activity-badge">💡</div>
              <div className="activity-content">
                <div className="activity-title">AI models loaded & ready</div>
                <div className="activity-time">A moment ago</div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default Dashboard;
