import React, { useEffect, useMemo, useState } from 'react';
import Card from '../components/Card';
import { botAPI } from '../services/api';
import './Playground.css';

function JsonPanel({ title, data }) {
  return (
    <Card title={title}>
      <pre className="playground-json">{data ? JSON.stringify(data, null, 2) : '—'}</pre>
    </Card>
  );
}

function MessagePanel({ message }) {
  return (
    <Card title="🤖 Vera Output" subtitle="Deterministic compose() preview">
      {!message ? (
        <div className="playground-empty">Select a test case and click Compose</div>
      ) : (
        <div className="playground-message">
          <div className="msg-row">
            <div className="msg-label">Body</div>
            <div className="msg-value">
              <pre className="msg-body">{message.body}</pre>
            </div>
          </div>
          <div className="msg-grid">
            <div className="msg-kv">
              <div className="msg-label">CTA</div>
              <div className="msg-pill">{message.cta || '—'}</div>
            </div>
            <div className="msg-kv">
              <div className="msg-label">Send As</div>
              <div className="msg-pill">{message.send_as || '—'}</div>
            </div>
            <div className="msg-kv">
              <div className="msg-label">Suppression</div>
              <div className="msg-pill mono">{message.suppression_key || '—'}</div>
            </div>
          </div>
          <div className="msg-row">
            <div className="msg-label">Rationale</div>
            <div className="msg-value">
              <pre className="msg-rationale">{message.rationale}</pre>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function Playground() {
  const [pairs, setPairs] = useState([]);
  const [selectedTestId, setSelectedTestId] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [composeResult, setComposeResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [kindFilter, setKindFilter] = useState('');
  const [search, setSearch] = useState('');

  const filteredPairs = useMemo(() => {
    const q = search.trim().toLowerCase();
    return pairs.filter((p) => {
      if (kindFilter && p.kind !== kindFilter) return false;
      if (!q) return true;
      const hay = `${p.test_id} ${p.kind} ${p.merchant_name} ${p.merchant_id} ${p.category_slug}`.toLowerCase();
      return hay.includes(q);
    });
  }, [pairs, kindFilter, search]);

  const kinds = useMemo(() => {
    const set = new Set(pairs.map((p) => p.kind).filter(Boolean));
    return Array.from(set).sort();
  }, [pairs]);

  const refreshPairs = async () => {
    setLoading(true);
    setError(null);
    try {
      await botAPI.playgroundGenerate();
      const res = await botAPI.playgroundTestPairs();
      setPairs(res.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshPairs();
  }, []);

  const selectTest = async (testId) => {
    setSelectedTestId(testId);
    setComposeResult(null);
    setError(null);
    try {
      const res = await botAPI.playgroundTestCase(testId);
      setCaseData(res.data);
    } catch (e) {
      setCaseData(null);
      setError(e?.response?.data?.detail || e.toString());
    }
  };

  const compose = async () => {
    if (!selectedTestId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await botAPI.playgroundCompose({ test_id: selectedTestId, force_template: true });
      setComposeResult(res.data?.message || null);
    } catch (e) {
      setComposeResult(null);
      setError(e?.response?.data?.detail || e.toString());
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="playground-page">
      <div className="playground-header">
        <div>
          <h2>🧠 Vera Playground</h2>
          <p>Browse canonical test pairs, inspect context, and run deterministic compose()</p>
        </div>
        <div className="playground-actions">
          <button className="btn-secondary" onClick={refreshPairs} disabled={loading}>
            {loading ? 'Loading…' : 'Reload'}
          </button>
          <button className="btn-primary" onClick={compose} disabled={!selectedTestId || loading}>
            Compose
          </button>
        </div>
      </div>

      {error && (
        <div className="playground-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      <div className="playground-layout">
        <div className="playground-left">
          <Card title="✅ Canonical Test Pairs" subtitle={`${filteredPairs.length}/${pairs.length} shown`}>
            <div className="playground-filters">
              <input
                className="playground-search"
                placeholder="Search merchant / kind / id…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select className="playground-select" value={kindFilter} onChange={(e) => setKindFilter(e.target.value)}>
                <option value="">All kinds</option>
                {kinds.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <div className="pair-list">
              {filteredPairs.map((p) => (
                <button
                  key={p.test_id}
                  className={`pair-item ${selectedTestId === p.test_id ? 'active' : ''}`}
                  onClick={() => selectTest(p.test_id)}
                >
                  <div className="pair-top">
                    <span className="pair-id">{p.test_id}</span>
                    <span className="pair-kind">{p.kind}</span>
                  </div>
                  <div className="pair-merchant">{p.merchant_name || p.merchant_id}</div>
                  <div className="pair-meta">
                    <span className="mono">{p.merchant_id}</span>
                    <span className="pair-dot">•</span>
                    <span>{p.category_slug}</span>
                    {p.customer_id ? (
                      <>
                        <span className="pair-dot">•</span>
                        <span className="mono">customer</span>
                      </>
                    ) : null}
                  </div>
                </button>
              ))}
              {filteredPairs.length === 0 && <div className="playground-empty">No matches</div>}
            </div>
          </Card>
        </div>

        <div className="playground-center">
          <MessagePanel message={composeResult} />
          <div className="playground-context-grid">
            <JsonPanel title="Category" data={caseData?.category} />
            <JsonPanel title="Merchant" data={caseData?.merchant} />
            <JsonPanel title="Trigger" data={caseData?.trigger} />
            <JsonPanel title="Customer" data={caseData?.customer} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default Playground;

