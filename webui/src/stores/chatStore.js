import { create } from "zustand";

const API_BASE = "http://192.168.11.80:5000";

async function _performStream(set, get, messagesToSend, assistantMessage) {
    try {
        const response = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-NPP-Header': ''
            },
            body: JSON.stringify({
                session_uuid: get().sessionUuid,
                messages: messagesToSend,
                mode: 'normal',
                temperature: 0.7
            })
        });

        if (!response.ok) throw new Error('Gagal konek ke backend, bolo!');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedReply = '';
        let streamBuffer = '';
        let renderTimeout = null;

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

                    if (parsedData.chunk) {
                        accumulatedReply += parsedData.chunk;
                        assistantMessage.content = accumulatedReply;

                        if (!renderTimeout) {
                            renderTimeout = requestAnimationFrame(() => {
                                // 🔥 FIX 1: Begitu chunk pertama masuk, matikan isThinking biar bubble pindah ke mode ngetik text stream
                                set({
                                    messages: [...get().messages],
                                    isThinking: false
                                });
                                renderTimeout = null;
                            });
                        }
                    }
                } catch (jsonErr) {
                    // Buffering
                }
            }
        }

    } catch (error) {
        console.error('💥 [FE STREAM ERROR]:', error);
        assistantMessage.content = '⚠️ Gagal memuat balasan. Pastikan backend FastAPI lo idup, bolo!';
        set({ messages: [...get().messages], isThinking: false });
    } finally {
        set({ isStreaming: false, isLoading: false, isThinking: false });
    }
}

export const useChatStore = create((set, get) => ({
    messages: [],
    isLoading: false,
    isStreaming: false,
    isThinking: false, // 👈 Sedia kolom state isThinking di store global
    sessionUuid: null,

    sendMessage: async (content) => {
        if (!content.trim() || get().isStreaming) return;

        const userMessage = { role: 'user', content };
        const updatedMessages = [...get().messages, userMessage];
        const assistantMessage = { role: 'assistant', content: '' };

        set({
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            isLoading: true,
            isThinking: true // 🔥 Set true pas kirim biasa
        });

        await new Promise(resolve => setTimeout(resolve, 100));
        await _performStream(set, get, updatedMessages, assistantMessage);
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

        // 🔥 FIX 2: Lu wajib oper `isThinking: true` di sini asu!
        // Biar pas edit disubmit, view lu langsung tau kalau AI masuk fase mikir ulang.
        set({
            messages: currentMessages,
            isStreaming: true,
            isLoading: true,
            isThinking: true
        });

        await new Promise(resolve => setTimeout(resolve, 100));

        const messagesToSend = currentMessages.slice(0, index + 1);
        await _performStream(set, get, messagesToSend, assistantMessage);
    },

    clearChat: () => set({ messages: [], sessionUuid: null, isThinking: false }),

    // =========================================================================
    // ⚙️ SEKTOR ADAPTASI SIDEBAR: SINKRONISASI MURNI SESUAI ENDPOINT FASTAPI LU
    // =========================================================================
    fetchChatHistory: async (npp) => {
        try {
            // 🔥 MURNI FETCH NATIVE: Tanpa apiClient, aman dari ReferenceError!
            const response = await fetch(`${API_BASE}/api/chat/sessions`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    // Kirim NPP lo biar divalidasi dan ngebuka riwayat dari RAGDB
                    'X-NPP-Header': npp || ''
                }
            });

            if (!response.ok) throw new Error("Gagal mengambil data riwayat");
            return await response.json();
        } catch (err) {
            console.error("❌ [STORE HISTORY ERROR]:", err);
            return { status: "error", data: [] };
        }
    },

    pinChat: async (sessionUuid, isPinnedCurrentValue) => {
        try {
            // 🔥 SINKRON BE: Menggunakan method PUT ke /sessions/{uuid}/pin?is_pinned=...
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
            // 🔥 SINKRON BE: Menggunakan method PUT ke /sessions/{uuid}/title dengan body JSON
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

    deleteChat: async (sessionUuid) => {
        try {
            // 🔥 Coba buang '/chat' di sini, kemungkinan besar prefix-nya udah d handle main router lo
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}`, {
                method: 'DELETE',
                headers: {
                    // Tambahin header NPP juga buat jaga-jaga kalau dia butuh validasi
                    'X-NPP-Header': JSON.parse(localStorage.getItem('cakra_user'))?.npp || ''
                }
            });
            return await response.json();
        } catch (err) {
            console.error("❌ [STORE DELETE ERROR]:", err);
            return { status: "error" };
        }
    },
    // Tambahin ini di dalam useChatStore (src/stores/chatStore.js)
    loadChatSession: async (sessionUuid) => {
        set({ isLoading: true });
        try {
            // Nembak ke endpoint untuk ambil isi chat detail
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}/messages`, {
                headers: { 'X-NPP-Header': JSON.parse(localStorage.getItem('cakra_user'))?.npp || '' }
            });
            const result = await response.json();

            if (result.status === "success") {
                set({ messages: result.data, sessionUuid: sessionUuid, isLoading: false });
            }
        } catch (err) {
            console.error("Gagal load session chat:", err);
            set({ isLoading: false });
        }
    }

}));