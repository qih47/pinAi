import * as endpoints from "../../services/endpoints";
import apiClient from "../../services/apiClient";
import { performStream, normalizeAttachments, parseMessageFileTags } from "../helpers/streamHelper";

export const createStreamSlice = (set, get) => ({
    stopStream: (sessionUuid = null) => {
        const targetSession = sessionUuid || get().sessionUuid;
        const activeStreams = { ...get().activeStreams };
        
        let currentMessages = [...get().messages];
        if (currentMessages.length > 0) {
            const lastIdx = currentMessages.length - 1;
            if (currentMessages[lastIdx].role === 'assistant') {
                const prevContent = currentMessages[lastIdx].content || '';
                const stopText = prevContent.trim() ? `${prevContent}\n\n*Respons dihentikan*` : '*Respons dihentikan*';
                currentMessages[lastIdx] = {
                    ...currentMessages[lastIdx],
                    content: stopText,
                    isStreaming: false,
                    isThinking: false,
                    statusMessage: ''
                };
            }
        }

        if (activeStreams[targetSession] && activeStreams[targetSession].abortController) {
            activeStreams[targetSession].abortController.abort();
            delete activeStreams[targetSession];
        }
        
        if (targetSession === get().sessionUuid) {
            const controller = get().abortController;
            if (controller) controller.abort();
        }

        set({ 
            activeStreams,
            messages: currentMessages,
            isStreaming: false, 
            isThinking: false, 
            abortController: null 
        });
    },

    sendMessage: async (content, npp, onSessionCreatedCallback, directUploadedFiles = null, chatMode = 'auto', isThinkingMode = true, toast = null, options = {}) => {
        const hasAttachments = (directUploadedFiles?.length > 0) || (get().stagedAttachments?.length > 0);
        if (!content.trim() && !hasAttachments) return;

        // Broadcast to Analytics Live Pipeline Canvas (Same-Origin BroadcastChannel & Cross-Origin Backend SSE Bridge)
        try {
            const telemetryPayload = {
                type: 'PIPELINE_LIFECYCLE',
                stage: 'INIT',
                prompt: content,
                chatMode: chatMode,
                timestamp: Date.now()
            };
            if (typeof window !== 'undefined' && window.BroadcastChannel) {
                const bc = new BroadcastChannel('cakra_pipeline_telemetry');
                bc.postMessage(telemetryPayload);
                bc.close();
            }
            apiClient.post('/analytics/pipeline/event', telemetryPayload).catch(() => {});
        } catch (e) {
            // silent broadcast error
        }

        const currentActiveStreams = get().activeStreams || {};
        if (Object.keys(currentActiveStreams).length >= 4) {
            // Silent return, backend or queue handles limit
            return;
        }
        
        const activeSessionUuid_temp = get().sessionUuid;
        if (currentActiveStreams[activeSessionUuid_temp]?.isStreaming) {
            return; // Cegah kirim di sesi yang sama jika sedang stream
        }

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
        const attachmentMeta = normalizeAttachments(targetFiles);

        const currentIsolatedDocId = options?.isolated_doc_id || options?.isolatedDocId || get().activeIsolatedDocId;
        const currentChatMode = get().chatMode;
        
        let effectiveChatMode = chatMode;
        if (currentIsolatedDocId && currentChatMode !== 'documents' && options?.forced_mode !== 'documents') {
            effectiveChatMode = (currentChatMode === 'compliance' || currentChatMode === 'redteam') ? currentChatMode : 'focus';
        }

        const userMessage = {
            role: 'user',
            content: content.trim(),
            timestamp: new Date().toISOString(),
            chatMode: effectiveChatMode,
            mode: effectiveChatMode,
            isThinkingMode: isThinkingMode,
            thinking: isThinkingMode,
            isolatedDocId: currentIsolatedDocId || null,
            streamOptions: options || {},
            ...(attachmentMeta.length > 0 ? { attachments: attachmentMeta } : {}),
        };
        const updatedMessages = [...get().messages, userMessage];
        const assistantMessage = { 
            role: 'assistant', 
            content: '', 
            timestamp: new Date().toISOString(), 
            isStreaming: true,
            chatMode: effectiveChatMode,
            mode: effectiveChatMode,
            isThinkingMode: isThinkingMode,
            thinking: isThinkingMode ? '' : undefined,
            statusKey: isThinkingMode ? 'THINKING_PROGRESS' : null,
            statusMessage: isThinkingMode ? 'THINKING_PROGRESS' : ''
        };

        const currentAttachmentPaths = attachmentMeta
            .map((file) => file.file_path)
            .filter(Boolean);

        // Setup Multi-Session Stream State
        const controller = new AbortController();
        const activeStreams = { ...get().activeStreams };
        activeStreams[currentSessionUuid] = {
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            isThinking: isThinkingMode,
            abortController: controller,
            currentThinking: ''
        };

        // Sinkronisasi state chatMode sebelum perubahan rute URL
        set({
            activeStreams,
            chatMode: effectiveChatMode, // Menyinkronkan chatMode ke store
            isThinkingMode: isThinkingMode,
            isStreaming: true,
            isThinking: isThinkingMode,
            abortController: controller,
            messages: [...updatedMessages, assistantMessage],
            currentThinking: '',
            isLoading: false
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        // Simpan preferensi toggle ke DB secara asinkron
        endpoints.updateSessionSettings(currentSessionUuid, { chatMode: effectiveChatMode, isThinkingMode }).catch(() => {});

        await performStream(
            set,
            get,
            updatedMessages,
            assistantMessage,
            currentSessionUuid,
            npp,
            currentIsolatedDocId,
            currentAttachmentPaths,
            effectiveChatMode,
            isThinkingMode,
            toast,
            null, // targetAssistantIdx null untuk chat baru
            null, // editIndex null untuk chat baru
            options
        );

        set({ stagedAttachments: [] });

        // Untuk mode 'documents', isolasi dokumen spesifik HANYA berlaku untuk 1 turn awal ini.
        // Setelah stream selesai dikirim & diterima, bersihkan activeIsolatedDocId jika user memang sedang di tab documents.
        if (get().activeModeTag === 'documents') {
            get().setContextIsolation(null, null, 'documents');
        }
    },

    editAndRegenerate: async (index, newContent, toast = null, messageId = null) => {
        const sessionUuid = get().sessionUuid;
        if (!newContent.trim() || get().activeStreams?.[sessionUuid]?.isStreaming) return;

        // 1. Truncate pesan percakapan: hanya pertahankan sampai indeks yang diedit,
        // buang/reset seluruh turn anak di bawahnya karena parent di-regenerate
        const allMessages = get().messages;
        const editedMsg = allMessages[index];
        const prevAssistantMsg = allMessages[index + 1];
        const targetMessageId = messageId || editedMsg?.id || null;
        const targetAssistantMessageId = prevAssistantMsg?.id || null;

        const currentMessages = allMessages.slice(0, index + 1);
        currentMessages[index] = { ...currentMessages[index], content: newContent };

        const currentIsolatedDocId = get().activeIsolatedDocId;
        const currentChatMode = get().chatMode || 'auto';
        let effectiveChatMode = currentChatMode;

        let detectedMode = editedMsg?.chatMode || editedMsg?.mode || editedMsg?.metadata?.mode;
        if (!detectedMode && prevAssistantMsg) {
            detectedMode = prevAssistantMsg.chatMode || prevAssistantMsg.mode || prevAssistantMsg.metadata?.mode;
            if (!detectedMode && prevAssistantMsg.thought) {
                const match = prevAssistantMsg.thought.match(/Mode:\s*([a-zA-Z_]+)/i);
                if (match && match[1]) {
                    detectedMode = match[1].toLowerCase();
                }
            }
        }

        if (currentIsolatedDocId) {
            effectiveChatMode = currentChatMode === 'compliance' ? 'compliance' : 'focus';
        } else if (get().activeModeTag) {
            effectiveChatMode = get().activeModeTag;
        } else {
            effectiveChatMode = 'auto';
        }

        // Cek thinking mode asli dari pesan yang diedit atau respons setelahnya
        let effectiveThinkingMode = get().isThinkingMode;
        let detectedThinking = editedMsg?.isThinkingMode ?? editedMsg?.thinking ?? editedMsg?.isThinking;

        if (detectedThinking === undefined && prevAssistantMsg) {
            if (prevAssistantMsg.isThinkingMode !== undefined) {
                detectedThinking = Boolean(prevAssistantMsg.isThinkingMode);
            } else if (prevAssistantMsg.thinking !== undefined && typeof prevAssistantMsg.thinking === 'boolean') {
                detectedThinking = prevAssistantMsg.thinking;
            } else if (prevAssistantMsg.thought) {
                const thoughtStr = String(prevAssistantMsg.thought);
                const hasThinkingFlag = /Thinking:\s*true/i.test(thoughtStr);
                const hasThinkingTag = thoughtStr.includes('<think>') || thoughtStr.includes('<|channel>thought');
                const hasRealThought = thoughtStr.length > 50 && !thoughtStr.startsWith('Gemma Agentic | Mode:') && !thoughtStr.startsWith('Gemma Agentic [Mode:');
                detectedThinking = hasThinkingFlag || hasThinkingTag || hasRealThought;
            }
        }

        if (detectedThinking !== undefined) {
            effectiveThinkingMode = Boolean(detectedThinking);
        }

        // 2. Tambahkan asisten message baru tepat di posisi index + 1
        const assistantMessage = {
            role: 'assistant',
            content: '',
            isThinking: effectiveThinkingMode,
            isStreaming: true,
            thinking: '',
            fileGenerations: [],
            allFilesDone: false,
            statusKey: effectiveThinkingMode ? 'THINKING_PROGRESS' : null,
            statusMessage: effectiveThinkingMode ? 'THINKING_PROGRESS' : '',
            chatMode: effectiveChatMode,
            mode: effectiveChatMode,
            isThinkingMode: effectiveThinkingMode
        };
        currentMessages.push(assistantMessage);

        const controller = new AbortController();
        const activeStreams = { ...get().activeStreams };
        activeStreams[sessionUuid] = {
            messages: currentMessages,
            isStreaming: true,
            isThinking: effectiveThinkingMode,
            abortController: controller,
            currentThinking: effectiveThinkingMode ? 'Sedang berpikir...' : ''
        };

        const newWizardAnswers = { ...(get().wizardAnswers || {}) };
        Object.keys(newWizardAnswers).forEach(k => {
            if (parseInt(k, 10) >= index) {
                delete newWizardAnswers[k];
            }
        });

        // Simpan downstream messages pada assistant message sebelumnya jika ada varian
        if (prevAssistantMsg && Array.isArray(prevAssistantMsg.variants)) {
            const prevActiveVIdx = prevAssistantMsg.activeVariantIndex !== undefined ? prevAssistantMsg.activeVariantIndex : (prevAssistantMsg.variants.length - 1);
            if (prevAssistantMsg.variants[prevActiveVIdx]) {
                prevAssistantMsg.variants[prevActiveVIdx].downstreamMessages = allMessages.slice(index + 2);
                prevAssistantMsg.variants[prevActiveVIdx].userPrompt = allMessages[index]?.content || null;
            }
        }

        set({
            activeStreams,
            messages: currentMessages,
            isStreaming: true,
            isThinking: effectiveThinkingMode,
            isEditRegenerating: true,
            activeWizard: null,
            wizardAnswers: newWizardAnswers,
            abortController: controller,
            currentThinking: effectiveThinkingMode ? 'Sedang berpikir...' : ''
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        // 3. Kirimkan pesan HANYA sampai indeks yang diedit
        const messagesToSend = currentMessages.slice(0, index + 1);
        const npp = JSON.parse(localStorage.getItem('cakra_user') || '{}')?.npp || null;

        const currentAttachmentPaths = (currentMessages[index].attachments || [])
            .map((file) => file.file_path)
            .filter(Boolean);

        const msgStreamOptions = editedMsg?.streamOptions || {};
        const savedIsolatedDocId = msgStreamOptions.isolated_doc_id || 
                                   msgStreamOptions.isolatedDocId || 
                                   editedMsg?.isolatedDocId || 
                                   get().activeIsolatedDocId || 
                                   null;

        const regenerationOptions = {
            ...msgStreamOptions,
            isolated_doc_id: savedIsolatedDocId,
            isolatedDocId: savedIsolatedDocId,
            forced_mode: msgStreamOptions.forced_mode || msgStreamOptions.forcedMode || (savedIsolatedDocId ? 'documents' : effectiveChatMode),
            forcedMode: msgStreamOptions.forced_mode || msgStreamOptions.forcedMode || (savedIsolatedDocId ? 'documents' : effectiveChatMode),
            bypass_router: msgStreamOptions.bypass_router !== undefined ? msgStreamOptions.bypass_router : Boolean(savedIsolatedDocId),
            bypassRouter: msgStreamOptions.bypassRouter !== undefined ? msgStreamOptions.bypassRouter : Boolean(savedIsolatedDocId),
            editMessageId: targetMessageId,
            assistantMessageId: targetAssistantMessageId,
        };

        await performStream(
            set,
            get,
            messagesToSend,
            assistantMessage,
            sessionUuid,
            npp,
            savedIsolatedDocId,
            currentAttachmentPaths,
            effectiveChatMode,
            effectiveThinkingMode,
            toast,
            index + 1, // targetAssistantIdx
            index,     // 🔥 editIndex
            regenerationOptions
        );
    },

    /**
     * Regenerate Assistant Response as a new variant (< 1 / 3 >) without overwriting previous versions.
     * @param {number} assistantIdx - Index of the assistant message in messages array
     */
    regenerateAssistant: async (assistantIdx, toast = null) => {
        const sessionUuid = get().sessionUuid;
        if (get().activeStreams?.[sessionUuid]?.isStreaming) return;

        const allMessages = get().messages;
        const targetAssistantMsg = allMessages[assistantIdx];
        if (!targetAssistantMsg || targetAssistantMsg.role !== 'assistant') return;

        // Cari user message sebelumnya
        let userIdx = assistantIdx - 1;
        while (userIdx >= 0 && allMessages[userIdx]?.role !== 'user') {
            userIdx--;
        }
        if (userIdx < 0) return;
        const userMsg = allMessages[userIdx];

        // Truncate pesan percakapan: buang seluruh turn anak di bawah assistantIdx
        const currentMessages = allMessages.slice(0, assistantIdx + 1);

        // Dapatkan mode dan thinking asli
        const currentIsolatedDocId = get().activeIsolatedDocId;
        const currentChatMode = get().chatMode || 'auto';
        let effectiveChatMode = currentChatMode;

        let detectedMode = targetAssistantMsg.chatMode || targetAssistantMsg.mode || targetAssistantMsg.metadata?.mode;
        if (!detectedMode && userMsg) {
            detectedMode = userMsg.chatMode || userMsg.mode || userMsg.metadata?.mode;
        }

        if (currentIsolatedDocId) {
            effectiveChatMode = currentChatMode === 'compliance' ? 'compliance' : 'focus';
        } else if (get().activeModeTag) {
            effectiveChatMode = get().activeModeTag;
        } else {
            effectiveChatMode = detectedMode || 'auto';
        }

        let effectiveThinkingMode = get().isThinkingMode;
        if (targetAssistantMsg.isThinkingMode !== undefined) {
            effectiveThinkingMode = Boolean(targetAssistantMsg.isThinkingMode);
        } else if (targetAssistantMsg.thinking !== undefined && typeof targetAssistantMsg.thinking === 'boolean') {
            effectiveThinkingMode = targetAssistantMsg.thinking;
        } else if (targetAssistantMsg.thought) {
            const thoughtStr = String(targetAssistantMsg.thought);
            const hasThinkingFlag = /Thinking:\s*true/i.test(thoughtStr);
            const hasThinkingTag = thoughtStr.includes('<think>') || thoughtStr.includes('<|channel>thought');
            const hasRealThought = thoughtStr.length > 50 && !thoughtStr.startsWith('Gemma Agentic | Mode:') && !thoughtStr.startsWith('Gemma Agentic [Mode:');
            effectiveThinkingMode = hasThinkingFlag || hasThinkingTag || hasRealThought;
        }

        // Siapkan struktur variants
        let existingVariants = [];
        if (Array.isArray(targetAssistantMsg.variants) && targetAssistantMsg.variants.length > 0) {
            existingVariants = targetAssistantMsg.variants.map((v, i) => {
                const parsedV = parseMessageFileTags({ ...v, role: 'assistant', metadata: targetAssistantMsg.metadata });
                return {
                    ...parsedV,
                    variant_index: parsedV.variant_index || (i + 1)
                };
            });
        } else {
            const parsedTarget = parseMessageFileTags(targetAssistantMsg);
            existingVariants = [{
                id: parsedTarget.id,
                content: parsedTarget.content,
                thought: parsedTarget.thought,
                sources: parsedTarget.sources,
                metadata: parsedTarget.metadata,
                fileGenerations: parsedTarget.fileGenerations || [],
                allFilesDone: parsedTarget.allFilesDone || false,
                feedback: parsedTarget.feedback,
                timestamp: parsedTarget.timestamp || parsedTarget.created_at,
                created_at: parsedTarget.created_at || parsedTarget.timestamp,
                variant_index: 1
            }];
        }

        // Pastikan varian aktif saat ini tersimpan sempurna dengan content & downstreamMessages yang rapi
        const currentActiveVIdx = targetAssistantMsg.activeVariantIndex !== undefined ? targetAssistantMsg.activeVariantIndex : (existingVariants.length - 1);
        if (existingVariants[currentActiveVIdx]) {
            existingVariants[currentActiveVIdx] = {
                ...existingVariants[currentActiveVIdx],
                content: targetAssistantMsg.content,
                thought: targetAssistantMsg.thought || targetAssistantMsg.thinking || '',
                fileGenerations: targetAssistantMsg.fileGenerations || [],
                allFilesDone: targetAssistantMsg.allFilesDone || false,
                sources: targetAssistantMsg.sources,
                metadata: targetAssistantMsg.metadata,
                userPrompt: userMsg?.content || null,
                downstreamMessages: allMessages.slice(assistantIdx + 1)
            };
        }

        const newVariantIndex = existingVariants.length + 1;
        const nowIso = new Date().toISOString();
        const newVariant = {
            id: null,
            content: '',
            thought: '',
            sources: null,
            metadata: null,
            feedback: null,
            fileGenerations: [],
            allFilesDone: false,
            isThinking: effectiveThinkingMode,
            isStreaming: true,
            variant_index: newVariantIndex,
            timestamp: nowIso,
            created_at: nowIso,
            userPrompt: userMsg?.content || null,
            downstreamMessages: [] // Branch baru dimulai tanpa turn anak lama
        };

        const updatedVariants = [...existingVariants, newVariant];
        const newActiveVariantIndex = updatedVariants.length - 1;

        const updatedAssistantMessage = {
            ...targetAssistantMsg,
            content: '',
            thought: '',
            sources: null,
            metadata: null,
            feedback: null,
            fileGenerations: [],
            allFilesDone: false,
            created_at: nowIso,
            timestamp: nowIso,
            isThinking: effectiveThinkingMode,
            isStreaming: true,
            statusKey: effectiveThinkingMode ? 'THINKING_PROGRESS' : null,
            statusMessage: effectiveThinkingMode ? 'THINKING_PROGRESS' : '',
            chatMode: effectiveChatMode,
            mode: effectiveChatMode,
            isThinkingMode: effectiveThinkingMode,
            variants: updatedVariants,
            activeVariantIndex: newActiveVariantIndex,
            parent_id: userMsg.id || targetAssistantMsg.parent_id || null,
            regenerated_from_id: targetAssistantMsg.id || (existingVariants[targetAssistantMsg.activeVariantIndex || 0]?.id) || null
        };

        currentMessages[assistantIdx] = updatedAssistantMessage;

        const controller = new AbortController();
        const activeStreams = { ...get().activeStreams };
        activeStreams[sessionUuid] = {
            messages: currentMessages,
            isStreaming: true,
            isThinking: effectiveThinkingMode,
            abortController: controller,
            currentThinking: effectiveThinkingMode ? 'Sedang berpikir...' : ''
        };

        const newWizardAnswers = { ...(get().wizardAnswers || {}) };
        Object.keys(newWizardAnswers).forEach(k => {
            if (parseInt(k, 10) >= userIdx) {
                delete newWizardAnswers[k];
            }
        });



        set({
            activeStreams,
            messages: currentMessages,
            isStreaming: true,
            isThinking: effectiveThinkingMode,
            isEditRegenerating: true,
            activeWizard: null,
            wizardAnswers: newWizardAnswers,
            abortController: controller,
            currentThinking: effectiveThinkingMode ? 'Sedang berpikir...' : ''
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        // Kirim riwayat percakapan HANYA sampai user prompt yang bersangkutan
        const messagesToSend = currentMessages.slice(0, userIdx + 1);
        const npp = JSON.parse(localStorage.getItem('cakra_user') || '{}')?.npp || null;

        const currentAttachmentPaths = (userMsg.attachments || [])
            .map((file) => file.file_path)
            .filter(Boolean);

        const msgStreamOptions = targetAssistantMsg?.streamOptions || userMsg?.streamOptions || {};
        const savedIsolatedDocId = msgStreamOptions.isolated_doc_id || 
                                   msgStreamOptions.isolatedDocId || 
                                   userMsg?.isolatedDocId || 
                                   get().activeIsolatedDocId || 
                                   null;

        const regenerationOptions = {
            ...msgStreamOptions,
            isolated_doc_id: savedIsolatedDocId,
            isolatedDocId: savedIsolatedDocId,
            forced_mode: msgStreamOptions.forced_mode || msgStreamOptions.forcedMode || (savedIsolatedDocId ? 'documents' : effectiveChatMode),
            forcedMode: msgStreamOptions.forced_mode || msgStreamOptions.forcedMode || (savedIsolatedDocId ? 'documents' : effectiveChatMode),
            bypass_router: msgStreamOptions.bypass_router !== undefined ? msgStreamOptions.bypass_router : Boolean(savedIsolatedDocId),
            bypassRouter: msgStreamOptions.bypassRouter !== undefined ? msgStreamOptions.bypassRouter : Boolean(savedIsolatedDocId),
            is_regenerate: true,
            isRegenerate: true,
            target_index: assistantIdx,
            targetIndex: assistantIdx,
            parent_index: userIdx,
            parentIndex: userIdx,
            regenerated_from_id: updatedAssistantMessage.regenerated_from_id,
            parent_id: updatedAssistantMessage.parent_id,
            regeneratedFromId: updatedAssistantMessage.regenerated_from_id,
            parentId: updatedAssistantMessage.parent_id
        };

        await performStream(
            set,
            get,
            messagesToSend,
            updatedAssistantMessage,
            sessionUuid,
            npp,
            savedIsolatedDocId,
            currentAttachmentPaths,
            effectiveChatMode,
            effectiveThinkingMode,
            toast,
            assistantIdx, // targetAssistantIdx
            null,         // editIndex null agar tidak menimpa via update_chat_message!
            regenerationOptions
        );
    },

    /**
     * Seamless Token Continuation: Lanjutkan stream pesan asisten yang terpotong tanpa membuat bubble chat baru.
     * @param {number} assistantIdx - Indeks pesan asisten dalam array messages
     */
    continueAssistantResponse: async (assistantIdx) => {
        const sessionUuid = get().sessionUuid;
        const currentActiveStreams = get().activeStreams || {};
        if (currentActiveStreams[sessionUuid]?.isStreaming) return;

        const currentMessages = [...get().messages];
        const targetAssistantMsg = currentMessages[assistantIdx];
        if (!targetAssistantMsg || targetAssistantMsg.role !== 'assistant') return;

        // Cari user message sebelumnya
        let userIdx = assistantIdx - 1;
        while (userIdx >= 0 && currentMessages[userIdx]?.role !== 'user') {
            userIdx--;
        }
        if (userIdx < 0) return;
        const userMsg = currentMessages[userIdx];

        // Matikan flag is_truncated pada pesan asisten agar tombol hilang dan status streaming kembali aktif
        targetAssistantMsg.is_truncated = false;
        if (targetAssistantMsg.metadata) {
            targetAssistantMsg.metadata = {
                ...targetAssistantMsg.metadata,
                is_truncated: false
            };
        }
        targetAssistantMsg.isStreaming = true;

        const controller = new AbortController();
        const activeStreams = { ...currentActiveStreams };
        activeStreams[sessionUuid] = {
            messages: currentMessages,
            isStreaming: true,
            isThinking: false,
            abortController: controller,
            currentThinking: ''
        };

        set({
            activeStreams,
            messages: currentMessages,
            isStreaming: true,
            isThinking: false,
            abortController: controller,
            currentThinking: ''
        });

        const npp = JSON.parse(localStorage.getItem('cakra_user') || '{}')?.npp || null;
        const effectiveChatMode = targetAssistantMsg.chatMode || targetAssistantMsg.mode || userMsg.chatMode || 'auto';
        const msgStreamOptions = targetAssistantMsg?.streamOptions || userMsg?.streamOptions || {};
        const savedIsolatedDocId = msgStreamOptions.isolated_doc_id || 
                                   msgStreamOptions.isolatedDocId || 
                                   targetAssistantMsg?.isolatedDocId || 
                                   userMsg?.isolatedDocId || 
                                   get().activeIsolatedDocId || 
                                   null;

        const continuationOptions = {
            ...msgStreamOptions,
            is_continuation: true,
            isContinuation: true,
            assistant_message_id: targetAssistantMsg.id,
            assistantMessageId: targetAssistantMsg.id,
            partial_content: targetAssistantMsg.content || '',
            target_index: assistantIdx,
            isolated_doc_id: savedIsolatedDocId,
            isolatedDocId: savedIsolatedDocId,
            forced_mode: effectiveChatMode,
            forcedMode: effectiveChatMode,
            bypass_router: true,
            bypassRouter: true,
        };

        // Kirim riwayat percakapan sampai assistant message saat ini
        const messagesToSend = currentMessages.slice(0, assistantIdx + 1);

        await performStream(
            set,
            get,
            messagesToSend,
            targetAssistantMsg,
            sessionUuid,
            npp,
            savedIsolatedDocId,
            [],
            effectiveChatMode,
            false,
            null,
            assistantIdx, // targetAssistantIdx
            null,
            continuationOptions
        );
    },

    /**
     * Switch actively displayed variant of a message (< 1 / 3 >) in-memory without reloading
     * @param {number} messageIdx - Index of message in messages array
     * @param {number} targetVariantIdx - Index in msg.variants (0-based)
     */
    switchMessageVariant: (messageIdx, targetVariantIdx) => {
        const messages = [...get().messages];
        const targetMsg = messages[messageIdx];
        if (!targetMsg || !targetMsg.variants || !targetMsg.variants[targetVariantIdx]) return;

        // Cari user message sebelumnya untuk sinkronisasi userPrompt
        let userIdx = messageIdx - 1;
        while (userIdx >= 0 && messages[userIdx]?.role !== 'user') {
            userIdx--;
        }

        // 1. Simpan downstream messages saat ini ke varian yang sedang aktif
        const currentActiveVIdx = targetMsg.activeVariantIndex !== undefined ? targetMsg.activeVariantIndex : (targetMsg.variants.length - 1);
        if (targetMsg.variants[currentActiveVIdx]) {
            targetMsg.variants[currentActiveVIdx] = {
                ...targetMsg.variants[currentActiveVIdx],
                content: targetMsg.content,
                thought: targetMsg.thought || targetMsg.thinking || '',
                fileGenerations: targetMsg.fileGenerations || [],
                allFilesDone: targetMsg.allFilesDone || false,
                sources: targetMsg.sources,
                metadata: targetMsg.metadata,
                userPrompt: (userIdx >= 0 && messages[userIdx]) ? messages[userIdx].content : null,
                downstreamMessages: messages.slice(messageIdx + 1)
            };
        }

        // 2. Siapkan varian target yang dipilih
        let selectedVariant = targetMsg.variants[targetVariantIdx];
        selectedVariant = parseMessageFileTags({
            ...selectedVariant,
            role: 'assistant',
            metadata: targetMsg.metadata
        });
        targetMsg.variants[targetVariantIdx] = selectedVariant;

        const selectedThought = selectedVariant.thought || selectedVariant.thinking || '';
        const selectedTime = selectedVariant.created_at || selectedVariant.timestamp || targetMsg.created_at || targetMsg.timestamp;
        
        const updatedTargetMsg = {
            ...targetMsg,
            ...selectedVariant,
            content: selectedVariant.content,
            fileGenerations: selectedVariant.fileGenerations || [],
            allFilesDone: selectedVariant.allFilesDone || false,
            created_at: selectedTime,
            timestamp: selectedTime,
            thought: selectedThought,
            thinking: selectedThought,
            activeVariantIndex: targetVariantIdx
        };

        // Update user message jika varian target menyimpan userPrompt spesifik
        if (userIdx >= 0 && messages[userIdx] && selectedVariant.userPrompt) {
            messages[userIdx] = {
                ...messages[userIdx],
                content: selectedVariant.userPrompt
            };
        }

        // 3. Ambil downstream messages milik varian target (jika ada)
        const targetDownstream = Array.isArray(selectedVariant.downstreamMessages) ? selectedVariant.downstreamMessages : [];

        // 4. Rekonstruksi array messages: pesan sebelum target + updatedTargetMsg + downstream messages varian target
        const newMessages = [
            ...messages.slice(0, messageIdx),
            updatedTargetMsg,
            ...targetDownstream
        ];

        set({ messages: newMessages });

        const sessionUuid = get().sessionUuid;
        if (sessionUuid && get().activeStreams?.[sessionUuid]) {
            const activeStreams = { ...get().activeStreams };
            activeStreams[sessionUuid] = {
                ...activeStreams[sessionUuid],
                messages: newMessages
            };
            set({ activeStreams });
        }
    }
});
