import { create } from 'zustand';
import apiClient from '../services/apiClient';

export const useChatAuthStore = create((set) => ({
  // 🔥 FIX 1: Bersihkan kelebihan kurung tutup di baris token ini
  user: JSON.parse(localStorage.getItem('cakra_user')) || null,
  token: localStorage.getItem('cakra_token') || null,
  expiresAt: localStorage.getItem('cakra_expiresAt') ? new Date(localStorage.getItem('cakra_expiresAt')) : null,
  isAuthenticated: !!localStorage.getItem('cakra_token'),
  isLoading: false,
  error: null,

  // 🔐 FUNGSI 1: LOGIN ENGINE (SINKRON DATA & TOKEN FASTAPI)
  login: async (identifier, password, guestSessionId = null) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post('/auth/login', {
        username: identifier,
        password: password,
        guest_session_id: guestSessionId
      });

      // Di dalam fungsi login & checkSession pada authStore.js lo, simpan objeknya utuh:
      const { token, npp, fullname, preferred_name, profile_photo_url, divisi, role, email, is_onboarded, preferred_language, theme_preference, communication_style, expires_at } = response.data.data;
      const bustedPhotoUrl = profile_photo_url ? `${profile_photo_url.split('?')[0]}?t=${Date.now()}` : null;
      const userData = { 
        npp, 
        fullname, 
        name: fullname, 
        preferred_name, 
        profile_photo_url: bustedPhotoUrl, 
        username: npp, 
        divisi, 
        role, 
        email,
        is_onboarded: is_onboarded ?? false,
        preferred_language: preferred_language || 'id',
        theme_preference: theme_preference || 'light',
        communication_style: communication_style || 'formal_saya_anda'
      }; // 👈 Mengikuti struktur row data DB FastAPI lo
      
      // Parse expires_at timestamp (B10 Token Expiry Sync)
      const expiresAt = expires_at ? new Date(expires_at) : new Date(Date.now() + 8 * 60 * 60 * 1000);

      localStorage.setItem('cakra_token', token);
      localStorage.setItem('cakra_user', JSON.stringify(userData));
      localStorage.setItem('cakra_expiresAt', expiresAt.toISOString());

      set({ token, user: userData, expiresAt, isAuthenticated: true, isLoading: false });
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
      set({ isAuthenticated: false, user: null, token: null, expiresAt: null });
      return false;
    }

    try {
      const response = await apiClient.get(`/auth/verify-session?token=${currentToken}&_t=${Date.now()}`);
      const { npp, fullname, preferred_name, profile_photo_url, divisi, role, email, is_onboarded, preferred_language, theme_preference, communication_style, expires_at } = response.data.data;

      const bustedPhotoUrl = profile_photo_url ? `${profile_photo_url.split('?')[0]}?t=${Date.now()}` : null;

      const userData = {
        npp,
        username: npp,
        name: fullname,
        fullname,
        preferred_name,
        profile_photo_url: bustedPhotoUrl,
        divisi,
        role,
        email,
        is_onboarded: is_onboarded ?? false,
        preferred_language: preferred_language || 'id',
        theme_preference: theme_preference || 'light',
        communication_style: communication_style || 'formal_saya_anda'
      };

      // Parse expires_at timestamp (B10 Token Expiry Sync)
      const expiresAt = expires_at ? new Date(expires_at) : new Date(Date.now() + 8 * 60 * 60 * 1000);
      localStorage.setItem('cakra_expiresAt', expiresAt.toISOString());
      localStorage.setItem('cakra_user', JSON.stringify(userData)); // Sync updated user profile to local storage

      set({
        user: userData,
        token: currentToken,
        expiresAt,
        isAuthenticated: true
      });
      return true;
    } catch (err) {
      localStorage.removeItem('cakra_token');
      localStorage.removeItem('cakra_user');
      localStorage.removeItem('cakra_expiresAt');
      set({ isAuthenticated: false, user: null, token: null, expiresAt: null });
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
      localStorage.removeItem('cakra_expiresAt');
      set({
        user: null,
        token: null,
        expiresAt: null,
        isAuthenticated: false,
        error: null
      });
    }
  },

  clearError: () => set({ error: null })
}));