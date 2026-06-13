import { create } from "zustand";
import * as endpoints from "../services/endpoints";

export const API_BASE = endpoints.getApiBase();
export const getUploadUrl = endpoints.getUploadUrl;

let _sessionLoadSeq = 0;

function _normalizeAttachments(files) {
    if (!files || !files.length) return [];
    return files.map((f) => ({
        id: f.id,
        file_name: f.original_filename || f.file_name || 'lampiran',
        file_path: f.file_path && f.file_path.includes('/')
            ? f.file_path.split('/').pop()
            : f.file_path,
        mime_type: f.mime_type,
    }));
}

async function _performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null, isolatedDocId = null, attachmentPaths = [], chatMode = 'auto', toast = null) {
    let attempts = 0;
    const maxAttempts = 4; // 1 initial attempt + 3 retries
    let success = false;
    const activeSessionUuid = forcedSessionUuid || get().sessionUuid;

    while (attempts < maxAttempts && !success) {
        try {
            if (attempts > 0) {
                if (toast) toast.info(`Koneksi terputus. Menghubungkan kembali... (${attempts}/3)`);
                const delay = Math.pow(2, attempts - 1) * 1000;
                await new Promise(resolve => setTimeout(resolve, delay));
            }

            let accumulatedReply = '';
            let renderTimeout = null;

            await endpoints.streamChat(
                {
                    sessionUuid: activeSessionUuid,
                    messages: messagesToSend,
                    chatMode: get().chatMode || chatMode,
                    isolatedDocId,
                    attachmentPaths,
                    npp
                },
                {
                    onThinking: (thinking) => {
                        const updatedAssistantMsg = { ...assistantMessage, thought: thinking };
                        const updatedMessages = get().messages.map(msg =>
                            msg === assistantMessage ? updatedAssistantMsg : msg
                        );
                        assistantMessage = updatedAssistantMsg;
                        set({
                            currentThinking: thinking,
                            isThinking: true,
                            messages: updatedMessages
                        });
                    },
                    onSources: (sources) => {
                        console.log('📚 [SSE] Received sources:', sources);
                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            sources: sources,
                            citations: sources  // Dual assignment untuk kompatibilitas
                        };
                        const updatedMessages = get().messages.map(msg =>
                            msg === assistantMessage ? updatedAssistantMsg : msg
                        );
                        assistantMessage = updatedAssistantMsg;
                        set({ messages: updatedMessages });
                    },
                    onChunk: (chunk) => {
                        accumulatedReply += chunk;
                        assistantMessage.content = accumulatedReply;

                        if (!renderTimeout) {
                            renderTimeout = requestAnimationFrame(() => {
                                set({
                                    messages: [...get().messages],
                                    isThinking: false
                                });
                                renderTimeout = null;
                            });
                        }
                    },
                    onDone: () => {
                        set({
                            isThinking: false,
                            currentThinking: ''
                        });
                    }
                }
            );
            success = true;
        } catch (error) {
            console.warn(`💥 [FE STREAM ERROR - Attempt ${attempts + 1}]:`, error);
            attempts++;
            if (attempts >= maxAttempts) {
                assistantMessage.content = '⚠️ Gagal memuat balasan. Koneksi terputus sepenuhnya.';
                set({ messages: [...get().messages], isThinking: false, currentThinking: '' });
                if (toast) toast.error('Koneksi terputus. Gagal memuat balasan.');
            }
        }
    }
    set({ isStreaming: false, isLoading: false, isThinking: false });
}

export const useChatStore = create((set, get) => ({
    messages: [],
    isLoading: false,
    isStreaming: false,
    isThinking: false,
    currentThinking: '',  // New: current thinking signal from pipeline
    sessionUuid: null,
    stagedAttachments: [],
    activeIsolatedDocId: null,
    activeIsolatedTitle: null,
    documents: [],
    isLoadingDocuments: false,

    sendMessage: async (content, npp, onSessionCreatedCallback, directUploadedFiles = null, chatMode = 'auto', toast = null) => {
        const hasAttachments = (directUploadedFiles?.length > 0) || (get().stagedAttachments?.length > 0);
        if ((!content.trim() && !hasAttachments) || get().isStreaming) return;

        let currentSessionUuid = get().sessionUuid;

        if (!currentSessionUuid || currentSessionUuid === "new") {
            try {
                const generatedTitle = content.split(" ").slice(0, 4).join(" ") + "...";
                const result = await endpoints.createChatSession(generatedTitle, npp);

                if (result.status === "success") {
                    currentSessionUuid = result.data.session_uuid;

                    if (onSessionCreatedCallback) {
                        onSessionCreatedCallback({
                            session_uuid: currentSessionUuid,
                            judul: generatedTitle,
                            is_pinned: false,
                            started_at: new Date().toISOString()
                        });
                    }

                    set({ sessionUuid: currentSessionUuid });
                } else {
                    throw new Error("Gagal booking session id dari backend.");
                }
            } catch (err) {
                console.error("❌ [STREAM AUTH SESSION ERROR]:", err);
                return;
            }
        }

        const targetFiles = directUploadedFiles !== null ? directUploadedFiles : get().stagedAttachments;
        const attachmentMeta = _normalizeAttachments(targetFiles);

        const userMessage = {
            role: 'user',
            content: content.trim(),
            ...(attachmentMeta.length > 0 ? { attachments: attachmentMeta } : {}),
        };
        const updatedMessages = [...get().messages, userMessage];
        const assistantMessage = { role: 'assistant', content: '' };

        const currentAttachmentPaths = attachmentMeta
            .map((file) => file.file_path)
            .filter(Boolean);

        const currentIsolatedDocId = get().activeIsolatedDocId;

        // Sinkronisasi state chatMode sebelum perubahan rute URL
        set({
            chatMode: chatMode, // Menyinkronkan chatMode ke store
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            isLoading: true,
            isThinking: true
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        await _performStream(
            set,
            get,
            updatedMessages,
            assistantMessage,
            currentSessionUuid,
            npp,
            currentIsolatedDocId,
            currentAttachmentPaths,
            chatMode,
            toast
        );

        set({ stagedAttachments: [] });
    },

    editAndRegenerate: async (index, newContent, toast = null) => {
        if (!newContent.trim() || get().isStreaming) return;

        const currentMessages = [...get().messages];
        currentMessages[index] = { role: 'user', content: newContent };

        const assistantMessage = { role: 'assistant', content: '' };

        if (currentMessages[index + 1] && currentMessages[index + 1].role === 'assistant') {
            currentMessages[index + 1] = assistantMessage;
        } else {
            currentMessages.splice(index + 1, 0, assistantMessage);
        }

        set({
            messages: currentMessages,
            isStreaming: true,
            isLoading: true,
            isThinking: true
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        const messagesToSend = currentMessages.slice(0, index + 1);
        const npp = JSON.parse(localStorage.getItem('cakra_user') || '{}')?.npp || null;

        await _performStream(set, get, messagesToSend, assistantMessage, null, npp, get().activeIsolatedDocId, [], 'auto', toast);
    },

    clearChat: () => {
        set({
            messages: [],
            sessionUuid: null,
            isThinking: false,
            stagedAttachments: [],
            activeIsolatedDocId: null,
            activeIsolatedTitle: null
        });
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

        const seq = ++_sessionLoadSeq;
        console.log('📥 [STORE] Loading session:', sessionUuid);
        set({ sessionUuid, messages: [], isLoading: true, activeIsolatedDocId: null, activeIsolatedTitle: null });

        try {
            const npp = JSON.parse(localStorage.getItem('cakra_user'))?.npp || '';
            const result = await endpoints.fetchSessionMessages(sessionUuid, npp);

            if (seq !== _sessionLoadSeq) return;

            if (result.status === "success" && result.data) {
                // SINKRONISASI RIWAYAT: Mengambil nama berkas saja dari riwayat lampiran lama
                const sanitizedMessages = result.data.map(msg => {
                    if (msg.attachments && msg.attachments.length > 0) {
                        return {
                            ...msg,
                            attachments: msg.attachments.map(file => ({
                                ...file,
                                file_path: file.file_path && file.file_path.includes('/')
                                    ? file.file_path.split('/').pop()
                                    : file.file_path
                            }))
                        };
                    }
                    return msg;
                });

                set({
                    messages: sanitizedMessages,
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

    createNewSession: async (npp) => {
        try {
            const result = await endpoints.createChatSession(null, npp);
            if (result.status === 'success') {
                set({ sessionUuid: result.data.session_uuid, messages: [], stagedAttachments: [], activeIsolatedDocId: null, activeIsolatedTitle: null });
                return result.data.session_uuid;
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

    setStagedAttachments: (attachments) => {
        set({ stagedAttachments: attachments });
    },

    fetchDocumentsList: async () => {
        set({ isLoadingDocuments: true });
        try {
            const result = await endpoints.fetchAllDocuments();
            if (result.status === "success" && result.data) {
                set({ documents: result.data });
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

    setContextIsolation: (docId, docTitle) => {
        if (get().activeIsolatedDocId === docId || docId === null) {
            set({ activeIsolatedDocId: null, activeIsolatedTitle: null });
        } else {
            set({ activeIsolatedDocId: docId, activeIsolatedTitle: docTitle });
        }
    }
}));