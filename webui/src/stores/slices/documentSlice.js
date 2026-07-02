import * as endpoints from "../../services/endpoints";

export const createDocumentSlice = (set, get) => ({
    fetchDocumentsList: async () => {
        set({ isLoadingDocuments: true });
        try {
            const result = await endpoints.fetchAllDocuments();
            if (result && result.items) {
                set({ documents: result.items });
            } else if (Array.isArray(result)) {
                set({ documents: result });
            } else {
                set({ documents: [] });
            }
        } catch (err) {
            console.error("Gagal mengambil daftar dokumen:", err);
            set({ documents: [] });
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
