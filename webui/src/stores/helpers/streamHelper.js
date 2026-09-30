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
export async function performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null, isolatedDocId = null, attachmentPaths = [], chatMode = 'auto', isThinkingMode = true, toast = null, targetAssistantIdx = null, editIndex = null, streamOptions = {}) {
    let attempts = 0;
    const maxAttempts = 4;
    let success = false;
    const activeSessionUuid = forcedSessionUuid || get().sessionUuid;

    const updateStreamState = (updater) => {
        set(state => {
            let newState = {};
            const activeStreams = { ...state.activeStreams };

            // Inisialisasi stream jika belum ada
            if (!activeStreams[activeSessionUuid]) {
                activeStreams[activeSessionUuid] = {
                    messages: state.messages || [],
                    isStreaming: true,
                    isThinking: true,
                    currentThinking: state.currentThinking || ''
                };
            }

            const currentStream = { ...activeStreams[activeSessionUuid] };
            const currentMessages = [...currentStream.messages];

            // Panggil fungsi atau object updater (kompatibel dengan setState bawaan Zustand)
            let changes = typeof updater === 'function' ? updater({ ...state, messages: currentMessages }) : updater;

            if (changes.messages) currentStream.messages = changes.messages;
            if (changes.currentThinking !== undefined) currentStream.currentThinking = changes.currentThinking;
            if (changes.isThinking !== undefined) currentStream.isThinking = changes.isThinking;
            if (changes.isStreaming !== undefined) currentStream.isStreaming = changes.isStreaming;
            if (changes.isLoading !== undefined) currentStream.isLoading = changes.isLoading;

            activeStreams[activeSessionUuid] = currentStream;
            newState.activeStreams = activeStreams;

            // SINKRONISASI ke state global HANYA JIKA user sedang berada di sesi ini
            if (state.sessionUuid === activeSessionUuid) {
                if (changes.messages) newState.messages = changes.messages;
                if (changes.currentThinking !== undefined) newState.currentThinking = changes.currentThinking;
                if (changes.isThinking !== undefined) newState.isThinking = changes.isThinking;
                if (changes.isStreaming !== undefined) newState.isStreaming = changes.isStreaming;
                if (changes.isLoading !== undefined) newState.isLoading = changes.isLoading;
            }
            return newState;
        });
    };

    while (attempts < maxAttempts && !success) {
        try {
            if (attempts > 0) {
                // Silently attempt reconnect
                const delay = Math.pow(2, attempts - 1) * 1000;
                await new Promise(resolve => setTimeout(resolve, delay));
            }

            let accumulatedReply = '';
            let renderTimeout = null;
            let renderThinkingTimeout = null;
            let renderStatusTimeout = null;
            let accumulatedThinking = '';
            let backendBatchIndex = 0;

            const controller = new AbortController();
            set({ abortController: controller });

            const activeForcedMode = streamOptions.forcedMode || streamOptions.forced_mode || get().activeModeTag || null;
            const activeBypassRouter = streamOptions.bypassRouter !== undefined ? streamOptions.bypassRouter : Boolean(streamOptions.bypass_router);

            await endpoints.streamChat(
                {
                    sessionUuid: activeSessionUuid,
                    messages: messagesToSend,
                    chatMode: chatMode || get().chatMode || 'auto',
                    thinking: isThinkingMode !== undefined ? isThinkingMode : get().isThinkingMode,
                    isolatedDocId: streamOptions.isolated_doc_id || streamOptions.isolatedDocId || isolatedDocId,
                    attachmentPaths,
                    npp,
                    editIndex,
                    isRegenerate: Boolean(streamOptions.isRegenerate || streamOptions.is_regenerate),
                    targetIndex: streamOptions.targetIndex !== undefined ? streamOptions.targetIndex : streamOptions.target_index,
                    parentIndex: streamOptions.parentIndex !== undefined ? streamOptions.parentIndex : streamOptions.parent_index,
                    regeneratedFromId: streamOptions.regeneratedFromId || streamOptions.regenerated_from_id || null,
                    parentId: streamOptions.parentId || streamOptions.parent_id || null,
                    signal: controller.signal,
                    activeTopic: (typeof get().sessionTopics?.[activeSessionUuid] === 'object' ? get().sessionTopics[activeSessionUuid]?.topic : get().sessionTopics?.[activeSessionUuid]) || get().activeTopic || null,
                    keySubject: (typeof get().sessionTopics?.[activeSessionUuid] === 'object' ? get().sessionTopics[activeSessionUuid]?.keySubject : null) || get().keySubject || null,
                    forcedMode: activeForcedMode,
                    bypassRouter: activeBypassRouter,
                    docTitle: streamOptions.doc_title || streamOptions.docTitle || get().activeIsolatedTitle || null,
                    hintSource: streamOptions.hint_source || streamOptions.hintSource || null,
                    contextIsolation: streamOptions.context_isolation || streamOptions.contextIsolation || null,
                    language: get().language || (typeof localStorage !== 'undefined' ? localStorage.getItem("cakra_language") : 'id') || 'id'
                },
                {
                    onTopicUpdate: (topic, keySubject) => {
                        console.log('🏷️ [TOPIC_UPDATE] Session active topic updated:', topic, '| key subject:', keySubject);
                        set(state => ({
                            activeTopic: topic,
                            keySubject: keySubject || null,
                            sessionTopics: {
                                ...(state.sessionTopics || {}),
                                [activeSessionUuid]: {
                                    topic: topic,
                                    keySubject: keySubject || null
                                }
                            }
                        }));
                    },
                    onThinking: (thinking) => {
                        // Bersihkan marker <|channel> dan [GEMMA_THINK] dari string thinking
                        let cleanThinking = thinking
                            .replace(/<\|channel>thought/g, '')
                            .replace(/<channel\|>/g, '')
                            .replace(/\[GEMMA_THINK\]/g, '');

                        accumulatedThinking += cleanThinking;

                        // Status resmi yang bersih dan elegan (prioritaskan status dari backend jika ada)
                        const activeLang = get().language || (typeof localStorage !== 'undefined' ? localStorage.getItem("cakra_language") : 'id') || 'id';
                        let currentStatus = assistantMessage.statusMessage || (activeLang === 'en' ? '🧠 Analyzing context' : '🧠 Menganalisis konteks');

                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            thinking: accumulatedThinking,
                            isThinking: true,
                            statusMessage: currentStatus,
                            content: accumulatedReply // Preserve actual content independently
                        };

                        assistantMessage = updatedAssistantMsg;

                        if (!renderThinkingTimeout) {
                            renderThinkingTimeout = requestAnimationFrame(() => {
                                updateStreamState(state => {
                                    const newMessages = [...state.messages];
                                    const idx = targetAssistantIdx !== null ? targetAssistantIdx : newMessages.length - 1;
                                    if (newMessages[idx]) {
                                        newMessages[idx] = assistantMessage;
                                    }
                                    return {
                                        messages: newMessages,
                                        currentThinking: cleanThinking,
                                        isThinking: true
                                    };
                                });
                                renderThinkingTimeout = null;
                            });
                        }
                    },
                    onStatus: (statusStr, statusKey) => {
                        // Dipanggil oleh RAG / pipeline statis / agentic tool
                        let activeTool = assistantMessage.activeTool || null;
                        if (statusKey) {
                            const upperKey = statusKey.toUpperCase();
                            if (upperKey.includes('WEBSEARCH') || upperKey.includes('WEB_SEARCH')) activeTool = 'websearch';
                            else if (upperKey.includes('URLFETCH') || upperKey.includes('URL_FETCH') || upperKey.includes('READ_URL')) activeTool = 'urlfetch';
                            else if (upperKey.includes('DOCSEARCH') || upperKey.includes('DOC_SEARCH')) activeTool = 'docsearch';
                            else if (upperKey.includes('CALC')) activeTool = 'python_calc';
                            else if (upperKey.includes('MAP')) activeTool = 'map_search';
                            else if (upperKey.includes('CLI') || upperKey.includes('TERMINAL')) activeTool = 'terminal_runner';
                            else if (upperKey === 'DRAFTING_RESPONSE' || upperKey === 'FINISHED') activeTool = null;
                        }

                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            statusMessage: statusStr,
                            statusKey: statusKey || assistantMessage.statusKey || null,
                            activeTool: activeTool
                        };
                        assistantMessage = updatedAssistantMsg;

                        if (!renderStatusTimeout) {
                            renderStatusTimeout = requestAnimationFrame(() => {
                                updateStreamState(state => {
                                    const newMessages = [...state.messages];
                                    const idx = targetAssistantIdx !== null ? targetAssistantIdx : newMessages.length - 1;
                                    if (newMessages[idx]) {
                                        newMessages[idx] = assistantMessage;
                                    }
                                    return {
                                        messages: newMessages,
                                        currentThinking: statusStr
                                    };
                                });
                                renderStatusTimeout = null;
                            });
                        }
                    },
                    onSources: (sources) => {
                        console.log('📚 [SSE] Received sources:', sources);
                        let finalSources = Array.isArray(sources) ? [...sources] : [];

                        // 📚 MERGE DOKUMEN RUJUKAN dari hint jika ada streamOptions.hint_source
                        if (streamOptions?.hint_source) {
                            const hintSrc = streamOptions.hint_source;
                            const existingIdx = finalSources.findIndex(s => 
                                (hintSrc.id && (String(s.id) === String(hintSrc.id) || String(s.dokumen_id) === String(hintSrc.id) || String(s.id_berita) === String(hintSrc.id))) ||
                                (hintSrc.title && s.title && s.title.trim().toLowerCase() === hintSrc.title.trim().toLowerCase())
                            );
                            if (existingIdx !== -1) {
                                finalSources[existingIdx] = {
                                    ...hintSrc,
                                    ...finalSources[existingIdx],
                                    nomor: finalSources[existingIdx].nomor || hintSrc.nomor || "",
                                    tanggal: finalSources[existingIdx].tanggal || hintSrc.tanggal || "",
                                    total_pages: finalSources[existingIdx].total_pages || hintSrc.total_pages || "",
                                    category: finalSources[existingIdx].category || hintSrc.category || "Regulasi",
                                    jenis: finalSources[existingIdx].jenis || hintSrc.jenis || "Regulasi",
                                };
                            } else {
                                finalSources = [hintSrc, ...finalSources];
                            }
                        }

                        const updatedAssistantMsg = {
                            ...assistantMessage,
                            sources: finalSources,
                            citations: finalSources
                        };
                        const currentMessages = [...(get().activeStreams[activeSessionUuid]?.messages || get().messages)];
                        const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                        currentMessages[idxToUpdate] = updatedAssistantMsg;

                        assistantMessage = updatedAssistantMsg;
                        updateStreamState({ messages: currentMessages });
                    },
                    onChunk: (chunk) => {
                        accumulatedReply += chunk;
                        let cleanReply = accumulatedReply;

                        if (cleanReply.includes('<|channel>thought')) {
                            cleanReply = cleanReply.replace(/<\|channel>thought/g, '').replace(/<channel\|>/g, '');
                        }

                        // 🔥 HANDLE <thinking> LEAKAGE 🔥
                        let leakedThinking = "";
                        if (cleanReply.includes('<thinking>')) {
                            cleanReply = cleanReply.replace(/<thinking>([\s\S]*?)(?:<\/thinking>|$)/gi, (match, p1) => {
                                leakedThinking += p1;
                                return ""; // Hapus dari output chat utama
                            });
                        }

                        // 🔥 DETEKSI SINYAL SEMUA FILE SELESAI 🔥
                        const hasAllFilesDoneSignal = cleanReply.includes('[[ALL_FILES_COMPLETED]]') || cleanReply.includes('<all_files_done');
                        if (hasAllFilesDoneSignal) {
                            cleanReply = cleanReply
                                .replace(/\[\[ALL_FILES_COMPLETED\]\]/g, '')
                                .replace(/<all_files_done\s*\/?>/gi, '');
                        }

                        const existingGens = [...(assistantMessage.fileGenerations || [])];

                        // 🔥 DYNAMIC FRONTEND PARSER 🔥
                        let textDisplay = cleanReply;

                        if (cleanReply.includes('<create_file') || cleanReply.includes('<edit_file')) {
                            const openTagRegex = /<(create_file|edit_file)\s+filename=["']([^"'>\s]+)["']\s*>/gi;
                            const closeTagRegex = /<\/(create_file|edit_file)\s*>/gi;

                            textDisplay = "";
                            let lastIdx = 0;
                            let currentBatchIndex = 0;
                            let hasInjectedFirst = false;

                            let match;
                            while ((match = openTagRegex.exec(cleanReply)) !== null) {
                                const precedingText = cleanReply.substring(lastIdx, match.index);
                                const filename = match[2];

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

                                // Sinkronkan batchIndex fileGeneration yang cocok dengan urutan penempatan teks
                                if (filename) {
                                    const fgIdx = existingGens.findIndex(fg => fg.filename === filename);
                                    if (fgIdx !== -1) {
                                        existingGens[fgIdx] = {
                                            ...existingGens[fgIdx],
                                            batchIndex: currentBatchIndex
                                        };
                                    } else {
                                        // 🔥 OPTIMISTIC INITIALIZATION:
                                        // Begitu open tag terdeteksi, langsung buatkan entri awal agar FileProcessLog
                                        // langsung render status live (tidak blank/null) sejak detik pertama!
                                        existingGens.push({
                                            filename,
                                            stage: (match[1] || '').toLowerCase() === 'edit_file' ? 'editing' : 'creating',
                                            tag_type: (match[1] || 'create_file').toLowerCase(),
                                            liveCode: '',
                                            file_path: null,
                                            batchIndex: currentBatchIndex
                                        });
                                    }
                                }

                                const contentStart = openTagRegex.lastIndex;

                                closeTagRegex.lastIndex = contentStart;
                                const nextClose = closeTagRegex.exec(cleanReply);

                                const nextOpenRegex = /<(create_file|edit_file)\s+filename=/gi;
                                nextOpenRegex.lastIndex = contentStart;
                                const nextOpen = nextOpenRegex.exec(cleanReply);

                                if (nextClose && (!nextOpen || nextClose.index < nextOpen.index)) {
                                    const codeContent = cleanReply.substring(contentStart, nextClose.index);
                                    const fgIdx = existingGens.findIndex(fg => fg.filename === filename);
                                    if (fgIdx !== -1) {
                                        existingGens[fgIdx] = {
                                            ...existingGens[fgIdx],
                                            stage: 'done',
                                            liveCode: codeContent
                                        };
                                    }
                                    lastIdx = closeTagRegex.lastIndex;
                                } else if (nextOpen && (!nextClose || nextOpen.index < nextClose.index)) {
                                    const codeContent = cleanReply.substring(contentStart, nextOpen.index);
                                    const fgIdx = existingGens.findIndex(fg => fg.filename === filename);
                                    if (fgIdx !== -1) {
                                        existingGens[fgIdx] = {
                                            ...existingGens[fgIdx],
                                            stage: 'done',
                                            liveCode: codeContent
                                        };
                                    }
                                    lastIdx = nextOpen.index;
                                    openTagRegex.lastIndex = lastIdx;
                                } else {
                                    const codeContent = cleanReply.substring(contentStart);
                                    const fgIdx = existingGens.findIndex(fg => fg.filename === filename);
                                    if (fgIdx !== -1) {
                                        existingGens[fgIdx] = {
                                            ...existingGens[fgIdx],
                                            liveCode: codeContent
                                        };
                                    }
                                    lastIdx = cleanReply.length;
                                }
                            }
                            textDisplay += cleanReply.substring(lastIdx);
                        }

                        assistantMessage = {
                            ...assistantMessage,
                            content: textDisplay,
                            fileGenerations: existingGens,
                            allFilesDone: Boolean(hasAllFilesDoneSignal || assistantMessage.allFilesDone)
                        };

                        // Gabungkan hasil pemikiran yang bocor jika ada
                        if (leakedThinking) {
                            assistantMessage.thinking = accumulatedThinking + "\n" + leakedThinking.trim();
                            assistantMessage.isThinking = true;
                        }

                        if (!renderTimeout) {
                            renderTimeout = requestAnimationFrame(() => {
                                const currentMessages = [...(get().activeStreams[activeSessionUuid]?.messages || get().messages)];
                                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                                currentMessages[idxToUpdate] = assistantMessage;

                                updateStreamState({
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
                                // Update global state directly to ensure UI reactivity
                                const currentState = get();
                                const currentArtifacts = [...(currentState.artifacts || [])];
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

                                console.log('[STREAM_HELPER] Menambahkan artifact baru:', newArt);
                                set({ artifacts: currentArtifacts });

                                // Juga update stream state untuk konsistensi internal
                                updateStreamState({ artifacts: currentArtifacts });
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
                                if (tag_type) fileGens[existingIdx].tag_type = tag_type;
                                fileGens[existingIdx].batchIndex = backendBatchIndex;
                            }
                        } else if (stage === 'code_chunk') {
                            if (existingIdx !== -1) {
                                fileGens[existingIdx].stage = 'streaming';
                                fileGens[existingIdx].liveCode = (fileGens[existingIdx].liveCode || '') + (fileStatus.code_chunk || '');
                                if (tag_type) fileGens[existingIdx].tag_type = tag_type;
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
                                const currentMessages = [...(get().activeStreams[activeSessionUuid]?.messages || get().messages)];
                                const idx = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                                currentMessages[idx] = assistantMessage;
                                updateStreamState({ messages: currentMessages });
                                renderTimeout = null;
                            });
                        }
                    },
                    onDone: (data) => {
                        let finalFileGens = assistantMessage.fileGenerations;
                        if (finalFileGens && finalFileGens.length > 0) {
                            finalFileGens = finalFileGens.map(fg => {
                                if (fg.stage === 'creating' || fg.stage === 'editing' || fg.stage === 'streaming') {
                                    return { ...fg, stage: 'done' };
                                }
                                return fg;
                            });
                        }
                        assistantMessage = {
                            ...assistantMessage,
                            isStreaming: false,
                            isThinking: false,
                            activeTool: null,
                            fileGenerations: finalFileGens
                        };

                        // 📚 MERGE DOKUMEN RUJUKAN dari hint di akhir stream jika belum terdaftar
                        if (streamOptions?.hint_source) {
                            const hintSrc = streamOptions.hint_source;
                            let currentSources = assistantMessage.sources || assistantMessage.citations || [];
                            if (!Array.isArray(currentSources)) currentSources = [];

                            const existingIdx = currentSources.findIndex(s => 
                                (hintSrc.id && (String(s.id) === String(hintSrc.id) || String(s.dokumen_id) === String(hintSrc.id) || String(s.id_berita) === String(hintSrc.id))) ||
                                (hintSrc.title && s.title && s.title.trim().toLowerCase() === hintSrc.title.trim().toLowerCase())
                            );
                            if (existingIdx !== -1) {
                                currentSources[existingIdx] = {
                                    ...hintSrc,
                                    ...currentSources[existingIdx],
                                    nomor: currentSources[existingIdx].nomor || hintSrc.nomor || "",
                                    tanggal: currentSources[existingIdx].tanggal || hintSrc.tanggal || "",
                                    total_pages: currentSources[existingIdx].total_pages || hintSrc.total_pages || "",
                                    category: currentSources[existingIdx].category || hintSrc.category || "Regulasi",
                                    jenis: currentSources[existingIdx].jenis || hintSrc.jenis || "Regulasi",
                                };
                            } else {
                                currentSources = [hintSrc, ...currentSources];
                            }
                            assistantMessage = {
                                ...assistantMessage,
                                sources: currentSources,
                                citations: currentSources
                            };
                        }

                        // --- INTERCEPT EMPTY RESPONSE ONLY ---
                        const cleanContent = (assistantMessage.content || '').trim();
                        const hasFiles = assistantMessage.fileGenerations && assistantMessage.fileGenerations.length > 0;
                        if (!hasFiles && cleanContent.length === 0) {
                            assistantMessage.content = "Mohon maaf, saya tidak dapat memproses pesan Anda dengan baik. Silakan coba beberapa saat lagi atau perjelas pertanyaan Anda.";
                            console.warn("[FE STREAM] Respons kosong, menggunakan fallback.");
                        }
                        if (data && data.is_truncated) {
                            assistantMessage.is_truncated = true;
                            assistantMessage.metadata = {
                                ...(assistantMessage.metadata || {}),
                                is_truncated: true
                            };
                        }
                        if (data && data.eval_count && data.eval_duration) {
                            assistantMessage.eval_count = data.eval_count;
                            assistantMessage.eval_duration = data.eval_duration;
                        }

                        if (data && data.title) {
                            window.dispatchEvent(new CustomEvent("cakra_title_update", {
                                detail: { sessionUuid: get().sessionUuid, title: data.title }
                            }));
                        }

                        // Sync ke varian aktif jika pesan memiliki variants
                        if (assistantMessage.variants && assistantMessage.activeVariantIndex !== undefined && assistantMessage.variants[assistantMessage.activeVariantIndex]) {
                            const activeThought = assistantMessage.thought || assistantMessage.thinking || accumulatedThinking || '';
                            assistantMessage.thought = activeThought;
                            assistantMessage.thinking = activeThought;
                            assistantMessage.variants[assistantMessage.activeVariantIndex] = {
                                ...assistantMessage.variants[assistantMessage.activeVariantIndex],
                                content: assistantMessage.content,
                                thought: activeThought,
                                thinking: activeThought,
                                sources: assistantMessage.sources,
                                metadata: assistantMessage.metadata,
                                fileGenerations: assistantMessage.fileGenerations || [],
                                allFilesDone: assistantMessage.allFilesDone || false,
                                isStreaming: false,
                                isThinking: false
                            };
                        }

                        const currentMessages = [...(get().activeStreams[activeSessionUuid]?.messages || get().messages)];
                        const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                        currentMessages[idxToUpdate] = assistantMessage;
                        updateStreamState({ messages: currentMessages });

                        updateStreamState({
                            isThinking: false,
                            isStreaming: false,
                            currentThinking: ''
                        });
                    }
                }
            );

            success = true;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.info('[FE STREAM] Stream stopped by user (aborted).');
                assistantMessage.content += ' *Respons dihentikan*';
                assistantMessage.isStreaming = false;
                assistantMessage.isThinking = false;
                const currentMessages = [...(get().activeStreams[activeSessionUuid]?.messages || get().messages)];
                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                currentMessages[idxToUpdate] = assistantMessage;
                updateStreamState({ messages: currentMessages, isThinking: false, currentThinking: '', isStreaming: false, isLoading: false, isEditRegenerating: false });
                break; // Stop retry loop
            }
            console.warn(`💥 [FE STREAM ERROR]:`, error);

            attempts++;
            if (attempts >= maxAttempts) {
                assistantMessage.content = '⚠️ Gagal memuat balasan. Koneksi terputus sepenuhnya.';
                assistantMessage.isStreaming = false;
                assistantMessage.isThinking = false;
                const currentMessages = [...(get().activeStreams[activeSessionUuid]?.messages || get().messages)];
                const idxToUpdate = targetAssistantIdx !== null ? targetAssistantIdx : currentMessages.length - 1;
                currentMessages[idxToUpdate] = assistantMessage;
                updateStreamState({ messages: currentMessages, isThinking: false, currentThinking: '', isEditRegenerating: false });
                // Silent failure
            }
        }
    }
    updateStreamState({ isStreaming: false, isLoading: false, isThinking: false, isEditRegenerating: false });
}

/**
 * Robust Parser: Mengonversi sintaks raw <create_file> / <edit_file> dan [[ALL_FILES_COMPLETED]]
 * menjadi placeholder [[CAKRA_FILE_PROCESS_LOG_...]] dan array fileGenerations agar
 * teks tampil bersih dengan kartu file interaktif di semua varian respons.
 */
export function parseMessageFileTags(msg) {
    if (!msg || !msg.content || typeof msg.content !== 'string') return msg;

    let content = msg.content;
    let allFilesDone = Boolean(msg.allFilesDone);

    const hasAllFilesDoneSignal = content.includes('[[ALL_FILES_COMPLETED]]') || content.includes('<all_files_done');
    if (hasAllFilesDoneSignal) {
        allFilesDone = true;
        content = content
            .replace(/\[\[ALL_FILES_COMPLETED\]\]/g, '')
            .replace(/<all_files_done\s*\/?>/gi, '');
    }

    if (!content.includes('<create_file') && !content.includes('<edit_file')) {
        return {
            ...msg,
            content,
            allFilesDone,
            fileGenerations: msg.fileGenerations || []
        };
    }

    const openTagRegex = /<(create_file|edit_file)\s+filename=["']([^"'>\s]+)["']\s*>/gi;
    const closeTagRegex = /<\/(create_file|edit_file)\s*>/gi;

    let textDisplay = "";
    const parsedFileGens = [];
    let lastIdx = 0;
    let currentBatchIndex = 0;
    let hasInjectedFirst = false;

    let match;
    openTagRegex.lastIndex = 0;
    while ((match = openTagRegex.exec(content)) !== null) {
        const precedingText = content.substring(lastIdx, match.index);

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

        closeTagRegex.lastIndex = contentStart;
        const nextClose = closeTagRegex.exec(content);

        const nextOpenRegex = /<(create_file|edit_file)\s+filename=/gi;
        nextOpenRegex.lastIndex = contentStart;
        const nextOpen = nextOpenRegex.exec(content);

        let contentEnd = content.length;

        if (nextClose && (!nextOpen || nextClose.index < nextOpen.index)) {
            contentEnd = nextClose.index;
            lastIdx = closeTagRegex.lastIndex;
        } else if (nextOpen && (!nextClose || nextOpen.index < nextClose.index)) {
            contentEnd = nextOpen.index;
            lastIdx = nextOpen.index;
            openTagRegex.lastIndex = lastIdx;
        } else {
            contentEnd = content.length;
            lastIdx = content.length;
        }

        const codeContent = content.substring(contentStart, contentEnd);
        parsedFileGens.push({
            filename,
            stage: 'done',
            liveCode: codeContent,
            batchIndex: currentBatchIndex,
            tag_type: (match[1] || 'create_file').toLowerCase()
        });
    }
    textDisplay += content.substring(lastIdx);

    let fileGenerations = parsedFileGens;
    if (msg.metadata && msg.metadata.artifacts && Array.isArray(msg.metadata.artifacts)) {
        fileGenerations = parsedFileGens.map(pfg => {
            const metaArt = msg.metadata.artifacts.find(a => a.filename === pfg.filename);
            return {
                ...pfg,
                file_path: metaArt ? metaArt.file_path : null,
                lines_count: metaArt ? metaArt.lines_count : 1
            };
        });
        msg.metadata.artifacts.forEach(art => {
            if (!fileGenerations.find(fg => fg.filename === art.filename)) {
                fileGenerations.push({
                    filename: art.filename,
                    stage: 'done',
                    file_path: art.file_path,
                    liveCode: art.code || '',
                    lines_count: art.lines_count || 1
                });
            }
        });
    }

    return {
        ...msg,
        content: textDisplay,
        allFilesDone,
        fileGenerations: fileGenerations.length > 0 ? fileGenerations : (msg.fileGenerations || [])
    };
}

