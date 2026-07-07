import * as endpoints from "../../services/endpoints";

export function normalizeAttachments(files) {
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
export async function performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null, isolatedDocId = null, attachmentPaths = [], chatMode = 'auto', isThinkingMode = true, toast = null, targetAssistantIdx = null, editIndex = null) {
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
                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            statusMessage: statusStr
                        };
                        assistantMessage = updatedAssistantMsg;

                        set(state => {
                            const newMessages = [...state.messages];
                            const idx = targetAssistantIdx !== null ? targetAssistantIdx : newMessages.length - 1;
                            if (newMessages[idx]) {
                                newMessages[idx] = updatedAssistantMsg;
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
