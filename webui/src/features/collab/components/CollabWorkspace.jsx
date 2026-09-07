import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Users2,
  Plus,
  FileText,
  UserPlus,
  ArrowLeft,
  Loader2,
  Sparkles,
  Wifi,
  WifiOff,
  Search,
  MessageSquare,
  Clock,
  Menu,
  Layers
} from 'lucide-react';
import { collabApi } from '../services/collabApi';
import { useCollabStream } from '../hooks/useCollabStream';
import CollabChatArea from './CollabChatArea';
import CollabChatInputArea from './CollabChatInputArea';
import CollabDocumentPad from './CollabDocumentPad';
import CreateRoomModal from './CreateRoomModal';
import InviteMemberModal from './InviteMemberModal';
import CollabAvatar from './CollabAvatar';
import PreviewImageModal from '../../chat/components/modals/PreviewImageModal';
import NextcloudModal from '../../chat/components/NextcloudModal';

export const CollabWorkspace = ({
  theme,
  darkMode = true,
  userData,
  language,
  isMobile,
  toggleSidebar,
  onOpenArtifact,
  toggleRightSidebar,
  showRightSidebar
}) => {
  const { roomId } = useParams();
  const navigate = useNavigate();

  const currentNpp = userData?.npp || (() => {
    try {
      const raw = localStorage.getItem('cakra_user');
      return raw ? JSON.parse(raw)?.npp : '';
    } catch {
      return '';
    }
  })();

  // Skema warna konsisten persis ChatPage
  const pageBg = theme?.mainBg || (darkMode ? '#151517' : '#ffffff');
  const borderColor = theme?.borderColor || (darkMode ? '#2a2a2d' : '#e5e7eb');
  const cardBg = darkMode ? '#1e1e20' : '#ffffff';
  const cardHoverBorder = '#14b8a6';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');
  const inputBg = theme?.inputBg || (darkMode ? '#1e1e20' : '#f3f4f6');

  // Pembatas halus & seamless tanpa garis putih tebal
  const subtleBorder = darkMode ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.08)';

  // State
  const [rooms, setRooms] = useState([]);
  const [roomDetail, setRoomDetail] = useState(null);
  const [messages, setMessages] = useState([]);
  const [documentContent, setDocumentContent] = useState('');
  const [isPadOpen, setIsPadOpen] = useState(false);
  const [isSavingDoc, setIsSavingDoc] = useState(false);
  const [typingStatus, setTypingStatus] = useState(null);
  const [isLoadingRooms, setIsLoadingRooms] = useState(true);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Resizable Document Pad Width
  const [padWidth, setPadWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('collab_pad_width');
      return saved ? Math.max(340, Math.min(950, parseInt(saved, 10))) : 460;
    } catch {
      return 460;
    }
  });
  const isResizingPad = useRef(false);

  const handleMouseMovePad = useCallback((e) => {
    if (!isResizingPad.current) return;
    const newWidth = window.innerWidth - e.clientX;
    const minW = 340;
    const maxW = Math.min(950, Math.floor(window.innerWidth * 0.75));
    if (newWidth >= minW && newWidth <= maxW) {
      setPadWidth(newWidth);
    }
  }, []);

  const stopResizingPad = useCallback(() => {
    if (!isResizingPad.current) return;
    isResizingPad.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    document.removeEventListener('mousemove', handleMouseMovePad);
    document.removeEventListener('mouseup', stopResizingPad);
    try {
      setPadWidth((currentW) => {
        localStorage.setItem('collab_pad_width', currentW.toString());
        return currentW;
      });
    } catch {}
  }, [handleMouseMovePad]);

  const startResizingPad = useCallback((e) => {
    e.preventDefault();
    isResizingPad.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleMouseMovePad);
    document.addEventListener('mouseup', stopResizingPad);
  }, [handleMouseMovePad, stopResizingPad]);

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMovePad);
      document.removeEventListener('mouseup', stopResizingPad);
    };
  }, [handleMouseMovePad, stopResizingPad]);

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);

  // Load Rooms list
  const loadRooms = useCallback(async () => {
    try {
      setIsLoadingRooms(true);
      const list = await collabApi.getMyRooms();
      setRooms(list);
    } catch (err) {
      console.error('Failed to load collab rooms:', err);
    } finally {
      setIsLoadingRooms(false);
    }
  }, []);

  useEffect(() => {
    loadRooms();
  }, [loadRooms]);

  // Load Room Detail & Messages when roomId is present in URL
  useEffect(() => {
    if (!roomId) {
      setRoomDetail(null);
      setMessages([]);
      return;
    }

    let isMounted = true;
    const fetchDetailAndMessages = async () => {
      try {
        setIsLoadingChat(true);
        const [detail, msgs] = await Promise.all([
          collabApi.getRoomDetail(roomId),
          collabApi.getMessages(roomId, 100)
        ]);

        if (isMounted) {
          setRoomDetail(detail);
          setDocumentContent(detail.document_content || '');
          setMessages(msgs);
        }
      } catch (err) {
        console.error('Failed to load room data:', err);
      } finally {
        if (isMounted) setIsLoadingChat(false);
      }
    };

    fetchDetailAndMessages();
    return () => {
      isMounted = false;
    };
  }, [roomId]);

  // Map NPP and Name to Member Info
  const membersMap = useMemo(() => {
    const map = {};
    if (roomDetail?.members) {
      roomDetail.members.forEach((m) => {
        if (m.npp) {
          map[m.npp] = m;
          map[String(m.npp).trim()] = m;
          map[String(m.npp).trim().toLowerCase()] = m;
        }
        if (m.name) {
          map[m.name] = m;
          map[String(m.name).trim()] = m;
          map[String(m.name).trim().toLowerCase()] = m;
        }
      });
    }
    return map;
  }, [roomDetail]);

  // State Streaming Real-time CAKRA
  const [streamingCakra, setStreamingCakra] = useState(null);
  const [cakraThinkingPhase, setCakraThinkingPhase] = useState('');

  // SSE Stream Event Handlers
  const handleNewMessage = useCallback((msg) => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === msg.id)) return prev;
      return [...prev, msg];
    });
  }, []);

  const handleCakraStreamStart = useCallback((payload) => {
    setStreamingCakra({
      id: payload.message_id,
      sender_type: 'CAKRA',
      sender_name: 'CAKRA AI Teammate',
      message_text: '',
      interjection_type: payload.interjection_type || 'EXPLICIT_MENTION',
      created_at: new Date().toISOString()
    });
    setCakraThinkingPhase('CAKRA sedang berpikir...');
  }, []);

  const handleCakraStreamChunk = useCallback((payload) => {
    setStreamingCakra((prev) => {
      if (!prev) {
        return {
          id: payload.message_id,
          sender_type: 'CAKRA',
          sender_name: 'CAKRA AI Teammate',
          message_text: payload.chunk || '',
          created_at: new Date().toISOString()
        };
      }
      return {
        ...prev,
        message_text: (prev.message_text || '') + (payload.chunk || '')
      };
    });
    setCakraThinkingPhase('CAKRA sedang menyusun respon...');
  }, []);

  const handleCakraStreamEnd = useCallback((payload) => {
    setStreamingCakra(null);
    setCakraThinkingPhase('');
    if (payload.message) {
      setMessages((prev) => {
        if (prev.some((m) => m.id === payload.message.id)) return prev;
        return [...prev, payload.message];
      });
    }
  }, []);

  const handleTyping = useCallback((typing) => {
    setTypingStatus(typing);
  }, []);

  const handleDocumentUpdated = useCallback((payload) => {
    if (payload.document_content !== undefined) {
      setDocumentContent(payload.document_content);
    }
  }, []);

  const handleMessageEdited = useCallback((editedMsg) => {
    if (!editedMsg?.id) return;
    setMessages((prev) =>
      prev.map((m) => (m.id === editedMsg.id ? { ...m, ...editedMsg } : m))
    );
  }, []);

  const handleMembersUpdated = useCallback(() => {
    if (roomId) {
      collabApi.getRoomDetail(roomId).then(setRoomDetail).catch(console.error);
    }
  }, [roomId]);

  // Real-time SSE Hook
  const { isConnected } = useCollabStream({
    roomId,
    onNewMessage: handleNewMessage,
    onMessageEdited: handleMessageEdited,
    onTyping: handleTyping,
    onDocumentUpdated: handleDocumentUpdated,
    onMembersUpdated: handleMembersUpdated,
    onCakraStreamStart: handleCakraStreamStart,
    onCakraStreamChunk: handleCakraStreamChunk,
    onCakraStreamEnd: handleCakraStreamEnd
  });

  // Action: Broadcast Mengetik
  const handleTypingChange = useCallback((isTyping) => {
    if (roomId) {
      collabApi.sendTypingStatus(roomId, isTyping);
    }
  }, [roomId]);

  // Action: Edit Pesan Sendiri
  const handleEditMessage = async (messageId, newText) => {
    if (!roomId || !messageId || !newText?.trim()) return;
    try {
      // Update optimistik di state lokal
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, message_text: newText.trim() } : m))
      );
      await collabApi.editMessage(roomId, messageId, newText.trim());
    } catch (err) {
      console.error('Failed to edit message:', err);
      // Rollback jika gagal
      collabApi.getMessages(roomId).then(setMessages).catch(console.error);
    }
  };

  // Action: Kirim Pesan (Mendukung Teks, Lampiran File/Gambar, dan Mode Presets)
  const handleSendMessage = async (text, attachments = [], mode = null) => {
    if (!roomId || (!text?.trim() && attachments.length === 0)) return;
    try {
      await collabApi.sendMessage(roomId, text, attachments, mode);
    } catch (err) {
      console.error('Failed to send message:', err);
      alert('Gagal mengirim pesan ke ruang diskusi.');
    }
  };

  // Action: Simpan Dokumen
  const handleSaveDocument = async (newContent) => {
    if (!roomId) return;
    try {
      setIsSavingDoc(true);
      await collabApi.updateDocument(roomId, newContent);
      setDocumentContent(newContent);
    } catch (err) {
      console.error('Failed to save document:', err);
      alert('Gagal menyimpan perubahan draf dokumen.');
    } finally {
      setIsSavingDoc(false);
    }
  };

  // Action: Salin respons Cakra ke Document Pad dengan pencegahan duplikasi
  const handleApplyToDocument = (text) => {
    if (!text?.trim()) return;
    const cleanText = text.trim();

    // Pencegahan duplikasi: jika teks sudah ada di dalam dokumen, jangan duplikasi
    if (documentContent && documentContent.includes(cleanText)) {
      alert('Poin atau respons ini sudah ada di dalam Catatan Tim.');
      setIsPadOpen(true);
      return;
    }

    const timeStamp = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    const updated = documentContent && documentContent.trim()
      ? `${documentContent.trim()}\n\n---\n**Tambahan (${timeStamp} WIB):**\n${cleanText}`
      : cleanText;

    setDocumentContent(updated);
    setIsPadOpen(true);
    handleSaveDocument(updated);
  };

  // Action: Rangkum otomatis obrolan tim menjadi Notulensi Resmi via CAKRA AI
  const handleSummarizeRoom = async () => {
    if (!roomId) return;
    try {
      setIsSavingDoc(true);
      const res = await collabApi.summarizeRoom(roomId);
      if (res?.document_content) {
        setDocumentContent(res.document_content);
        setIsPadOpen(true);
      }
    } catch (err) {
      console.error('Failed to summarize room:', err);
      alert('Gagal menyusun notulensi otomatis: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsSavingDoc(false);
    }
  };

  // Filtered rooms for lobby search
  const filteredRooms = useMemo(() => {
    if (!searchQuery.trim()) return rooms;
    const q = searchQuery.toLowerCase();
    return rooms.filter(
      (r) =>
        r.name?.toLowerCase().includes(q) ||
        r.topic?.toLowerCase().includes(q)
    );
  }, [rooms, searchQuery]);

  return (
    <div
      className="h-full w-full flex flex-col overflow-hidden font-sans relative"
      style={{
        background: pageBg,
        color: textColor
      }}
    >
      {/* ─────────────────────────────────────────────────────────────
          1. JIKA BELUM MEMILIH RUANGAN (LOBBY VIEW - PERSIS CLAUDE UI)
         ───────────────────────────────────────────────────────────── */}
      {!roomId ? (
        <div className="h-full flex flex-col overflow-hidden" style={{ background: pageBg }}>
          {/* Header Lobby */}
          <div
            className="h-16 px-6 flex items-center justify-between shrink-0 border-b"
            style={{
              background: pageBg,
              borderColor: borderColor
            }}
          >
            <div className="flex items-center gap-3">
              {isMobile && toggleSidebar && (
                <button
                  onClick={toggleSidebar}
                  className="p-2 rounded-lg transition-colors"
                  style={{ color: secondaryTextColor }}
                >
                  <Menu size={18} />
                </button>
              )}
              <div>
                <h1 className="text-lg font-bold flex items-center gap-2" style={{ color: textColor }}>
                  <span>Diskusi Tim</span>
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Kolom Pencarian Ruang Diskusi */}
              <div className="relative w-56 sm:w-72">
                <Search
                  size={15}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2"
                  style={{ color: secondaryTextColor }}
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cari ruang diskusi..."
                  className="w-full pl-9 pr-3.5 py-1.5 rounded-xl text-xs transition-all focus:outline-none focus:ring-1 focus:ring-teal-500"
                  style={{
                    background: inputBg,
                    borderColor: borderColor,
                    borderWidth: '1px',
                    color: textColor
                  }}
                />
              </div>

              {/* Tombol Buat Ruang Diskusi Baru */}
              <button
                onClick={() => setIsCreateOpen(true)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold shadow-sm transition-all hover:scale-[1.02] bg-teal-600 hover:bg-teal-500 text-white"
              >
                <Plus size={15} />
                <span>Buat Ruang Diskusi</span>
              </button>
            </div>
          </div>

          {/* Body Lobby */}
          <div className="flex-1 overflow-y-auto p-6 sm:p-10 custom-scrollbar">
            {isLoadingRooms ? (
              <div className="h-full flex items-center justify-center" style={{ color: secondaryTextColor }}>
                <Loader2 size={24} className="animate-spin text-teal-400" />
              </div>
            ) : filteredRooms.length === 0 ? (
              // Tampilan Kosong Minimalis (Persis Layout Gambar Claude)
              <div className="h-full min-h-[420px] flex flex-col items-center justify-center text-center max-w-md mx-auto">
                {/* Minimalist Illustration Icon Box */}
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 border shadow-inner"
                  style={{
                    background: cardBg,
                    borderColor: borderColor
                  }}
                >
                  <div className="relative">
                    <Users2 size={28} style={{ color: secondaryTextColor }} />
                    <Sparkles size={14} className="absolute -top-1 -right-2 text-teal-400" />
                  </div>
                </div>

                <h2 className="text-base sm:text-lg font-bold mb-2" style={{ color: textColor }}>
                  Mulai Diskusi Tim bersama Rekan & CAKRA
                </h2>

                <p className="text-xs sm:text-sm leading-relaxed mb-6" style={{ color: secondaryTextColor }}>
                  Buat ruang kolaborasi untuk membahas proyek, koordinasi kerja tim, 
                  brainstorming ide, atau pemecahan masalah bersama rekan kerja dan CAKRA AI Teammate.
                </p>

                <button
                  onClick={() => setIsCreateOpen(true)}
                  className="px-5 py-2.5 rounded-xl font-semibold text-xs transition-all shadow-md hover:scale-[1.02] bg-teal-600 hover:bg-teal-500 text-white"
                >
                  Buat Ruang Diskusi Baru
                </button>
              </div>
            ) : (
              // Grid Daftar Ruang Diskusi Aktif
              <div className="max-w-6xl mx-auto">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-bold uppercase tracking-wider" style={{ color: secondaryTextColor }}>
                    Ruang Diskusi Anda ({filteredRooms.length})
                  </h2>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredRooms.map((room) => (
                    <div
                      key={room.id}
                      onClick={() => navigate(`/collab/${room.id}`)}
                      className="group border rounded-2xl p-5 cursor-pointer transition-all duration-200 shadow-md flex flex-col justify-between hover:border-teal-500"
                      style={{
                        background: cardBg,
                        borderColor: borderColor
                      }}
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h3
                            className="font-bold text-sm group-hover:text-teal-400 transition-colors line-clamp-1"
                            style={{ color: textColor }}
                          >
                            {room.name}
                          </h3>
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full border shrink-0 font-medium"
                            style={{
                              background: darkMode ? '#222226' : '#f3f4f6',
                              borderColor: borderColor,
                              color: secondaryTextColor
                            }}
                          >
                            {room.member_count || 1} Anggota
                          </span>
                        </div>

                        <p
                          className="text-xs line-clamp-2 mb-4 leading-relaxed"
                          style={{ color: secondaryTextColor }}
                        >
                          {room.topic || 'Ruang diskusi dan kolaborasi tim.'}
                        </p>
                      </div>

                      <div
                        className="pt-3 border-t flex items-center justify-between text-[11px]"
                        style={{
                          borderColor: borderColor,
                          color: secondaryTextColor
                        }}
                      >
                        <span className="flex items-center gap-1">
                          <Sparkles size={11} className="text-teal-400" />
                          CAKRA Aktif
                        </span>
                        <span className="text-teal-400 font-medium group-hover:translate-x-1 transition-transform">
                          Buka Ruangan →
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ─────────────────────────────────────────────────────────────
           2. JIKA DI DALAM RUANG DISKUSI (TAMPILAN CHAT DENGAN CAKRA)
           ───────────────────────────────────────────────────────────── */
        <div className="h-full flex flex-col overflow-hidden" style={{ background: pageBg }}>
          {/* Top Header Ruangan */}
          <div
            className="h-14 px-4 flex items-center justify-between shrink-0"
            style={{
              background: pageBg
            }}
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="min-w-0">
                <h2 className="text-sm font-bold truncate flex items-center gap-2" style={{ color: textColor }}>
                  <span>{roomDetail?.name || 'Ruang Diskusi'}</span>
                </h2>
                {roomDetail?.topic && (
                  <p className="text-[11px] truncate max-w-md" style={{ color: secondaryTextColor }}>
                    {roomDetail.topic}
                  </p>
                )}
              </div>
            </div>

            {/* Action Bar Ruangan */}
            <div className="flex items-center gap-2 shrink-0">
              {/* Avatar Stack Anggota */}
              <div className="flex -space-x-2 overflow-hidden items-center mr-1">
                {roomDetail?.members?.slice(0, 4).map((m) => (
                  <CollabAvatar
                    key={m.npp}
                    npp={m.npp}
                    name={m.name}
                    photoUrl={m.profile_photo_url}
                    size="w-7 h-7"
                    className="inline-block ring-2 ring-neutral-900"
                    title={`${m.name} (${m.divisi || 'PT Pindad'})`}
                  />
                ))}
                {(roomDetail?.members?.length || 0) > 4 && (
                  <div
                    className="h-7 w-7 rounded-full font-medium text-[10px] flex items-center justify-center border ring-2 ring-neutral-900"
                    style={{
                      background: darkMode ? '#222226' : '#e5e7eb',
                      borderColor: borderColor,
                      color: secondaryTextColor
                    }}
                  >
                    +{roomDetail.members.length - 4}
                  </div>
                )}
              </div>

              {/* Undang Rekan */}
              <button
                onClick={() => setIsInviteOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-colors"
                style={{
                  background: darkMode ? '#1e1e20' : '#f3f4f6',
                  borderColor: borderColor,
                  color: textColor
                }}
                title="Undang rekan kerja ke ruangan ini"
              >
                <UserPlus size={14} className="text-teal-400" />
                <span className="hidden sm:inline">Undang</span>
              </button>

              {/* Toggle Document Pad */}
              <button
                onClick={() => setIsPadOpen((prev) => !prev)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                  isPadOpen
                    ? 'bg-teal-500/20 text-teal-300 border-teal-500/40 shadow-sm'
                    : 'hover:bg-white/5'
                }`}
                style={!isPadOpen ? {
                  background: darkMode ? '#1e1e20' : '#f3f4f6',
                  borderColor: borderColor,
                  color: textColor
                } : {}}
                title="Buka / Tutup Panel Catatan Bersama & Notulen"
              >
                <FileText size={14} className="text-teal-400" />
                <span className="hidden sm:inline">Catatan Tim</span>
              </button>

              {/* Toggle Artifacts & Berkas Sesi */}
              {toggleRightSidebar && (
                <button
                  onClick={toggleRightSidebar}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    showRightSidebar
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm'
                      : 'hover:bg-white/5'
                  }`}
                  style={!showRightSidebar ? {
                    background: darkMode ? '#1e1e20' : '#f3f4f6',
                    borderColor: borderColor,
                    color: textColor
                  } : {}}
                  title="Buka / Tutup Workspace Artifacts & Berkas Sesi"
                >
                  <Layers size={14} className={showRightSidebar ? 'text-indigo-400' : 'text-indigo-400/80'} />
                  <span className="hidden sm:inline">Artifacts</span>
                </button>
              )}
            </div>
          </div>

          {/* Area Utama: Chat (Kiri) + Document Pad (Kanan) */}
          <div className="flex-1 flex min-h-0 overflow-hidden" style={{ background: pageBg }}>
            {/* Area Obrolan Grup */}
            <div className="flex-1 flex flex-col min-w-0" style={{ background: pageBg }}>
              {isLoadingChat ? (
                <div className="flex-1 flex items-center justify-center" style={{ color: secondaryTextColor }}>
                  <Loader2 size={24} className="animate-spin text-teal-400" />
                </div>
              ) : (
                <CollabChatArea
                  messages={messages}
                  currentNpp={currentNpp}
                  membersMap={membersMap}
                  typingStatus={typingStatus}
                  streamingCakra={streamingCakra}
                  cakraThinkingPhase={cakraThinkingPhase}
                  darkMode={darkMode}
                  theme={theme}
                  language={language}
                  onApplyToDocument={handleApplyToDocument}
                  setPreviewImage={setPreviewImage}
                  onOpenArtifact={onOpenArtifact}
                  onEditMessage={handleEditMessage}
                />
              )}

              {/* Input Chat Tim Persis ChatPage Utama (Kapsul Melayang Elevated, Plus, Attachment, Voice, Send, Disclaimer) */}
              <CollabChatInputArea
                onSendMessage={handleSendMessage}
                onTypingChange={handleTypingChange}
                members={roomDetail?.members || []}
                isSending={false}
                darkMode={darkMode}
                theme={theme}
                isMobile={isMobile}
                language={language}
              />
            </div>

            {/* Document Pad Samping (Collapsible & Resizable ke Kiri) */}
            {isPadOpen && (
              <div
                className="relative shrink-0 h-full animate-in slide-in-from-right duration-200"
                style={{
                  width: `${padWidth}px`,
                  borderLeft: `1px solid ${subtleBorder}`
                }}
              >
                {/* Drag Handle to Resize to the Left */}
                {!isMobile && (
                  <div
                    onMouseDown={startResizingPad}
                    className="absolute -left-1.5 top-0 bottom-0 w-3 cursor-col-resize z-30 group flex items-center justify-center transition-colors"
                    title="Geser ke kiri untuk memperbesar, ke kanan untuk memperkecil"
                  >
                    <div className="w-[3px] h-12 rounded-full bg-white/10 group-hover:bg-teal-500/80 group-active:bg-teal-400 group-hover:h-20 transition-all duration-150" />
                  </div>
                )}
                <CollabDocumentPad
                  roomId={roomId}
                  documentContent={documentContent}
                  onSave={handleSaveDocument}
                  onSummarize={handleSummarizeRoom}
                  onClose={() => setIsPadOpen(false)}
                  isSaving={isSavingDoc}
                  roomTopic={roomDetail?.topic}
                  darkMode={darkMode}
                  theme={theme}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modals */}
      <CreateRoomModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onRoomCreated={(newRoom) => {
          loadRooms();
          if (newRoom?.id) {
            navigate(`/collab/${newRoom.id}`);
          }
        }}
        darkMode={darkMode}
        theme={theme}
      />

      {roomId && (
        <InviteMemberModal
          isOpen={isInviteOpen}
          onClose={() => setIsInviteOpen(false)}
          roomId={roomId}
          currentMembers={roomDetail?.members || []}
          onMembersInvited={handleMembersUpdated}
          darkMode={darkMode}
          theme={theme}
        />
      )}

      {/* 🖼️ IMAGE PREVIEW MODAL */}
      <PreviewImageModal
        previewImage={previewImage}
        onClose={() => setPreviewImage(null)}
      />

      {/* ☁️ NEXTCLOUD MODAL */}
      <NextcloudModal
        darkMode={darkMode}
        language={language}
        onFileSelect={(files) => {
          if (Array.isArray(files) && files.length > 0) {
            // Forward files to send
            const formatted = files.map(f => ({
              name: f.name,
              size: f.size,
              type: f.type,
              file_obj: f.file_obj || f,
              preview: f.preview || null
            }));
            handleSendMessage('', formatted);
          }
        }}
      />
    </div>
  );
};

export default CollabWorkspace;
