import React from 'react';
import Card from '../components/Card';
import './Settings.css';

function Settings({ metadata }) {
  return (
    <div className="settings">
      <div className="settings-header">
        <h2>⚙️ Configuration</h2>
        <p>Your Vera assistant's brain & team</p>
      </div>

      <Card title="🤖 How Vera Works">
        <div className="settings-form">
          <div className="form-group">
            <label>👥 Team Name</label>
            <input type="text" value={metadata?.team_name || ''} disabled />
          </div>
          <div className="form-group">
            <label>🧠 Brain Power</label>
            <input type="text" value={metadata?.model || ''} disabled />
          </div>
          <div className="form-group">
            <label>💬 Our Strategy</label>
            <textarea value={metadata?.approach || ''} disabled></textarea>
          </div>
          <div className="form-group">
            <label>📧 Reach Us</label>
            <input type="email" value={metadata?.contact_email || ''} disabled />
          </div>
          <div className="form-group">
            <label>🔖 Version</label>
            <input type="text" value={metadata?.version || ''} disabled />
          </div>
        </div>
      </Card>

      <Card title="🏆 The Dream Team">
        <div className="team-members">
          {metadata?.team_members?.map((member, idx) => (
            <div key={idx} className="member-item">
              <div className="member-avatar">{member.charAt(0)}</div>
              <span className="member-name">{member}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default Settings;
