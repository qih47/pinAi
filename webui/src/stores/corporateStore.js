import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useCorporateStore = create(
  persist(
    (set, get) => ({
      zimbraEmails: [],
      zimbraSentEmails: [],
      zimbraDraftEmails: [],
      setZimbraEmails: (emails) => set({ zimbraEmails: emails }),
      setZimbraSentEmails: (emails) => set({ zimbraSentEmails: emails }),
      setZimbraDraftEmails: (drafts) => set({ zimbraDraftEmails: drafts }),
      addOrUpdateZimbraDraft: (draft) => set((state) => {
        const existingIdx = state.zimbraDraftEmails.findIndex(d => d.id === draft.id);
        if (existingIdx >= 0) {
          const updated = [...state.zimbraDraftEmails];
          updated[existingIdx] = draft;
          return { zimbraDraftEmails: updated };
        }
        return { zimbraDraftEmails: [draft, ...state.zimbraDraftEmails] };
      }),
      removeZimbraDraft: (draftId) => set((state) => ({
        zimbraDraftEmails: state.zimbraDraftEmails.filter(d => d.id !== draftId)
      })),
      updateZimbraEmail: (id, updates) => set((state) => ({
        zimbraEmails: state.zimbraEmails.map(e => e.id === id ? { ...e, ...updates } : e)
      })),
      clearZimbraEmails: () => set({ zimbraEmails: [], zimbraSentEmails: [], zimbraDraftEmails: [] }),
    }),
    {
      name: "cakra_corporate_store",
      partialize: (state) => ({ 
        zimbraEmails: state.zimbraEmails,
        zimbraSentEmails: state.zimbraSentEmails,
        zimbraDraftEmails: state.zimbraDraftEmails
      }),
    }
  )
);

