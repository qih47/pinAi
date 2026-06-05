import axios from 'axios';

const apiClient = axios.create({
  // 🔥 KUNCI DI SINI: Samakan dengan IP server BE lo, port 8000, plus prefix /api
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://192.168.11.80:5000/api', 
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