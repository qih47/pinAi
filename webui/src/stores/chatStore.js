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
        file_size: f.file_size || f.size || 0,
    }));
}

// Tambahkan parameter targetAssistantIdx di akhir (default null)
async function _performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null, isolatedDocId = null, attachmentPaths = [], chatMode = 'auto', isThinkingMode = true, toast = null, targetAssistantIdx = null, editIndex = null) {
    let attempts = 0;
    const maxAttempts = 4;
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
            let accumulatedThinking = '';

            const controller = new AbortController();
            set({ abortController: controller });

            await endpoints.streamChat(
                {
                    sessionUuid: activeSessionUuid,
                    messages: messagesToSend,
                    chatMode: get().chatMode || chatMode,
                    thinking: isThinkingMode,
                    isolatedDocId,
                    attachmentPaths,
                    npp,
                    editIndex,
                    signal: controller.signal
                },
                {
                    onThinking: (thinking) => {
                        // Bersihkan marker <|channel> dan [GEMMA_THINK] dari string thinking
                        let cleanThinking = thinking
                            .replace(/<\|channel>thought/g, '')
                            .replace(/<channel\|>/g, '')
                            .replace(/\[GEMMA_THINK\]/g, '');
                            
                        accumulatedThinking += cleanThinking;

                        // 🔥 TRULY DYNAMIC STATUS: Mengekstrak topik yang sedang dipikirkan secara native!
                        // Tidak lagi kaku 3 langkah, melainkan membaca apapun yang ditulis AI sebelum titik dua (:)
                        let currentStatus = 'Sedang memproses...';
                        const lines = accumulatedThinking.split('\n');
                        
                        for (const line of lines) {
                            // Cari pola bullet point dengan header. Contoh: "*   Context:", "*   *Step 1 - Selection:*", "    * Analysis:"
                            // Regex ini menangkap teks di dalam bullet sebelum tanda titik dua (:), maksimal 35 karakter.
                            const match = line.match(/^\s*[\*-]\s+(?:\*+)?([^:\n\*]{3,35})(?:\*+)?\s*:/);
                            if (match && match[1]) {
                                let topic = match[1].trim();
                                // Percantik output status
                                currentStatus = topic + '...';
                            }
                        }

                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            thinking: accumulatedThinking,
                            isThinking: true,
                            statusMessage: currentStatus,
                            content: accumulatedReply // Preserve actual content independently
                        };

                        set(state => {
                            const newMessages = [...state.messages];
                            const idx = targetAssistantIdx !== null ? targetAssistantIdx : newMessages.length - 1;
                            if (newMessages[idx]) {
                                // Kita paksa update statusMessage di sini
                                newMessages[idx] = updatedAssistantMsg;
                            }
                            return {
                                messages: newMessages,
                                currentThinking: cleanThinking
                            };
                        });
                        assistantMessage = updatedAssistantMsg;
                    },
                    onStatus: (statusStr) => {
                        // Dipanggil oleh RAG / pipeline statis
                        set(state => {
                            const newMessages = [...state.messages];
                            const idx = targetAssistantIdx !== null ? targetAssistantIdx : newMessages.length - 1;
                            if (newMessages[idx]) {
                                newMessages[idx] = {
                                    ...newMessages[idx],
                                    statusMessage: statusStr
                                };
                            }
                            return {
                                messages: newMessages,
                                currentThinking: statusStr
                            };
                        });
                    },
                    onSources: (sources) => {
                        console.log('📚 [SSE] Received sources:', sources);
                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            sources: sources,
                            citations: sources
                        };
                        const currentMessages = [...get().messages];
                        const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                        currentMessages[idxToUpdate] = updatedAssistantMsg;

                        assistantMessage = updatedAssistantMsg;
                        set({ messages: currentMessages });
                    },
                    onChunk: (chunk) => {
                        accumulatedReply += chunk;
                        let cleanReply = accumulatedReply.replace(/<\|channel>thought/g, '').replace(/<channel\|>/g, '');
                        assistantMessage = { ...assistantMessage, content: cleanReply };

                        if (!renderTimeout) {
                            renderTimeout = requestAnimationFrame(() => {
                                const currentMessages = [...get().messages];

                                // 🔥 KUNCI UTAMA: Tembak indeks yang tepat!
                                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                                currentMessages[idxToUpdate] = assistantMessage;

                                set({
                                    messages: currentMessages,
                                    isThinking: false // ✨ FIX: matikan isThinking saat teks mulai keluar
                                });
                                renderTimeout = null;
                            });
                        }
                    },
                    onDone: (data) => {
                        assistantMessage = { ...assistantMessage, isStreaming: false, isThinking: false };
                        
                        if (data && data.eval_count && data.eval_duration) {
                            assistantMessage.eval_count = data.eval_count;
                            assistantMessage.eval_duration = data.eval_duration;
                        }
                        
                        const currentMessages = [...get().messages];
                        const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                        currentMessages[idxToUpdate] = assistantMessage;
                        set({ messages: currentMessages });
                        
                        set({
                            isThinking: false,
                            isStreaming: false,
                            currentThinking: ''
                        });
                    }
                }
            );

            success = true;
        } catch (error) {
            console.warn(`💥 [FE STREAM ERROR]:`, error);
            if (error.name === 'AbortError') {
                assistantMessage.content += ' *Respons dihentikan*';
                assistantMessage.isStreaming = false;
                assistantMessage.isThinking = false;
                const currentMessages = [...get().messages];
                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                currentMessages[idxToUpdate] = assistantMessage;
                set({ messages: currentMessages, isThinking: false, currentThinking: '', isStreaming: false, isLoading: false });
                break; // Stop retry loop
            }

            attempts++;
            if (attempts >= maxAttempts) {
                assistantMessage.content = '⚠️ Gagal memuat balasan. Koneksi terputus sepenuhnya.';
                assistantMessage.isStreaming = false;
                assistantMessage.isThinking = false;
                const currentMessages = [...get().messages];
                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                currentMessages[idxToUpdate] = assistantMessage;
                set({ messages: currentMessages, isThinking: false, currentThinking: '' });
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
    abortController: null,

    stopStream: () => {
        const controller = get().abortController;
        if (controller) {
            controller.abort();
            set({ isStreaming: false, isThinking: false, abortController: null });
        }
    },

    sendMessage: async (content, npp, onSessionCreatedCallback, directUploadedFiles = null, chatMode = 'auto', isThinkingMode = true, toast = null) => {
        const hasAttachments = (directUploadedFiles?.length > 0) || (get().stagedAttachments?.length > 0);
        if ((!content.trim() && !hasAttachments) || get().isStreaming) return;

        // ── GUEST OVERRIDE (FE GUARD) ──
        if (npp === 'GUEST') {
            chatMode = 'flash';
            isThinkingMode = false;
        }

        let currentSessionUuid = get().sessionUuid;

        if (!currentSessionUuid || currentSessionUuid === "new") {
            try {
                const generatedTitle = "Obrolan Baru";
                const result = await endpoints.createChatSession(generatedTitle, npp);

                if (result.status === "success") {
                    currentSessionUuid = result.data.session_uuid;
                    
                    // 🔥 FIX: Simpan preferensi pengguna ke DB agar tidak kere-set saat di-fetch ulang oleh ChatPage
                    await endpoints.updateSessionSettings(currentSessionUuid, { chatMode, isThinkingMode }).catch(() => {});

                    if (onSessionCreatedCallback) {
                        onSessionCreatedCallback({
                            session_uuid: currentSessionUuid,
                            judul: result.data.judul || content.split(" ").slice(0, 4).join(" "),
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
        const assistantMessage = { role: 'assistant', content: '', isStreaming: true };

        const currentAttachmentPaths = attachmentMeta
            .map((file) => file.file_path)
            .filter(Boolean);

        const currentIsolatedDocId = get().activeIsolatedDocId;

        // Sinkronisasi state chatMode sebelum perubahan rute URL
        set({
            chatMode: chatMode, // Menyinkronkan chatMode ke store
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            // isLoading: true,
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
            isThinkingMode,
            toast
        );

        set({ stagedAttachments: [] });
    },

    editAndRegenerate: async (index, newContent, toast = null) => {
        if (!newContent.trim() || get().isStreaming) return;

        const currentMessages = [...get().messages];
        const sessionUuid = get().sessionUuid;

        // 1. In-Place Update: Ubah isi pesan user pada index tersebut
        currentMessages[index] = { ...currentMessages[index], content: newContent };

        // 2. In-Place Update: Siapkan asisten message baru di index + 1 (menimpa respons lama)
        const assistantMessage = {
            role: 'assistant',
            content: '',
            isThinking: true,
            isStreaming: true,
            thinking: '',
            statusMessage: 'Sedang berpikir...' // Gunakan statusMessage alih-alih thinking untuk loading state
        };

        // Jika kebetulan sebelahnya bukan assistant, kita push/splice (tapi idealnya selalu assistant)
        if (currentMessages[index + 1] && currentMessages[index + 1].role === 'assistant') {
            currentMessages[index + 1] = assistantMessage;
        } else {
            currentMessages.splice(index + 1, 0, assistantMessage);
        }

        set({
            messages: currentMessages,
            isStreaming: true,
            isThinking: true,
            currentThinking: 'Sedang berpikir...'
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        // 3. Kirimkan pesan HANYA sampai indeks yang diedit
        const messagesToSend = currentMessages.slice(0, index + 1);
        const npp = JSON.parse(localStorage.getItem('cakra_user') || '{}')?.npp || null;

        const currentAttachmentPaths = (currentMessages[index].attachments || [])
            .map((file) => file.file_path)
            .filter(Boolean);

        // 4. Panggil stream dengan target parameter (index + 1) dan editIndex = index
        await _performStream(
            set,
            get,
            messagesToSend,
            assistantMessage,
            sessionUuid,
            npp,
            get().activeIsolatedDocId,
            currentAttachmentPaths,
            'auto',
            true, // default isThinkingMode for edit/regenerate
            toast,
            index + 1, // targetAssistantIdx
            index      // 🔥 editIndex
        );
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
            if (result && result.items) {
                set({ documents: result.items });
            } else if (Array.isArray(result)) {
                set({ documents: result });
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