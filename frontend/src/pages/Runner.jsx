import React, { useEffect, useMemo, useState } from 'react';
import Card from '../components/Card';
import { botAPI } from '../services/api';
import './Runner.css';

function nowIso() {
  return new Date().toISOString();
}

function Runner() {
  const [pairs, setPairs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [actions, setActions] = useState([]);
  const [replyResult, setReplyResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [log, setLog] = useState([]);
  const [batchReport, setBatchReport] = useState(null);

  const kinds = useMemo(() => {
    const set = new Set(pairs.map((p) => p.kind).filter(Boolean));
    return Array.from(set).sort();
  }, [pairs]);

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

  const pushLog = (entry) => setLog((prev) => [{ at: nowIso(), ...entry }, ...prev].slice(0, 50));

  const loadPairs = async () => {
    setLoading(true);
    setError(null);
    try {
      await botAPI.playgroundGenerate();
      const res = await botAPI.playgroundTestPairs();
      setPairs(res.data || []);
      pushLog({ type: 'ok', label: 'Loaded test pairs', data: { count: res.data?.length || 0 } });
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: 'Load test pairs failed', data: e?.response?.data || e.toString() });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPairs();
  }, []);

  const selectTest = async (testId) => {
    setSelected(testId);
    setCaseData(null);
    setActions([]);
    setReplyResult(null);
    setError(null);
    try {
      const res = await botAPI.playgroundTestCase(testId);
      setCaseData(res.data);
      pushLog({ type: 'ok', label: `Loaded ${testId}`, data: { test_id: testId } });
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: `Load ${testId} failed`, data: e?.response?.data || e.toString() });
    }
  };

  const pushContext = async (scope, contextId, payload, version = 1) => {
    const body = { scope, context_id: contextId, version, payload, delivered_at: nowIso() };
    pushLog({ type: 'req', label: `POST /v1/context (${scope})`, data: { scope, context_id: contextId, version } });
    const res = await botAPI.pushContext(body);
    pushLog({ type: 'ok', label: `Context stored (${scope})`, data: res.data });
    return res.data;
  };

  const resetBot = async () => {
    setLoading(true);
    setError(null);
    try {
      pushLog({ type: 'req', label: 'POST /v1/playground/reset', data: {} });
      const res = await botAPI.playgroundReset();
      pushLog({ type: 'ok', label: 'Bot state reset', data: res.data });
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: 'Reset failed', data: e?.response?.data || e.toString() });
    } finally {
      setLoading(false);
    }
  };

  const loadIntoBot = async () => {
    if (!caseData) return;
    setLoading(true);
    setError(null);
    setActions([]);
    setReplyResult(null);
    try {
      await pushContext('category', caseData.category.slug, caseData.category, 1);
      await pushContext('merchant', caseData.merchant.merchant_id, caseData.merchant, 1);
      await pushContext('trigger', caseData.trigger.id, caseData.trigger, 1);
      if (caseData.customer?.customer_id) {
        await pushContext('customer', caseData.customer.customer_id, caseData.customer, 1);
      }
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: 'Load into bot failed', data: e?.response?.data || e.toString() });
    } finally {
      setLoading(false);
    }
  };

  const runTick = async () => {
    if (!caseData?.trigger?.id) return;
    setLoading(true);
    setError(null);
    setActions([]);
    setReplyResult(null);
    try {
      pushLog({ type: 'req', label: 'POST /v1/tick', data: { available_triggers: [caseData.trigger.id] } });
      const res = await botAPI.tick({ now: nowIso(), available_triggers: [caseData.trigger.id] });
      setActions(res.data?.actions || []);
      pushLog({ type: 'ok', label: 'Tick returned', data: { actions: res.data?.actions?.length || 0 } });
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: 'Tick failed', data: e?.response?.data || e.toString() });
    } finally {
      setLoading(false);
    }
  };

  const [replyMessage, setReplyMessage] = useState('Yes');
  const [replyRole, setReplyRole] = useState('merchant');

  const sendReply = async (action) => {
    if (!action?.conversation_id || !action?.merchant_id) return;
    setLoading(true);
    setError(null);
    setReplyResult(null);
    try {
      const body = {
        conversation_id: action.conversation_id,
        merchant_id: action.merchant_id,
        customer_id: action.customer_id || null,
        from_role: replyRole,
        message: replyMessage,
        received_at: nowIso(),
        turn_number: 2,
      };
      pushLog({ type: 'req', label: 'POST /v1/reply', data: { conversation_id: body.conversation_id, from_role: body.from_role } });
      const res = await botAPI.reply(body);
      setReplyResult(res.data);
      pushLog({ type: 'ok', label: 'Reply returned', data: res.data });
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: 'Reply failed', data: e?.response?.data || e.toString() });
    } finally {
      setLoading(false);
    }
  };

  const runAllPairs = async () => {
    setLoading(true);
    setError(null);
    setBatchReport(null);
    setActions([]);
    setReplyResult(null);
    try {
      await botAPI.playgroundGenerate();
      await botAPI.playgroundReset();

      const clamp = (n, min = 0, max = 10) => Math.max(min, Math.min(max, n));
      const countMatches = (text, re) => {
        if (!text) return 0;
        const m = text.match(re);
        return m ? m.length : 0;
      };
      const includesAny = (text, arr) => (arr || []).some((x) => (x ? text.includes(String(x)) : false));
      const tokenize = (text) => String(text || '').toLowerCase();

      const scoreMessage = ({ body, category, merchant, trigger }) => {
        const txt = tokenize(body);

        // 1) Specificity: numbers/₹/%/dates/ids.
        const nums = countMatches(body, /\d+/g);
        const hasRupee = body.includes('₹');
        const hasPct = body.includes('%');
        const hasDateLike = /\b(20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b/i.test(body);
        const specificity = clamp((nums >= 2 ? 6 : nums === 1 ? 4 : 1) + (hasRupee ? 2 : 0) + (hasPct ? 1 : 0) + (hasDateLike ? 1 : 0));

        // 2) Category fit: avoid taboos; reward allowed vocab usage.
        const taboos = category?.voice?.taboos || category?.voice?.vocab_taboo || [];
        const vocabAllowed = category?.voice?.vocab_allowed || category?.voice?.vocabAllowed || [];
        const tabooHits = (taboos || []).filter((t) => t && txt.includes(String(t).toLowerCase())).length;
        const vocabHits = (vocabAllowed || []).filter((v) => v && txt.includes(String(v).toLowerCase())).length;
        const categoryFit = clamp(7 + Math.min(3, vocabHits) - Math.min(7, tabooHits * 3));

        // 3) Merchant fit: include merchant name/locality/city/offer or concrete merchant metric.
        const mName = merchant?.identity?.name || '';
        const mCity = merchant?.identity?.city || '';
        const mLocality = merchant?.identity?.locality || '';
        const offers = (merchant?.offers || []).map((o) => o?.title).filter(Boolean);
        const perf = merchant?.performance || {};
        const perfSignals = [
          perf.views ? String(perf.views) : null,
          perf.calls ? String(perf.calls) : null,
          perf.ctr ? String(perf.ctr) : null,
        ].filter(Boolean);
        let merchantFit = 2;
        if (mName && txt.includes(String(mName).toLowerCase())) merchantFit += 4;
        if (mCity && txt.includes(String(mCity).toLowerCase())) merchantFit += 1;
        if (mLocality && txt.includes(String(mLocality).toLowerCase())) merchantFit += 1;
        if (includesAny(body, offers)) merchantFit += 2;
        else if (includesAny(body, perfSignals)) merchantFit += 2;
        merchantFit = clamp(merchantFit);

        // 4) Engagement compulsion: a single clear ask (question / YES/NO / reply).
        const hasQuestion = body.includes('?');
        const hasYesNo = /\b(yes|no|haan|nahi)\b/i.test(body);
        const hasReplyVerb = /\b(reply|respond|bhej|send)\b/i.test(body);
        const engagement = clamp((hasQuestion ? 6 : 3) + (hasYesNo ? 2 : 0) + (hasReplyVerb ? 2 : 0));

        // 5) Decision quality: references trigger kind/payload or clearly “why now”.
        const kind = trigger?.kind || '';
        const scope = trigger?.scope || '';
        const whyNowAnchors = ['today', 'this week', 'right now', 'abhi', 'aaj', 'due', 'reminder'];
        const payloadStrings = Object.values(trigger?.payload || {}).map((v) => (typeof v === 'string' ? v : null)).filter(Boolean);
        let decision = 2;
        if (kind && txt.includes(String(kind).toLowerCase().replaceAll('_', ' '))) decision += 4;
        if (scope && txt.includes(String(scope).toLowerCase())) decision += 1;
        if (includesAny(body, payloadStrings)) decision += 2;
        if (includesAny(txt, whyNowAnchors)) decision += 2;
        decision = clamp(decision);

        return {
          decision_quality: decision,
          specificity,
          category_fit: categoryFit,
          merchant_fit: merchantFit,
          engagement_compulsion: engagement,
          total_50: decision + specificity + categoryFit + merchantFit + engagement,
        };
      };

      const report = {
        started_at: nowIso(),
        total_pairs: pairs.length,
        ok_tick: 0,
        ok_reply: 0,
        score: {
          avg_total_50: 0,
          avg_decision_quality: 0,
          avg_specificity: 0,
          avg_category_fit: 0,
          avg_merchant_fit: 0,
          avg_engagement_compulsion: 0,
        },
        scored: 0,
        failures: [],
        samples: [],
        results: [],
      };

      for (const p of pairs) {
        const tc = await botAPI.playgroundTestCase(p.test_id);
        const d = tc.data;

        // Push contexts (versions start at 1; reset ensures clean run).
        await botAPI.pushContext({ scope: 'category', context_id: d.category.slug, version: 1, payload: d.category, delivered_at: nowIso() });
        await botAPI.pushContext({ scope: 'merchant', context_id: d.merchant.merchant_id, version: 1, payload: d.merchant, delivered_at: nowIso() });
        await botAPI.pushContext({ scope: 'trigger', context_id: d.trigger.id, version: 1, payload: d.trigger, delivered_at: nowIso() });
        if (d.customer?.customer_id) {
          await botAPI.pushContext({ scope: 'customer', context_id: d.customer.customer_id, version: 1, payload: d.customer, delivered_at: nowIso() });
        }

        // Tick
        const tickRes = await botAPI.tick({ now: nowIso(), available_triggers: [d.trigger.id] });
        const tickActions = tickRes.data?.actions || [];
        const firstAction = tickActions[0];

        const tickOk =
          !!firstAction?.conversation_id &&
          !!firstAction?.merchant_id &&
          !!firstAction?.trigger_id &&
          typeof firstAction?.body === 'string' &&
          typeof firstAction?.suppression_key === 'string';

        if (tickOk) {
          report.ok_tick += 1;
          const s = scoreMessage({
            body: firstAction.body,
            category: d.category,
            merchant: d.merchant,
            trigger: d.trigger,
          });
          report.scored += 1;
          report.score.avg_total_50 += s.total_50;
          report.score.avg_decision_quality += s.decision_quality;
          report.score.avg_specificity += s.specificity;
          report.score.avg_category_fit += s.category_fit;
          report.score.avg_merchant_fit += s.merchant_fit;
          report.score.avg_engagement_compulsion += s.engagement_compulsion;
          report.results.push({
            test_id: p.test_id,
            kind: p.kind,
            merchant_id: d.merchant.merchant_id,
            trigger_id: d.trigger.id,
            score: s,
            preview: String(firstAction.body || '').slice(0, 180),
          });
        } else {
          report.failures.push({
            test_id: p.test_id,
            stage: 'tick',
            detail: { first_action: firstAction || null },
          });
          continue;
        }

        // Reply (basic)
        const replyRes = await botAPI.reply({
          conversation_id: firstAction.conversation_id,
          merchant_id: firstAction.merchant_id,
          customer_id: firstAction.customer_id || null,
          from_role: 'merchant',
          message: 'Yes',
          received_at: nowIso(),
          turn_number: 2,
        });

        const replyOk = ['send', 'wait', 'end'].includes(replyRes.data?.action);
        if (replyOk) report.ok_reply += 1;
        else {
          report.failures.push({
            test_id: p.test_id,
            stage: 'reply',
            detail: replyRes.data,
          });
        }

        if (report.samples.length < 5) {
          report.samples.push({
            test_id: p.test_id,
            kind: p.kind,
            tick_action: firstAction,
            reply: replyRes.data,
          });
        }
      }

      if (report.scored > 0) {
        report.score.avg_total_50 = Number((report.score.avg_total_50 / report.scored).toFixed(2));
        report.score.avg_decision_quality = Number((report.score.avg_decision_quality / report.scored).toFixed(2));
        report.score.avg_specificity = Number((report.score.avg_specificity / report.scored).toFixed(2));
        report.score.avg_category_fit = Number((report.score.avg_category_fit / report.scored).toFixed(2));
        report.score.avg_merchant_fit = Number((report.score.avg_merchant_fit / report.scored).toFixed(2));
        report.score.avg_engagement_compulsion = Number((report.score.avg_engagement_compulsion / report.scored).toFixed(2));
      }

      report.finished_at = nowIso();
      setBatchReport(report);
      pushLog({ type: 'ok', label: 'Batch run finished', data: { ok_tick: report.ok_tick, ok_reply: report.ok_reply } });
    } catch (e) {
      setError(e?.response?.data?.detail || e.toString());
      pushLog({ type: 'err', label: 'Batch run failed', data: e?.response?.data || e.toString() });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="runner-page">
      <div className="runner-header">
        <div>
          <h2>🧪 Judge-Flow Runner</h2>
          <p>Looks like the real harness: push context → tick → reply</p>
        </div>
        <div className="runner-actions">
          <button className="btn-secondary" onClick={loadPairs} disabled={loading}>
            Reload pairs
          </button>
          <button className="btn-secondary" onClick={resetBot} disabled={loading}>
            Reset bot
          </button>
          <button className="btn-primary" onClick={runAllPairs} disabled={loading || pairs.length === 0}>
            {loading ? 'Running…' : 'Run all 30'}
          </button>
        </div>
      </div>

      {error && <div className="runner-error">⚠️ {error}</div>}

      <div className="runner-grid">
        <Card title="1) Pick a canonical test">
          <div className="runner-filters">
            <input
              className="runner-search"
              placeholder="Search test_id / kind / merchant…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select className="runner-select" value={kindFilter} onChange={(e) => setKindFilter(e.target.value)}>
              <option value="">All kinds</option>
              {kinds.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <div className="runner-pairs">
            {filteredPairs.map((p) => (
              <button
                key={p.test_id}
                className={`runner-pair ${selected === p.test_id ? 'active' : ''}`}
                onClick={() => selectTest(p.test_id)}
              >
                <div className="pair-top">
                  <span className="pair-id">{p.test_id}</span>
                  <span className="pair-kind">{p.kind}</span>
                </div>
                <div className="pair-merchant">{p.merchant_name || p.merchant_id}</div>
                <div className="pair-meta">
                  <span className="mono">{p.merchant_id}</span>
                  <span className="dot">•</span>
                  <span>{p.category_slug}</span>
                </div>
              </button>
            ))}
            {filteredPairs.length === 0 && <div className="runner-empty">No matches</div>}
          </div>
        </Card>

        <div className="runner-right">
          <Card
            title="2) Load context into your bot"
            subtitle="This calls the real challenge endpoints: POST /v1/context"
          >
            <div className="runner-step">
              <button className="btn-primary" disabled={!caseData || loading} onClick={loadIntoBot}>
                Load Category + Merchant + Trigger (+ Customer)
              </button>
              <div className="runner-hint">
                Uses context_ids: <span className="mono">{caseData?.category?.slug || '—'}</span>,{' '}
                <span className="mono">{caseData?.merchant?.merchant_id || '—'}</span>,{' '}
                <span className="mono">{caseData?.trigger?.id || '—'}</span>
              </div>
            </div>
          </Card>

          <Card title="3) Tick (proactive send)" subtitle="POST /v1/tick with available_triggers">
            <div className="runner-step">
              <button className="btn-primary" disabled={!caseData || loading} onClick={runTick}>
                Run Tick
              </button>
            </div>
            <div className="runner-actions-list">
              {actions.length === 0 ? (
                <div className="runner-empty">No actions yet</div>
              ) : (
                actions.map((a) => (
                  <div key={a.conversation_id} className="action-card">
                    <div className="action-meta">
                      <span className="mono">{a.conversation_id}</span>
                      <span className="pill">{a.send_as}</span>
                      <span className="pill mono">{a.trigger_id}</span>
                    </div>
                    <pre className="action-body">{a.body}</pre>
                    <div className="action-footer">
                      <div className="pill">cta: {a.cta}</div>
                      <div className="pill mono">supp: {a.suppression_key}</div>
                    </div>
                    <div className="reply-box">
                      <div className="reply-row">
                        <select value={replyRole} onChange={(e) => setReplyRole(e.target.value)} className="runner-select">
                          <option value="merchant">merchant</option>
                          <option value="customer">customer</option>
                        </select>
                        <input
                          className="runner-search"
                          value={replyMessage}
                          onChange={(e) => setReplyMessage(e.target.value)}
                          placeholder="Type a simulated reply…"
                        />
                        <button className="btn-secondary" disabled={loading} onClick={() => sendReply(a)}>
                          Send Reply
                        </button>
                      </div>
                      <pre className="runner-json">{replyResult ? JSON.stringify(replyResult, null, 2) : 'Reply result shows here'}</pre>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card title="Submission checklist" subtitle="What you need to submit to magicpin">
            <div className="checklist">
              <div className="check-row">
                <span className="check-dot" />
                <span>Public base URL (example: https://your-bot.example.com)</span>
              </div>
              <div className="check-row">
                <span className="check-dot" />
                <span>Endpoints: GET `/v1/healthz`, GET `/v1/metadata`</span>
              </div>
              <div className="check-row">
                <span className="check-dot" />
                <span>Endpoints: POST `/v1/context`, POST `/v1/tick`, POST `/v1/reply`</span>
              </div>
              <div className="check-row">
                <span className="check-dot" />
                <span>Deterministic outputs for same input</span>
              </div>
              <div className="check-row">
                <span className="check-dot" />
                <span>Fast responses (≤ 30s) + stable server</span>
              </div>
            </div>
          </Card>

          <Card title="Recent runner log" subtitle="Last 50 events">
            <div className="runner-log">
              {log.length === 0 ? (
                <div className="runner-empty">No log yet</div>
              ) : (
                log.map((l, idx) => (
                  <div key={idx} className={`log-item ${l.type}`}>
                    <span className="mono log-at">{l.at.split('T')[1]?.replace('Z', '')}</span>
                    <span className="log-label">{l.label}</span>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card title="Batch report" subtitle="Quick confidence check across canonical pairs">
            {!batchReport ? (
              <pre className="runner-json">Run “Run all 30” to see a report here</pre>
            ) : (
              <div className="runner-batch">
                <div className="runner-scoregrid">
                  <div className="scorecard">
                    <div className="scorelabel">Avg Score (50)</div>
                    <div className="scorevalue">{batchReport.score?.avg_total_50 ?? '—'}</div>
                  </div>
                  <div className="scorecard">
                    <div className="scorelabel">Decision</div>
                    <div className="scorevalue">{batchReport.score?.avg_decision_quality ?? '—'}</div>
                  </div>
                  <div className="scorecard">
                    <div className="scorelabel">Specificity</div>
                    <div className="scorevalue">{batchReport.score?.avg_specificity ?? '—'}</div>
                  </div>
                  <div className="scorecard">
                    <div className="scorelabel">Category</div>
                    <div className="scorevalue">{batchReport.score?.avg_category_fit ?? '—'}</div>
                  </div>
                  <div className="scorecard">
                    <div className="scorelabel">Merchant</div>
                    <div className="scorevalue">{batchReport.score?.avg_merchant_fit ?? '—'}</div>
                  </div>
                  <div className="scorecard">
                    <div className="scorelabel">Engagement</div>
                    <div className="scorevalue">{batchReport.score?.avg_engagement_compulsion ?? '—'}</div>
                  </div>
                </div>

                <div className="runner-tablewrap">
                  <table className="runner-table">
                    <thead>
                      <tr>
                        <th>Test</th>
                        <th>Kind</th>
                        <th>Total/50</th>
                        <th>Preview</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(batchReport.results || []).slice(0, 30).map((r) => (
                        <tr key={r.test_id}>
                          <td className="mono">{r.test_id}</td>
                          <td>{r.kind}</td>
                          <td className="mono">{r.score?.total_50}</td>
                          <td className="mono">{r.preview}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <details className="runner-details">
                  <summary>Raw JSON report</summary>
                  <pre className="runner-json">{JSON.stringify(batchReport, null, 2)}</pre>
                </details>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

export default Runner;
