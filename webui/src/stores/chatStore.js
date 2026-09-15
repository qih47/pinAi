import { create } from "zustand";
import * as endpoints from "../services/endpoints";
import apiClient from "../services/apiClient";
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
    activeTopic: null,
    keySubject: null,
    sessionTopics: {}, // Track active topic and key subject per session: { [sessionUuid]: { topic, keySubject } }
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
    ghostWriterContent: "",
    autoReadAloud: localStorage.getItem('cakra_auto_read_aloud') === 'true',
    setAutoReadAloud: (val) => {
        localStorage.setItem('cakra_auto_read_aloud', val);
        set({ autoReadAloud: val });
        get().syncSettings();
    },
    ttsVoice: localStorage.getItem('cakra_tts_voice') || 'id-ID-ArdiNeural',
    setTtsVoice: (val) => {
        localStorage.setItem('cakra_tts_voice', val);
        set({ ttsVoice: val });
        get().syncSettings();
    },
    ttsSpeed: localStorage.getItem('cakra_tts_speed') || 'normal',
    setTtsSpeed: (val) => {
        localStorage.setItem('cakra_tts_speed', val);
        set({ ttsSpeed: val });
        get().syncSettings();
    },
    activeTtsMessageId: null,
    setActiveTtsMessageId: (id) => set({ activeTtsMessageId: id }),
    stopAllTTS: () => set({ activeTtsMessageId: null }),
    
    // Sync Settings Logic
    syncSettings: async () => {
        const token = localStorage.getItem('cakra_token');
        if (!token) return;
        const state = get();
        const themeSetting = localStorage.getItem('cakra-theme-setting') || 'dark';
        const preferredLang = localStorage.getItem('cakra_language') || 'id';
        const settings = {
            autoReadAloud: state.autoReadAloud,
            ttsVoice: state.ttsVoice,
            ttsSpeed: state.ttsSpeed,
            theme_preference: themeSetting,
            preferred_language: preferredLang
        };
        try {
            await apiClient.put('/user/settings', { token, settings });
        } catch (e) {
            console.error("Gagal sync settings", e);
        }
    },
    fetchSettings: async () => {
        const token = localStorage.getItem('cakra_token');
        if (!token) return;
        try {
            const res = await apiClient.get(`/user/settings?token=${token}`);
            if (res.data?.settings) {
                const s = res.data.settings;
                if (s.autoReadAloud !== undefined) {
                    localStorage.setItem('cakra_auto_read_aloud', s.autoReadAloud);
                    set({ autoReadAloud: s.autoReadAloud });
                }
                if (s.ttsVoice) {
                    localStorage.setItem('cakra_tts_voice', s.ttsVoice);
                    set({ ttsVoice: s.ttsVoice });
                }
                if (s.ttsSpeed) {
                    localStorage.setItem('cakra_tts_speed', s.ttsSpeed);
                    set({ ttsSpeed: s.ttsSpeed });
                }
                if (s.theme_preference) {
                    localStorage.setItem('cakra-theme-setting', s.theme_preference);
                    const isDark = s.theme_preference === 'dark' || (s.theme_preference === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
                    if (isDark) {
                        document.documentElement.classList.add('dark');
                    } else {
                        document.documentElement.classList.remove('dark');
                    }
                }
                if (s.preferred_language) {
                    localStorage.setItem('cakra_language', s.preferred_language);
                }
                window.dispatchEvent(new CustomEvent('cakra-settings-updated', { detail: s }));
            }
        } catch (e) {
            console.error("Gagal load settings", e);
        }
    },

    // Slices
    ...createChatSlice(set, get),
    ...createStreamSlice(set, get),
    ...createDocumentSlice(set, get),
    ...createAttachmentSlice(set, get)
}));