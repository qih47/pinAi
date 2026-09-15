import * as endpoints from "../../services/endpoints";
import { performStream, normalizeAttachments } from "../helpers/streamHelper";

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
            effectiveChatMode = currentChatMode === 'compliance' ? 'compliance' : 'focus';
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

    editAndRegenerate: async (index, newContent, toast = null) => {
        const sessionUuid = get().sessionUuid;
        if (!newContent.trim() || get().activeStreams?.[sessionUuid]?.isStreaming) return;

        // 1. Pertahankan SELURUH pesan percakapan (JANGAN hapus/potong chat di bawahnya!)
        const currentMessages = [...get().messages];
        currentMessages[index] = { ...currentMessages[index], content: newContent };

        // Cek mode asli dan thinking asli dari pesan yang diedit atau respons setelahnya
        const editedMsg = currentMessages[index];
        const prevAssistantMsg = currentMessages[index + 1];

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

        // 2. Siapkan/update asisten message tepat di posisi index + 1
        const assistantMessage = {
            role: 'assistant',
            content: '',
            isThinking: effectiveThinkingMode,
            isStreaming: true,
            thinking: '',
            statusKey: effectiveThinkingMode ? 'THINKING_PROGRESS' : null,
            statusMessage: effectiveThinkingMode ? 'THINKING_PROGRESS' : '',
            chatMode: effectiveChatMode,
            mode: effectiveChatMode,
            isThinkingMode: effectiveThinkingMode
        };
        if (currentMessages[index + 1] && currentMessages[index + 1].role === 'assistant') {
            currentMessages[index + 1] = assistantMessage;
        } else {
            currentMessages.splice(index + 1, 0, assistantMessage);
        }

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
            existingVariants = targetAssistantMsg.variants.map((v, i) => ({
                ...v,
                variant_index: v.variant_index || (i + 1)
            }));
        } else {
            existingVariants = [{
                id: targetAssistantMsg.id,
                content: targetAssistantMsg.content,
                thought: targetAssistantMsg.thought,
                sources: targetAssistantMsg.sources,
                metadata: targetAssistantMsg.metadata,
                feedback: targetAssistantMsg.feedback,
                timestamp: targetAssistantMsg.timestamp || targetAssistantMsg.created_at,
                created_at: targetAssistantMsg.created_at || targetAssistantMsg.timestamp,
                variant_index: 1
            }];
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
            isThinking: effectiveThinkingMode,
            isStreaming: true,
            variant_index: newVariantIndex,
            timestamp: nowIso,
            created_at: nowIso
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

        set({
            activeStreams,
            messages: currentMessages,
            isStreaming: true,
            isThinking: effectiveThinkingMode,
            isEditRegenerating: true,
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
     * Switch actively displayed variant of a message (< 1 / 3 >) in-memory without reloading
     * @param {number} messageIdx - Index of message in messages array
     * @param {number} targetVariantIdx - Index in msg.variants (0-based)
     */
    switchMessageVariant: (messageIdx, targetVariantIdx) => {
        const messages = [...get().messages];
        const targetMsg = messages[messageIdx];
        if (!targetMsg || !targetMsg.variants || !targetMsg.variants[targetVariantIdx]) return;

        const selectedVariant = targetMsg.variants[targetVariantIdx];
        const selectedThought = selectedVariant.thought || selectedVariant.thinking || '';
        const selectedTime = selectedVariant.created_at || selectedVariant.timestamp || targetMsg.created_at || targetMsg.timestamp;
        messages[messageIdx] = {
            ...targetMsg,
            ...selectedVariant,
            created_at: selectedTime,
            timestamp: selectedTime,
            thought: selectedThought,
            thinking: selectedThought,
            activeVariantIndex: targetVariantIdx
        };

        set({ messages });

        const sessionUuid = get().sessionUuid;
        if (sessionUuid && get().activeStreams?.[sessionUuid]) {
            const activeStreams = { ...get().activeStreams };
            activeStreams[sessionUuid] = {
                ...activeStreams[sessionUuid],
                messages
            };
            set({ activeStreams });
        }
    }
});
