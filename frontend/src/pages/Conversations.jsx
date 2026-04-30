import React, { useState } from 'react';
import Card from '../components/Card';
import './Conversations.css';

function Conversations() {
  const [conversations, setConversations] = useState([
    {
      id: 'conv_001',
      merchant: 'Dr. Meera\'s Dental',
      messages: 3,
      lastMessage: 'Thanks for the update!',
      status: 'active',
      timestamp: '2m ago',
    },
    {
      id: 'conv_002',
      merchant: 'Studio11 Salon',
      messages: 5,
      lastMessage: 'Can you send me more details?',
      status: 'pending',
      timestamp: '5m ago',
    },
  ]);

  return (
    <div className="conversations">
      <div className="conversations-header">
        <h2>💬 Chat History</h2>
        <p>All your conversations with merchants in one place</p>
      </div>

      <Card>
        <div className="conversations-list">
          {conversations.length > 0 ? (
            conversations.map((conv) => (
              <div key={conv.id} className="conversation-item">
                <div className="conversation-avatar">
                  {conv.merchant.charAt(0)}
                </div>
                <div className="conversation-info">
                  <div className="conversation-header-row">
                    <h4 className="conversation-merchant">{conv.merchant}</h4>
                    <span className={`conversation-status status-${conv.status}`}>
                      {conv.status}
                    </span>
                  </div>
                  <p className="conversation-preview">{conv.lastMessage}</p>
                  <span className="conversation-time">{conv.timestamp}</span>
                </div>
                <div className="conversation-meta">
                  <span className="message-count">{conv.messages}</span>
                  <span className="message-label">messages</span>
                </div>
              </div>
            ))
          ) : (
            <div className="empty-state">
              <p>No conversations yet</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default Conversations;
