import React, { useState, useEffect, useRef } from 'react';
import './APIMonitor.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const METHOD_COLORS = {
  GET: '#10b981',
  POST: '#6366f1',
  PUT: '#f59e0b',
  PATCH: '#f59e0b',
  DELETE: '#ef4444',
};

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatMs(ms) {
  if (ms < 10) return `${ms.toFixed(1)}ms`;
  return `${Math.round(ms)}ms`;
}

function statusColor(code) {
  if (code < 300) return '#10b981';
  if (code < 400) return '#f59e0b';
  return '#ef4444';
}

function truncateJson(obj, max = 300) {
  if (!obj) return '';
  const s = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
  return s.length > max ? s.slice(0, max) + '\n...' : s;
}

function APIMonitor() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(3);
  const [filterMethod, setFilterMethod] = useState('');
  const [filterPath, setFilterPath] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [search, setSearch] = useState('');
  const [selectedLog, setSelectedLog] = useState(null);
  const [page, setPage] = useState(0);
  const pageSize = 50;
  const intervalRef = useRef(null);

  const fetchLogs = async () => {
    try {
      const params = new URLSearchParams({ limit: pageSize, offset: page * pageSize });
      if (filterMethod) params.set('method', filterMethod);
      if (filterPath) params.set('path', filterPath);
      if (filterStatus) params.set('status', filterStatus);
      if (search) params.set('search', search);

      const resp = await fetch(`${API_BASE}/v1/monitor/logs?${params}`);
      const data = await resp.json();
      setLogs(data.logs || []);
      setStats(data.stats || null);
    } catch (e) {
      console.error('Failed to fetch logs:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, filterMethod, filterPath, filterStatus, search]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchLogs, refreshInterval * 1000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, refreshInterval]);

  const handleClear = async () => {
    if (!confirm('Clear all request logs?')) return;
    await fetch(`${API_BASE}/v1/monitor/logs`, { method: 'DELETE' });
    fetchLogs();
  };

  const totalPages = stats ? Math.ceil(stats.total_requests / pageSize) : 1;

  return (
    <div className="api-monitor">
      <div className="monitor-header">
        <div>
          <h2>🔍 API Monitor</h2>
          <p className="monitor-subtitle">Real-time request tracking — who hits the backend, what they request, when</p>
        </div>
        <div className="monitor-controls">
          <label className="auto-refresh-toggle">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            <span>Auto-refresh</span>
          </label>
          <select value={refreshInterval} onChange={e => setRefreshInterval(Number(e.target.value))} disabled={!autoRefresh}>
            <option value={1}>Every 1s</option>
            <option value={3}>Every 3s</option>
            <option value={5}>Every 5s</option>
            <option value={10}>Every 10s</option>
          </select>
          <button className="btn-clear" onClick={handleClear}>🗑️ Clear</button>
          <button className="btn-refresh" onClick={fetchLogs}>🔄 Refresh</button>
        </div>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_requests}</div>
            <div className="stat-label">Total Requests</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: statusColor(200) }}>{stats.avg_duration_ms}ms</div>
            <div className="stat-label">Avg Response Time</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: stats.error_rate > 5 ? '#ef4444' : '#10b981' }}>
              {stats.error_rate}%
            </div>
            <div className="stat-label">Error Rate ({stats.error_count} errors)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.methods['POST'] || 0}</div>
            <div className="stat-label">POST Requests</div>
          </div>
        </div>
      )}

      <div className="monitor-filters">
        <select value={filterMethod} onChange={e => { setFilterMethod(e.target.value); setPage(0); }} className="filter-select">
          <option value="">All Methods</option>
          <option value="GET">GET</option>
          <option value="POST">POST</option>
          <option value="DELETE">DELETE</option>
        </select>
        <input
          type="text"
          placeholder="Filter by path..."
          value={filterPath}
          onChange={e => { setFilterPath(e.target.value); setPage(0); }}
          className="filter-input"
        />
        <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(0); }} className="filter-select">
          <option value="">All Status</option>
          <option value="200">200 OK</option>
          <option value="201">201 Created</option>
          <option value="400">400 Bad Request</option>
          <option value="401">401 Unauthorized</option>
          <option value="404">404 Not Found</option>
          <option value="422">422 Unprocessable</option>
          <option value="500">500 Error</option>
        </select>
        <input
          type="text"
          placeholder="Search in request/response..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
          className="filter-input search-input"
        />
        {(filterMethod || filterPath || filterStatus || search) && (
          <button className="btn-reset-filters" onClick={() => { setFilterMethod(''); setFilterPath(''); setFilterStatus(''); setSearch(''); setPage(0); }}>
            ✕ Reset
          </button>
        )}
      </div>

      {stats && stats.top_endpoints && Object.keys(stats.top_endpoints).length > 0 && (
        <div className="top-endpoints">
          <h3>Top Endpoints</h3>
          <div className="endpoint-bars">
            {Object.entries(stats.top_endpoints).slice(0, 8).map(([path, count]) => {
              const maxCount = Math.max(...Object.values(stats.top_endpoints));
              const pct = (count / maxCount) * 100;
              return (
                <div key={path} className="endpoint-bar-row" onClick={() => { setFilterPath(path); setPage(0); }}>
                  <span className="endpoint-bar-path" title={path}>{path}</span>
                  <div className="endpoint-bar-bg">
                    <div className="endpoint-bar-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="endpoint-bar-count">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="logs-table-container">
        <table className="logs-table">
          <thead>
            <tr>
              <th style={{ width: '70px' }}>Time</th>
              <th style={{ width: '65px' }}>Method</th>
              <th style={{ width: '220px' }}>Path</th>
              <th style={{ width: '65px' }}>Status</th>
              <th style={{ width: '80px' }}>Duration</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="6" className="loading-row">Loading...</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan="6" className="empty-row">No requests logged yet. Interact with the API to see logs here.</td></tr>
            ) : (
              logs.map((log) => (
                <tr
                  key={log.id}
                  className={`log-row ${selectedLog?.id === log.id ? 'selected' : ''} ${log.status_code >= 400 ? 'error-row' : ''}`}
                  onClick={() => setSelectedLog(selectedLog?.id === log.id ? null : log)}
                >
                  <td className="time-cell">
                    <div className="time-date">{formatDate(log.timestamp)}</div>
                    <div className="time-clock">{formatTime(log.timestamp)}</div>
                  </td>
                  <td>
                    <span className="method-badge" style={{ background: METHOD_COLORS[log.method] + '25', color: METHOD_COLORS[log.method] }}>
                      {log.method}
                    </span>
                  </td>
                  <td className="path-cell" title={log.path}>{log.path}</td>
                  <td>
                    <span className="status-badge" style={{ background: statusColor(log.status_code) + '25', color: statusColor(log.status_code) }}>
                      {log.status_code}
                    </span>
                  </td>
                  <td className="duration-cell">
                    <span className={`duration-badge ${log.duration_ms > 500 ? 'slow' : log.duration_ms > 200 ? 'medium' : 'fast'}`}>
                      {formatMs(log.duration_ms)}
                    </span>
                  </td>
                  <td className="summary-cell" title={log.response_summary}>{log.response_summary}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedLog && (
        <div className="log-detail-overlay" onClick={() => setSelectedLog(null)}>
          <div className="log-detail-card" onClick={e => e.stopPropagation()}>
            <div className="log-detail-header">
              <h3>Request Details</h3>
              <button className="log-detail-close" onClick={() => setSelectedLog(null)}>✕</button>
            </div>
            <div className="log-detail-grid">
              <div className="detail-field">
                <label>Timestamp</label>
                <span>{selectedLog.timestamp}</span>
              </div>
              <div className="detail-field">
                <label>Method</label>
                <span className="method-badge" style={{ background: METHOD_COLORS[selectedLog.method] + '25', color: METHOD_COLORS[selectedLog.method] }}>
                  {selectedLog.method}
                </span>
              </div>
              <div className="detail-field full-width">
                <label>Path</label>
                <code>{selectedLog.path}{selectedLog.query ? `?${selectedLog.query}` : ''}</code>
              </div>
              <div className="detail-field">
                <label>Status</label>
                <span style={{ color: statusColor(selectedLog.status_code), fontWeight: 600 }}>{selectedLog.status_code}</span>
              </div>
              <div className="detail-field">
                <label>Duration</label>
                <span>{formatMs(selectedLog.duration_ms)}</span>
              </div>
              <div className="detail-field">
                <label>IP</label>
                <code>{selectedLog.ip || '—'}</code>
              </div>
              <div className="detail-field">
                <label>User Agent</label>
                <code className="ua-code">{selectedLog.user_agent || '—'}</code>
              </div>
              {selectedLog.request_body && (
                <div className="detail-field full-width">
                  <label>Request Body</label>
                  <pre className="json-block">{truncateJson(selectedLog.request_body, 2000)}</pre>
                </div>
              )}
              {selectedLog.response_body && (
                <div className="detail-field full-width">
                  <label>Response Body</label>
                  <pre className="json-block">{truncateJson(selectedLog.response_body, 2000)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span>Page {page + 1} of {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}

export default APIMonitor;
