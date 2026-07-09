import * as endpoints from "../../services/endpoints";
import { performStream, normalizeAttachments } from "../helpers/streamHelper";

export const createStreamSlice = (set, get) => ({
    stopStream: (sessionUuid = null) => {
        const targetSession = sessionUuid || get().sessionUuid;
        const activeStreams = { ...get().activeStreams };
        
        if (activeStreams[targetSession] && activeStreams[targetSession].abortController) {
            activeStreams[targetSession].abortController.abort();
            delete activeStreams[targetSession];
            set({ activeStreams });
        }
        
        if (targetSession === get().sessionUuid) {
            const controller = get().abortController;
            if (controller) controller.abort();
            set({ isStreaming: false, isThinking: false, abortController: null });
        }
    },

    sendMessage: async (content, npp, onSessionCreatedCallback, directUploadedFiles = null, chatMode = 'auto', isThinkingMode = true, toast = null) => {
        const hasAttachments = (directUploadedFiles?.length > 0) || (get().stagedAttachments?.length > 0);
        if (!content.trim() && !hasAttachments) return;

        const currentActiveStreams = get().activeStreams || {};
        if (Object.keys(currentActiveStreams).length >= 2) {
            if (toast) toast.error("Maksimal 2 obrolan bersamaan sedang berjalan. Harap tunggu.");
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
        const currentChatMode = get().chatMode;
        
        let effectiveChatMode = chatMode;
        if (currentIsolatedDocId) {
            effectiveChatMode = currentChatMode === 'compliance' ? 'compliance' : 'focus';
        }

        // Setup Multi-Session Stream State
        const controller = new AbortController();
        const activeStreams = { ...get().activeStreams };
        activeStreams[currentSessionUuid] = {
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            isThinking: true,
            abortController: controller,
            currentThinking: ''
        };

        // Sinkronisasi state chatMode sebelum perubahan rute URL
        set({
            activeStreams,
            chatMode: effectiveChatMode, // Menyinkronkan chatMode ke store
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            // isLoading: true,
            isThinking: true,
            abortController: controller
        });

        await new Promise(resolve => setTimeout(resolve, 100));

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
            toast
        );

        set({ stagedAttachments: [] });
    },

    editAndRegenerate: async (index, newContent, toast = null) => {
        const activeSessionUuid_temp = get().sessionUuid;
        if (!newContent.trim() || get().activeStreams?.[activeSessionUuid_temp]?.isStreaming) return;

        const currentMessages = [...get().messages];
        const sessionUuid = get().sessionUuid;

        // 1. In-Place Update: Ubah isi pesan user pada index tersebut
        currentMessages[index] = { ...currentMessages[index], content: newContent };

        // 2. In-Place Update: Siapkan asisten message baru di index + 1 (menimpa respons lama)
        const assistantMessage = {
            role: 'assistant',
            content: '',
            isThinking: get().isThinkingMode,
            isStreaming: true,
            thinking: '',
            statusMessage: get().isThinkingMode ? 'Sedang berpikir...' : '' // Gunakan statusMessage alih-alih thinking untuk loading state
        };

        // Jika kebetulan sebelahnya bukan assistant, kita push/splice (tapi idealnya selalu assistant)
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
            isThinking: true,
            abortController: controller,
            currentThinking: get().isThinkingMode ? 'Sedang berpikir...' : ''
        };

        set({
            activeStreams,
            messages: currentMessages,
            isStreaming: true,
            isThinking: true,
            abortController: controller,
            currentThinking: get().isThinkingMode ? 'Sedang berpikir...' : ''
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        // 3. Kirimkan pesan HANYA sampai indeks yang diedit
        const messagesToSend = currentMessages.slice(0, index + 1);
        const npp = JSON.parse(localStorage.getItem('cakra_user') || '{}')?.npp || null;

        const currentAttachmentPaths = (currentMessages[index].attachments || [])
            .map((file) => file.file_path)
            .filter(Boolean);

        // 4. Panggil stream dengan target parameter (index + 1) dan editIndex = index
        const currentIsolatedDocId = get().activeIsolatedDocId;
        const currentChatMode = get().chatMode || 'auto';
        let effectiveChatMode = currentChatMode;
        if (currentIsolatedDocId) {
            effectiveChatMode = currentChatMode === 'compliance' ? 'compliance' : 'focus';
        }
        
        await performStream(
            set,
            get,
            messagesToSend,
            assistantMessage,
            sessionUuid,
            npp,
            currentIsolatedDocId,
            currentAttachmentPaths,
            effectiveChatMode,
            get().isThinkingMode,
            toast,
            index + 1, // targetAssistantIdx
            index      // 🔥 editIndex
        );
    }
});
