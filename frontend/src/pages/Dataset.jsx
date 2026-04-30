import React, { useEffect, useState } from 'react';
import Card from '../components/Card';
import { botAPI } from '../services/api';
import './Dataset.css';

function Dataset() {
  const [files, setFiles] = useState([]);
  const [content, setContent] = useState(null);

  useEffect(() => {
    botAPI.listDatasets().then((res) => setFiles(res.data)).catch(() => setFiles([]));
  }, []);

  const load = (name) => {
    botAPI.getDataset(name).then((res) => setContent(res.data)).catch((e) => setContent({ error: e.toString() }));
  };

  return (
    <div className="dataset-page">
      <div className="dataset-header">
        <h2>📦 Dataset</h2>
        <p>View seed data used by the system</p>
      </div>

      <div className="dataset-grid">
        <Card title="Files">
          <ul className="dataset-list">
            {files.map((f) => (
              <li key={f}>
                <button onClick={() => load(f)}>{f}</button>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Content">
          <pre className="dataset-content">{content ? JSON.stringify(content, null, 2) : 'Select a file to view'}</pre>
        </Card>
      </div>
    </div>
  );
}

export default Dataset;
