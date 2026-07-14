import { create } from 'zustand';

const useNextcloudStore = create((set) => ({
  credentials: null, // { username, password }
  isLoggedIn: false,
  isModalOpen: false,

  setCredentials: (username, password) => set({ 
    credentials: { username, password },
    isLoggedIn: true 
  }),
  
  clearCredentials: () => set({ 
    credentials: null, 
    isLoggedIn: false 
  }),

  openModal: () => set({ isModalOpen: true }),
  closeModal: () => set({ isModalOpen: false })
}));

export default useNextcloudStore;
