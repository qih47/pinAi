import axios from 'axios';

// W12: Generate a unique request ID for each page session (changes on refresh)
const generateRequestId = () => Math.random().toString(36).substring(2, 10).toUpperCase();

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const apiClient = axios.create({
  // 🔥 KUNCI DI SINI: Gunakan env var jika tersedia, jika tidak fallback ke port 5000 di host saat ini.
  baseURL: DEFAULT_API_BASE || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:5000/api` : '/api'),
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
    const user = JSON.parse(localStorage.getItem('cakra_user') || 'null');

    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    if (user && user.npp) {
      config.headers['X-NPP-Header'] = user.npp;
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