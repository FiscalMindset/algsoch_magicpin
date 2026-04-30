import React, { useState, useEffect } from 'react';
import { useBot } from './hooks/useBot';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Conversations from './pages/Conversations';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import Dataset from './pages/Dataset';
import Testing from './pages/Testing';
import Playground from './pages/Playground';
import Docs from './pages/Docs';
import Runner from './pages/Runner';
import FAQ from './pages/FAQ';
import MerchantChat from './pages/MerchantChat';
import APIMonitor from './pages/APIMonitor';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const { health, metadata, loading, error } = useBot();

  return (
    <Layout
      currentPage={currentPage}
      setCurrentPage={setCurrentPage}
      health={health}
      metadata={metadata}
      loading={loading}
    >
      <div className="app-container">
        {loading && (
          <div className="loading-banner">
            <div className="spinner"></div>
            <p>Initializing Vera AI...</p>
          </div>
        )}

        {error && (
          <div className="error-banner">
            <p>⚠️ Connection Error: {error}</p>
          </div>
        )}

        {currentPage === 'dashboard' && <Dashboard health={health} metadata={metadata} />}
        {currentPage === 'conversations' && <Conversations />}
        {currentPage === 'analytics' && <Analytics />}
        {currentPage === 'dataset' && <Dataset />}
        {currentPage === 'playground' && <Playground />}
        {currentPage === 'runner' && <Runner />}
        {currentPage === 'docs' && <Docs />}
        {currentPage === 'faq' && <FAQ />}
        {currentPage === 'testing' && <Testing />}
        {currentPage === 'settings' && <Settings metadata={metadata} />}
        {currentPage === 'merchant-chat' && <MerchantChat />}
        {currentPage === 'api-monitor' && <APIMonitor />}
      </div>
    </Layout>
  );
}

export default App;
