import { create } from "zustand";
import * as endpoints from "../services/endpoints";
import { createChatSlice } from "./slices/chatSlice";
import { createStreamSlice } from "./slices/streamSlice";
import { createDocumentSlice } from "./slices/documentSlice";
import { createAttachmentSlice } from "./slices/attachmentSlice";

export const API_BASE = endpoints.getApiBase();
export const getUploadUrl = endpoints.getUploadUrl;

export const useChatStore = create((set, get) => ({
    // Initial State
    messages: [],
    isLoading: false,
    isStreaming: false,
    isThinking: false,
    isThinkingMode: false,
    currentThinking: '',
    sessionUuid: null,
    activeStreams: {}, // Track background streams: { [sessionUuid]: { isStreaming: true, messages: [], ... } }
    stagedAttachments: [],
    activeIsolatedDocId: null,
    activeIsolatedTitle: null,
    documents: [],
    isLoadingDocuments: false,
    abortController: null,
    artifacts: [],
    isSplitScreen: false,
    activePdfUrl: null,
    showGhostWriter: false,
    showGhostWriter: false,
    ghostWriterContent: "",
    autoReadAloud: localStorage.getItem('cakra_auto_read_aloud') === 'true',
    setAutoReadAloud: (val) => {
        localStorage.setItem('cakra_auto_read_aloud', val);
        set({ autoReadAloud: val });
    },
    ttsVoice: localStorage.getItem('cakra_tts_voice') || 'id-ID-ArdiNeural',
    setTtsVoice: (val) => {
        localStorage.setItem('cakra_tts_voice', val);
        set({ ttsVoice: val });
    },
    ttsSpeed: localStorage.getItem('cakra_tts_speed') || 'normal',
    setTtsSpeed: (val) => {
        localStorage.setItem('cakra_tts_speed', val);
        set({ ttsSpeed: val });
    },

    // Slices
    ...createChatSlice(set, get),
    ...createStreamSlice(set, get),
    ...createDocumentSlice(set, get),
    ...createAttachmentSlice(set, get)
}));