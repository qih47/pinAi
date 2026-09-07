/**
 * CAKRA AI — Collab API Client
 * Berkomunikasi secara aman dengan Backend melalui API Gateway (:8000).
 */
import apiClient from '../../../services/apiClient';

export const collabApi = {
  // Ambil daftar ruang tim milik user
  getMyRooms: async () => {
    const res = await apiClient.get('/collab/rooms');
    return res.data?.rooms || [];
  },

  // Buat ruang diskusi baru
  createRoom: async ({ name, topic, initialMembers, documentContent }) => {
    const res = await apiClient.post('/collab/rooms', {
      name,
      topic,
      initial_members: initialMembers || [],
      document_content: documentContent || ''
    });
    return res.data?.room;
  },

  // Ambil detail ruang & daftar anggota
  getRoomDetail: async (roomId) => {
    const res = await apiClient.get(`/collab/rooms/${roomId}`);
    return res.data?.room;
  },

  // Update draf dokumen kerja di Document Pad
  updateDocument: async (roomId, documentContent) => {
    const res = await apiClient.put(`/collab/rooms/${roomId}/document`, {
      document_content: documentContent
    });
    return res.data;
  },

  // Undang anggota baru
  inviteMembers: async (roomId, npps) => {
    const res = await apiClient.post(`/collab/rooms/${roomId}/invite`, {
      npps
    });
    return res.data;
  },

  // Ambil riwayat chat ruang
  getMessages: async (roomId, limit = 50) => {
    const res = await apiClient.get(`/collab/rooms/${roomId}/messages?limit=${limit}`);
    return res.data?.messages || [];
  },

  // Kirim pesan obrolan tim baru (dengan dukungan lampiran & mode preset)
  sendMessage: async (roomId, messageText, attachments = [], mode = null) => {
    const res = await apiClient.post(`/collab/rooms/${roomId}/messages`, {
      message_text: messageText,
      attachments,
      mode: mode || undefined
    });
    return res.data?.message;
  },

  // Edit pesan milik sendiri
  editMessage: async (roomId, messageId, messageText) => {
    const res = await apiClient.put(`/collab/rooms/${roomId}/messages/${messageId}`, {
      message_text: messageText
    });
    return res.data?.message;
  },

  // Kirim status mengetik real-time
  sendTypingStatus: async (roomId, isTyping) => {
    try {
      await apiClient.post(`/collab/rooms/${roomId}/typing`, {
        is_typing: isTyping
      });
    } catch (e) {
      // Non-blocking error
    }
  },

  // Cari personil untuk diundang
  searchPersonnel: async (query) => {
    if (!query || query.trim().length < 1) return [];
    const res = await apiClient.get(`/collab/personnel/search?q=${encodeURIComponent(query.trim())}`);
    return res.data?.results || [];
  }
};
