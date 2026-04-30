import React, { useEffect, useState } from 'react';
import Card from '../components/Card';
import { botAPI } from '../services/api';
import './Docs.css';

function Docs() {
  const [files, setFiles] = useState([]);
  const [active, setActive] = useState(null);
  const [content, setContent] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    botAPI
      .listDocs()
      .then((res) => setFiles(res.data || []))
      .catch((e) => setError(e?.response?.data?.detail || e.toString()));
  }, []);

  const open = async (name) => {
    setActive(name);
    setError(null);
    try {
      const res = await botAPI.getDoc(name);
      setContent(res.data?.content || '');
    } catch (e) {
      setContent(null);
      setError(e?.response?.data?.detail || e.toString());
    }
  };

  return (
    <div className="docs-page">
      <div className="docs-header">
        <h2>📄 Docs</h2>
        <p>Read the provided markdown briefs inside the dashboard</p>
      </div>

      {error && (
        <div className="docs-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      <div className="docs-layout">
        <Card title="Files">
          <ul className="docs-list">
            {files.map((f) => (
              <li key={f}>
                <button className={`docs-item ${active === f ? 'active' : ''}`} onClick={() => open(f)}>
                  {f}
                </button>
              </li>
            ))}
            {files.length === 0 && <div className="docs-empty">No docs found</div>}
          </ul>
        </Card>

        <Card title={active ? active : 'Content'}>
          <pre className="docs-content">{content ?? 'Select a file'}</pre>
        </Card>
      </div>
    </div>
  );
}

export default Docs;

