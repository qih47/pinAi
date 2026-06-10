import axios from 'axios';

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

// REQUEST INTERCEPTOR (Tetap sama untuk menyuntikkan X-NPP-Header otomatis)
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('cakra_token');
    const user = JSON.parse(localStorage.getItem('cakra_user'));

    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    if (user && user.npp) {
      config.headers['X-NPP-Header'] = user.npp;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;