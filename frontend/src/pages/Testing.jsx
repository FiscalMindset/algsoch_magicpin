import React, { useMemo, useState } from 'react';
import Card from '../components/Card';
import { botAPI } from '../services/api';
import './Testing.css';

function Testing() {
  const [result, setResult] = useState(null);
  const [smoke, setSmoke] = useState([]);
  const [running, setRunning] = useState(false);

  const summary = useMemo(() => {
    const total = smoke.length;
    const ok = smoke.filter((s) => s.ok).length;
    return { total, ok, fail: total - ok };
  }, [smoke]);

  const runHealth = async () => {
    try {
      const res = await botAPI.healthz();
      setResult(res.data);
    } catch (e) {
      setResult({ error: e.toString() });
    }
  };

  const runMetadata = async () => {
    try {
      const res = await botAPI.metadata();
      setResult(res.data);
    } catch (e) {
      setResult({ error: e.toString() });
    }
  };

  const runSmoke = async () => {
    setRunning(true);
    setResult(null);

    const checks = [];
    const push = (name, ok, data) => checks.push({ name, ok, data });

    try {
      const health = await botAPI.healthz();
      push('GET /v1/healthz', true, health.data);
    } catch (e) {
      push('GET /v1/healthz', false, e?.response?.data || e.toString());
    }

    try {
      const meta = await botAPI.metadata();
      push('GET /v1/metadata', true, meta.data);
    } catch (e) {
      push('GET /v1/metadata', false, e?.response?.data || e.toString());
    }

    try {
      const gen = await botAPI.playgroundGenerate();
      push('POST /v1/playground/generate', true, gen.data);
    } catch (e) {
      push('POST /v1/playground/generate', false, e?.response?.data || e.toString());
    }

    let firstTestId = null;
    let firstCase = null;
    try {
      const pairs = await botAPI.playgroundTestPairs();
      firstTestId = pairs.data?.[0]?.test_id || null;
      push('GET /v1/playground/test-pairs', Array.isArray(pairs.data), { count: pairs.data?.length || 0, first: pairs.data?.[0] });
    } catch (e) {
      push('GET /v1/playground/test-pairs', false, e?.response?.data || e.toString());
    }

    if (firstTestId) {
      try {
        const tc = await botAPI.playgroundTestCase(firstTestId);
        firstCase = tc.data;
        push('GET /v1/playground/test-case/:id', true, { test_id: firstTestId });
      } catch (e) {
        push('GET /v1/playground/test-case/:id', false, e?.response?.data || e.toString());
      }

      try {
        const composed = await botAPI.playgroundCompose({ test_id: firstTestId, force_template: true });
        push('POST /v1/playground/compose', true, composed.data);
      } catch (e) {
        push('POST /v1/playground/compose', false, e?.response?.data || e.toString());
      }
    }

    try {
      const docs = await botAPI.listDocs();
      push('GET /v1/docs/', Array.isArray(docs.data), { count: docs.data?.length || 0, first: docs.data?.[0] });
    } catch (e) {
      push('GET /v1/docs/', false, e?.response?.data || e.toString());
    }

    // Challenge contract smoke (real endpoints): /v1/context → /v1/tick → /v1/reply
    try {
      if (!firstCase?.category?.slug || !firstCase?.merchant?.merchant_id || !firstCase?.trigger?.id) {
        throw new Error('Missing test-case fields needed for contract flow');
      }

      const categoryCtx = await botAPI.pushContext({
        scope: 'category',
        context_id: firstCase.category.slug,
        version: 1,
        payload: firstCase.category,
        delivered_at: new Date().toISOString(),
      });
      push('POST /v1/context (category v1)', true, categoryCtx.data);

      const merchantV1 = await botAPI.pushContext({
        scope: 'merchant',
        context_id: firstCase.merchant.merchant_id,
        version: 1,
        payload: firstCase.merchant,
        delivered_at: new Date().toISOString(),
      });
      push('POST /v1/context (merchant v1)', true, merchantV1.data);

      const triggerV1 = await botAPI.pushContext({
        scope: 'trigger',
        context_id: firstCase.trigger.id,
        version: 1,
        payload: firstCase.trigger,
        delivered_at: new Date().toISOString(),
      });
      push('POST /v1/context (trigger v1)', true, triggerV1.data);

      if (firstCase.customer?.customer_id) {
        const customerV1 = await botAPI.pushContext({
          scope: 'customer',
          context_id: firstCase.customer.customer_id,
          version: 1,
          payload: firstCase.customer,
          delivered_at: new Date().toISOString(),
        });
        push('POST /v1/context (customer v1)', true, customerV1.data);
      }

      // Idempotency check: same version again should be rejected as stale/no-op.
      const merchantV1Again = await botAPI.pushContext({
        scope: 'merchant',
        context_id: firstCase.merchant.merchant_id,
        version: 1,
        payload: firstCase.merchant,
        delivered_at: new Date().toISOString(),
      });
      push('POST /v1/context (merchant v1 again)', merchantV1Again.data?.accepted === false, merchantV1Again.data);

      const merchantV2 = await botAPI.pushContext({
        scope: 'merchant',
        context_id: firstCase.merchant.merchant_id,
        version: 2,
        payload: firstCase.merchant,
        delivered_at: new Date().toISOString(),
      });
      push('POST /v1/context (merchant v2)', true, merchantV2.data);

      const tickRes = await botAPI.tick({
        now: new Date().toISOString(),
        available_triggers: [firstCase.trigger.id],
      });
      const actions = tickRes.data?.actions || [];
      push('POST /v1/tick', Array.isArray(actions), { actions_count: actions.length, first_action: actions[0] || null });

      const firstAction = actions[0];
      if (firstAction?.conversation_id && firstAction?.merchant_id) {
        const replyRes = await botAPI.reply({
          conversation_id: firstAction.conversation_id,
          merchant_id: firstAction.merchant_id,
          customer_id: firstAction.customer_id || null,
          from_role: 'merchant',
          message: 'Yes, send me the abstract',
          received_at: new Date().toISOString(),
          turn_number: 2,
        });
        push('POST /v1/reply', !!replyRes.data?.action, replyRes.data);
      } else {
        push('POST /v1/reply', false, { error: 'No action returned from /v1/tick to reply to' });
      }
    } catch (e) {
      push('Contract flow (/v1/context→/v1/tick→/v1/reply)', false, e?.response?.data || e.toString());
    }

    setSmoke(checks);
    setResult({
      summary: { total: checks.length, ok: checks.filter((c) => c.ok).length },
      checks,
    });
    setRunning(false);
  };

  return (
    <div className="testing-page">
      <div className="testing-header">
        <h2>🧪 Tests</h2>
        <p>Quickly run API checks + a one-click smoke test</p>
      </div>

      <div className="testing-grid">
        <Card title="Smoke Test" subtitle="Verifies key endpoints + playground helpers">
          <button onClick={runSmoke} disabled={running}>
            {running ? 'Running…' : 'Run Smoke Test'}
          </button>
          {smoke.length > 0 && (
            <div className="smoke-summary">
              <span>Checks: {summary.total}</span>
              <span className="ok">OK: {summary.ok}</span>
              <span className="fail">Fail: {summary.fail}</span>
            </div>
          )}
          <div className="smoke-list">
            {smoke.map((s) => (
              <div key={s.name} className={`smoke-item ${s.ok ? 'ok' : 'fail'}`}>
                <span className="smoke-dot" />
                <span className="smoke-name">{s.name}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Health Check">
          <button onClick={runHealth}>Run /v1/healthz</button>
        </Card>

        <Card title="Metadata">
          <button onClick={runMetadata}>Run /v1/metadata</button>
        </Card>

        <Card title="Result">
          <pre className="test-result">{result ? JSON.stringify(result, null, 2) : 'No result yet'}</pre>
        </Card>
      </div>
    </div>
  );
}

export default Testing;
