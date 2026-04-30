import { useState, useEffect } from 'react';
import { apiClient } from '../services/api';

export function useBot() {
  const [health, setHealth] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBotStatus = async () => {
      try {
        setLoading(true);
        const [healthRes, metadataRes] = await Promise.all([
          apiClient.get('/v1/healthz'),
          apiClient.get('/v1/metadata'),
        ]);
        
        setHealth(healthRes.data);
        setMetadata(metadataRes.data);
        setError(null);
      } catch (err) {
        setError(err.message || 'Failed to connect to bot');
        console.error('Bot status fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchBotStatus();
    
    // Refresh every 10 seconds
    const interval = setInterval(fetchBotStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  return { health, metadata, loading, error };
}
