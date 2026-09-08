/**
 * CAKRA AI — Collab API Client
 * Berkomunikasi secara aman dengan Backend melalui API Gateway (:8000).
 */
import apiClient from '../../../services/apiClient';

export const collabApi = {
  // Ambil daftar ruang tim milik user
  getMyRooms: async (isArchived = false) => {
    const res = await apiClient.get(`/collab/rooms?is_archived=${isArchived}`);
    return res.data?.rooms || [];
  },

  // Ambil daftar ruang tim yang diarsipkan
  getArchivedRooms: async () => {
    const res = await apiClient.get('/collab/rooms?is_archived=true');
    return res.data?.rooms || [];
  },

  // Ubah nama/judul ruang diskusi
  renameRoom: async (roomId, name) => {
    const res = await apiClient.put(`/collab/rooms/${roomId}/title`, { name });
    return res.data;
  },

  // Arsipkan atau pulihkan ruang diskusi
  archiveRoom: async (roomId, isArchived = true) => {
    const res = await apiClient.put(`/collab/rooms/${roomId}/archive?is_archived=${isArchived}`);
    return res.data;
  },

  // Hapus ruang diskusi permanen
  deleteRoom: async (roomId) => {
    const res = await apiClient.delete(`/collab/rooms/${roomId}`);
    return res.data;
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

  // Tambahkan poin catatan baru (addition) ke dokumen Pad secara atomic di backend
  appendToDocument: async (roomId, text, senderName = null) => {
    const res = await apiClient.post(`/collab/rooms/${roomId}/document/append`, {
      text,
      sender_name: senderName
    });
    return res.data;
  },

  // Rangkum seluruh obrolan tim menjadi Notulensi Resmi otomatis via CAKRA AI
  summarizeRoom: async (roomId) => {
    const res = await apiClient.post(`/collab/rooms/${roomId}/summarize`);
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

  // Upload lampiran berkas fisik ke ruang diskusi tim
  uploadAttachments: async (roomId, files) => {
    const formData = new FormData();
    files.forEach((f) => {
      const fileBlob = f?.file_obj || f;
      formData.append('files', fileBlob);
    });
    const res = await apiClient.post(`/collab/rooms/${roomId}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data?.attachments || [];
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
  },

  // Ambil daftar undangan pending
  getInvitations: async () => {
    const res = await apiClient.get('/collab/rooms/invitations');
    return res.data?.invitations || [];
  },

  // Ambil total jumlah undangan pending untuk notification badge
  getInvitationsCount: async () => {
    const res = await apiClient.get('/collab/rooms/invitations/count');
    return res.data?.count || 0;
  },

  // Respons undangan: action = 'accept' | 'reject'
  respondInvitation: async (roomId, action) => {
    const res = await apiClient.put(`/collab/rooms/${roomId}/invitations/respond`, {
      action
    });
    return res.data;
  },

  // Ambil total pesan belum dibaca di seluruh ruangan
  getUnreadCount: async () => {
    const res = await apiClient.get('/collab/rooms/unread/count');
    return res.data?.unread_count || 0;
  },

  // Tandai ruangan sudah dibaca
  markRoomRead: async (roomId) => {
    const res = await apiClient.put(`/collab/rooms/${roomId}/read`);
    return res.data;
  }
};
