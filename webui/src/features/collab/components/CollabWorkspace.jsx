import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  Menu
} from 'lucide-react';
import { collabApi } from '../services/collabApi';
import { useCollabStream } from '../hooks/useCollabStream';
import CollabChatArea from './CollabChatArea';
import CollabInputArea from './CollabInputArea';
import CollabDocumentPad from './CollabDocumentPad';
import CreateRoomModal from './CreateRoomModal';
import InviteMemberModal from './InviteMemberModal';

export const CollabWorkspace = ({
  theme,
  darkMode = true,
  userData,
  language,
  isMobile,
  toggleSidebar
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

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isInviteOpen, setIsInviteOpen] = useState(false);

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

  // Map NPP to Member Info
  const membersMap = useMemo(() => {
    const map = {};
    if (roomDetail?.members) {
      roomDetail.members.forEach((m) => {
        map[m.npp] = m;
      });
    }
    return map;
  }, [roomDetail]);

  // SSE Stream Event Handlers
  const handleNewMessage = useCallback((msg) => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === msg.id)) return prev;
      return [...prev, msg];
    });
  }, []);

  const handleTyping = useCallback((typing) => {
    setTypingStatus(typing);
  }, []);

  const handleDocumentUpdated = useCallback((payload) => {
    if (payload.document_content !== undefined) {
      setDocumentContent(payload.document_content);
    }
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
    onTyping: handleTyping,
    onDocumentUpdated: handleDocumentUpdated,
    onMembersUpdated: handleMembersUpdated
  });

  // Action: Kirim Pesan
  const handleSendMessage = async (text) => {
    if (!roomId || !text.trim()) return;
    try {
      await collabApi.sendMessage(roomId, text);
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

  // Action: Salin respons Cakra ke Document Pad
  const handleApplyToDocument = (text) => {
    const updated = documentContent ? `${documentContent}\n\n${text}` : text;
    setDocumentContent(updated);
    setIsPadOpen(true);
    handleSaveDocument(updated);
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
                  Buat ruang obrolan kerja untuk merumuskan konsep, menyusun draf Surat Edaran (SE), 
                  atau mendiskusikan aturan perusahaan bersama tim Anda dan CAKRA AI Teammate.
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
                          {room.topic || 'Pembahasan draf dan regulasi tim.'}
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
            className="h-14 px-4 border-b flex items-center justify-between shrink-0"
            style={{
              background: pageBg,
              borderColor: borderColor
            }}
          >
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={() => navigate('/collab')}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-white/5"
                style={{ color: secondaryTextColor }}
                title="Kembali ke Daftar Ruang"
              >
                <ArrowLeft size={16} />
                <span className="hidden sm:inline">Semua Ruang</span>
              </button>

              <div className="h-4 w-px hidden sm:block" style={{ background: borderColor }} />

              <div className="min-w-0">
                <h2 className="text-sm font-bold truncate flex items-center gap-2" style={{ color: textColor }}>
                  <span>{roomDetail?.name || 'Ruang Diskusi'}</span>
                  {isConnected ? (
                    <span className="flex items-center gap-1 text-[10px] font-normal text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-800/60" title="Terhubung Real-time">
                      <Wifi size={10} /> Live
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] font-normal text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded-full border border-amber-800/60">
                      <WifiOff size={10} /> Reconnecting
                    </span>
                  )}
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
                  <div
                    key={m.npp}
                    className="inline-block h-7 w-7 rounded-full text-teal-400 font-bold text-[10px] flex items-center justify-center border"
                    style={{
                      background: darkMode ? '#222226' : '#e5e7eb',
                      borderColor: borderColor
                    }}
                    title={`${m.name} (${m.divisi})`}
                  >
                    {m.name.charAt(0).toUpperCase()}
                  </div>
                ))}
                {(roomDetail?.members?.length || 0) > 4 && (
                  <div
                    className="h-7 w-7 rounded-full font-medium text-[10px] flex items-center justify-center border"
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
                title="Buka / Tutup Panel Draf Dokumen"
              >
                <FileText size={14} className="text-teal-400" />
                <span className="hidden sm:inline">Draf Dokumen</span>
              </button>
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
                  onApplyToDocument={handleApplyToDocument}
                  darkMode={darkMode}
                  theme={theme}
                />
              )}

              {/* Input Chat Tim dengan Mention @cakra */}
              <CollabInputArea
                onSendMessage={handleSendMessage}
                members={roomDetail?.members || []}
                darkMode={darkMode}
                theme={theme}
              />
            </div>

            {/* Document Pad Samping (Collapsible) */}
            {isPadOpen && (
              <div
                className="w-[380px] lg:w-[440px] shrink-0 border-l h-full animate-in slide-in-from-right duration-200"
                style={{ borderColor: borderColor }}
              >
                <CollabDocumentPad
                  documentContent={documentContent}
                  onSave={handleSaveDocument}
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
    </div>
  );
};

export default CollabWorkspace;
