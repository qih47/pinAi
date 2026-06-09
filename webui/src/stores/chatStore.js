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

// 🔥 PERLUASAN PARAMETER: Menambahkan parameter isolatedDocId dan attachmentPaths tanpa merusak fungsi oroknya
async function _performStream(set, get, messagesToSend, assistantMessage, forcedSessionUuid = null, npp = null, isolatedDocId = null, attachmentPaths = []) {
    try {
        const activeSessionUuid = forcedSessionUuid || get().sessionUuid;

        const response = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: _buildAuthHeaders(npp),
            body: JSON.stringify({
                session_uuid: activeSessionUuid, 
                messages: messagesToSend,
                mode: 'normal',
                temperature: 0.7,
                // 🔥 TAMBAHAN PAYLOAD SAKTI UNTUK FASE 1 ATTACHMENT SUPPORT
                isolated_doc_id: isolatedDocId,       // Mengunci mode chat dokumen spesifik (RAG)
                attachment_paths: attachmentPaths      // Jalur file attachment biasa (User Upload)
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

    // ─────────────────────────────────────────────────────────────────────────
    // 🔥 TAMBAHAN STATE BARU UNTUK SEKTOR ATTACHMENT SUPPORT & ISOLASI KONTEKS
    // ─────────────────────────────────────────────────────────────────────────
    stagedAttachments: [],     // Menampung metadata file yang sudah terupload ke backend sementara
    activeIsolatedDocId: null, // ID dokumen RAG aktif untuk mode isolasi chat context
    activeIsolatedTitle: null, // Judul dokumen RAG aktif untuk komponen penanda di UI input form

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

        // Ambil data attachment paths dan isolated context saat ini sebelum dikirim
        const currentAttachmentPaths = get().stagedAttachments.map(file => file.file_path) || [];
        const currentIsolatedDocId = get().activeIsolatedDocId;

        set({
            messages: [...updatedMessages, assistantMessage],
            isStreaming: true,
            isLoading: true,
            isThinking: true
        });

        await new Promise(resolve => setTimeout(resolve, 100));
        
        // 🔥 TAMBAHAN OPERAN PARAMETER: Mengirimkan data isolasi dan attachment ke performStream
        await _performStream(
            set, 
            get, 
            updatedMessages, 
            assistantMessage, 
            currentSessionUuid, 
            npp, 
            currentIsolatedDocId, 
            currentAttachmentPaths
        );

        // 🔥 AUTO CLEAR STAGED: Kosongkan list file staged attachments setelah pesan berhasil terkirim
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
        
        // Tambahan parameter default null pada editAndRegenerate demi menjaga kestabilan sasis aslinya
        await _performStream(set, get, messagesToSend, assistantMessage, null, npp, get().activeIsolatedDocId, []);
    },

    clearChat: () => {
        // 🔥 TAMBAHAN: Reset juga state isolasi dan attachments saat clear chat dilakukan
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
        // 🔥 TAMBAHAN: Reset state isolasi dokumen lama saat berpindah ke sesi obrolan yang berbeda
        set({ sessionUuid, messages: [], isLoading: true, activeIsolatedDocId: null, activeIsolatedTitle: null });

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
                // 🔥 TAMBAHAN: Pastikan state isolasi dan attachment bersih total saat inisialisasi sesi baru murni
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

    // ─────────────────────────────────────────────────────────────────────────
    // 🔥 TAMBAHAN BARIS ACTION MANAJEMEN BARU TANPA MERUSAK STRUKTUR DI ATAS
    // ─────────────────────────────────────────────────────────────────────────
    
    // Action untuk menyimpan metadata berkas yang berhasil diunggah di chat form staged
    setStagedAttachments: (attachments) => {
        set({ stagedAttachments: attachments });
    },

    // Action sakti untuk toggle/mengunci/keluar dari mode isolasi pencarian dokumen RAG spesifik
    setContextIsolation: (docId, docTitle) => {
        // Jika dokumen yang diklik sama dengan yang sedang aktif, anggap user men-toggle untuk keluar (reset)
        if (get().activeIsolatedDocId === docId || docId === null) {
            set({ activeIsolatedDocId: null, activeIsolatedTitle: null });
        } else {
            set({ activeIsolatedDocId: docId, activeIsolatedTitle: docTitle });
        }
    }

}));