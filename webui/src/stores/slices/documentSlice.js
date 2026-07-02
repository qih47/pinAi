import * as endpoints from "../../services/endpoints";

export const createDocumentSlice = (set, get) => ({
    documentsTotal: 0,
    
    fetchDocumentsList: async ({ offset = 0, limit = 15, search = '' } = {}) => {
        set({ isLoadingDocuments: true });
        try {
            const result = await endpoints.fetchAllDocuments({ offset, limit, search });
            if (result && result.items) {
                set({ documents: result.items, documentsTotal: result.total || 0 });
            } else if (Array.isArray(result)) {
                set({ documents: result, documentsTotal: result.length });
            } else {
                set({ documents: [], documentsTotal: 0 });
            }
        } catch (err) {
            console.error("Gagal mengambil daftar dokumen:", err);
            set({ documents: [], documentsTotal: 0 });
        } finally {
            set({ isLoadingDocuments: false });
        }
    },

    setActiveIsolatedDoc: (docId, title) => {
        set({
            activeIsolatedDocId: docId,
            activeIsolatedTitle: title,
        });
    }
});
