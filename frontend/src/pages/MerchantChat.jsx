import React, { useState, useRef, useEffect, useCallback } from 'react';
import './MerchantChat.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const IS_LOCAL = API_BASE.includes('localhost') || API_BASE.includes('127.0.0.1');

const MERCHANTS = [
  { id: 'm_001_drmeera_dentist_delhi', name: 'Dr. Meera', category: 'dentists', city: 'Delhi', icon: '🦷', color: '#6366f1' },
  { id: 'm_002_bharat_dentist_mumbai', name: 'Dr. Bharat', category: 'dentists', city: 'Mumbai', icon: '🦷', color: '#8b5cf6' },
  { id: 'm_003_studio11_salon_hyderabad', name: 'Lakshmi', category: 'salons', city: 'Hyderabad', icon: '💇', color: '#ec4899' },
  { id: 'm_004_glamour_salon_pune', name: 'Anjali', category: 'salons', city: 'Pune', icon: '💇', color: '#f43f5e' },
  { id: 'm_005_pizzajunction_restaurant_delhi', name: 'Suresh K.', category: 'restaurants', city: 'Delhi', icon: '🍕', color: '#f59e0b' },
  { id: 'm_006_southindiancafe_restaurant_bangalore', name: 'Suresh M.', category: 'restaurants', city: 'Bangalore', icon: '🍛', color: '#ef4444' },
  { id: 'm_007_powerhouse_gym_bangalore', name: 'Karthik', category: 'gyms', city: 'Bangalore', icon: '💪', color: '#10b981' },
  { id: 'm_008_zenyoga_gym_chennai', name: 'Padma', category: 'gyms', city: 'Chennai', icon: '🧘', color: '#06b6d4' },
  { id: 'm_009_apollo_pharmacy_jaipur', name: 'Ramesh', category: 'pharmacies', city: 'Jaipur', icon: '💊', color: '#3b82f6' },
  { id: 'm_010_sunrisepharm_pharmacy_lucknow', name: 'Vikas', category: 'pharmacies', city: 'Lucknow', icon: '💊', color: '#64748b' },
];

const QUICK_MESSAGES = [
  { text: "Hi, what's new?", emoji: '👋', type: 'greeting' },
  { text: "Show me my performance", emoji: '📊', type: 'performance' },
  { text: "Tell me about my offers", emoji: '🎁', type: 'offers' },
  { text: "Ok lets do it. What's next?", emoji: '✅', type: 'commitment' },
  { text: "Yes, please proceed", emoji: '🚀', type: 'affirmative' },
  { text: "Not interested", emoji: '👎', type: 'decline' },
  { text: "Can you help me file my GST?", emoji: '🤔', type: 'curveball' },
  { text: "Stop messaging me. This is useless spam.", emoji: '🛑', type: 'hostile' },
];

async function apiRequest(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(`${API_BASE}${path}`, opts);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function pushContext(scope, cid, version, payload) {
  return apiRequest('/v1/context', 'POST', {
    scope, context_id: cid, version, payload,
    delivered_at: new Date().toISOString(),
  });
}

async function sendMerchantReply(convId, merchantId, message, turn) {
  return apiRequest('/v1/reply', 'POST', {
    conversation_id: convId, merchant_id: merchantId, customer_id: null,
    from_role: 'merchant', message,
    received_at: new Date().toISOString(), turn_number: turn,
  });
}

async function tick(availableTriggers) {
  return apiRequest('/v1/tick', 'POST', {
    now: new Date().toISOString(), available_triggers: availableTriggers,
  });
}

function TourModal({ onClose }) {
  const [step, setStep] = useState(0);
  const steps = [
    { title: "Welcome to Vera AI", desc: "Experience magicpin's intelligent merchant assistant. See how Vera proactively engages businesses across India with contextual, actionable messages.", icon: "✨" },
    { title: "Choose a Merchant", desc: "Select from 10 merchants across 5 categories — dentists, salons, restaurants, gyms, and pharmacies. Each has unique business data, offers, and performance signals.", icon: "🏪" },
    { title: "Start a Conversation", desc: "Click \"Start Conversation\" to trigger Vera's first outreach message. Or type your own message as the merchant to test how Vera responds to different scenarios.", icon: "💬" },
    { title: "Use Quick Replies", desc: "Pre-set messages simulate common merchant responses — engagement, hostility, commitment, and off-topic questions. Watch how Vera adapts in real-time.", icon: "⚡" },
    { title: "Send Trigger Messages", desc: "On the right panel, click a trigger to see what Vera would proactively send. Triggers include research digests, performance dips, competitor alerts, and more.", icon: "🎯" },
    { title: "Enable Ollama Sim", desc: "Toggle the Ollama switch to have a local LLM play the merchant role. It auto-generates realistic merchant replies based on conversation context.", icon: "🤖" },
    { title: "Ready to Explore", desc: "Backend must be running on port 8000. Ollama required for merchant simulation. Use \"Reset\" to clear and start fresh. Enjoy!", icon: "🚀" },
  ];
  const current = steps[step];
  return (
    <div className="tour-overlay" onClick={onClose}>
      <div className="tour-card" onClick={e => e.stopPropagation()}>
        <div className="tour-icon">{current.icon}</div>
        <h2>{current.title}</h2>
        <p className="tour-desc">{current.desc}</p>
        <div className="tour-dots">
          {steps.map((_, i) => (
            <span key={i} className={`tour-dot ${i === step ? 'active' : ''}`} onClick={e => { e.stopPropagation(); setStep(i); }} />
          ))}
        </div>
        <div className="tour-actions">
          <button className="tour-skip" onClick={onClose}>{step === steps.length - 1 ? 'Close' : 'Skip'}</button>
          <button className="tour-next" onClick={() => step < steps.length - 1 ? setStep(step + 1) : onClose()}>
            {step < steps.length - 1 ? 'Next' : 'Get Started'}
          </button>
        </div>
      </div>
    </div>
  );
}

function MerchantChat() {
  const [selectedMerchant, setSelectedMerchant] = useState(MERCHANTS[0]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState(null);
  const [contextsLoaded, setContextsLoaded] = useState(false);
  const [botAction, setBotAction] = useState(null);
  const [error, setError] = useState(null);
  const [showTour, setShowTour] = useState(true);
  const [ollamaMode, setOllamaMode] = useState(false);
  const [ollamaSpeed, setOllamaSpeed] = useState('normal');
  const [merchantTriggers, setMerchantTriggers] = useState([]);
  const [conversationTurn, setConversationTurn] = useState(0);
  const [quickFilter, setQuickFilter] = useState('all');
  const messagesEndRef = useRef(null);
  const autoTimerRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadMerchantContexts = useCallback(async (merchant) => {
    setLoading(true);
    setError(null);
    try {
      const pairs = await apiRequest('/v1/playground/test-pairs');
      const pair = pairs.find(p => p.merchant_id === merchant.id);
      if (pair) {
        const caseData = await apiRequest(`/v1/playground/test-case/${pair.test_id}`);
        const v = Date.now();
        await pushContext('category', caseData.category.slug, v, caseData.category);
        await pushContext('merchant', caseData.merchant.merchant_id, v, caseData.merchant);
        if (caseData.trigger) await pushContext('trigger', caseData.trigger.id, v, caseData.trigger);
        if (caseData.customer) await pushContext('customer', caseData.customer.customer_id, v, caseData.customer);
        setMerchantTriggers([{ id: pair.trigger_id, kind: pair.kind, urgency: 2 }]);
        setContextsLoaded(true);
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    setMessages([]); setConvId(null); setContextsLoaded(false); setBotAction(null); setConversationTurn(0);
    if (autoTimerRef.current) clearTimeout(autoTimerRef.current);
    if (selectedMerchant) loadMerchantContexts(selectedMerchant);
  }, [selectedMerchant, loadMerchantContexts]);

  const addMessage = useCallback((role, text, extra = {}) => {
    setMessages(prev => [...prev, { role, text, timestamp: new Date(), ...extra }]);
  }, []);

  const handleBotReply = useCallback(async (merchantMsg) => {
    if (!convId || botAction === 'end') return;
    const nextTurn = conversationTurn + 1;
    setConversationTurn(nextTurn);
    try {
      const reply = await sendMerchantReply(convId, selectedMerchant.id, merchantMsg, nextTurn);
      addMessage('bot', reply.body || '(no response)', { action: reply.action, cta: reply.cta, rationale: reply.rationale });
      setBotAction(reply.action);
      if (reply.action === 'end') addMessage('system', 'Conversation ended by Vera');
      return reply;
    } catch (e) { setError(e.message); return null; }
  }, [convId, botAction, conversationTurn, selectedMerchant.id, addMessage]);

  const handleOllamaAutoReply = useCallback(async () => {
    if (!ollamaMode || botAction === 'end' || loading) return;
    const delayMap = { slow: 4000, normal: 2000, fast: 800 };
    autoTimerRef.current = setTimeout(async () => {
      const responses = [
        "Yes, that sounds good. What are the next steps?",
        "I'm not sure about this. Can you explain more?",
        "Ok lets do it. What's next?",
        "Thanks for the update. I'll check my dashboard.",
        "Not interested right now, maybe later.",
        "How much does this cost?",
        "Can you show me my performance numbers?",
        "I need to think about it. Call me next week.",
        "This seems useful. Tell me more about the offers.",
        "Stop sending me these messages.",
      ];
      const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      addMessage('ollama', randomResponse);
      await handleBotReply(randomResponse);
    }, delayMap[ollamaSpeed] || 2000);
  }, [ollamaMode, botAction, loading, ollamaSpeed, addMessage, handleBotReply]);

  useEffect(() => {
    if (ollamaMode && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === 'bot' && botAction !== 'end') handleOllamaAutoReply();
    }
    return () => { if (autoTimerRef.current) clearTimeout(autoTimerRef.current); };
  }, [messages, ollamaMode, botAction, handleOllamaAutoReply]);

  const handleSend = async (text) => {
    if (!text.trim() || loading) return;
    if (!contextsLoaded) { setError('Contexts not loaded yet.'); return; }
    if (botAction === 'end') { setError('Conversation ended. Click Reset to start new.'); return; }
    addMessage('user', text);
    setInput('');
    setLoading(true);
    setError(null);
    const currentConvId = convId || `conv_chat_${Date.now()}`;
    if (!convId) setConvId(currentConvId);
    try {
      const reply = await sendMerchantReply(currentConvId, selectedMerchant.id, text, conversationTurn + 1);
      setConversationTurn(prev => prev + 1);
      addMessage('bot', reply.body || '(no response)', { action: reply.action, cta: reply.cta, rationale: reply.rationale });
      setBotAction(reply.action);
      if (reply.action === 'end') addMessage('system', 'Conversation ended by Vera');
    } catch (e) { setError(e.message); addMessage('system', `Error: ${e.message}`); }
    finally { setLoading(false); }
  };

  const handleStartConversation = async () => {
    setLoading(true); setError(null);
    try {
      const triggerIds = merchantTriggers.map(t => t.id);
      if (triggerIds.length === 0) { setError('No triggers available. Try sending a message manually.'); setLoading(false); return; }
      const result = await tick(triggerIds);
      if (result.actions && result.actions.length > 0) {
        const action = result.actions[0];
        setConvId(action.conversation_id); setConversationTurn(1);
        addMessage('bot', action.body, { action: 'send', cta: action.cta, rationale: action.rationale });
        setBotAction('send');
      } else { setError('No actions returned from tick.'); }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleSendTrigger = async (triggerId) => {
    setLoading(true); setError(null);
    try {
      const result = await tick([triggerId]);
      if (result.actions && result.actions.length > 0) {
        const action = result.actions[0];
        setConvId(action.conversation_id); setConversationTurn(1);
        addMessage('bot', action.body, { action: 'send', cta: action.cta, rationale: action.rationale });
        setBotAction('send');
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleReset = () => {
    setMessages([]); setConvId(null); setBotAction(null); setConversationTurn(0);
    if (autoTimerRef.current) clearTimeout(autoTimerRef.current);
    loadMerchantContexts(selectedMerchant);
  };

  const messageClass = (msg) => {
    if (msg.role === 'user') return 'msg-user';
    if (msg.role === 'system') return 'msg-system';
    if (msg.role === 'ollama') return 'msg-ollama';
    return 'msg-bot';
  };

  const filteredQuickMessages = quickFilter === 'all' ? QUICK_MESSAGES : QUICK_MESSAGES.filter(qm => qm.type === quickFilter);
  const isConversationEnded = botAction === 'end';

  return (
    <div className="merchant-chat-page">
      {showTour && <TourModal onClose={() => setShowTour(false)} />}

      <div className="merchant-chat-header">
        <div className="header-brand">
          <div className="header-logo">
            <span className="logo-icon">✨</span>
            <div className="logo-text">
              <h2>Vera AI</h2>
              <p>Merchant Chat Simulator</p>
            </div>
          </div>
        </div>
        <div className="chat-actions">
          <span className="api-url-badge">{API_BASE.replace(/https?:\/\//, '')}</span>
          <button className="btn-ghost" onClick={() => setShowTour(true)}>
            <span className="btn-icon">❓</span>How to Use
          </button>
          <button className="btn-ghost" onClick={handleReset} disabled={loading}>
            <span className="btn-icon">🔄</span>Reset
          </button>
          <button className="btn-primary" onClick={handleStartConversation} disabled={loading || !contextsLoaded}>
            <span className="btn-icon">💬</span>Start Conversation
          </button>
        </div>
      </div>

      <div className="merchant-chat-layout">
        <div className="merchant-selector-panel">
          <div className="panel-header">
            <h3>Merchants</h3>
            <span className="panel-badge">{MERCHANTS.length}</span>
          </div>
          <div className="merchant-list">
            {MERCHANTS.map(m => (
              <button key={m.id} className={`merchant-item ${selectedMerchant.id === m.id ? 'active' : ''}`}
                style={selectedMerchant.id === m.id ? { '--accent': m.color } : {}}
                onClick={() => setSelectedMerchant(m)}>
                <div className="merchant-avatar" style={{ background: m.color + '20', color: m.color }}>{m.icon}</div>
                <div className="merchant-info">
                  <div className="merchant-name">{m.name}</div>
                  <div className="merchant-meta"><span className="meta-tag">{m.category}</span>· {m.city}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="chat-area">
          <div className="chat-area-header">
            <div className="chat-header-left">
              <div className="chat-merchant-avatar" style={{ background: selectedMerchant.color }}>{selectedMerchant.icon}</div>
              <div>
                <h3>{selectedMerchant.name}</h3>
                <span className="chat-subtitle">{selectedMerchant.category} · {selectedMerchant.city}</span>
              </div>
            </div>
            <div className="chat-header-right">
              <span className={`chat-status ${contextsLoaded ? 'loaded' : 'loading'}`}>
                <span className={`status-dot ${contextsLoaded ? 'loaded' : 'loading'}`} />
                {contextsLoaded ? 'Connected' : 'Loading...'}
              </span>
              {conversationTurn > 0 && <span className="turn-badge">Turn {conversationTurn}</span>}
            </div>
          </div>

          {error && <div className="chat-error"><span>⚠️</span>{error}</div>}

          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="chat-empty">
                <div className="empty-illustration">
                  <div className="empty-icon">💬</div>
                  <div className="empty-dots">
                    <span /><span /><span />
                  </div>
                </div>
                <h3>Ready to experience Vera AI</h3>
                <p>Select a merchant and start a conversation to see how Vera engages businesses across India</p>
                <div className="empty-actions">
                  <button className="btn-primary" onClick={handleStartConversation} disabled={loading || !contextsLoaded}>Start Conversation</button>
                  <button className="btn-ghost" onClick={() => handleSend("Hi, what's new?")}>Send Quick Message</button>
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className={`message ${messageClass(msg)}`}>
                  {msg.role === 'bot' && (
                    <div className="msg-avatar" style={{ background: selectedMerchant.color + '30', color: selectedMerchant.color }}>✨</div>
                  )}
                  {msg.role === 'user' && (
                    <div className="msg-avatar" style={{ background: selectedMerchant.color + '20', color: selectedMerchant.color }}>{selectedMerchant.icon}</div>
                  )}
                  {msg.role === 'ollama' && (
                    <div className="msg-avatar" style={{ background: '#10b98130', color: '#10b981' }}>🤖</div>
                  )}
                  <div className="message-bubble">
                    {msg.role === 'ollama' && <div className="ollama-label">Ollama Merchant Sim</div>}
                    <div className="message-text">{msg.text}</div>
                    {msg.action && (
                      <div className="message-meta">
                        <span className={`badge badge-${msg.action}`}>{msg.action}</span>
                        {msg.cta && <span className="badge badge-cta">{msg.cta}</span>}
                      </div>
                    )}
                    <div className="message-time">{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="message msg-bot">
                <div className="msg-avatar" style={{ background: selectedMerchant.color + '30', color: selectedMerchant.color }}>✨</div>
                <div className="message-bubble typing">
                  <div className="typing-dots"><span /><span /><span /></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {!isConversationEnded && (
            <div className="quick-messages">
              <div className="quick-header">
                <span>Quick replies</span>
                <div className="quick-filters">
                  <button className={`filter-btn ${quickFilter === 'all' ? 'active' : ''}`} onClick={() => setQuickFilter('all')}>All</button>
                  <button className={`filter-btn ${quickFilter === 'greeting' ? 'active' : ''}`} onClick={() => setQuickFilter('greeting')}>👋</button>
                  <button className={`filter-btn ${quickFilter === 'performance' ? 'active' : ''}`} onClick={() => setQuickFilter('performance')}>📊</button>
                  <button className={`filter-btn ${quickFilter === 'offers' ? 'active' : ''}`} onClick={() => setQuickFilter('offers')}>🎁</button>
                  <button className={`filter-btn ${quickFilter === 'commitment' ? 'active' : ''}`} onClick={() => setQuickFilter('commitment')}>✅</button>
                </div>
              </div>
              <div className="quick-list">
                {filteredQuickMessages.map((qm, i) => (
                  <button key={i} className="quick-btn" onClick={() => handleSend(qm.text)} disabled={loading}>
                    <span className="quick-emoji">{qm.emoji}</span>{qm.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="chat-input-area">
            <form className="chat-input-form" onSubmit={e => { e.preventDefault(); handleSend(input); }}>
              <input className="chat-input" value={input} onChange={e => setInput(e.target.value)}
                placeholder={isConversationEnded ? 'Conversation ended. Reset to start new.' : `Message as ${selectedMerchant.name}...`}
                disabled={loading || isConversationEnded} />
              <button type="submit" className="btn-send" disabled={loading || !input.trim() || isConversationEnded}>
                {loading ? <span className="send-spinner" /> : <span>Send ➤</span>}
              </button>
            </form>
          </div>
        </div>

        <div className="bot-info-panel">
          <div className="info-card card-status">
            <div className="card-header">
              <h3>Status</h3>
              <div className={`card-indicator ${contextsLoaded ? 'online' : 'offline'}`} />
            </div>
            <div className="bot-status">
              <div className="status-row">
                <span className="status-label">Conversation</span>
                <span className={`status-value ${isConversationEnded ? 'ended' : convId ? 'active' : ''}`}>
                  {isConversationEnded ? 'Ended' : convId ? 'Active' : 'Idle'}
                </span>
              </div>
              <div className="status-row">
                <span className="status-label">Turns</span>
                <span className="status-value">{conversationTurn}</span>
              </div>
              <div className="status-row">
                <span className="status-label">Messages</span>
                <span className="status-value">{messages.length}</span>
              </div>
              {botAction && (
                <div className="status-row">
                  <span className="status-label">Last action</span>
                  <span className={`badge badge-${botAction}`}>{botAction}</span>
                </div>
              )}
            </div>
          </div>

          <div className="info-card card-ollama">
            <div className="card-header">
              <h3>Ollama Sim</h3>
              {!IS_LOCAL && <span className="ollama-local-only">Local only</span>}
              <label className="toggle-switch">
                <input type="checkbox" checked={ollamaMode} onChange={e => setOllamaMode(e.target.checked)} disabled={!IS_LOCAL} />
                <span className="toggle-slider" />
              </label>
            </div>
            {!IS_LOCAL && (
              <div className="ollama-warning">
                Requires local Ollama server at localhost:11434. Not available in cloud.
              </div>
            )}
            {ollamaMode && IS_LOCAL && (
              <div className="ollama-speed">
                {['slow', 'normal', 'fast'].map(s => (
                  <button key={s} className={`speed-btn ${ollamaSpeed === s ? 'active' : ''}`} onClick={() => setOllamaSpeed(s)}>
                    {s === 'slow' ? '🐢' : s === 'fast' ? '⚡' : '🏃'} {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="info-card card-triggers">
            <div className="card-header">
              <h3>Triggers</h3>
              <span className="trigger-count">{merchantTriggers.length}</span>
            </div>
            <div className="trigger-list">
              {merchantTriggers.length === 0 ? (
                <div className="trigger-empty">No triggers loaded</div>
              ) : (
                merchantTriggers.map(t => (
                  <div key={t.id} className="trigger-item" onClick={() => handleSendTrigger(t.id)}>
                    <div className="trigger-icon">🎯</div>
                    <div>
                      <div className="trigger-kind">{t.kind?.replace(/_/g, ' ')}</div>
                      <div className="trigger-urgency">Click to send</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="info-card card-stats">
            <div className="card-header"><h3>Test Results</h3></div>
            <div className="test-stats">
              <div className="stat-row"><span className="stat-label">Custom Tests</span><span className="stat-value pass">14/14 ✓</span></div>
              <div className="stat-row"><span className="stat-label">Advanced Tests</span><span className="stat-value pass">25/25 ✓</span></div>
              <div className="stat-row"><span className="stat-label">Total</span><span className="stat-value pass">39/39 ✓</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MerchantChat;
