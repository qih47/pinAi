import * as endpoints from "../../services/endpoints";
import { parseMessageFileTags } from "../helpers/streamHelper";

let _sessionLoadSeq = 0;

export const createChatSlice = (set, get) => ({
    activeWizard: null, // { messageIndex, data }
    wizardAnswers: {}, // { [messageIndex]: [ { question: string, answer: string } ] }
    activeModeTag: null, // null | 'websearch' | 'documents' | 'code' | 'focus'
    setActiveModeTag: (tag) => set({ activeModeTag: tag }),
    setActiveWizard: (wizard) => set({ activeWizard: wizard }),
    dismissActiveWizard: () => set({ activeWizard: null }),
    saveWizardAnswer: (messageIndex, answersList) => {
        set((state) => ({
            wizardAnswers: {
                ...state.wizardAnswers,
                [messageIndex]: answersList
            },
            activeWizard: null
        }));
    },

    clearChat: () => {
        set({
            messages: [],
            sessionUuid: null,
            activeTopic: null,
            keySubject: null,
            isThinking: false,
            stagedAttachments: [],
            activeIsolatedDocId: null,
            activeIsolatedTitle: null,
            activeIsolatedMeta: null,
            activeModeTag: null,
            artifacts: [],  // ← Reset artifacts saat session baru
            isSplitScreen: false,
            activePdfUrl: null,
            showGhostWriter: false,
            ghostWriterContent: "",
            sessionAttachments: [],
            activeWizard: null,
            wizardAnswers: {}
        });
    },

    setContextIsolation: (docId, docTitle, mode = null, meta = null) => {
        set((state) => {
            const newChatMode = mode ? mode : (docId ? (state.chatMode === 'compliance' || state.chatMode === 'redteam' ? state.chatMode : 'focus') : 'auto');
            return {
                activeIsolatedDocId: docId || null,
                activeIsolatedTitle: docTitle || null,
                activeIsolatedMeta: meta !== null ? meta : (docId && docId === state.activeIsolatedDocId ? state.activeIsolatedMeta : null),
                chatMode: newChatMode,
                activeModeTag: (newChatMode === 'focus' || newChatMode === 'compliance' || newChatMode === 'redteam')
                    ? newChatMode
                    : (newChatMode === 'documents' ? 'documents' : (docId ? state.activeModeTag : null))
            };
        });
    },

    setSplitScreen: (isSplit, url = null) => {
        set((state) => ({
            isSplitScreen: isSplit,
            activePdfUrl: isSplit ? url : state.activePdfUrl // Pertahankan URL saat close biar animasi smooth
        }));
    },

    setGhostWriter: (isOpen, content = "") => {
        set({ showGhostWriter: isOpen, ghostWriterContent: content });
    },

    fetchChatHistory: async (npp) => {
        if (!npp) return { status: "error", data: [] };
        try {
            const result = await endpoints.fetchChatSessions(npp);
            return result;
        } catch (err) {
            console.error("❌ [FETCH ERROR]:", err);
            return { status: "error", data: [] };
        }
    },

    loadChatSession: async (sessionUuid) => {
        if (!sessionUuid || sessionUuid === 'new') return;

        const savedTopicObj = get().sessionTopics?.[sessionUuid];
        const activeTopic = typeof savedTopicObj === 'object' ? savedTopicObj?.topic : (savedTopicObj || null);
        const keySubject = typeof savedTopicObj === 'object' ? savedTopicObj?.keySubject : null;

        // 🔥 MULTI-SESSION BACKGROUND STREAM RESUMPTION
        const activeStream = get().activeStreams?.[sessionUuid];
        if (activeStream) {
            console.log('📥 [STORE] Resuming background stream session:', sessionUuid);
            set({ 
                sessionUuid, 
                activeTopic,
                keySubject,
                messages: activeStream.messages, 
                isStreaming: activeStream.isStreaming, 
                isThinking: activeStream.isThinking,
                currentThinking: activeStream.currentThinking,
                isLoading: false,
                activeIsolatedDocId: null, 
                activeIsolatedTitle: null, 
                artifacts: [] // Should technically preserve artifacts if any, but stream doesn't produce artifacts until done
            });
            return;
        }

        const seq = ++_sessionLoadSeq;
        console.log('📥 [STORE] Loading session:', sessionUuid);
        set({ 
            sessionUuid, 
            activeTopic,
            keySubject,
            messages: [], 
            isLoading: true, 
            activeIsolatedDocId: null, 
            activeIsolatedTitle: null, 
            artifacts: [], 
            isStreaming: false, 
            isThinking: false 
        });

        try {
            const npp = JSON.parse(localStorage.getItem('cakra_user'))?.npp || '';
            const result = await endpoints.fetchSessionMessages(sessionUuid, npp);

            if (seq !== _sessionLoadSeq) return;

            if (result.status === "success" && result.data) {
                let loadedArtifacts = [];
                // SINKRONISASI RIWAYAT: Mengambil nama berkas saja dari riwayat lampiran lama
                const sanitizedMessages = result.data.map(msg => {
                    let newMsg = { ...msg };
                    
                    // 🔥 PARSE TAGS FROM SAVED CONTENT (FIX RELOAD & VARIANTS BUG) 🔥
                    if (newMsg.role === 'assistant') {
                        newMsg = parseMessageFileTags(newMsg);

                        // Parse juga seluruh varian yang tersimpan agar saat berpindah varian tetap ter-render rapi
                        if (Array.isArray(newMsg.variants) && newMsg.variants.length > 0) {
                            newMsg.variants = newMsg.variants.map(v =>
                                parseMessageFileTags({ ...v, role: 'assistant', metadata: newMsg.metadata })
                            );
                        }

                        if (newMsg.fileGenerations && newMsg.fileGenerations.length > 0) {
                            loadedArtifacts = [...loadedArtifacts, ...newMsg.fileGenerations];
                        }
                    } else if (newMsg.metadata && newMsg.metadata.artifacts && Array.isArray(newMsg.metadata.artifacts)) {
                        loadedArtifacts = [...loadedArtifacts, ...newMsg.metadata.artifacts];
                        newMsg.fileGenerations = newMsg.metadata.artifacts.map(art => ({
                            filename: art.filename,
                            stage: 'done',
                            file_path: art.file_path,
                            liveCode: art.code || '',
                            lines_count: art.lines_count || 1
                        }));
                    }
                    
                    if (newMsg.attachments && newMsg.attachments.length > 0) {
                        return {
                            ...newMsg,
                            attachments: newMsg.attachments.map(file => {
                                const fp = file.file_path || "";
                                // Keep new path structure intact, otherwise extract filename for legacy
                                const newPath = fp.startsWith('accounts/') 
                                    ? fp 
                                    : (fp.includes('/') ? fp.split('/').pop() : fp);
                                return {
                                    ...file,
                                    file_path: newPath
                                };
                            })
                        };
                    }
                    return newMsg;
                });

                // Deduplicate artifacts by filename just in case
                const uniqueArtifactsMap = new Map();
                loadedArtifacts.forEach(a => uniqueArtifactsMap.set(a.filename, a));
                const finalArtifacts = Array.from(uniqueArtifactsMap.values());

                set({
                    messages: sanitizedMessages,
                    artifacts: finalArtifacts,
                    isLoading: false
                });
            } else {
                set({ messages: [], isLoading: false });
            }
        } catch (err) {
            if (seq !== _sessionLoadSeq) return;
            console.error("❌ Gagal load session:", err);
            set({ isLoading: false });
        }
    },

    pinChat: async (sessionUuid, isPinnedCurrentValue) => {
        try {
            const nextPinState = !isPinnedCurrentValue;
            const result = await endpoints.pinSession(sessionUuid, nextPinState);
            return result;
        } catch (err) {
            console.error("❌ [STORE PIN ERROR]:", err);
            return { status: "error" };
        }
    },

    renameChat: async (sessionUuid, tempTitle) => {
        try {
            const result = await endpoints.renameSession(sessionUuid, tempTitle);
            return result;
        } catch (err) {
            console.error("❌ [STORE RENAME ERROR]:", err);
            return { status: "error" };
        }
    },

    createNewSession: async (npp, chatMode = 'auto', isThinkingMode = false) => {
        try {
            const result = await endpoints.createChatSession(null, npp);
            if (result.status === 'success') {
                const newUuid = result.data.session_uuid;
                await endpoints.updateSessionSettings(newUuid, { chatMode, isThinkingMode }).catch(() => {});
                set({ sessionUuid: newUuid, messages: [], stagedAttachments: [], activeIsolatedDocId: null, activeIsolatedTitle: null });
                return newUuid;
            }
            throw new Error('Gagal membuat sesi baru');
        } catch (err) {
            console.error('❌ [CREATE SESSION ERROR]:', err);
            return null;
        }
    },

    deleteChat: async (sessionUuid, npp) => {
        try {
            const result = await endpoints.deleteSession(sessionUuid, npp);
            return result;
        } catch (err) {
            console.error("❌ [STORE DELETE ERROR]:", err);
            return { status: "error" };
        }
    },

    archiveChat: async (sessionUuid, isArchived = true) => {
        try {
            const result = await endpoints.archiveSession(sessionUuid, isArchived);
            return result;
        } catch (err) {
            console.error("❌ [STORE ARCHIVE ERROR]:", err);
            return { status: "error" };
        }
    }
});
