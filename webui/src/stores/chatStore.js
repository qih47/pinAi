import { create } from "zustand";

const API_BASE = "http://192.168.11.80:5000";
let _sessionLoadSeq = 0;

function _buildAuthHeaders(npp) {
    const headers = { 'Content-Type': 'application/json' };
    const cleanNpp = (npp || '').trim();
    const isPlaceholder = !cleanNpp || cleanNpp.startsWith('NPP');
    if (!isPlaceholder) {
        headers['X-NPP-Header'] = cleanNpp;
    }
    return headers;
}

async function _performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null) {
    try {
        const activeSessionUuid = forcedSessionUuid || get().sessionUuid;

        const response = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: _buildAuthHeaders(npp),
            body: JSON.stringify({
                session_uuid: activeSessionUuid, 
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
    isThinking: false, 
    sessionUuid: null,

    sendMessage: async (content, npp, onSessionCreatedCallback) => {
        if (!content.trim() || get().isStreaming) return;

        let currentSessionUuid = get().sessionUuid;

        // 🧠 TRANSMISI OTOMATIS SESI BARU (Lurus dari lahir)
        if (!currentSessionUuid || currentSessionUuid === "new") {
            try {
                // Peras 4 kata pertama chat user buat dijadikan judul valid
                const generatedTitle = content.split(" ").slice(0, 4).join(" ") + "...";

                // 🔥 SUNTIK PARAMETER ?judul=... ke endpoint create session resmi bawaan FastAPI lu bolo!
                const response = await fetch(`${API_BASE}/api/chat/sessions/create?judul=${encodeURIComponent(generatedTitle)}`, {
                    method: 'POST',
                    headers: _buildAuthHeaders(npp),
                });
                const result = await response.json();
                
                if (result.status === "success") {
                    currentSessionUuid = result.data.session_uuid;
                    
                    // 1. Injeksi instan baris baru ke state array sidebar agar tampilan langsung berubah tanpa nunggu stream beres
                    if (onSessionCreatedCallback) {
                        onSessionCreatedCallback({
                            session_uuid: currentSessionUuid,
                            judul: generatedTitle,
                            is_pinned: false,
                            started_at: new Date().toISOString()
                        });
                    }

                    // 2. Kunci UUID baru ke state store global (useEffect di ChatPage akan pindahin URL secara pasif)
                    set({ sessionUuid: currentSessionUuid });
                } else {
                    throw new Error("Gagal booking session id dari backend.");
                }
            } catch (err) {
                console.error("❌ [STREAM AUTH SESSION ERROR]:", err);
                return;
            }
        }

        // Jalur normal pengaliran pesan regular
        const userMessage = { role: 'user', content };
        const updatedMessages = [...get().messages, userMessage];
        const assistantMessage = { role: 'assistant', content: '' };

        set({
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            isLoading: true,
            isThinking: true
        });

        await new Promise(resolve => setTimeout(resolve, 100));
        await _performStream(set, get, updatedMessages, assistantMessage, currentSessionUuid, npp);
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
        await _performStream(set, get, messagesToSend, assistantMessage, null, npp);
    },

    clearChat: () => {
        set({ messages: [], sessionUuid: null, isThinking: false });
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
        set({ sessionUuid, messages: [], isLoading: true });

        try {
            const npp = JSON.parse(localStorage.getItem('cakra_user'))?.npp || '';
            const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionUuid}/messages`, {
                headers: { 'X-NPP-Header': npp }
            });
            const result = await response.json();

            if (seq !== _sessionLoadSeq) return;

            if (result.status === "success") {
                set({
                    messages: result.data || [],
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
                set({ sessionUuid: result.data.session_uuid, messages: [] });
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

}));