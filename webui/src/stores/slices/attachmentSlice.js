export const createAttachmentSlice = (set, get) => ({
    setStagedAttachments: (attachments) => {
        set({ stagedAttachments: attachments });
    },

    clearArtifacts: () => set({ artifacts: [] })
});
