import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Archive,
  MessageSquare,
  Users2,
  RotateCcw,
  Trash2,
  Search,
  ExternalLink,
  Menu,
  Clock,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  FolderArchive
} from 'lucide-react';
import { getArchivedSessions, archiveSession, deleteSession } from '../../services/endpoints';
import { collabApi } from '../collab/services/collabApi';
import { useChatStore } from '../../stores/chatStore';
import { translations } from '../../utils/translations';

export default function ArchiveTab({
  theme,
  darkMode,
  userData,
  language = 'id',
  isMobile,
  toggleSidebar,
  setChatHistory
}) {
  const navigate = useNavigate();
  const fetchChatHistory = useChatStore((state) => state.fetchChatHistory);
  const t = translations[language]?.archive || translations.id.archive;

  const [activeTab, setActiveTab] = useState('chats'); // 'chats' | 'collab'
  const [searchQuery, setSearchQuery] = useState('');
  
  // Data states
  const [archivedChats, setArchivedChats] = useState([]);
  const [archivedRooms, setArchivedRooms] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  // Modal konfirmasi hapus & pulihkan
  const [deleteTarget, setDeleteTarget] = useState(null); // { type: 'chat' | 'room', id, title }
  const [restoreTarget, setRestoreTarget] = useState(null); // { type: 'chat' | 'room', id, title }
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // 1. Fetch Archived Chats & Rooms
  const loadArchivedData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [chats, rooms] = await Promise.all([
        getArchivedSessions().catch(() => []),
        collabApi.getArchivedRooms().catch(() => [])
      ]);
      setArchivedChats(chats || []);
      setArchivedRooms(rooms || []);
    } catch (err) {
      console.error('Error loading archive data:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadArchivedData();
  }, [loadArchivedData]);

  // 2. Unarchive / Restore Chat
  const handleRestoreChat = async (sessionUuid) => {
    try {
      setActionLoadingId(sessionUuid);
      await archiveSession(sessionUuid, false);
      setArchivedChats((prev) => prev.filter((c) => c.session_uuid !== sessionUuid));
      
      const npp = userData?.npp || userData?.username;
      if (npp && fetchChatHistory) {
        const res = await fetchChatHistory(npp);
        if (res?.status === "success" && setChatHistory) {
          setChatHistory(res.data);
        }
      }
      window.dispatchEvent(new CustomEvent("cakra-refresh-chat-history"));
      showToast(t.chatRestoreSuccess || 'Obrolan berhasil dipulihkan ke riwayat aktif.');
    } catch (err) {
      console.error('Gagal memulihkan obrolan:', err);
      showToast(t.chatRestoreFail || 'Gagal memulihkan obrolan.');
    } finally {
      setActionLoadingId(null);
    }
  };

  // 3. Unarchive / Restore Collab Room
  const handleRestoreRoom = async (roomId) => {
    try {
      setActionLoadingId(roomId);
      await collabApi.archiveRoom(roomId, false);
      setArchivedRooms((prev) => prev.filter((r) => r.id !== roomId));
      window.dispatchEvent(new CustomEvent("cakra-refresh-collab-rooms"));
      showToast(t.roomRestoreSuccess || 'Ruang diskusi berhasil dipulihkan.');
    } catch (err) {
      console.error('Gagal memulihkan ruang diskusi:', err);
      showToast(t.roomRestoreFail || 'Gagal memulihkan ruang diskusi.');
    } finally {
      setActionLoadingId(null);
    }
  };

  // 3b. Confirm Restore
  const handleConfirmRestore = async () => {
    if (!restoreTarget) return;
    const { type, id } = restoreTarget;
    if (type === 'chat') {
      await handleRestoreChat(id);
    } else {
      await handleRestoreRoom(id);
    }
    setRestoreTarget(null);
  };

  // 4. Confirm Delete Permanent
  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    const { type, id } = deleteTarget;
    try {
      setActionLoadingId(id);
      if (type === 'chat') {
        await deleteSession(id);
        setArchivedChats((prev) => prev.filter((c) => c.session_uuid !== id));
        showToast(t.chatDeleteSuccess || 'Obrolan berhasil dihapus secara permanen.');
      } else {
        await collabApi.deleteRoom(id);
        setArchivedRooms((prev) => prev.filter((r) => r.id !== id));
        showToast(t.roomDeleteSuccess || 'Ruang diskusi tim berhasil dihapus permanen.');
      }
    } catch (err) {
      console.error('Gagal menghapus item permanen:', err);
      showToast(t.chatDeleteFail || 'Gagal menghapus item.');
    } finally {
      setActionLoadingId(null);
      setDeleteTarget(null);
    }
  };

  // Filtered lists
  const filteredChats = useMemo(() => {
    if (!searchQuery.trim()) return archivedChats;
    const q = searchQuery.toLowerCase();
    return archivedChats.filter((c) => (c.judul || '').toLowerCase().includes(q));
  }, [archivedChats, searchQuery]);

  const filteredRooms = useMemo(() => {
    if (!searchQuery.trim()) return archivedRooms;
    const q = searchQuery.toLowerCase();
    return archivedRooms.filter(
      (r) => (r.name || '').toLowerCase().includes(q) || (r.topic || '').toLowerCase().includes(q)
    );
  }, [archivedRooms, searchQuery]);

  // Styling helpers
  const pageBg = darkMode ? '#121214' : '#f9fafb';
  const cardBg = darkMode ? '#1a1a1d' : '#ffffff';
  const borderColor = darkMode ? '#2d2d32' : '#e5e7eb';
  const textColor = darkMode ? '#f3f4f6' : '#111827';
  const secondaryTextColor = darkMode ? '#9ca3af' : '#6b7280';

  return (
    <div className="h-full flex flex-col overflow-hidden select-none" style={{ background: pageBg }}>
      {/* ── TOP HEADER ── */}
      <div
        className="h-16 px-6 flex items-center justify-between shrink-0 border-b"
        style={{
          background: darkMode ? '#17171a' : '#ffffff',
          borderColor: borderColor
        }}
      >
        <div className="flex items-center gap-3">
          {isMobile && (
            <button
              onClick={toggleSidebar}
              className="p-2 rounded-xl transition-colors hover:bg-black/5 dark:hover:bg-white/5"
              style={{ color: textColor }}
            >
              <Menu size={20} />
            </button>
          )}
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-amber-500/10 text-amber-500">
            <Archive size={20} strokeWidth={2.2} />
          </div>
          <div>
            <h1 className="text-base font-bold flex items-center gap-2" style={{ color: textColor }}>
              {t.title || 'Pusat Arsip'}
            </h1>
            <p className="text-[11px]" style={{ color: secondaryTextColor }}>
              {t.subtitle || 'Kelola riwayat obrolan dan ruang diskusi tim yang disimpan'}
            </p>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative w-48 sm:w-64">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: secondaryTextColor }}
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t.searchPlaceholder || 'Cari dalam arsip...'}
            className="w-full pl-9 pr-3 py-1.5 rounded-xl text-xs border outline-none transition-all"
            style={{
              background: darkMode ? '#1f1f23' : '#f3f4f6',
              borderColor: borderColor,
              color: textColor
            }}
          />
        </div>
      </div>

      {/* ── TABS NAVIGATION ── */}
      <div
        className="px-6 pt-4 pb-2 flex items-center gap-2 border-b shrink-0"
        style={{
          background: darkMode ? '#141416' : '#ffffff',
          borderColor: borderColor
        }}
      >
        <button
          onClick={() => setActiveTab('chats')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'chats'
              ? 'bg-amber-500 text-white shadow-sm'
              : 'hover:bg-black/5 dark:hover:bg-white/5'
          }`}
          style={{ color: activeTab === 'chats' ? '#ffffff' : secondaryTextColor }}
        >
          <MessageSquare size={14} />
          <span>{t.chatsTab || 'Percakapan Chat'}</span>
          <span
            className="text-[10px] px-1.5 py-0.2 rounded-full font-bold"
            style={{
              background: activeTab === 'chats' ? 'rgba(0,0,0,0.2)' : darkMode ? '#26262a' : '#e5e7eb',
              color: activeTab === 'chats' ? '#ffffff' : textColor
            }}
          >
            {archivedChats.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('collab')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'collab'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'hover:bg-black/5 dark:hover:bg-white/5'
          }`}
          style={{ color: activeTab === 'collab' ? '#ffffff' : secondaryTextColor }}
        >
          <Users2 size={14} />
          <span>{t.collabTab || 'Ruang Diskusi Tim'}</span>
          <span
            className="text-[10px] px-1.5 py-0.2 rounded-full font-bold"
            style={{
              background: activeTab === 'collab' ? 'rgba(0,0,0,0.2)' : darkMode ? '#26262a' : '#e5e7eb',
              color: activeTab === 'collab' ? '#ffffff' : textColor
            }}
          >
            {archivedRooms.length}
          </span>
        </button>
      </div>

      {/* ── CONTENT AREA ── */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="h-64 flex flex-col items-center justify-center gap-3">
            <Loader2 size={28} className="animate-spin text-amber-500" />
            <p className="text-xs" style={{ color: secondaryTextColor }}>
              {t.loading || 'Memuat data arsip...'}
            </p>
          </div>
        ) : activeTab === 'chats' ? (
          /* ── TAB 1: ARSIP CHAT ── */
          filteredChats.length === 0 ? (
            <div className="h-80 flex flex-col items-center justify-center text-center max-w-sm mx-auto">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 border"
                style={{
                  background: darkMode ? '#1b1b1e' : '#f3f4f6',
                  borderColor: borderColor
                }}
              >
                <FolderArchive size={28} className="text-amber-500/60" />
              </div>
              <h3 className="font-bold text-sm mb-1" style={{ color: textColor }}>
                {t.noArchivedChats || 'Tidak ada obrolan diarsipkan'}
              </h3>
              <p className="text-xs leading-relaxed" style={{ color: secondaryTextColor }}>
                {searchQuery
                  ? (t.noSearchResults || 'Tidak ditemukan obrolan yang sesuai dengan pencarian Anda.')
                  : (t.noArchivedChatsDesc || 'Anda dapat mengarsipkan percakapan lama dari menu tiga titik di sidebar obrolan.')}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-6xl mx-auto">
              {filteredChats.map((chat) => (
                <div
                  key={chat.session_uuid}
                  className="border rounded-2xl p-4 transition-all duration-200 shadow-sm flex flex-col justify-between hover:shadow-md"
                  style={{
                    background: cardBg,
                    borderColor: borderColor
                  }}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <MessageSquare size={16} className="text-amber-500 shrink-0" />
                        <h4
                          className="font-semibold text-xs truncate"
                          style={{ color: textColor }}
                          title={chat.judul}
                        >
                          {chat.judul || t.untitledChat || 'Obrolan Tanpa Judul'}
                        </h4>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 text-[11px] mb-4" style={{ color: secondaryTextColor }}>
                      <Clock size={12} />
                      <span>
                        {chat.started_at
                          ? new Date(chat.started_at).toLocaleDateString(language === 'en' ? 'en-US' : 'id-ID', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric'
                            })
                          : (t.justNow || 'Baru saja')}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div
                    className="pt-3 border-t flex items-center justify-between gap-2 text-xs"
                    style={{ borderColor: borderColor }}
                  >
                    <button
                      onClick={() => navigate(`/chat/${chat.session_uuid}`)}
                      className="flex items-center gap-1 font-medium hover:underline text-amber-500"
                    >
                      <span>{t.view || 'Lihat'}</span>
                      <ExternalLink size={12} />
                    </button>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() =>
                          setRestoreTarget({
                            type: 'chat',
                            id: chat.session_uuid,
                            title: chat.judul || t.untitledChat || 'Obrolan'
                          })
                        }
                        disabled={actionLoadingId === chat.session_uuid}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium text-[11px] border transition-colors hover:bg-amber-500 hover:text-white"
                        style={{
                          borderColor: borderColor,
                          color: textColor
                        }}
                        title={t.restore || 'Pulihkan'}
                      >
                        <RotateCcw size={12} />
                        <span>{t.restore || 'Pulihkan'}</span>
                      </button>

                      <button
                        onClick={() =>
                          setDeleteTarget({
                            type: 'chat',
                            id: chat.session_uuid,
                            title: chat.judul || t.untitledChat || 'Obrolan'
                          })
                        }
                        className="p-1.5 rounded-lg text-red-500 hover:bg-red-500/10 transition-colors"
                        title={t.delete || 'Hapus'}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          /* ── TAB 2: ARSIP RUANG DISKUSI TIM ── */
          filteredRooms.length === 0 ? (
            <div className="h-80 flex flex-col items-center justify-center text-center max-w-sm mx-auto">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 border"
                style={{
                  background: darkMode ? '#1b1b1e' : '#f3f4f6',
                  borderColor: borderColor
                }}
              >
                <FolderArchive size={28} className="text-teal-500/60" />
              </div>
              <h3 className="font-bold text-sm mb-1" style={{ color: textColor }}>
                {t.noArchivedRooms || 'Tidak ada ruang diskusi diarsipkan'}
              </h3>
              <p className="text-xs leading-relaxed" style={{ color: secondaryTextColor }}>
                {searchQuery
                  ? (t.noSearchResults || 'Tidak ditemukan ruang diskusi yang sesuai dengan pencarian.')
                  : (t.noArchivedRoomsDesc || 'Ruang diskusi yang telah selesai dapat diarsipkan agar tidak memenuhi daftar aktif.')}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-6xl mx-auto">
              {filteredRooms.map((room) => (
                <div
                  key={room.id}
                  className="border rounded-2xl p-5 transition-all duration-200 shadow-sm flex flex-col justify-between hover:shadow-md"
                  style={{
                    background: cardBg,
                    borderColor: borderColor
                  }}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h4
                        className="font-bold text-xs line-clamp-1"
                        style={{ color: textColor }}
                        title={room.name}
                      >
                        {room.name || t.untitledRoom}
                      </h4>
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
                    </div>

                    <p
                      className="text-xs line-clamp-2 mb-4 leading-relaxed"
                      style={{ color: secondaryTextColor }}
                    >
                      {room.topic || (translations[language]?.collab?.defaultTopic || 'Ruang diskusi dan kolaborasi tim.')}
                    </p>
                  </div>

                  {/* Actions */}
                  <div
                    className="pt-3 border-t flex items-center justify-between gap-2 text-xs"
                    style={{ borderColor: borderColor }}
                  >
                    <button
                      onClick={() => navigate(`/collab/${room.id}`)}
                      className="flex items-center gap-1 font-medium hover:underline text-teal-400"
                    >
                      <span>{t.openRoom || 'Buka Ruangan →'}</span>
                      <ExternalLink size={12} />
                    </button>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() =>
                          setRestoreTarget({
                            type: 'room',
                            id: room.id,
                            title: room.name
                          })
                        }
                        disabled={actionLoadingId === room.id}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium text-[11px] border transition-colors hover:bg-teal-600 hover:text-white"
                        style={{
                          borderColor: borderColor,
                          color: textColor
                        }}
                        title={t.restore || 'Pulihkan'}
                      >
                        <RotateCcw size={12} />
                        <span>{t.restore || 'Pulihkan'}</span>
                      </button>

                      <button
                        onClick={() =>
                          setDeleteTarget({
                            type: 'room',
                            id: room.id,
                            title: room.name
                          })
                        }
                        className="p-1.5 rounded-lg text-red-500 hover:bg-red-500/10 transition-colors"
                        title={t.delete || 'Hapus'}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* ── MODAL KONFIRMASI PULIHKAN ── */}
      {restoreTarget && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div
            className="w-full max-w-sm rounded-2xl border p-5 shadow-2xl flex flex-col gap-4 animate-scaleUp"
            style={{
              background: darkMode ? '#1c1c1f' : '#ffffff',
              borderColor: borderColor
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-emerald-500/10 text-emerald-500 shrink-0">
                <RotateCcw size={20} />
              </div>
              <div>
                <h4 className="font-bold text-sm" style={{ color: textColor }}>
                  {t.confirmRestoreTitle || 'Konfirmasi Pemulihan'}
                </h4>
                <p className="text-xs" style={{ color: secondaryTextColor }}>
                  {translations[language]?.collab?.archiveModalSub || 'Dapat dipulihkan kapan saja di menu Arsip.'}
                </p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: secondaryTextColor }}>
              {restoreTarget.type === 'chat'
                ? (t.confirmRestoreChat?.replace('{title}', restoreTarget.title) || `Apakah Anda yakin ingin memulihkan obrolan "${restoreTarget.title}" kembali ke menu aktif?`)
                : (t.confirmRestoreRoom?.replace('{name}', restoreTarget.title) || `Apakah Anda yakin ingin memulihkan ruang diskusi "${restoreTarget.title}" kembali ke menu aktif?`)}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setRestoreTarget(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                style={{
                  borderColor: borderColor,
                  color: textColor
                }}
              >
                {t.cancel || 'Batal'}
              </button>
              <button
                onClick={handleConfirmRestore}
                disabled={actionLoadingId === restoreTarget.id}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-md flex items-center gap-1.5"
              >
                {actionLoadingId === restoreTarget.id && <Loader2 size={12} className="animate-spin" />}
                <span>{t.yesRestore || 'Ya, Pulihkan'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL KONFIRMASI HAPUS PERMANEN ── */}
      {deleteTarget && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div
            className="w-full max-w-sm rounded-2xl border p-5 shadow-2xl flex flex-col gap-4 animate-scaleUp"
            style={{
              background: darkMode ? '#1c1c1f' : '#ffffff',
              borderColor: borderColor
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-red-500/10 text-red-500 shrink-0">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h4 className="font-bold text-sm" style={{ color: textColor }}>
                  {t.confirmDeleteTitle || 'Hapus Permanen?'}
                </h4>
                <p className="text-xs" style={{ color: secondaryTextColor }}>
                  {translations[language]?.collab?.deleteModalSub || 'Tindakan ini permanen dan tidak dapat dibatalkan.'}
                </p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: secondaryTextColor }}>
              {deleteTarget.type === 'chat'
                ? (t.confirmDeleteChat?.replace('{title}', deleteTarget.title) || `Apakah Anda yakin ingin menghapus obrolan "${deleteTarget.title}" secara permanen?`)
                : (t.confirmDeleteRoom?.replace('{name}', deleteTarget.title) || `Apakah Anda yakin ingin menghapus ruang diskusi "${deleteTarget.title}" secara permanen?`)}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                style={{
                  borderColor: borderColor,
                  color: textColor
                }}
              >
                {t.cancel || 'Batal'}
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={actionLoadingId === deleteTarget.id}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-red-600 hover:bg-red-500 text-white transition-all shadow-md flex items-center gap-1.5"
              >
                {actionLoadingId === deleteTarget.id && <Loader2 size={12} className="animate-spin" />}
                <span>{t.yesDelete || 'Ya, Hapus Permanen'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── TOAST NOTIFICATION ── */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-[250] flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-900 text-white border border-white/10 shadow-2xl text-xs animate-slideUp">
          <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
