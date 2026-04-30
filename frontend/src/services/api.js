import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle authentication error
      console.error('Unauthorized');
    }
    return Promise.reject(error);
  }
);

export const botAPI = {
  healthz: () => apiClient.get('/v1/healthz'),
  metadata: () => apiClient.get('/v1/metadata'),
  pushContext: (data) => apiClient.post('/v1/context', data),
  tick: (data) => apiClient.post('/v1/tick', data),
  reply: (data) => apiClient.post('/v1/reply', data),
  listDatasets: () => apiClient.get('/v1/datasets/'),
  getDataset: (name) => apiClient.get(`/v1/datasets/${name}`),
  playgroundGenerate: () => apiClient.post('/v1/playground/generate'),
  playgroundReset: () => apiClient.post('/v1/playground/reset'),
  playgroundTestPairs: () => apiClient.get('/v1/playground/test-pairs'),
  playgroundTestCase: (testId) => apiClient.get(`/v1/playground/test-case/${testId}`),
  playgroundCompose: (data) => apiClient.post('/v1/playground/compose', data),
  listDocs: () => apiClient.get('/v1/docs/'),
  getDoc: (name) => apiClient.get(`/v1/docs/${name}`),
};

// GROQ token: prefer Vite env, otherwise backend may have a default (check /v1/metadata.groq_default)
export const GROQ = {
  defaultKey: import.meta.env.VITE_GROQ_API_KEY || null,
};
