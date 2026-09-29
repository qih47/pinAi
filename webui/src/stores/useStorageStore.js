import { create } from 'zustand';
import apiClient from '../services/apiClient';

export const useStorageStore = create((set, get) => ({
  storageStats: null,
  isLoading: false,
  isPurging: false,
  error: null,
  
  // UI Dialog & Banner States
  isStorageQuotaModalOpen: false,
  dismissedWarningBanner: false,
  isSettingsModalOpen: false,
  settingsTab: "storage",
  
  // Setter untuk dismiss banner
  dismissBanner: () => set({ dismissedWarningBanner: true }),
  
  // Modal Quota Warning Control
  openQuotaModal: () => set({ isStorageQuotaModalOpen: true }),
  closeQuotaModal: () => set({ isStorageQuotaModalOpen: false }),

  // Global Settings Modal Opener (allows opening specific tab from anywhere)
  openSettingsModal: (tab = "storage") => set({ isSettingsModalOpen: true, settingsTab: tab }),
  closeSettingsModal: () => set({ isSettingsModalOpen: false }),

  // Fetch Storage Stats (Hanya aktif untuk user terautentikasi, Guest tidak memiliki batas kuota akun)
  fetchStorageStats: async (forceRefresh = false) => {
    const token = localStorage.getItem('cakra_token');
    if (!token) {
      set({ storageStats: null, isLoading: false, error: null });
      return null;
    }
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.get(`/user/storage/stats${forceRefresh ? '?force_refresh=true' : ''}`);
      if (response.data?.status === 'success') {
        set({ storageStats: response.data.data, isLoading: false });
        return response.data.data;
      }
    } catch (err) {
      if (err.response?.status === 401) {
        set({ storageStats: null, isLoading: false });
        return null;
      }
      console.error("Gagal mengambil data kuota storage:", err);
      set({ error: err.message || 'Gagal memuat status penyimpanan', isLoading: false });
    }
    return null;
  },

  // 1. Purge Attachments & Images (Free space instantly without deleting text chat)
  purgeAttachments: async () => {
    const token = localStorage.getItem('cakra_token');
    if (!token) return null;
    set({ isPurging: true, error: null });
    try {
      const response = await apiClient.post('/user/storage/purge-attachments');
      if (response.data?.status === 'success') {
        const stats = response.data.data?.current_stats;
        if (stats) set({ storageStats: stats });
        set({ isPurging: false, isStorageQuotaModalOpen: false });
        return response.data.data;
      }
    } catch (err) {
      console.error("Gagal membersihkan lampiran:", err);
      set({ isPurging: false, error: err.message });
      throw err;
    }
  },

  // 2. Purge AI Artifacts & Drafts
  purgeArtifacts: async () => {
    const token = localStorage.getItem('cakra_token');
    if (!token) return null;
    set({ isPurging: true, error: null });
    try {
      const response = await apiClient.post('/user/storage/purge-artifacts');
      if (response.data?.status === 'success') {
        const stats = response.data.data?.current_stats;
        if (stats) set({ storageStats: stats });
        set({ isPurging: false });
        return response.data.data;
      }
    } catch (err) {
      console.error("Gagal membersihkan artefak:", err);
      set({ isPurging: false, error: err.message });
      throw err;
    }
  },

  // 3. Clear All Private Chats
  clearPrivateChats: async () => {
    const token = localStorage.getItem('cakra_token');
    if (!token) return null;
    set({ isPurging: true, error: null });
    try {
      const response = await apiClient.post('/user/storage/clear-chats');
      if (response.data?.status === 'success') {
        const stats = response.data.data?.current_stats;
        if (stats) set({ storageStats: stats });
        set({ isPurging: false });
        // Tembakkan event agar sidebar & chat history ter-refresh seketika
        window.dispatchEvent(new CustomEvent("cakra-refresh-chat-history"));
        return response.data.data;
      }
    } catch (err) {
      console.error("Gagal menghapus percakapan pribadi:", err);
      set({ isPurging: false, error: err.message });
      throw err;
    }
  },

  // 4. Clear Collab Rooms
  clearCollabs: async () => {
    const token = localStorage.getItem('cakra_token');
    if (!token) return null;
    set({ isPurging: true, error: null });
    try {
      const response = await apiClient.post('/user/storage/clear-collabs');
      if (response.data?.status === 'success') {
        const stats = response.data.data?.current_stats;
        if (stats) set({ storageStats: stats });
        set({ isPurging: false });
        return response.data.data;
      }
    } catch (err) {
      console.error("Gagal menghapus ruang collab:", err);
      set({ isPurging: false, error: err.message });
      throw err;
    }
  },

  // 5. Total Wipe Out Data
  wipeAllUserData: async () => {
    const token = localStorage.getItem('cakra_token');
    if (!token) return null;
    set({ isPurging: true, error: null });
    try {
      const response = await apiClient.post('/user/storage/wipe-all');
      if (response.data?.status === 'success') {
        const stats = response.data.data?.current_stats;
        if (stats) set({ storageStats: stats });
        set({ isPurging: false, isStorageQuotaModalOpen: false });
        // Tembakkan event agar riwayat chat bersih seketika
        window.dispatchEvent(new CustomEvent("cakra-refresh-chat-history"));
        return response.data.data;
      }
    } catch (err) {
      console.error("Gagal melakukan pembersihan total:", err);
      set({ isPurging: false, error: err.message });
      throw err;
    }
  }
}));

export default useStorageStore;
