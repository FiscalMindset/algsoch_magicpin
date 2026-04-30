import React from 'react';
import './Header.css';

function Header({ health, metadata, loading }) {
  const online = health?.status === 'ok';
  const contexts = health?.contexts_loaded || {};
  const ctxTotal = Object.values(contexts).reduce((a, b) => a + (Number(b) || 0), 0);

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-logo">
          <div className="logo-icon">🤖</div>
          <h1>Vera AI</h1>
          <span className="logo-subtitle">Merchant Assistant</span>
        </div>
        <div className="header-status">
          <div className="status-indicator">
            <div className={`status-dot ${online ? 'ok' : 'bad'}`}></div>
            <span>{loading ? 'Connecting…' : online ? 'Online' : 'Offline'}</span>
          </div>
          <div className="status-indicator subtle">
            <span className="status-k">Contexts</span>
            <span className="status-v">{ctxTotal}</span>
          </div>
          <div className="status-indicator subtle">
            <span className="status-k">Model</span>
            <span className="status-v mono">{metadata?.model || '—'}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Header;
