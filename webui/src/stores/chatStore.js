import { create } from "zustand";

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || "";
export const API_BASE = typeof window !== 'undefined' && !DEFAULT_API_BASE
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : DEFAULT_API_BASE;
let _sessionLoadSeq = 0;

export function getUploadUrl(filePath) {
    if (!filePath) return '';
    const filename = filePath.includes('/') ? filePath.split('/').pop() : filePath;
    return `${API_BASE}/uploads/${filename}`;
}

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

function _buildAuthHeaders(npp) {
    const headers = { 'Content-Type': 'application/json' };
    const cleanNpp = (npp || '').trim();
    const isPlaceholder = !cleanNpp || cleanNpp.startsWith('NPP');
    if (!isPlaceholder) {
        headers['X-NPP-Header'] = cleanNpp;
    }
    return headers;
}

async function _performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null, isolatedDocId = null, attachmentPaths = [], chatMode = 'auto') {
    try {
        const activeSessionUuid = forcedSessionUuid || get().sessionUuid;

        const response = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: _buildAuthHeaders(npp),
            body: JSON.stringify({
                session_uuid: activeSessionUuid,
                messages: messagesToSend,
                ode: get().chatMode || chatMode,
                temperature: 0.7,
                isolated_doc_id: isolatedDocId,
                attachment_paths: attachmentPaths
            })
        });

        if (!response.ok) throw new Error('Gagal konek ke backend, bolo!');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedReply = '';
        let streamBuffer = '';
        let renderTimeout = null;
        let accumulatedThinking = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            streamBuffer += decoder.decode(value, { stream: true });
            const lines = streamBuffer.split('\n');
            streamBuffer = lines.pop();

            for (const line of lines) {
                const cleanedLine = line.trim();
                if (!cleanedLine) continue;

                try {
                    const parsedData = JSON.parse(cleanedLine);

                    // 🧠 HANDLE STATUS DINAMIS
                    if (parsedData.thinking) {
                        accumulatedThinking = parsedData.thinking;
                        const updatedAssistantMsg = { ...assistantMessage, thought: accumulatedThinking };
                        const updatedMessages = get().messages.map(msg =>
                            msg === assistantMessage ? updatedAssistantMsg : msg
                        );
                        assistantMessage = updatedAssistantMsg;
                        set({
                            currentThinking: accumulatedThinking,
                            isThinking: true,
                            messages: updatedMessages
                        });
                    }

                    // 🔥 NEW: HANDLE SOURCES FROM RAG
                    if (parsedData.sources && Array.isArray(parsedData.sources)) {
                        console.log('📚 [SSE] Received sources:', parsedData.sources);
                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            sources: parsedData.sources,
                            citations: parsedData.sources  // 🔥 Dual assignment untuk kompatibilitas
                        };
                        const updatedMessages = get().messages.map(msg =>
                            msg === assistantMessage ? updatedAssistantMsg : msg
                        );
                        assistantMessage = updatedAssistantMsg;
                        set({ messages: updatedMessages });
                    }

                    // 📝 HANDLE RESPONSE CHUNK
                    if (parsedData.chunk) {
                        accumulatedReply += parsedData.chunk;
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
                    }

                    // 🏁 HANDLE COMPLETION
                    if (parsedData.done === true) {
                        set({
                            isThinking: false,
                            currentThinking: ''
                        });
                    }
                } catch (jsonErr) {
                    // Buffering
                }
            }
        }

    } catch (error) {
        console.error('💥 [FE STREAM ERROR]:', error);
        assistantMessage.content = '⚠️ Gagal memuat balasan.';
        set({ messages: [...get().messages], isThinking: false, currentThinking: '' });
    } finally {
        set({ isStreaming: false, isLoading: false, isThinking: false });
    }
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

    sendMessage: async (content, npp, onSessionCreatedCallback, directUploadedFiles = null, chatMode = 'auto') => {
        const hasAttachments = (directUploadedFiles?.length > 0) || (get().stagedAttachments?.length > 0);
        if ((!content.trim() && !hasAttachments) || get().isStreaming) return;

        let currentSessionUuid = get().sessionUuid;

        if (!currentSessionUuid || currentSessionUuid === "new") {
            try {
                const generatedTitle = content.split(" ").slice(0, 4).join(" ") + "...";

                const response = await fetch(`${API_BASE}/api/chat/sessions/create?judul=${encodeURIComponent(generatedTitle)}`, {
                    method: 'POST',
                    headers: _buildAuthHeaders(npp),
                });
                const result = await response.json();

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

        // 🔒 KUNCI STATE CHATMODE DI SINI SEBELUM URL ROUTE BERUBAH!
        set({
            chatMode: chatMode, // 👈 Tambahkan baris sakti ini bolo!
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
            chatMode // 🔥 Oper chatMode ke _performStream
        );

        set({ stagedAttachments: [] });
    },

    editAndRegenerate: async (index, newContent) => {
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

        await _performStream(set, get, messagesToSend, assistantMessage, null, npp, get().activeIsolatedDocId, []);
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
            const response = await fetch(`${API_BASE}/api/chat/sessions`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-NPP-Header': npp
                }
            });
            if (!response.ok) throw new Error("Gagal mengambil data");
            const result = await response.json();
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
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}/messages`, {
                headers: { 'X-NPP-Header': npp }
            });
            const result = await response.json();

            if (seq !== _sessionLoadSeq) return;

            if (result.status === "success" && result.data) {
                // 🔥 TAMBAHAN SAKTI 2: Saring total data riwayat lama di level Store agar nama filenya murni keping ujungnya doang!
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
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}/pin?is_pinned=${nextPinState}`, {
                method: 'PUT'
            });
            return await response.json();
        } catch (err) {
            console.error("❌ [STORE PIN ERROR]:", err);
            return { status: "error" };
        }
    },

    renameChat: async (sessionUuid, tempTitle) => {
        try {
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}/title`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ judul: tempTitle })
            });
            return await response.json();
        } catch (err) {
            console.error("❌ [STORE RENAME ERROR]:", err);
            return { status: "error" };
        }
    },

    createNewSession: async (npp) => {
        try {
            const response = await fetch(`${API_BASE}/api/chat/sessions/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-NPP-Header': npp || ''
                }
            });
            const result = await response.json();
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
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}`, {
                method: 'DELETE',
                headers: {
                    'X-NPP-Header': npp || ''
                }
            });
            return await response.json();
        } catch (err) {
            console.error("❌ [STORE DELETE ERROR]:", err);
            return { status: "error" };
        }
    },

    setStagedAttachments: (attachments) => {
        set({ stagedAttachments: attachments });
    },

    setContextIsolation: (docId, docTitle) => {
        if (get().activeIsolatedDocId === docId || docId === null) {
            set({ activeIsolatedDocId: null, activeIsolatedTitle: null });
        } else {
            set({ activeIsolatedDocId: docId, activeIsolatedTitle: docTitle });
        }
    }
}));