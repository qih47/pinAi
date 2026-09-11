import { create } from 'zustand';
import apiClient from '../services/apiClient';
import { defaultTemplates } from '../features/doc_writer/templates/defaultTemplates';

const getUserInfo = () => {
  try {
    const raw = localStorage.getItem('cakra_user');
    if (!raw) return { isGuest: true, npp: 'guest', name: 'Tamu' };
    const u = JSON.parse(raw);
    const isGuest = Boolean(u?.isGuest || u?.role === 'guest' || u?.npp === 'GUEST');
    return {
      isGuest,
      npp: u?.npp || 'guest',
      name: u?.nama || u?.name || 'Pegawai PT Pindad'
    };
  } catch {
    return { isGuest: true, npp: 'guest', name: 'Tamu' };
  }
};

const getStorageKey = (sessionId, roomId, npp) => {
  if (roomId) return `cakra_active_doc_room_${roomId}`;
  if (sessionId) return `cakra_active_doc_session_${sessionId}`;
  return `cakra_active_doc_user_${npp || 'default'}`;
};

export const useDocWriterStore = create((set, get) => ({
  isOpen: false,
  isAiActivated: false,
  setAiActivated: (val) => set({ isAiActivated: Boolean(val) }),
  splitWidth: null, // null = default 50% split-screen

  currentSessionId: null,
  currentRoomId: null,

  // Dokumen Aktif
  currentDocId: null,
  activeDocument: {
    id: null,
    title: 'Surat Keputusan Direksi PT Pindad',
    templateId: 'template_skep',
    htmlContent: '',
    lastSavedAt: null,
  },
  activeTemplateId: 'template_skep',
  templates: [],
  isLoadingTemplates: false,
  isCreatingDocument: false,
  isExporting: false,
  isTemplateModalOpen: false,
  setTemplateModalOpen: (val) => set({ isTemplateModalOpen: Boolean(val) }),
  lastAiEditTimestamp: null,

  setContext: (sessionId = null, roomId = null) => {
    const prevSession = get().currentSessionId;
    const prevRoom = get().currentRoomId;
    if (prevSession === sessionId && prevRoom === roomId) return;

    set({ currentSessionId: sessionId, currentRoomId: roomId });
    // Restore dokumen aktif untuk konteks ini
    const { npp } = getUserInfo();
    const storageKey = getStorageKey(sessionId, roomId, npp);
    try {
      const savedDocId = localStorage.getItem(storageKey);
      if (savedDocId) {
        set({ currentDocId: savedDocId });
      }
    } catch (e) {}
  },

  // Mengambil dokumen aktif yang tersimpan di server untuk sesi/room saat ini
  loadActiveDocument: async (sessionId = null, roomId = null) => {
    const { isGuest, npp } = getUserInfo();
    if (isGuest) return null;

    const sId = sessionId || get().currentSessionId || '';
    const rId = roomId || get().currentRoomId || '';

    try {
      const res = await apiClient.get('/doc-writer/active', {
        params: {
          npp: npp,
          session_id: sId,
          room_id: rId
        }
      });

      if (res.data?.success && res.data?.document) {
        const doc = res.data.document;
        const storageKey = getStorageKey(sId, rId, npp);
        try { localStorage.setItem(storageKey, doc.doc_id); } catch (e) {}

        set({
          currentDocId: doc.doc_id,
          activeTemplateId: doc.template_id || 'template_se',
          activeDocument: {
            id: doc.doc_id,
            title: doc.title || 'Dokumen Resmi PT Pindad',
            templateId: doc.template_id || 'template_se',
            lastSavedAt: doc.updated_at
          }
        });
        return doc;
      }
    } catch (err) {
      console.warn('[DOC_WRITER] Gagal memuat dokumen aktif dari server:', err);
    }
    return null;
  },

  // Pembuatan dokumen baru via Backend API
  createDocument: async (templateId = 'template_blank', initialTitle = null, sessionId = null, roomId = null) => {
    const { isGuest, npp } = getUserInfo();
    if (isGuest) {
      console.warn('[DOC_WRITER] Akses tamu ditolak.');
      return null;
    }

    const sId = sessionId || get().currentSessionId || '';
    const rId = roomId || get().currentRoomId || '';

    set({ isCreatingDocument: true });
    try {
      const res = await apiClient.post('/doc-writer/create', {
        template_id: templateId,
        title: initialTitle,
        npp: npp,
        session_id: sId,
        room_id: rId
      });

      if (res.data?.success && res.data?.document) {
        const doc = res.data.document;
        const storageKey = getStorageKey(sId, rId, npp);
        try { localStorage.setItem(storageKey, doc.doc_id); } catch (e) {}

        set({
          currentDocId: doc.doc_id,
          activeTemplateId: doc.template_id,
          activeDocument: {
            id: doc.doc_id,
            title: doc.title,
            templateId: doc.template_id,
            lastSavedAt: doc.updated_at
          },
          isCreatingDocument: false
        });
        return doc;
      }
    } catch (err) {
      console.error('[DOC_WRITER] Gagal membuat dokumen baru di server:', err);
    } finally {
      set({ isCreatingDocument: false });
    }
    return null;
  },

  openWriter: async (templateId = null, initialTitle = null, initialContent = null, docId = null, sessionId = null, roomId = null) => {
    const { isGuest, npp } = getUserInfo();
    if (isGuest) {
      console.warn('[DOC_WRITER] Tamu (Guest) dilarang membuka Document Studio.');
      return;
    }

    const state = get();
    const sId = sessionId || state.currentSessionId || null;
    const rId = roomId || state.currentRoomId || null;
    if (sId !== state.currentSessionId || rId !== state.currentRoomId) {
      set({ currentSessionId: sId, currentRoomId: rId });
    }

    // 1. Jika docId spesifik diberikan, langsung gunakan
    if (docId) {
      const targetTemplateId = templateId || state.activeTemplateId || 'template_se';
      const storageKey = getStorageKey(sId, rId, npp);
      try { localStorage.setItem(storageKey, docId); } catch (e) {}

      set({
        isOpen: true,
        isAiActivated: true,
        currentDocId: docId,
        activeTemplateId: targetTemplateId,
        activeDocument: {
          ...state.activeDocument,
          id: docId,
          title: initialTitle || state.activeDocument.title,
          templateId: targetTemplateId
        }
      });
      return docId;
    }

    // 2. Jika sudah ada dokumen aktif di state yang valid, gunakan itu
    if (state.currentDocId) {
      set({ isOpen: true, isAiActivated: true });
      return state.currentDocId;
    }

    // 3. Cek localStorage apakah ada dokumen tersimpan untuk konteks ini
    const storageKey = getStorageKey(sId, rId, npp);
    try {
      const savedDocId = localStorage.getItem(storageKey);
      if (savedDocId) {
        set({
          isOpen: true,
          isAiActivated: true,
          currentDocId: savedDocId,
          activeTemplateId: templateId || state.activeTemplateId || 'template_se'
        });
        return savedDocId;
      }
    } catch (e) {}

    // 4. Cek ke backend apakah ada dokumen aktif yang sudah pernah dibuat untuk sesi / room ini
    const existingDoc = await get().loadActiveDocument(sId, rId);
    if (existingDoc && existingDoc.doc_id) {
      set({ isOpen: true, isAiActivated: true });
      return existingDoc.doc_id;
    }

    // 5. Hanya jika benar-benar belum pernah ada dokumen, buat baru dari template
    const targetTemplateId = templateId || state.activeTemplateId || 'template_se';
    set({ isOpen: true, isAiActivated: true });
    const newDoc = await get().createDocument(targetTemplateId, initialTitle, sId, rId);
    if (newDoc) {
      return newDoc.doc_id;
    }
    return null;
  },

  closeWriter: () => set({ isOpen: false }),

  toggleWriter: () => {
    const { isGuest } = getUserInfo();
    if (isGuest) {
      console.warn('[DOC_WRITER] Tamu (Guest) dilarang membuka Document Studio.');
      return;
    }
    const willOpen = !get().isOpen;
    if (willOpen && !get().currentDocId) {
      get().openWriter();
    } else {
      set({ isOpen: willOpen });
    }
  },

  resetSplitWidth: () => set({ splitWidth: null }),
  setSplitWidth: (width) => set({ splitWidth: typeof width === 'number' ? Math.max(380, width) : null }),

  setDocumentTitle: (title) => {
    set((state) => ({
      activeDocument: {
        ...state.activeDocument,
        title
      }
    }));
  },

  selectTemplate: async (templateId) => {
    set({ activeTemplateId: templateId });
    const sId = get().currentSessionId;
    const rId = get().currentRoomId;
    await get().createDocument(templateId, null, sId, rId);
  },

  // Menerapkan perubahan revisi AI ke dokumen Word
  applyAiEdit: async (instruction, sectionId = null, content = null, sessionId = null, roomId = null) => {
    const { isGuest, npp } = getUserInfo();
    if (isGuest) return false;

    const sId = sessionId || get().currentSessionId || '';
    const rId = roomId || get().currentRoomId || '';

    // Pastikan docId tersedia
    let docId = get().currentDocId;
    if (!docId) {
      const doc = await get().loadActiveDocument(sId, rId);
      if (doc?.doc_id) {
        docId = doc.doc_id;
      } else {
        const newDoc = await get().createDocument('template_se', null, sId, rId);
        if (newDoc?.doc_id) {
          docId = newDoc.doc_id;
        }
      }
    }

    if (!docId) return false;

    try {
      const res = await apiClient.post('/doc-writer/ai-edit', {
        doc_id: docId,
        instruction: instruction,
        section_id: sectionId,
        content: content,
        npp: npp,
        session_id: sId,
        room_id: rId
      });

      if (res.data?.success) {
        set({ lastAiEditTimestamp: Date.now() });
        return true;
      }
      return false;
    } catch (err) {
      console.error('[DOC_WRITER] Gagal mengirim instruksi edit AI:', err);
      return false;
    }
  },

  fetchTemplates: async () => {
    set({ isLoadingTemplates: true });
    try {
      const res = await apiClient.get('/doc-writer/templates');
      if (res.data?.success && Array.isArray(res.data?.templates)) {
        set({ templates: res.data.templates, isLoadingTemplates: false });
      }
    } catch (err) {
      console.warn('[DOC_WRITER] Gagal memuat template dari server, menggunakan lokal fallback:', err);
      set({ isLoadingTemplates: false });
    }
  },

  exportDocx: async () => {
    const { currentDocId, activeDocument, currentSessionId, currentRoomId } = get();
    const { npp } = getUserInfo();

    if (currentDocId) {
      const baseUrl = apiClient.defaults.baseURL || `${window.location.protocol}//${window.location.hostname}:8000/api`;
      const downloadUrl = `${baseUrl}/doc-writer/download/${currentDocId}?npp=${encodeURIComponent(npp)}&session_id=${encodeURIComponent(currentSessionId || '')}&room_id=${encodeURIComponent(currentRoomId || '')}`;
      const link = document.createElement('a');
      link.href = downloadUrl;
      const safeTitle = (activeDocument.title || 'Dokumen_PT_Pindad').trim().replace(/\s+/g, '_');
      link.download = `${safeTitle}.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return;
    }
  }
}));
