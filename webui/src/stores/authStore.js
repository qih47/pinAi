import { create } from 'zustand';
import apiClient from '../services/apiClient';

export const useChatAuthStore = create((set) => ({
  // 🔥 FIX 1: Bersihkan kelebihan kurung tutup di baris token ini
  user: JSON.parse(localStorage.getItem('cakra_user')) || null,
  token: localStorage.getItem('cakra_token') || null,
  isAuthenticated: !!localStorage.getItem('cakra_token'),
  isLoading: false,
  error: null,

  // 🔐 FUNGSI 1: LOGIN ENGINE (SINKRON DATA & TOKEN FASTAPI)
  login: async (identifier, password) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post('/auth/login', {
        username: identifier,
        password: password
      });

      // Di dalam fungsi login & checkSession pada authStore.js lo, simpan objeknya utuh:
      const { token, npp, fullname, divisi, role } = response.data.data;
      const userData = { npp, fullname, divisi, role }; // 👈 Mengikuti struktur row data DB FastAPI lo

      localStorage.setItem('cakra_token', token);
      localStorage.setItem('cakra_user', JSON.stringify(userData));

      set({ token, user: userData, isAuthenticated: true, isLoading: false });
      return { success: true };
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Gagal masuk, periksa kembali kredensial Anda! ❌';
      set({ error: errorMsg, isLoading: false });
      return { success: false, message: errorMsg };
    }
  },

  // 🔍 FUNGSI 2: VERIFIKASI TOKEN (ANTI-DUPLIKAT)
  checkSession: async () => {
    const currentToken = localStorage.getItem('cakra_token');
    if (!currentToken) {
      set({ isAuthenticated: false, user: null, token: null });
      return false;
    }

    try {
      const response = await apiClient.get(`/auth/verify-session?token=${currentToken}`);
      const { npp, fullname, divisi, role } = response.data.data;

      const userData = {
        npp,
        username: npp,
        name: fullname,
        fullname,
        divisi,
        role
      };

      set({
        user: userData,
        token: currentToken,
        isAuthenticated: true
      });
      return true;
    } catch (err) {
      localStorage.removeItem('cakra_token');
      localStorage.removeItem('cakra_user');
      set({ isAuthenticated: false, user: null, token: null });
      return false;
    }
  },

  // 🔓 FUNGSI 3: LOGOUT ENGINE + HIT AUDIT TRAIL BE
  logout: async () => {
    const currentToken = localStorage.getItem('cakra_token');
    try {
      if (currentToken) {
        await apiClient.post('/auth/logout', { token: currentToken });
      }
    } catch (err) {
      console.error("Gagal mencatat audit log keluar di server:", err);
    } finally {
      // 🔥 FIX 2: Sektor penentu yang bikin eror di gambar lo tadi, kurung tutup liarnya udah dibuang
      localStorage.removeItem('cakra_token');
      localStorage.removeItem('cakra_user');
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        error: null
      });
    }
  },

  clearError: () => set({ error: null })
}));