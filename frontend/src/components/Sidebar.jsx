import React from 'react';
import { Home, MessageSquare, BarChart3, Settings, Database, Beaker, Sparkles, BookOpen, MessageCircle, Activity } from 'lucide-react';
import './Sidebar.css';

function Sidebar({ currentPage, setCurrentPage }) {
  const menuItems = [
    { id: 'dashboard', label: '📊 Dashboard', icon: Home },
    { id: 'conversations', label: '💬 Chats', icon: MessageSquare },
    { id: 'merchant-chat', label: '🗨️ Chat as Merchant', icon: MessageCircle },
    { id: 'analytics', label: '📈 Insights', icon: BarChart3 },
    { id: 'dataset', label: '📚 Dataset', icon: Database },
    { id: 'playground', label: '🧠 Playground', icon: Sparkles },
    { id: 'api-monitor', label: '🔍 API Monitor', icon: Activity },
    { id: 'runner', label: '🧪 Runner', icon: Beaker },
    { id: 'docs', label: '📄 Docs', icon: BookOpen },
    { id: 'faq', label: '🧾 Submit', icon: BookOpen },
    { id: 'testing', label: '🧪 Tests', icon: Beaker },
    { id: 'settings', label: '⚙️ Config', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => setCurrentPage(item.id)}
            aria-label={item.label}
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
