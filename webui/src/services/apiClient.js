import axios from 'axios';

// W12: Generate a unique request ID for each page session (changes on refresh)
const generateRequestId = () => Math.random().toString(36).substring(2, 10).toUpperCase();

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const getBaseURL = () => {
  if (DEFAULT_API_BASE) return DEFAULT_API_BASE;
  if (typeof window === 'undefined') return '/api';
  // Jika port standar 80 / 443 (misal cakra.ai melalui Nginx reverse proxy), gunakan origin /api
  if (!window.location.port || window.location.port === '80' || window.location.port === '443') {
    return `${window.location.origin}/api`;
  }
  return `${window.location.protocol}//${window.location.hostname}:8000/api`;
};

const apiClient = axios.create({
  // Gateway sebagai single entry point. VITE_API_BASE_URL selalu ke port 8000 (Gateway) atau reverse proxy /api.
  baseURL: getBaseURL(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// REQUEST INTERCEPTOR — Menyuntikkan token, NPP, dan Request ID secara otomatis
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('cakra_token');
    let user = null;
    try {
      const rawUser = localStorage.getItem('cakra_user');
      if (rawUser && rawUser !== 'undefined' && rawUser !== 'null') {
        user = JSON.parse(rawUser);
      }
    } catch (e) {
      user = null;
    }

    if (token && token !== 'undefined' && token !== 'null' && token.trim()) {
      config.headers['Authorization'] = `Bearer ${token.trim()}`;
    }
    
    if (user && user.npp && user.npp !== 'undefined' && user.npp !== 'null' && String(user.npp).trim()) {
      config.headers['X-NPP-Header'] = String(user.npp).trim();
    }

    // W12: Auto-inject unique X-Request-ID per request for backend tracing
    const requestId = generateRequestId();
    config.headers['X-Request-ID'] = requestId;
    config._requestId = requestId; // Store on config for error interceptor

    // Log to console for developer debugging
    console.debug(`[REQ-${requestId}] ${config.method?.toUpperCase()} ${config.url}`);

    return config;
  },
  (error) => Promise.reject(error)
);

// RESPONSE INTERCEPTOR — Log request ID on errors for debugging
apiClient.interceptors.response.use(
  (response) => {
    const reqId = response.config?._requestId;
    if (reqId) {
      console.debug(`[REQ-${reqId}] ✅ ${response.status} ${response.config.url}`);
    }
    return response;
  },
  (error) => {
    const reqId = error.config?._requestId;
    const status = error.response?.status || 'NETWORK';
    if (reqId) {
      console.warn(`[REQ-${reqId}] ❌ ${status} ${error.config?.url} — ${error.message}`);
      // Attach request ID to error for toast display
      error.requestId = reqId;
    }
    return Promise.reject(error);
  }
);

export default apiClient;