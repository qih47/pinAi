import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Check, Archive, Trash2, X, MessageSquare, Users2, ArrowUpDown, MoreVertical, Pin, PinOff, Edit2 } from 'lucide-react';
import { formatDistanceToNow, isToday, isYesterday, format } from 'date-fns';
import { id as idLocale, enUS as enLocale } from 'date-fns/locale';
import { collabApi } from '../../collab/services/collabApi';
import { translations } from '../../../utils/translations';

/**
 * Format timestamp into Claude-like relative date string:
 * - Today: "21 hours ago" / "2 hours ago"
 * - Yesterday: "Yesterday"
 * - Same year: "Sep 7"
 * - Older: "Jun 11, 2025"
 */
function formatSessionDate(dateString, language = 'id') {
  if (!dateString) return '';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '';

  const locale = language === 'en' ? enLocale : idLocale;

  if (isToday(date)) {
    return formatDistanceToNow(date, { addSuffix: true, locale });
  }
  if (isYesterday(date)) {
    const yesterdayText = translations[language]?.sidebar?.yesterday;
    return yesterdayText || (language === 'en' ? 'Yesterday' : 'Kemarin');
  }
  const now = new Date();
  if (date.getFullYear() === now.getFullYear()) {
    return format(date, 'MMM d', { locale });
  }
  return format(date, 'MMM d, yyyy', { locale });
}

export default function AllChatsView({
  chatHistory = [],
  setChatHistory,
  currentSessionId,
  onSelectChat,
  onNewChat,
  onClose,
  deleteChat,
  archiveChat,
  pinChat,
  renameChat,
  darkMode = true,
  theme,
  language = 'id',
  userData = null,
  isMobile = false,
  toggleSidebar,
}) {
  const navigate = useNavigate();

  const [collabRooms, setCollabRooms] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState(new Set()); // set of unique_key
  const [sortOrder, setSortOrder] = useState('newest'); // 'newest' | 'oldest'
  const [activeMenuId, setActiveMenuId] = useState(null); // unique_key yang popover titik tiganya aktif
  const [editingKey, setEditingKey] = useState(null);
  const [editTitleValue, setEditTitleValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [itemToDeleteSingle, setItemToDeleteSingle] = useState(null);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [itemToArchiveSingle, setItemToArchiveSingle] = useState(null);

  const menuRef = useRef(null);

  // Ambil daftar Collab rooms saat mount
  useEffect(() => {
    let mounted = true;
    collabApi
      .getMyRooms()
      .then((rooms) => {
        if (mounted && Array.isArray(rooms)) {
          setCollabRooms(rooms);
        }
      })
      .catch((err) => {
        console.warn('Could not fetch collab rooms for AllChatsView:', err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Close popup menu when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Labels i18n from translations.js
  const t = translations[language]?.chatsAndCollabs || translations.id.chatsAndCollabs;
  const labels = {
    title: t.title || 'Chats and collabs',
    searchPlaceholder: t.searchPlaceholder || (language === 'en' ? 'Search chats & collabs...' : 'Cari percakapan & kolaborasi...'),
    searchTooltip: t.searchTooltip || t.searchPlaceholder || (language === 'en' ? 'Search chats & collabs' : 'Cari percakapan & kolaborasi'),
    sortNewest: t.sortNewest || (language === 'en' ? 'Newest to oldest' : 'Terbaru ke terlama'),
    sortOldest: t.sortOldest || (language === 'en' ? 'Oldest to newest' : 'Terlama ke terbaru'),
    select: t.select || (language === 'en' ? 'Select' : 'Pilih'),
    selectAll: t.selectAll || (language === 'en' ? 'Select all' : 'Pilih semua'),
    deselectAll: t.deselectAll || (language === 'en' ? 'Deselect all' : 'Batal pilih'),
    selected: t.selected || (language === 'en' ? 'selected' : 'dipilih'),
    new: t.new || (language === 'en' ? 'New' : 'Baru'),
    archive: t.archive || (language === 'en' ? 'Archive' : 'Arsipkan'),
    delete: t.delete || (language === 'en' ? 'Delete' : 'Hapus'),
    pin: t.pin || (language === 'en' ? 'Pin' : 'Sematkan'),
    unpin: t.unpin || (language === 'en' ? 'Unpin' : 'Lepas sematan'),
    rename: t.rename || (language === 'en' ? 'Rename' : 'Ubah nama'),
    options: t.options || (language === 'en' ? 'Options' : 'Opsi'),
    cancel: t.cancel || (language === 'en' ? 'Cancel' : 'Batal'),
    collabBadge: t.collabBadge || 'Collab',
    emptyTitle: t.emptyTitle || (language === 'en' ? 'No chats or collabs found' : 'Tidak ada percakapan atau kolaborasi'),
    emptyDesc: t.emptyDesc || (language === 'en' ? 'Start a new conversation or team discussion to see it here.' : 'Mulai percakapan atau diskusi tim baru untuk melihatnya di sini.'),
    deleteConfirmTitle: t.deleteConfirmTitle || (language === 'en' ? 'Delete item?' : 'Hapus item?'),
    deleteConfirmDesc: (count) =>
      (t.deleteConfirmDesc || (language === 'en'
        ? 'Are you sure you want to delete {count} item(s)? This action cannot be undone.'
        : 'Apakah Anda yakin ingin menghapus {count} percakapan/diskusi tim? Tindakan ini tidak dapat dibatalkan.'
      )).replace('{count}', count),
    deleting: t.deleting || (language === 'en' ? 'Deleting...' : 'Menghapus...'),
    archiveConfirmTitle: t.archiveConfirmTitle || (language === 'en' ? 'Archive item?' : 'Arsipkan item?'),
    archiveConfirmDesc: (count) =>
      (t.archiveConfirmDesc || (language === 'en'
        ? 'Are you sure you want to archive {count} item(s)? You can restore them anytime from the Archive.'
        : 'Apakah Anda yakin ingin mengarsipkan {count} percakapan/diskusi tim? Anda dapat memulihkannya kapan saja dari menu Arsip.'
      )).replace('{count}', count),
    archiving: t.archiving || (language === 'en' ? 'Archiving...' : 'Mengarsipkan...'),
    untitledChat: t.untitledChat || (language === 'en' ? 'Untitled Conversation' : 'Percakapan Tanpa Judul'),
    untitledCollab: t.untitledCollab || (language === 'en' ? 'Untitled Collab' : 'Ruang Diskusi Tim'),
  };

  // Gabungkan chatHistory dan collabRooms
  const combinedItems = useMemo(() => {
    const chats = Array.isArray(chatHistory)
      ? chatHistory.map((c) => ({
          ...c,
          item_type: 'chat',
          unique_key: `chat_${c.session_uuid}`,
          raw_id: c.session_uuid,
          display_title:
            c.judul ||
            c.title ||
            c.session_title ||
            c.name ||
            labels.untitledChat,
          item_date: c.updated_at || c.created_at || c.started_at,
          is_pinned: Boolean(c.is_pinned),
        }))
      : [];

    const collabs = Array.isArray(collabRooms)
      ? collabRooms.map((r) => ({
          ...r,
          item_type: 'collab',
          unique_key: `collab_${r.id}`,
          raw_id: r.id,
          display_title: r.name || r.topic || labels.untitledCollab,
          item_date: r.updated_at || r.created_at,
          is_pinned: false, // Collab tidak memiliki pin
        }))
      : [];

    let list = [...chats, ...collabs];

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((item) => item.display_title.toLowerCase().includes(q));
    }

    // Sort: Pinned chat paling atas, lalu urut tanggal
    list.sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) {
        return a.is_pinned ? -1 : 1;
      }
      const timeA = new Date(a.item_date || 0).getTime();
      const timeB = new Date(b.item_date || 0).getTime();
      return sortOrder === 'newest' ? timeB - timeA : timeA - timeB;
    });

    return list;
  }, [chatHistory, collabRooms, searchQuery, sortOrder, language]);

  // Selection helpers
  const handleToggleSelect = (uniqueKey, e) => {
    if (e) e.stopPropagation();
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(uniqueKey)) {
        next.delete(uniqueKey);
      } else {
        next.add(uniqueKey);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedKeys.size === combinedItems.length) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(combinedItems.map((c) => c.unique_key)));
    }
  };

  const handleExitSelectMode = () => {
    setIsSelectMode(false);
    setSelectedKeys(new Set());
  };

  // Single Action: Toggle Pin (Khusus Chat Saja)
  const handleTogglePin = async (item, e) => {
    if (e) e.stopPropagation();
    if (item.item_type !== 'chat') return;
    setActiveMenuId(null);
    try {
      if (pinChat) {
        await pinChat(item.raw_id, item.is_pinned);
        if (setChatHistory) {
          setChatHistory((prev) =>
            prev.map((c) =>
              c.session_uuid === item.raw_id ? { ...c, is_pinned: !c.is_pinned } : c
            )
          );
        }
      }
    } catch (err) {
      console.error('Gagal toggle pin:', err);
    }
  };

  // Single Action: Start Rename
  const handleStartRename = (item, e) => {
    if (e) e.stopPropagation();
    setActiveMenuId(null);
    setEditingKey(item.unique_key);
    setEditTitleValue(item.display_title);
  };

  // Single Action: Save Rename
  const handleSaveRename = async (item) => {
    if (!editTitleValue.trim()) {
      setEditingKey(null);
      return;
    }
    const newTitle = editTitleValue.trim();
    setEditingKey(null);
    try {
      if (item.item_type === 'chat') {
        if (renameChat) {
          await renameChat(item.raw_id, newTitle);
          if (setChatHistory) {
            setChatHistory((prev) =>
              prev.map((c) =>
                c.session_uuid === item.raw_id ? { ...c, judul: newTitle, title: newTitle } : c
              )
            );
          }
        }
      } else if (item.item_type === 'collab') {
        await collabApi.renameRoom(item.raw_id, newTitle);
        setCollabRooms((prev) =>
          prev.map((r) => (r.id === item.raw_id ? { ...r, name: newTitle } : r))
        );
      }
    } catch (err) {
      console.error('Gagal rename:', err);
    }
  };

  // Single Action: Trigger Archive
  const handleTriggerSingleArchive = (item, e) => {
    if (e) e.stopPropagation();
    setActiveMenuId(null);
    setItemToArchiveSingle(item);
    setShowArchiveConfirm(true);
  };

  // Single Action: Trigger Delete
  const handleTriggerSingleDelete = (item, e) => {
    if (e) e.stopPropagation();
    setActiveMenuId(null);
    setItemToDeleteSingle(item);
    setShowDeleteConfirm(true);
  };

  // Batch Action: Trigger Archive
  const handleTriggerBatchArchive = () => {
    if (selectedKeys.size === 0 || isProcessing) return;
    setItemToArchiveSingle(null);
    setShowArchiveConfirm(true);
  };

  // Confirm Archive Handler (Both Single & Batch)
  const handleExecuteArchive = async () => {
    setIsProcessing(true);
    try {
      if (itemToArchiveSingle) {
        const item = itemToArchiveSingle;
        if (item.item_type === 'chat') {
          if (archiveChat) await archiveChat(item.raw_id, true);
          if (setChatHistory) {
            setChatHistory((prev) => prev.filter((c) => c.session_uuid !== item.raw_id));
          }
          if (currentSessionId === item.raw_id) {
            onNewChat?.();
          }
        } else if (item.item_type === 'collab') {
          await collabApi.archiveRoom(item.raw_id, true);
          setCollabRooms((prev) => prev.filter((r) => r.id !== item.raw_id));
        }
      } else if (selectedKeys.size > 0) {
        for (const key of selectedKeys) {
          const item = combinedItems.find((i) => i.unique_key === key);
          if (!item) continue;
          if (item.item_type === 'chat') {
            if (archiveChat) await archiveChat(item.raw_id, true);
          } else if (item.item_type === 'collab') {
            await collabApi.archiveRoom(item.raw_id, true);
          }
        }
        if (setChatHistory) {
          setChatHistory((prev) =>
            prev.filter((c) => !selectedKeys.has(`chat_${c.session_uuid}`))
          );
        }
        setCollabRooms((prev) => prev.filter((r) => !selectedKeys.has(`collab_${r.id}`)));
        if (selectedKeys.has(`chat_${currentSessionId}`)) {
          onNewChat?.();
        }
        handleExitSelectMode();
      }
    } catch (err) {
      console.error('Failed to archive:', err);
    } finally {
      setIsProcessing(false);
      setShowArchiveConfirm(false);
      setItemToArchiveSingle(null);
    }
  };

  // Confirm Delete Handler (Both Single & Batch)
  const handleExecuteDelete = async () => {
    setIsProcessing(true);
    try {
      if (itemToDeleteSingle) {
        // Single delete
        const item = itemToDeleteSingle;
        if (item.item_type === 'chat') {
          if (deleteChat) await deleteChat(item.raw_id, userData?.npp);
          if (setChatHistory) {
            setChatHistory((prev) => prev.filter((c) => c.session_uuid !== item.raw_id));
          }
          if (currentSessionId === item.raw_id) {
            onNewChat?.();
          }
        } else if (item.item_type === 'collab') {
          await collabApi.deleteRoom(item.raw_id);
          setCollabRooms((prev) => prev.filter((r) => r.id !== item.raw_id));
        }
      } else if (selectedKeys.size > 0) {
        // Batch delete
        for (const key of selectedKeys) {
          const item = combinedItems.find((i) => i.unique_key === key);
          if (!item) continue;
          if (item.item_type === 'chat') {
            if (deleteChat) await deleteChat(item.raw_id, userData?.npp);
          } else if (item.item_type === 'collab') {
            await collabApi.deleteRoom(item.raw_id);
          }
        }
        if (setChatHistory) {
          setChatHistory((prev) =>
            prev.filter((c) => !selectedKeys.has(`chat_${c.session_uuid}`))
          );
        }
        setCollabRooms((prev) => prev.filter((r) => !selectedKeys.has(`collab_${r.id}`)));
        if (selectedKeys.has(`chat_${currentSessionId}`)) {
          onNewChat?.();
        }
        handleExitSelectMode();
      }
    } catch (err) {
      console.error('Failed to delete:', err);
    } finally {
      setIsProcessing(false);
      setShowDeleteConfirm(false);
      setItemToDeleteSingle(null);
    }
  };

  return (
    <div
      className="flex-1 w-full h-full overflow-y-auto custom-scrollbar"
      style={{
        background: darkMode ? '#141416' : '#ffffff',
        color: darkMode ? '#f3f4f6' : '#111827',
      }}
    >
      <div className="w-full max-w-4xl mx-auto px-6 pt-10 pb-20">
        {/* ── TOP HEADER ── */}
        <div className="flex items-center justify-between gap-4 pb-6">
          {/* Sisi Kiri: Judul Halaman "Chats and collabs" */}
          <h1 className="text-2xl font-serif font-medium tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
            {labels.title}
          </h1>

          {/* Sisi Kanan: Action Buttons & Select Toolbar */}
          <div className="flex items-center gap-2.5">
            {isSelectMode ? (
              /* Mode Seleksi: "{count} selected" + [Select all] + [Archive] + [Delete] (merah) + [X] */
              <div className="flex items-center gap-2.5 animate-in fade-in duration-150">
                <span className={`text-xs font-normal mr-1 tabular-nums ${darkMode ? 'text-zinc-400' : 'text-gray-500'}`}>
                  {selectedKeys.size} {labels.selected}
                </span>

                <button
                  onClick={handleSelectAll}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    darkMode
                      ? 'bg-zinc-850 border-zinc-700 hover:bg-zinc-750 text-gray-200'
                      : 'bg-gray-100 border-gray-300 hover:bg-gray-200 text-gray-700'
                  }`}
                >
                  {selectedKeys.size === combinedItems.length ? labels.deselectAll : labels.selectAll}
                </button>

                <button
                  onClick={handleTriggerBatchArchive}
                  disabled={selectedKeys.size === 0 || isProcessing}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    selectedKeys.size === 0
                      ? 'opacity-40 cursor-not-allowed border-zinc-700'
                      : darkMode
                      ? 'bg-zinc-850 border-zinc-700 hover:bg-zinc-750 text-gray-200'
                      : 'bg-gray-100 border-gray-300 hover:bg-gray-200 text-gray-700'
                  }`}
                >
                  <Archive size={13} />
                  <span>{labels.archive}</span>
                </button>

                <button
                  onClick={() => {
                    setItemToDeleteSingle(null);
                    setShowDeleteConfirm(true);
                  }}
                  disabled={selectedKeys.size === 0 || isProcessing}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    selectedKeys.size === 0
                      ? 'opacity-40 cursor-not-allowed bg-red-800/40 text-red-300'
                      : 'bg-[#dc2626] hover:bg-red-700 text-white shadow-sm'
                  }`}
                >
                  <Trash2 size={13} />
                  <span>{labels.delete}</span>
                </button>

                <button
                  onClick={handleExitSelectMode}
                  className={`p-1.5 rounded-lg transition-colors ml-0.5 ${
                    darkMode ? 'hover:bg-zinc-800 text-gray-400 hover:text-white' : 'hover:bg-gray-200 text-gray-500 hover:text-black'
                  }`}
                  title={labels.cancel}
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              /* Mode Normal: Search + Sort + [Select] + [New] */
              <>
                {/* Search Bar / Icon */}
                {isSearchOpen ? (
                  <div
                    className={`flex items-center gap-2 px-3 py-1 rounded-lg border transition-all ${
                      darkMode ? 'bg-zinc-900 border-zinc-700' : 'bg-gray-50 border-gray-300'
                    }`}
                  >
                    <Search size={14} className="text-gray-400" />
                    <input
                      type="text"
                      autoFocus
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder={labels.searchPlaceholder}
                      className="bg-transparent border-none outline-none text-xs w-36 sm:w-48 text-inherit placeholder-gray-500"
                    />
                    <button
                      onClick={() => {
                        setSearchQuery('');
                        setIsSearchOpen(false);
                      }}
                      className="text-gray-400 hover:text-gray-200"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setIsSearchOpen(true)}
                    className={`p-2 rounded-lg transition-colors ${
                      darkMode ? 'hover:bg-zinc-800 text-gray-400 hover:text-white' : 'hover:bg-gray-100 text-gray-600 hover:text-black'
                    }`}
                    title={labels.searchTooltip}
                  >
                    <Search size={16} />
                  </button>
                )}

                {/* Sort Order */}
                <button
                  onClick={() => setSortOrder((prev) => (prev === 'newest' ? 'oldest' : 'newest'))}
                  className={`p-2 rounded-lg transition-colors ${
                    darkMode ? 'hover:bg-zinc-800 text-gray-400 hover:text-white' : 'hover:bg-gray-100 text-gray-600 hover:text-black'
                  }`}
                  title={sortOrder === 'newest' ? labels.sortNewest : labels.sortOldest}
                >
                  <ArrowUpDown size={16} />
                </button>

                {/* Select Mode Toggle */}
                <button
                  onClick={() => setIsSelectMode(true)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    darkMode
                      ? 'bg-zinc-850 border-zinc-700/80 hover:bg-zinc-750 text-gray-200'
                      : 'bg-white border-gray-300 hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  {labels.select}
                </button>

                {/* New Chat Button */}
                <button
                  onClick={onNewChat}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all shadow-sm ${
                    darkMode
                      ? 'bg-white hover:bg-gray-100 text-black'
                      : 'bg-zinc-900 hover:bg-zinc-800 text-white'
                  }`}
                >
                  <Plus size={14} strokeWidth={2.5} />
                  <span>{labels.new}</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* ── LIST AREA ── */}
        <div className="space-y-0.5">
          {combinedItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-28 text-center">
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center mb-3 ${
                  darkMode ? 'bg-zinc-850 text-gray-400' : 'bg-gray-100 text-gray-500'
                }`}
              >
                <MessageSquare size={22} />
              </div>
              <h3 className="text-sm font-medium mb-1">{labels.emptyTitle}</h3>
              <p className={`text-xs max-w-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{labels.emptyDesc}</p>
            </div>
          ) : (
            combinedItems.map((item) => {
              const isSelected = selectedKeys.has(item.unique_key);
              const isCurrent = item.item_type === 'chat' && item.raw_id === currentSessionId;
              const dateDisplay = formatSessionDate(item.item_date, language);
              const title = item.display_title;
              const isMenuOpen = activeMenuId === item.unique_key;

              return (
                <div
                  key={item.unique_key}
                  onClick={() => {
                    if (isSelectMode) {
                      handleToggleSelect(item.unique_key);
                    } else if (editingKey !== item.unique_key) {
                      if (item.item_type === 'chat') {
                        onSelectChat?.(item.raw_id);
                      } else if (item.item_type === 'collab') {
                        onClose?.();
                        navigate('/collab');
                      }
                    }
                  }}
                  /* Rata kiri presisi dengan header via -mx-2.5 px-2.5 */
                  className={`group relative flex items-center justify-between gap-4 -mx-2.5 px-2.5 py-3 rounded-xl cursor-pointer transition-all duration-150 ${
                    isSelected
                      ? darkMode
                        ? 'bg-blue-500/10 border border-blue-500/30'
                        : 'bg-blue-50 border border-blue-200'
                      : isMenuOpen
                      ? darkMode
                        ? 'bg-[#1e1e24]'
                        : 'bg-gray-100'
                      : darkMode
                      ? 'hover:bg-[#1a1a1e] border border-transparent'
                      : 'hover:bg-gray-100/80 border border-transparent'
                  }`}
                >
                  {/* Sisi Kiri: Checkbox (jika select mode) + Judul (selalu di awal) + Pin/Collab Badge */}
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    {/* Checkbox */}
                    {isSelectMode && (
                      <div
                        onClick={(e) => handleToggleSelect(item.unique_key, e)}
                        className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 mr-1 transition-all ${
                          isSelected
                            ? 'bg-blue-600 border border-blue-600 text-white'
                            : darkMode
                            ? 'border border-zinc-600 hover:border-zinc-400 bg-zinc-850'
                            : 'border border-gray-300 hover:border-gray-400 bg-white'
                        }`}
                      >
                        {isSelected && <Check size={12} strokeWidth={3} />}
                      </div>
                    )}

                    {/* Judul Percakapan / Inline Edit Input */}
                    {editingKey === item.unique_key ? (
                      <input
                        autoFocus
                        type="text"
                        value={editTitleValue}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => setEditTitleValue(e.target.value)}
                        onBlur={() => handleSaveRename(item)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveRename(item);
                          if (e.key === 'Escape') setEditingKey(null);
                        }}
                        className={`w-full text-sm font-normal px-2 py-0.5 rounded outline-none border focus:ring-1 ${
                          darkMode
                            ? 'bg-zinc-800 border-zinc-600 text-white focus:ring-blue-500'
                            : 'bg-white border-gray-300 text-black focus:ring-blue-500'
                        }`}
                      />
                    ) : (
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        {/* Teks Judul Selalu di Depan: Menjamin huruf pertama judul sejajar sempurna dengan header */}
                        <span
                          className={`text-sm truncate font-normal leading-normal transition-colors ${
                            isCurrent
                              ? 'text-blue-400 font-medium'
                              : darkMode
                              ? 'text-zinc-200 group-hover:text-white'
                              : 'text-gray-800 group-hover:text-black'
                          }`}
                          title={title}
                        >
                          {title}
                        </span>

                        {/* Icon Pin untuk Chat yang dipin */}
                        {item.is_pinned && (
                          <Pin size={12} className="text-blue-400 fill-blue-400 flex-shrink-0 rotate-45" />
                        )}

                        {/* Icon Collab untuk Ruang Diskusi Tim */}
                        {item.item_type === 'collab' && (
                          <span
                            className={`flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-md flex-shrink-0 ${
                              darkMode ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30' : 'bg-teal-50 text-teal-700 border border-teal-200'
                            }`}
                          >
                            <Users2 size={11} />
                            <span>{labels.collabBadge}</span>
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Sisi Kanan: Tanggal saat normal & Titik Tiga saat Hover (Sejajar Presisi Ujung Tombol New) */}
                  <div className="relative flex items-center justify-end flex-shrink-0 min-w-[32px] min-h-[28px]">
                    <span
                      className={`text-xs whitespace-nowrap tabular-nums text-right transition-opacity duration-150 ${
                        isSelectMode
                          ? 'opacity-100'
                          : isMenuOpen
                          ? 'opacity-0 pointer-events-none'
                          : 'group-hover:opacity-0'
                      } ${darkMode ? 'text-zinc-500' : 'text-gray-400'}`}
                    >
                      {dateDisplay}
                    </span>

                    {/* Tombol Titik Tiga [⋮] yang muncul di posisi tepat sejajar kanan */}
                    {!isSelectMode && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuId(isMenuOpen ? null : item.unique_key);
                        }}
                        className={`absolute right-0 top-1/2 -translate-y-1/2 p-1.5 rounded-lg transition-all duration-150 ${
                          isMenuOpen
                            ? 'opacity-100 bg-zinc-800 text-white pointer-events-auto'
                            : 'opacity-0 pointer-events-none group-hover:pointer-events-auto group-hover:opacity-100 hover:bg-zinc-700/60 text-zinc-400 hover:text-white'
                        }`}
                        title={labels.options}
                      >
                        <MoreVertical size={16} />
                      </button>
                    )}

                    {/* Dropdown Menu Popup saat [⋮] diklik */}
                    {isMenuOpen && (
                      <div
                        ref={menuRef}
                        onClick={(e) => e.stopPropagation()}
                        className={`absolute right-0 top-9 w-44 rounded-xl border shadow-2xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-150 backdrop-blur-md ${
                          darkMode
                            ? 'bg-[#1e1e24] border-zinc-700/80 text-zinc-200 shadow-black/80'
                            : 'bg-white border-gray-200 text-gray-800 shadow-gray-300/60'
                        }`}
                      >
                        {/* Pin / Unpin: HANYA TAMPIL UNTUK CHAT (COLLAB TIDAK ADA PIN SESUAI PERMINTAAN) */}
                        {item.item_type === 'chat' && (
                          <button
                            onClick={(e) => handleTogglePin(item, e)}
                            className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs rounded-lg transition-colors text-left ${
                              darkMode ? 'hover:bg-white/10 text-zinc-200' : 'hover:bg-gray-100 text-gray-700'
                            }`}
                          >
                            {item.is_pinned ? <PinOff size={14} /> : <Pin size={14} />}
                            <span>{item.is_pinned ? labels.unpin : labels.pin}</span>
                          </button>
                        )}

                        <button
                          onClick={(e) => handleStartRename(item, e)}
                          className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs rounded-lg transition-colors text-left ${
                            darkMode ? 'hover:bg-white/10 text-zinc-200' : 'hover:bg-gray-100 text-gray-700'
                          }`}
                        >
                          <Edit2 size={14} />
                          <span>{labels.rename}</span>
                        </button>

                        <button
                          onClick={(e) => handleTriggerSingleArchive(item, e)}
                          className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs rounded-lg transition-colors text-left ${
                            darkMode ? 'hover:bg-white/10 text-zinc-200' : 'hover:bg-gray-100 text-gray-700'
                          }`}
                        >
                          <Archive size={14} />
                          <span>{labels.archive}</span>
                        </button>

                        <div className={`my-1 border-t ${darkMode ? 'border-zinc-700/60' : 'border-gray-200'}`} />

                        <button
                          onClick={(e) => handleTriggerSingleDelete(item, e)}
                          className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs rounded-lg transition-colors text-left text-red-500 ${
                            darkMode ? 'hover:bg-red-500/10' : 'hover:bg-red-50'
                          }`}
                        >
                          <Trash2 size={14} />
                          <span>{labels.delete}</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── MODAL KONFIRMASI HAPUS ── */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div
            className={`w-full max-w-sm rounded-xl p-5 border shadow-2xl ${
              darkMode ? 'bg-zinc-900 border-zinc-800 text-white' : 'bg-white border-gray-200 text-black'
            }`}
          >
            <h3 className="text-base font-semibold mb-2">{labels.deleteConfirmTitle}</h3>
            <p className={`text-xs mb-5 leading-relaxed ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {labels.deleteConfirmDesc(itemToDeleteSingle ? 1 : selectedKeys.size)}
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                disabled={isProcessing}
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setItemToDeleteSingle(null);
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                  darkMode ? 'border-zinc-700 hover:bg-zinc-800 text-gray-300' : 'border-gray-300 hover:bg-gray-100 text-gray-700'
                }`}
              >
                {labels.cancel}
              </button>
              <button
                disabled={isProcessing}
                onClick={handleExecuteDelete}
                className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
              >
                {isProcessing ? labels.deleting : labels.delete}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL KONFIRMASI ARSIP ── */}
      {showArchiveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div
            className={`w-full max-w-sm rounded-xl p-5 border shadow-2xl ${
              darkMode ? 'bg-zinc-900 border-zinc-800 text-white' : 'bg-white border-gray-200 text-black'
            }`}
          >
            <h3 className="text-base font-semibold mb-2">{labels.archiveConfirmTitle}</h3>
            <p className={`text-xs mb-5 leading-relaxed ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {labels.archiveConfirmDesc(itemToArchiveSingle ? 1 : selectedKeys.size)}
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                disabled={isProcessing}
                onClick={() => {
                  setShowArchiveConfirm(false);
                  setItemToArchiveSingle(null);
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                  darkMode ? 'border-zinc-700 hover:bg-zinc-800 text-gray-300' : 'border-gray-300 hover:bg-gray-100 text-gray-700'
                }`}
              >
                {labels.cancel}
              </button>
              <button
                disabled={isProcessing}
                onClick={handleExecuteArchive}
                className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
              >
                {isProcessing ? labels.archiving : labels.archive}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
