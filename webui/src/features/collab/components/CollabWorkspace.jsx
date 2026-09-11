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
  Layers,
  MoreVertical,
  Edit2,
  Archive,
  Trash2,
  Check,
  X,
  AlertTriangle,
  FileEdit
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
import { useCollabStore } from '../../../stores/collabStore';
import { useDocWriterStore } from '../../../stores/docWriterStore';
import DocWriterWorkspace from '../../doc_writer/components/DocWriterWorkspace';
import { translations } from '../../../utils/translations';

export const CollabWorkspace = ({
  theme,
  darkMode = true,
  userData,
  language = 'id',
  isMobile,
  sidebarOpen,
  setSidebarOpen,
  toggleSidebar,
  onOpenArtifact,
  toggleRightSidebar,
  showRightSidebar
}) => {
  const t = translations[language]?.collab || translations.id.collab;
  const { roomId } = useParams();
  const navigate = useNavigate();
  const { isDocWriterOpen, toggleDocWriter } = useDocWriterStore((state) => ({
    isDocWriterOpen: state.isOpen,
    toggleDocWriter: state.toggleWriter
  }));

  const currentNpp = userData?.npp || (() => {
    try {
      const raw = localStorage.getItem('cakra_user');
      return raw ? JSON.parse(raw)?.npp : '';
    } catch {
      return '';
    }
  })();

  const isGuest = Boolean(userData?.isGuest || userData?.role === 'guest' || currentNpp === 'GUEST');
  const isAiActivated = useDocWriterStore((state) => state.isAiActivated);

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
  const [autoNotedMessageIds, setAutoNotedMessageIds] = useState(new Set());
  const [streamingCakra, setStreamingCakra] = useState(null);
  const [cakraThinkingPhase, setCakraThinkingPhase] = useState('');

  const [hasRoomDocWriter, setHasRoomDocWriter] = useState(false);

  useEffect(() => {
    if (isGuest) {
      setHasRoomDocWriter(false);
      return;
    }
    if (isDocWriterOpen) {
      setHasRoomDocWriter(true);
    }
    if (messages && messages.length > 0) {
      const found = messages.some((m) => {
        const text = m.message_text || m.content || '';
        return typeof text === 'string' && /```(?:docwriter|doc_writer|document_writer)\b/i.test(text);
      });
      if (found) setHasRoomDocWriter(true);
    }
    if (streamingCakra) {
      const streamText = streamingCakra.message_text || streamingCakra.content || '';
      if (typeof streamText === 'string' && /```(?:docwriter|doc_writer|document_writer)\b/i.test(streamText)) {
        setHasRoomDocWriter(true);
      }
    }
  }, [isGuest, isDocWriterOpen, messages, streamingCakra]);

  useEffect(() => {
    setHasRoomDocWriter(false);
  }, [roomId]);

  const hasAiTriggeredDocWriter = useMemo(() => {
    if (isGuest) return false;
    if (isDocWriterOpen || hasRoomDocWriter) return true;
    if (messages && messages.length > 0) {
      const found = messages.some((m) => {
        const text = m.message_text || m.content || '';
        return typeof text === 'string' && /```(?:docwriter|doc_writer|document_writer)\b/i.test(text);
      });
      if (found) return true;
    }
    if (streamingCakra) {
      const streamText = streamingCakra.message_text || streamingCakra.content || '';
      if (typeof streamText === 'string' && /```(?:docwriter|doc_writer|document_writer)\b/i.test(streamText)) {
        return true;
      }
    }
    return Boolean(isAiActivated);
  }, [isGuest, isDocWriterOpen, hasRoomDocWriter, messages, streamingCakra, isAiActivated]);

  const wasSidebarOpenForPadRef = useRef(false);

  // ── Auto-collapse left sidebar when Collab Document Pad is open ──
  useEffect(() => {
    if (isPadOpen) {
      if (sidebarOpen && !isMobile) {
        wasSidebarOpenForPadRef.current = true;
        setSidebarOpen?.(false);
      }
    } else {
      if (wasSidebarOpenForPadRef.current && !isMobile) {
        setSidebarOpen?.(true);
        wasSidebarOpenForPadRef.current = false;
      }
    }
  }, [isPadOpen, isMobile, setSidebarOpen]);

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

  const stopResizingPad = useCallback(() => {
    if (!isResizingPad.current) return;
    isResizingPad.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    try {
      setPadWidth((currentW) => {
        localStorage.setItem('collab_pad_width', currentW.toString());
        return currentW;
      });
    } catch {}
  }, []);

  const handleMouseMovePad = useCallback((e) => {
    if (!isResizingPad.current) return;
    if (e.buttons === 0) {
      stopResizingPad();
      return;
    }
    const newWidth = window.innerWidth - e.clientX;
    const minW = 340;
    const maxW = Math.min(950, Math.floor(window.innerWidth * 0.75));
    if (newWidth >= minW && newWidth <= maxW) {
      setPadWidth(newWidth);
    }
  }, [stopResizingPad]);

  const startResizingPad = useCallback((e) => {
    e.preventDefault();
    isResizingPad.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseUp = () => {
      stopResizingPad();
      window.removeEventListener('mousemove', handleMouseMovePad);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMovePad, { passive: true });
    window.addEventListener('mouseup', onMouseUp);
  }, [handleMouseMovePad, stopResizingPad]);

  useEffect(() => {
    return () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, []);

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [showMembersModal, setShowMembersModal] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);

  // 🛠️ Collab Store & Invitations
  const invitations = useCollabStore((state) => state.invitations);
  const fetchInvitations = useCollabStore((state) => state.fetchInvitations);
  const respondToInvitation = useCollabStore((state) => state.respondToInvitation);
  const [respondingId, setRespondingId] = useState(null);

  // 🛠️ Room Action States (Rename, Archive, Delete)
  const [activeRoomMenuId, setActiveRoomMenuId] = useState(null);
  const [renameModalData, setRenameModalData] = useState(null); // { id, name, topic }
  const [deleteConfirmRoom, setDeleteConfirmRoom] = useState(null); // { id, name }
  const [archiveConfirmRoom, setArchiveConfirmRoom] = useState(null); // { id, name }
  const [toastMsg, setToastMsg] = useState(null);
  const roomMenuRef = useRef(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleRespondInvitation = async (invitationRoomId, action) => {
    try {
      setRespondingId(invitationRoomId);
      await respondToInvitation(invitationRoomId, action);
      if (action === 'accept') {
        showToast(language === 'en' ? 'Invitation accepted! You have joined the discussion room.' : 'Undangan diterima! Anda telah bergabung ke ruang diskusi.');
        await loadRooms();
      } else {
        showToast(language === 'en' ? 'Invitation rejected.' : 'Undangan ditolak.');
      }
    } catch (err) {
      showToast(err?.response?.data?.detail || (language === 'en' ? 'Failed to process invitation.' : 'Gagal memproses undangan.'));
    } finally {
      setRespondingId(null);
    }
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (roomMenuRef.current && !roomMenuRef.current.contains(e.target)) {
        setActiveRoomMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleConfirmArchiveRoom = async () => {
    if (!archiveConfirmRoom) return;
    const { id } = archiveConfirmRoom;
    try {
      await collabApi.archiveRoom(id, true);
      setRooms((prev) => prev.filter((r) => r.id !== id));
      if (roomId === id) {
        navigate('/collab');
      }
      showToast(language === 'en' ? 'Discussion room archived successfully.' : 'Ruang diskusi berhasil diarsipkan.');
    } catch (err) {
      console.error('Gagal mengarsipkan ruangan:', err);
      showToast(language === 'en' ? 'Failed to archive discussion room.' : 'Gagal mengarsipkan ruangan.');
    } finally {
      setArchiveConfirmRoom(null);
    }
  };

  const handleDeleteRoom = async () => {
    if (!deleteConfirmRoom) return;
    const { id } = deleteConfirmRoom;
    try {
      await collabApi.deleteRoom(id);
      setRooms((prev) => prev.filter((r) => r.id !== id));
      if (roomId === id) {
        navigate('/collab');
      }
      showToast(language === 'en' ? 'Discussion room permanently deleted.' : 'Ruang diskusi berhasil dihapus permanen.');
    } catch (err) {
      console.error('Gagal menghapus ruangan:', err);
      showToast(language === 'en' ? 'Failed to delete discussion room.' : 'Gagal menghapus ruangan.');
    } finally {
      setDeleteConfirmRoom(null);
    }
  };

  const handleSaveRename = async (e) => {
    if (e) e.preventDefault();
    if (!renameModalData || !renameModalData.name.trim()) return;
    try {
      await collabApi.renameRoom(renameModalData.id, renameModalData.name.trim(), renameModalData.topic?.trim() || null);
      setRooms((prev) =>
        prev.map((r) => (r.id === renameModalData.id ? { ...r, name: renameModalData.name.trim(), topic: renameModalData.topic?.trim() || r.topic } : r))
      );
      if (roomDetail && roomDetail.id === renameModalData.id) {
        setRoomDetail((prev) => ({
          ...prev,
          name: renameModalData.name.trim(),
          topic: renameModalData.topic?.trim() || prev.topic
        }));
      }
      showToast(language === 'en' ? 'Discussion room renamed successfully.' : 'Nama ruang diskusi berhasil diperbarui.');
      setRenameModalData(null);
    } catch (err) {
      console.error('Gagal mengubah nama ruangan:', err);
      showToast(language === 'en' ? 'Failed to rename discussion room.' : 'Gagal mengubah nama ruangan.');
    }
  };

  // Load Rooms list & pending invitations
  const loadRooms = useCallback(async () => {
    try {
      setIsLoadingRooms(true);
      const [list] = await Promise.all([
        collabApi.getMyRooms(),
        fetchInvitations()
      ]);
      setRooms(list);
    } catch (err) {
      console.error('Failed to load collab rooms:', err);
    } finally {
      setIsLoadingRooms(false);
    }
  }, [fetchInvitations]);

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
          collabApi.getMessages(roomId, 200)
        ]);

        if (isMounted) {
          setRoomDetail(detail);
          setDocumentContent(detail.document_content || '');
          setMessages(msgs);
          // Tandai ruangan sudah dibaca saat user membuka ruangan
          collabApi.markRoomRead(roomId).then(() => {
            useCollabStore.getState().fetchUnreadCount();
          }).catch(() => {});
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

  // ── Auto-close Collab Pad & Document Studio saat beralih ruangan ──
  useEffect(() => {
    setIsPadOpen(false);
    useDocWriterStore.getState().closeWriter();
    useDocWriterStore.getState().setContext(null, roomId || null);
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

  // State Scroll to Bottom (Button To Bottom identik dengan chat utama)
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const messagesContainerRef = useRef(null);

  const handleAtBottomChange = useCallback((isAtBottom) => {
    setShowScrollBottom((prev) => (prev === !isAtBottom ? prev : !isAtBottom));
  }, []);

  // SSE Stream Event Handlers
  const handleNewMessage = useCallback((msg) => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === msg.id)) return prev;
      return [...prev, msg];
    });
    // Tandai langsung sudah dibaca jika pengguna sedang berada di ruangan ini
    if (roomId) {
      collabApi.markRoomRead(roomId).then(() => {
        useCollabStore.getState().fetchUnreadCount();
      }).catch(() => {});
    }
  }, [roomId]);

  const handleCakraStreamStart = useCallback((payload) => {
    setStreamingCakra({
      id: payload.message_id,
      sender_type: 'CAKRA',
      sender_name: 'CAKRA AI Teammate',
      message_text: '',
      interjection_type: payload.interjection_type || 'EXPLICIT_MENTION',
      created_at: new Date().toISOString()
    });
    // Standarisasi SSE: hilangkan titik di akhir karena animasi titik (...) sudah dihandle di FE
    const initialPhase = (payload.thinking_phase || 'CAKRA sedang berpikir').replace(/\.+$/, '').trim();
    setCakraThinkingPhase(initialPhase);
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
    // Berpikir dulu baru mengetik: saat chunk teks mulai dialirkan, beralih ke sedang mengetik
    setCakraThinkingPhase('CAKRA sedang mengetik');
  }, []);

  const handleCakraThinkingPhase = useCallback((payload) => {
    if (payload?.thinking_phase) {
      setCakraThinkingPhase(payload.thinking_phase.replace(/\.+$/, '').trim());
    }
  }, []);

  const handleCakraStreamEnd = useCallback((payload) => {
    setStreamingCakra(null);
    setCakraThinkingPhase('');
    if (!payload?.aborted && payload?.message) {
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

  const handleAutoNoteAdded = useCallback((payload) => {
    if (payload?.message_id) {
      setAutoNotedMessageIds((prev) => new Set(prev).add(payload.message_id));
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
    onMessageEdited: handleMessageEdited,
    onTyping: handleTyping,
    onDocumentUpdated: handleDocumentUpdated,
    onMembersUpdated: handleMembersUpdated,
    onAutoNoteAdded: handleAutoNoteAdded,
    onCakraStreamStart: handleCakraStreamStart,
    onCakraStreamChunk: handleCakraStreamChunk,
    onCakraStreamEnd: handleCakraStreamEnd,
    onCakraThinkingPhase: handleCakraThinkingPhase
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
      alert(language === 'en' ? 'Failed to send message to discussion room.' : 'Gagal mengirim pesan ke ruang diskusi.');
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
      alert(language === 'en' ? 'Failed to save document changes.' : 'Gagal menyimpan perubahan draf dokumen.');
    } finally {
      setIsSavingDoc(false);
    }
  };

  // Action: Tambahkan poin/respons ke Document Pad secara aman & atomic di backend
  const handleApplyToDocument = async (text, senderName) => {
    if (!roomId || !text?.trim()) return;
    try {
      setIsSavingDoc(true);
      const res = await collabApi.appendToDocument(roomId, text.trim(), senderName);
      if (res?.document_content) {
        setDocumentContent(res.document_content);
      }
      setIsPadOpen(true);
      if (res?.status === 'already_exists') {
        showToast(language === 'en' ? 'This point is already recorded in Team Notes.' : 'Poin ini sudah tercatat di dalam Catatan Tim.');
      } else {
        showToast(language === 'en' ? 'Successfully added to Team Notes.' : 'Poin berhasil ditambahkan ke Catatan Tim.');
      }
    } catch (err) {
      console.error('Failed to append to document:', err);
      alert(language === 'en' ? 'Failed to append to Team Notes.' : 'Gagal menambahkan ke Catatan Tim.');
    } finally {
      setIsSavingDoc(false);
    }
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
      alert((language === 'en' ? 'Failed to generate automatic minutes: ' : 'Gagal menyusun notulensi otomatis: ') + (err.response?.data?.detail || err.message));
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
                  <span>{t.title || 'Diskusi Tim'}</span>
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
                  placeholder={t.searchPlaceholder || "Cari ruang diskusi..."}
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
                <span>{t.createRoom || "Buat Ruang Diskusi"}</span>
              </button>
            </div>
          </div>

          {/* Body Lobby */}
          <div className="flex-1 overflow-y-auto p-6 sm:p-10 custom-scrollbar">
            {isLoadingRooms ? (
              <div className="h-full flex items-center justify-center" style={{ color: secondaryTextColor }}>
                <Loader2 size={24} className="animate-spin text-teal-400" />
              </div>
            ) : (
              <div className="max-w-6xl mx-auto space-y-8">
                {/* ── SEKSI UNDANGAN DISKUSI TIM PENDING ── */}
                {invitations && invitations.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                      <h2 className="text-xs font-bold uppercase tracking-wider text-rose-400">
                        {t.invitationsTitle || 'Undangan Diskusi Tim'} ({invitations.length})
                      </h2>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {invitations.map((inv) => (
                        <div
                          key={inv.room_id}
                          className="border rounded-2xl p-5 shadow-lg flex flex-col justify-between transition-all relative overflow-hidden"
                          style={{
                            background: darkMode ? '#1c1c1f' : '#ffffff',
                            borderColor: darkMode ? 'rgba(244, 63, 94, 0.3)' : 'rgba(244, 63, 94, 0.4)'
                          }}
                        >
                          <div className="absolute top-0 right-0 left-0 h-1 bg-gradient-to-r from-rose-500 via-pink-500 to-teal-400" />
                          <div>
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <h3 className="font-bold text-sm line-clamp-1" style={{ color: textColor }}>
                                {inv.room_name}
                              </h3>
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 font-semibold border border-rose-500/20 shrink-0">
                                {t.newInvitationBadge || 'Undangan Baru'}
                              </span>
                            </div>

                            <p className="text-xs line-clamp-2 mb-3 leading-relaxed" style={{ color: secondaryTextColor }}>
                              {inv.room_topic || t.defaultTopic || 'Ruang diskusi dan koordinasi tim.'}
                            </p>

                            {/* Inviter Info */}
                            <div className="flex items-center gap-2.5 py-2 px-3 rounded-xl border mb-4" style={{ background: darkMode ? '#161618' : '#f9fafb', borderColor: borderColor }}>
                              <CollabAvatar
                                npp={inv.invited_by}
                                name={inv.inviter_name}
                                photoUrl={inv.inviter_photo_url}
                                size="w-8 h-8"
                              />
                              <div className="min-w-0 flex-1">
                                <p className="text-[11px] font-semibold truncate" style={{ color: textColor }}>
                                  {inv.inviter_name}
                                </p>
                                <p className="text-[10px] truncate" style={{ color: secondaryTextColor }}>
                                  {inv.inviter_divisi || 'PT Pindad'} • {inv.member_count || 1} {t.membersCount || 'Anggota'}
                                </p>
                              </div>
                            </div>
                          </div>

                          {/* Action Buttons */}
                          <div className="pt-2 border-t flex items-center gap-2" style={{ borderColor: subtleBorder }}>
                            <button
                              type="button"
                              disabled={respondingId === inv.room_id}
                              onClick={() => handleRespondInvitation(inv.room_id, 'reject')}
                              className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold border transition-all hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 flex items-center justify-center gap-1.5"
                              style={{ borderColor: borderColor, color: secondaryTextColor }}
                            >
                              <X size={14} />
                              <span>{t.reject || 'Tolak'}</span>
                            </button>

                            <button
                              type="button"
                              disabled={respondingId === inv.room_id}
                              onClick={() => handleRespondInvitation(inv.room_id, 'accept')}
                              className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white shadow-md hover:scale-[1.02] transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
                            >
                              {respondingId === inv.room_id ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : (
                                <Check size={14} />
                              )}
                              <span>{t.accept || 'Terima'}</span>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── SEKSI RUANG DISKUSI ANDA ── */}
                {filteredRooms.length === 0 ? (
                  <div className="py-12 flex flex-col items-center justify-center text-center max-w-md mx-auto">
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
                      {t.startDiscussionTitle || 'Mulai Diskusi Tim bersama Rekan & CAKRA'}
                    </h2>

                    <p className="text-xs sm:text-sm leading-relaxed mb-6" style={{ color: secondaryTextColor }}>
                      {t.startDiscussionDesc || 'Buat ruang kolaborasi untuk membahas proyek, koordinasi kerja tim, brainstorming ide, atau pemecahan masalah bersama rekan kerja dan CAKRA AI Teammate.'}
                    </p>

                    <button
                      onClick={() => setIsCreateOpen(true)}
                      className="px-5 py-2.5 rounded-xl font-semibold text-xs transition-all shadow-md hover:scale-[1.02] bg-teal-600 hover:bg-teal-500 text-white"
                    >
                      {t.startDiscussionBtn || 'Buat Ruang Diskusi Baru'}
                    </button>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-xs font-bold uppercase tracking-wider" style={{ color: secondaryTextColor }}>
                        {t.yourRooms || 'Ruang Diskusi Anda'} ({filteredRooms.length})
                      </h2>
                    </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredRooms.map((room) => (
                    <div
                      key={room.id}
                      onClick={() => navigate(`/collab/${room.id}`)}
                      className={`group border rounded-2xl p-5 cursor-pointer transition-all duration-200 shadow-md flex flex-col justify-between hover:border-teal-500 relative ${
                        room.unread_count > 0 ? 'border-teal-500/40 shadow-teal-950/20' : ''
                      }`}
                      style={{
                        background: cardBg,
                        borderColor: room.unread_count > 0 ? 'rgba(20, 184, 166, 0.4)' : borderColor
                      }}
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h3
                            className={`text-sm group-hover:text-teal-400 transition-colors line-clamp-1 ${
                              room.unread_count > 0 ? 'font-black text-teal-300' : 'font-bold'
                            }`}
                            style={{ color: room.unread_count > 0 ? undefined : textColor }}
                          >
                            {room.name}
                          </h3>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {room.unread_count > 0 && (
                              <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-teal-500/15 text-teal-300 font-bold border border-teal-500/30 shrink-0 shadow-sm animate-pulse">
                                <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
                                {room.unread_count} {t.newMessagesBadge || 'baru'}
                              </span>
                            )}
                            <span
                              className="text-[10px] px-2 py-0.5 rounded-full border shrink-0 font-medium"
                              style={{
                                background: darkMode ? '#222226' : '#f3f4f6',
                                borderColor: borderColor,
                                color: secondaryTextColor
                              }}
                            >
                              {room.member_count || 1} {t.membersCount || 'Anggota'}
                            </span>

                            {/* 3-dots actions dropdown */}
                            <div className="relative">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActiveRoomMenuId(activeRoomMenuId === room.id ? null : room.id);
                                }}
                                className="p-1 rounded-lg transition-colors hover:bg-black/10 dark:hover:bg-white/10"
                                style={{ color: secondaryTextColor }}
                                title={t.roomOptions || "Menu opsi ruangan"}
                              >
                                <MoreVertical size={14} />
                              </button>
                              {activeRoomMenuId === room.id && (
                                <div
                                  ref={roomMenuRef}
                                  onClick={(e) => e.stopPropagation()}
                                  className="absolute right-0 top-7 w-36 rounded-xl border shadow-xl py-1 z-30 text-xs"
                                  style={{
                                    background: darkMode ? '#1f1f23' : '#ffffff',
                                    borderColor: borderColor
                                  }}
                                >
                                  <button
                                    onClick={() => {
                                      setActiveRoomMenuId(null);
                                      setRenameModalData({ id: room.id, name: room.name, topic: room.topic || '' });
                                    }}
                                    className="w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                                    style={{ color: textColor }}
                                  >
                                    <span>{t.rename || 'Ubah Nama'}</span>
                                    <Edit2 size={13} className="opacity-60" />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setActiveRoomMenuId(null);
                                      setArchiveConfirmRoom({ id: room.id, name: room.name });
                                    }}
                                    className="w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                                    style={{ color: textColor }}
                                  >
                                    <span>{t.archive || 'Arsipkan'}</span>
                                    <Archive size={13} className="opacity-60" />
                                  </button>
                                  <button
                                    onClick={() => {
                                      setActiveRoomMenuId(null);
                                      setDeleteConfirmRoom({ id: room.id, name: room.name });
                                    }}
                                    className="w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-red-500/10 text-red-500 font-medium transition-colors"
                                  >
                                    <span>{t.delete || 'Hapus'}</span>
                                    <Trash2 size={13} />
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>

                        {room.last_message?.message_text ? (
                          <p
                            className={`text-xs line-clamp-1 mb-4 leading-relaxed ${
                              room.unread_count > 0 ? 'font-medium text-teal-300/90' : ''
                            }`}
                            style={{ color: room.unread_count > 0 ? undefined : secondaryTextColor }}
                          >
                            <span className="opacity-75 font-semibold">{room.last_message.sender_name}: </span>
                            {room.last_message.message_text}
                          </p>
                        ) : (
                          <p
                            className="text-xs line-clamp-2 mb-4 leading-relaxed"
                            style={{ color: secondaryTextColor }}
                          >
                            {room.topic || t.defaultTopic || 'Ruang diskusi dan kolaborasi tim.'}
                          </p>
                        )}
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
                          {t.cakraActive || 'CAKRA Aktif'}
                        </span>
                        <span className="text-teal-400 font-medium group-hover:translate-x-1 transition-transform">
                          {t.openRoom || 'Buka Ruangan →'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
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
            <div className="flex items-center gap-2 min-w-0">







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
              <button
                type="button"
                onClick={() => setShowMembersModal(true)}
                className="flex -space-x-2 overflow-hidden items-center mr-1 p-1 rounded-xl hover:bg-white/5 transition-colors cursor-pointer"
                title={t.viewMembersTitle}
              >
                {roomDetail?.members?.slice(0, 4).map((m) => (
                  <CollabAvatar
                    key={m.npp}
                    npp={m.npp}
                    name={m.name}
                    photoUrl={m.profile_photo_url}
                    size="w-7 h-7"
                    className="inline-block ring-2 ring-neutral-900"
                    title={`${m.name} (${m.divisi || 'PT Pindad'}) - ${m.status}`}
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
              </button>

              {/* Undang Rekan */}
              <button
                onClick={() => setIsInviteOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-colors"
                style={{
                  background: darkMode ? '#1e1e20' : '#f3f4f6',
                  borderColor: borderColor,
                  color: textColor
                }}
                title={t.inviteColleagueTitle}
              >
                <UserPlus size={14} className="text-teal-400" />
                <span className="hidden sm:inline">{t.invite}</span>
              </button>

              {/* Toggle Document Writer & Editor (Word/SKEP/SE) */}
              {!isGuest && hasAiTriggeredDocWriter && (
                <button
                  type="button"
                  onClick={toggleDocWriter}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    isDocWriterOpen
                      ? 'bg-sky-500/20 text-sky-300 border-sky-500/40 shadow-sm'
                      : 'hover:bg-white/5'
                  }`}
                  style={!isDocWriterOpen ? {
                    background: darkMode ? '#1e1e20' : '#f3f4f6',
                    borderColor: borderColor,
                    color: textColor
                  } : {}}
                  title="Buka Dokumen Writer (Word/SKEP/SE)"
                >
                  <FileEdit size={14} className="text-sky-400" />
                  <span className="hidden sm:inline">Doc Writer</span>
                </button>
              )}

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
                title={t.panelNotesTitle}
              >
                <FileText size={14} className="text-teal-400" />
                <span className="hidden sm:inline">{t.teamNotes}</span>
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
                  title={t.panelArtifactsTitle}
                >
                  <Layers size={14} className={showRightSidebar ? 'text-indigo-400' : 'text-indigo-400/80'} />
                  <span className="hidden sm:inline">{t.artifacts}</span>
                </button>
              )}

              {/* Menu Opsi Ruangan */}
              <div className="relative">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveRoomMenuId(activeRoomMenuId === 'header' ? null : 'header');
                  }}
                  className="p-1.5 rounded-xl border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                  style={{
                    borderColor: borderColor,
                    color: textColor
                  }}
                  title={t.roomOptions}
                >
                  <MoreVertical size={14} />
                </button>
                {activeRoomMenuId === 'header' && roomDetail && (
                  <div
                    ref={roomMenuRef}
                    onClick={(e) => e.stopPropagation()}
                    className="absolute right-0 top-9 w-36 rounded-xl border shadow-xl py-1 z-30 text-xs"
                    style={{
                      background: darkMode ? '#1f1f23' : '#ffffff',
                      borderColor: borderColor
                    }}
                  >
                    <button
                      onClick={() => {
                        setActiveRoomMenuId(null);
                        setRenameModalData({ id: roomDetail.id, name: roomDetail.name, topic: roomDetail.topic || '' });
                      }}
                      className="w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                      style={{ color: textColor }}
                    >
                      <span>{t.rename}</span>
                      <Edit2 size={13} className="opacity-60" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveRoomMenuId(null);
                        setArchiveConfirmRoom({ id: roomDetail.id, name: roomDetail.name });
                      }}
                      className="w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                      style={{ color: textColor }}
                    >
                      <span>{t.archive}</span>
                      <Archive size={13} className="opacity-60" />
                    </button>
                    <button
                      onClick={() => {
                        setActiveRoomMenuId(null);
                        setDeleteConfirmRoom({ id: roomDetail.id, name: roomDetail.name });
                      }}
                      className="w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-red-500/10 text-red-500 font-medium transition-colors"
                    >
                      <span>{t.delete}</span>
                      <Trash2 size={13} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Area Utama: Chat + Document Pad (Kanan) */}
          <div className="flex-1 flex min-h-0 overflow-hidden" style={{ background: pageBg }}>
            {!isGuest && isDocWriterOpen && (
              <DocWriterWorkspace
                darkMode={darkMode}
                theme={theme}
                isMobile={isMobile}
                sessionId={null}
                roomId={roomId}
              />
            )}
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
                  autoNotedMessageIds={autoNotedMessageIds}
                  onApplyToDocument={handleApplyToDocument}
                  setPreviewImage={setPreviewImage}
                  onOpenArtifact={onOpenArtifact}
                  onEditMessage={handleEditMessage}
                  scrollContainerRef={messagesContainerRef}
                  onAtBottomChange={handleAtBottomChange}
                />
              )}

              {/* Input Chat Tim Persis ChatPage Utama (Kapsul Melayang Elevated, Plus, Attachment, Voice, Send, Disclaimer) */}
              <CollabChatInputArea
                roomId={roomId}
                onSendMessage={handleSendMessage}
                onTypingChange={handleTypingChange}
                members={roomDetail?.members || []}
                isSending={false}
                darkMode={darkMode}
                theme={theme}
                isMobile={isMobile}
                language={language}
                showScrollBottom={showScrollBottom}
                messages={messages}
                messagesContainerRef={messagesContainerRef}
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
                  language={language}
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
        language={language}
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
          language={language}
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

      {/* ✏️ MODAL UBAH NAMA RUANGAN */}
      {renameModalData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div
            className="w-full max-w-md rounded-2xl border p-6 shadow-2xl space-y-4"
            style={{
              background: darkMode ? '#18181b' : '#ffffff',
              borderColor: borderColor
            }}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-base flex items-center gap-2" style={{ color: textColor }}>
                <Edit2 size={16} className="text-teal-400" />
                <span>{t.renameModalTitle}</span>
              </h3>
              <button
                onClick={() => setRenameModalData(null)}
                className="p-1 rounded-lg hover:bg-black/10 dark:hover:bg-white/10"
                style={{ color: secondaryTextColor }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveRename} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: secondaryTextColor }}>
                  {t.renameRoomName}
                </label>
                <input
                  type="text"
                  required
                  value={renameModalData.name}
                  onChange={(e) => setRenameModalData({ ...renameModalData, name: e.target.value })}
                  placeholder={t.renameRoomNamePlaceholder}
                  className="w-full px-3.5 py-2.5 rounded-xl border text-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all"
                  style={{
                    background: darkMode ? '#222226' : '#f9fafb',
                    borderColor: borderColor,
                    color: textColor
                  }}
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: secondaryTextColor }}>
                  {t.renameTopic}
                </label>
                <textarea
                  rows={3}
                  value={renameModalData.topic || ''}
                  onChange={(e) => setRenameModalData({ ...renameModalData, topic: e.target.value })}
                  placeholder={t.renameTopicPlaceholder}
                  className="w-full px-3.5 py-2.5 rounded-xl border text-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 resize-none transition-all"
                  style={{
                    background: darkMode ? '#222226' : '#f9fafb',
                    borderColor: borderColor,
                    color: textColor
                  }}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRenameModalData(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                  style={{
                    borderColor: borderColor,
                    color: secondaryTextColor
                  }}
                >
                  {t.cancel}
                </button>
                <button
                  type="submit"
                  disabled={!renameModalData.name.trim()}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-teal-500 hover:bg-teal-600 text-white transition-colors disabled:opacity-50"
                >
                  {t.saveChanges}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 📦 MODAL KONFIRMASI ARSIP RUANGAN */}
      {archiveConfirmRoom && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div
            className="w-full max-w-sm rounded-2xl border p-6 shadow-2xl space-y-4"
            style={{
              background: darkMode ? '#18181b' : '#ffffff',
              borderColor: borderColor
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0">
                <Archive size={20} />
              </div>
              <div>
                <h3 className="font-bold text-sm" style={{ color: textColor }}>
                  {t.archiveModalTitle}
                </h3>
                <p className="text-xs" style={{ color: secondaryTextColor }}>
                  {t.archiveModalSub}
                </p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: secondaryTextColor }}>
              {t.archiveModalDesc} <strong style={{ color: textColor }}>"{archiveConfirmRoom.name}"</strong>?
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setArchiveConfirmRoom(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                style={{
                  borderColor: borderColor,
                  color: secondaryTextColor
                }}
              >
                {t.cancel}
              </button>
              <button
                onClick={handleConfirmArchiveRoom}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white transition-colors shadow-md"
              >
                {t.yesArchive}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 🗑️ MODAL KONFIRMASI HAPUS RUANGAN */}
      {deleteConfirmRoom && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div
            className="w-full max-w-sm rounded-2xl border p-6 shadow-2xl space-y-4"
            style={{
              background: darkMode ? '#18181b' : '#ffffff',
              borderColor: borderColor
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 text-red-500 flex items-center justify-center shrink-0">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className="font-bold text-sm" style={{ color: textColor }}>
                  {t.deleteModalTitle}
                </h3>
                <p className="text-xs" style={{ color: secondaryTextColor }}>
                  {t.deleteModalSub}
                </p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: secondaryTextColor }}>
              {t.deleteModalDesc} <strong style={{ color: textColor }}>"{deleteConfirmRoom.name}"</strong> {t.deleteModalWarning}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDeleteConfirmRoom(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                style={{
                  borderColor: borderColor,
                  color: secondaryTextColor
                }}
              >
                {t.cancel}
              </button>
              <button
                onClick={handleDeleteRoom}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-red-600 hover:bg-red-700 text-white transition-colors shadow-md"
              >
                {t.yesDelete}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 👥 MODAL DAFTAR ANGGOTA TIM */}
      {showMembersModal && roomDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div
            className="w-full max-w-md border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
            style={{
              background: darkMode ? '#151517' : '#ffffff',
              borderColor: borderColor,
              color: textColor
            }}
          >
            <div
              className="px-5 py-4 border-b flex items-center justify-between"
              style={{
                background: darkMode ? '#18181b' : '#f9fafb',
                borderColor: borderColor
              }}
            >
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
                  <Users2 size={16} />
                </div>
                <h2 className="text-sm font-bold" style={{ color: textColor }}>
                  {t.membersModalTitle} ({roomDetail.members?.length || 0})
                </h2>
              </div>
              <button
                onClick={() => setShowMembersModal(false)}
                className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                style={{ color: secondaryTextColor }}
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-4 flex-1 overflow-y-auto divide-y" style={{ borderColor: subtleBorder }}>
              {roomDetail.members?.map((m) => {
                const isAccepted = m.status === 'ACCEPTED';
                const isPending = m.status === 'PENDING';
                const isRejected = m.status === 'REJECTED';

                return (
                  <div key={m.npp} className="py-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <CollabAvatar
                        npp={m.npp}
                        name={m.name}
                        photoUrl={m.profile_photo_url}
                        size="w-8 h-8"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <p className="text-xs font-semibold truncate" style={{ color: textColor }}>
                            {m.name}
                          </p>
                          {m.role_in_room === 'OWNER' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold uppercase">
                              Owner
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] truncate" style={{ color: secondaryTextColor }}>
                          {m.divisi} • NPP: {m.npp}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      {isAccepted && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          {t.statusJoined}
                        </span>
                      )}
                      {isPending && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                          {t.statusPending}
                        </span>
                      )}
                      {isRejected && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                          {t.statusRejected}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div
              className="px-5 py-3 border-t flex items-center justify-between"
              style={{
                background: darkMode ? '#18181b' : '#f9fafb',
                borderColor: borderColor
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setShowMembersModal(false);
                  setIsInviteOpen(true);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white transition-all shadow-sm"
              >
                <UserPlus size={13} />
                <span>{t.inviteOther}</span>
              </button>
              <button
                type="button"
                onClick={() => setShowMembersModal(false)}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold hover:bg-white/5 transition-colors"
                style={{ color: secondaryTextColor }}
              >
                {t.close}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 🔔 FLOATING TOAST NOTIFICATION */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-2xl shadow-2xl border backdrop-blur-md animate-fade-in text-xs font-semibold"
          style={{
            background: darkMode ? 'rgba(24, 24, 27, 0.95)' : 'rgba(255, 255, 255, 0.95)',
            borderColor: borderColor,
            color: textColor
          }}
        >
          <Sparkles size={15} className="text-teal-400 shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}
    </div>
  );
};

export default CollabWorkspace;
