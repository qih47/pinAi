import { create } from "zustand";

export const useCorporateStore = create((set, get) => ({
  zimbraEmails: [],
  setZimbraEmails: (emails) => set({ zimbraEmails: emails }),
  updateZimbraEmail: (id, updates) => set((state) => ({
    zimbraEmails: state.zimbraEmails.map(e => e.id === id ? { ...e, ...updates } : e)
  })),
  clearZimbraEmails: () => set({ zimbraEmails: [] }),
}));
