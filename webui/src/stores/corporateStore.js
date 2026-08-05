import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useCorporateStore = create(
  persist(
    (set, get) => ({
      zimbraEmails: [],
      setZimbraEmails: (emails) => set({ zimbraEmails: emails }),
      updateZimbraEmail: (id, updates) => set((state) => ({
        zimbraEmails: state.zimbraEmails.map(e => e.id === id ? { ...e, ...updates } : e)
      })),
      clearZimbraEmails: () => set({ zimbraEmails: [] }),
    }),
    {
      name: "cakra_corporate_store",
      partialize: (state) => ({ zimbraEmails: state.zimbraEmails }),
    }
  )
);
