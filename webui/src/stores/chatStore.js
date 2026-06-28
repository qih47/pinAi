import { create } from "zustand";
import * as endpoints from "../services/endpoints";

export const API_BASE = endpoints.getApiBase();
export const getUploadUrl = endpoints.getUploadUrl;

let _sessionLoadSeq = 0;

function _normalizeAttachments(files) {
    if (!files || !files.length) return [];
    return files.map((f) => {
        let newPath = f.file_path || f.unique_filename;
        if (newPath) {
            newPath = newPath.startsWith('accounts/') 
                ? newPath 
                : (newPath.includes('/') ? newPath.split('/').pop() : newPath);
        }
        
        return {
            id: f.id,
            file_name: f.original_filename || f.file_name || 'lampiran',
            file_path: newPath,
            mime_type: f.mime_type,
            file_size: f.file_size || f.size || 0,
        };
    });
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
            let backendBatchIndex = 0;

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

                        // 🔥 DYNAMIC FRONTEND PARSER 🔥
                        const openTagRegex = /<(create_file|edit_file)\s+filename=["']([^"'>\s]+)["']\s*>/gi;
                        const closeTagRegex = /<\/(create_file|edit_file)\s*>/gi;

                        let textDisplay = "";
                        let lastIdx = 0;
                        let currentBatchIndex = 0;
                        let hasInjectedFirst = false;
                        
                        let match;
                        while ((match = openTagRegex.exec(cleanReply)) !== null) {
                            const precedingText = cleanReply.substring(lastIdx, match.index);
                            
                            if (!hasInjectedFirst) {
                                textDisplay += precedingText;
                                textDisplay += `\n\n[[CAKRA_FILE_PROCESS_LOG_${currentBatchIndex}]]\n\n`;
                                hasInjectedFirst = true;
                            } else if (precedingText.trim().length > 0) {
                                currentBatchIndex++;
                                textDisplay += precedingText;
                                textDisplay += `\n\n[[CAKRA_FILE_PROCESS_LOG_${currentBatchIndex}]]\n\n`;
                            } else {
                                textDisplay += precedingText; // Just whitespace
                            }

                            const filename = match[2];
                            const contentStart = openTagRegex.lastIndex;

                            closeTagRegex.lastIndex = contentStart;
                            const nextClose = closeTagRegex.exec(cleanReply);

                            const nextOpenRegex = /<(create_file|edit_file)\s+filename=/gi;
                            nextOpenRegex.lastIndex = contentStart;
                            const nextOpen = nextOpenRegex.exec(cleanReply);

                            let contentEnd = cleanReply.length;

                            if (nextClose && (!nextOpen || nextClose.index < nextOpen.index)) {
                                contentEnd = nextClose.index;
                                lastIdx = closeTagRegex.lastIndex;
                            } else if (nextOpen && (!nextClose || nextOpen.index < nextClose.index)) {
                                contentEnd = nextOpen.index;
                                lastIdx = nextOpen.index; 
                                openTagRegex.lastIndex = lastIdx; 
                            } else {
                                contentEnd = cleanReply.length;
                                lastIdx = cleanReply.length;
                            }
                        }
                        textDisplay += cleanReply.substring(lastIdx);

                        const existingGens = [...(assistantMessage.fileGenerations || [])];

                        assistantMessage = { 
                            ...assistantMessage, 
                            content: textDisplay,
                            fileGenerations: existingGens 
                        };

                        if (!renderTimeout) {
                            renderTimeout = requestAnimationFrame(() => {
                                const currentMessages = [...get().messages];
                                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                                currentMessages[idxToUpdate] = assistantMessage;

                                set({
                                    messages: currentMessages,
                                    isThinking: false
                                });
                                renderTimeout = null;
                            });
                        }
                    },
                    onFileStatus: (fileStatus) => {
                        const { stage, filename, tag_type } = fileStatus;
                        
                        if (stage === 'batch_break') {
                            backendBatchIndex++;
                            return; // No need to update fileGenerations for batch_break
                        }
                        
                        const fileGens = [...(assistantMessage.fileGenerations || [])];
                        const existingIdx = fileGens.findIndex(fg => fg.filename === filename);
                        
                        if (stage === 'done') {
                            if (existingIdx !== -1) {
                                fileGens[existingIdx] = { 
                                    ...fileGens[existingIdx], 
                                    stage: 'done',
                                    file_path: fileStatus.file_path || null,
                                };
                            } else {
                                fileGens.push({ 
                                    filename, 
                                    stage: 'done', 
                                    liveCode: '', 
                                    file_path: fileStatus.file_path || null,
                                    tag_type,
                                    batchIndex: backendBatchIndex
                                });
                            }
                            
                            // ── Merekam ke Sidebar (Artifacts) ──
                            if (fileStatus.file_path) {
                                set(state => {
                                    const currentArtifacts = [...state.artifacts];
                                    const exArtIdx = currentArtifacts.findIndex(a => a.filename === filename);
                                    const newArt = {
                                        filename,
                                        file_path: fileStatus.file_path,
                                        lines_count: fileStatus.lines_count || 1,
                                    };
                                    if (exArtIdx !== -1) {
                                        currentArtifacts[exArtIdx] = newArt;
                                    } else {
                                        currentArtifacts.push(newArt);
                                    }
                                    return { artifacts: currentArtifacts };
                                });
                            }
                        } else if (stage === 'creating') {
                            if (existingIdx === -1) {
                                fileGens.push({
                                    filename,
                                    stage: 'creating',
                                    liveCode: '',
                                    file_path: null,
                                    tag_type,
                                    batchIndex: backendBatchIndex
                                });
                            } else {
                                fileGens[existingIdx].stage = 'creating';
                                if(tag_type) fileGens[existingIdx].tag_type = tag_type;
                                fileGens[existingIdx].batchIndex = backendBatchIndex;
                            }
                        } else if (stage === 'code_chunk') {
                            if (existingIdx !== -1) {
                                fileGens[existingIdx].stage = 'streaming';
                                fileGens[existingIdx].liveCode = (fileGens[existingIdx].liveCode || '') + (fileStatus.code_chunk || '');
                                if(tag_type) fileGens[existingIdx].tag_type = tag_type;
                            } else {
                                fileGens.push({
                                    filename,
                                    stage: 'streaming',
                                    liveCode: fileStatus.code_chunk || '',
                                    file_path: null,
                                    tag_type,
                                    batchIndex: backendBatchIndex
                                });
                            }
                        } else if (stage === 'error') {
                            if (existingIdx !== -1) {
                                fileGens[existingIdx] = { ...fileGens[existingIdx], stage: 'error' };
                            }
                        }
                        
                        // Mutate local variable to ensure the NEXT onChunk/onFileStatus reads this updated state
                        assistantMessage = { ...assistantMessage, fileGenerations: fileGens };

                        if (!renderTimeout) {
                            renderTimeout = requestAnimationFrame(() => {
                                const currentMessages = [...get().messages];
                                const idx = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                                currentMessages[idx] = assistantMessage;
                                set({ messages: currentMessages });
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
                        
                        if (data && data.title) {
                            window.dispatchEvent(new CustomEvent("cakra_title_update", { 
                                detail: { sessionUuid: get().sessionUuid, title: data.title } 
                            }));
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
    artifacts: [],  // ← Generated artifacts dari Interceptor-Analyst Pipeline

    clearArtifacts: () => set({ artifacts: [] }),

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
            get().chatMode,
            get().isThinkingMode,
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
            activeIsolatedTitle: null,
            artifacts: [],  // ← Reset artifacts saat session baru
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
        set({ sessionUuid, messages: [], isLoading: true, activeIsolatedDocId: null, activeIsolatedTitle: null, artifacts: [] });

        try {
            const npp = JSON.parse(localStorage.getItem('cakra_user'))?.npp || '';
            const result = await endpoints.fetchSessionMessages(sessionUuid, npp);

            if (seq !== _sessionLoadSeq) return;

            if (result.status === "success" && result.data) {
                let loadedArtifacts = [];
                // SINKRONISASI RIWAYAT: Mengambil nama berkas saja dari riwayat lampiran lama
                const sanitizedMessages = result.data.map(msg => {
                    let newMsg = { ...msg };
                    
                    // 🔥 PARSE TAGS FROM SAVED CONTENT (FIX RELOAD BUG) 🔥
                    if (newMsg.role === 'assistant' && newMsg.content) {
                        const openTagRegex = /<(create_file|edit_file)\s+filename=["']([^"'>\s]+)["']\s*>/gi;
                        const closeTagRegex = /<\/(create_file|edit_file)\s*>/gi;
                        
                        let textDisplay = "";
                        // Robust Parser with Auto-Close for loadChatSession
                        const parsedFileGens = [];
                        let lastIdx = 0;
                        let currentBatchIndex = 0;
                        let hasInjectedFirst = false;
                        
                        let match;
                        openTagRegex.lastIndex = 0;
                        while ((match = openTagRegex.exec(newMsg.content)) !== null) {
                            const precedingText = newMsg.content.substring(lastIdx, match.index);
                            
                            if (!hasInjectedFirst) {
                                textDisplay += precedingText;
                                textDisplay += `\n\n[[CAKRA_FILE_PROCESS_LOG_${currentBatchIndex}]]\n\n`;
                                hasInjectedFirst = true;
                            } else if (precedingText.trim().length > 0) {
                                currentBatchIndex++;
                                textDisplay += precedingText;
                                textDisplay += `\n\n[[CAKRA_FILE_PROCESS_LOG_${currentBatchIndex}]]\n\n`;
                            } else {
                                textDisplay += precedingText;
                            }

                            const filename = match[2];
                            const contentStart = openTagRegex.lastIndex;

                            // Look ahead for the next close tag or the next open tag (auto-close)
                            closeTagRegex.lastIndex = contentStart;
                            const nextClose = closeTagRegex.exec(newMsg.content);

                            const nextOpenRegex = /<(create_file|edit_file)\s+filename=/gi;
                            nextOpenRegex.lastIndex = contentStart;
                            const nextOpen = nextOpenRegex.exec(newMsg.content);

                            let contentEnd = newMsg.content.length;

                            if (nextClose && (!nextOpen || nextClose.index < nextOpen.index)) {
                                // Normal close
                                contentEnd = nextClose.index;
                                lastIdx = closeTagRegex.lastIndex;
                            } else if (nextOpen && (!nextClose || nextOpen.index < nextClose.index)) {
                                // Auto close because new tag started (LLM forgot to close)
                                contentEnd = nextOpen.index;
                                lastIdx = nextOpen.index; 
                                openTagRegex.lastIndex = lastIdx; 
                            } else {
                                // Still streaming / EOF
                                contentEnd = newMsg.content.length;
                                lastIdx = newMsg.content.length;
                            }

                            const codeContent = newMsg.content.substring(contentStart, contentEnd);
                            parsedFileGens.push({ filename, stage: 'done', liveCode: codeContent, batchIndex: currentBatchIndex });
                        }
                        textDisplay += newMsg.content.substring(lastIdx);
                        
                        newMsg.content = textDisplay;
                        
                        // Merge with metadata artifacts for file_path
                        if (newMsg.metadata && newMsg.metadata.artifacts && Array.isArray(newMsg.metadata.artifacts)) {
                            loadedArtifacts = [...loadedArtifacts, ...newMsg.metadata.artifacts];
                            
                            newMsg.fileGenerations = parsedFileGens.map(pfg => {
                                const metaArt = newMsg.metadata.artifacts.find(a => a.filename === pfg.filename);
                                return {
                                    ...pfg,
                                    file_path: metaArt ? metaArt.file_path : null,
                                    lines_count: metaArt ? metaArt.lines_count : 1
                                };
                            });
                            
                            // Include metadata artifacts that weren't caught by parser (fallback)
                            newMsg.metadata.artifacts.forEach(art => {
                                if (!newMsg.fileGenerations.find(fg => fg.filename === art.filename)) {
                                    newMsg.fileGenerations.push({
                                        filename: art.filename,
                                        stage: 'done',
                                        file_path: art.file_path,
                                        liveCode: art.code || '',
                                        lines_count: art.lines_count || 1
                                    });
                                }
                            });
                        } else if (parsedFileGens.length > 0) {
                            newMsg.fileGenerations = parsedFileGens;
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