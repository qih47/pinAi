import { create } from "zustand";
import { collabApi } from "../features/collab/services/collabApi";

export const useCollabStore = create((set, get) => ({
  invitations: [],
  invitationCount: 0,
  unreadCount: 0,
  isLoadingInvitations: false,

  fetchInvitationsCount: async () => {
    try {
      const count = await collabApi.getInvitationsCount();
      set({ invitationCount: count });
      return count;
    } catch (err) {
      console.error("[COLLAB_STORE] Failed to fetch invitations count:", err);
      return 0;
    }
  },

  fetchUnreadCount: async () => {
    try {
      const count = await collabApi.getUnreadCount();
      set({ unreadCount: count });
      return count;
    } catch (err) {
      console.error("[COLLAB_STORE] Failed to fetch unread count:", err);
      return 0;
    }
  },

  fetchInvitations: async () => {
    set({ isLoadingInvitations: true });
    try {
      const invitations = await collabApi.getInvitations();
      set({
        invitations,
        invitationCount: invitations.length,
        isLoadingInvitations: false,
      });
      return invitations;
    } catch (err) {
      console.error("[COLLAB_STORE] Failed to fetch invitations:", err);
      set({ isLoadingInvitations: false });
      return [];
    }
  },

  respondToInvitation: async (roomId, action) => {
    try {
      const result = await collabApi.respondInvitation(roomId, action);
      set((state) => {
        const remaining = state.invitations.filter((inv) => String(inv.room_id) !== String(roomId));
        return {
          invitations: remaining,
          invitationCount: remaining.length,
        };
      });
      return result;
    } catch (err) {
      console.error(`[COLLAB_STORE] Failed to respond (${action}) to invitation:`, err);
      throw err;
    }
  },

  markRoomAsRead: async (roomId) => {
    try {
      await collabApi.markRoomRead(roomId);
      get().fetchUnreadCount();
    } catch (err) {
      console.error("[COLLAB_STORE] Failed to mark room as read:", err);
    }
  },

  decrementInvitationCount: () =>
    set((state) => ({
      invitationCount: Math.max(0, state.invitationCount - 1),
    })),
}));
