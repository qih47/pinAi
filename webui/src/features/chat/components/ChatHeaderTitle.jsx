import React, { useState, useRef, useEffect } from "react";
import { 
  ChevronDown, 
  Pin, 
  PinOff, 
  Edit3, 
  Download, 
  Copy, 
  Trash2, 
  Check, 
  MessageSquare 
} from "lucide-react";
import { useChatStore } from "../../../stores/chatStore";
import { useChatAuthStore } from "../../../stores/authStore";
import { translations } from "../../../utils/translations";

export default function ChatHeaderTitle({
  sessionUuid,
  chatHistory = [],
  setChatHistory,
  messages = [],
  handleClearChat,
  darkMode = true,
  language = "id",
  toast
}) {
  const currentSession = chatHistory.find((s) => s.session_uuid === sessionUuid);
  const renameChat = useChatStore((state) => state.renameChat);
  const pinChat = useChatStore((state) => state.pinChat);
  const deleteChat = useChatStore((state) => state.deleteChat);
  const authUser = useChatAuthStore((state) => state.user);

  const t = translations[language]?.chatHeader || {
    pin: language === "en" ? "Pin chat" : "Sematkan percakapan",
    unpin: language === "en" ? "Unpin chat" : "Lepas sematan",
    rename: language === "en" ? "Rename" : "Ubah nama",
    export: language === "en" ? "Export chat (.md)" : "Ekspor percakapan (.md)",
    share: language === "en" ? "Copy conversation" : "Salin percakapan",
    delete: language === "en" ? "Delete chat" : "Hapus percakapan",
    deleteConfirm: language === "en" ? "Delete this chat? This cannot be undone." : "Hapus percakapan ini? Tindakan ini tidak dapat dibatalkan.",
    copied: language === "en" ? "Conversation copied to clipboard!" : "Percakapan disalin ke papan klip!",
    newChat: language === "en" ? "New Chat" : "Percakapan Baru",
  };

  const rawTitle = currentSession?.judul || currentSession?.title;
  const isGeneric = !rawTitle || ["obrolan baru", "new chat", "untitled", "percakapan baru", "salam", ""].includes(rawTitle.trim().toLowerCase());
  const displayTitle = isGeneric ? t.newChat : rawTitle.trim();
  const isPinned = currentSession?.is_pinned || false;

  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(displayTitle);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const menuRef = useRef(null);
  const inputRef = useRef(null);

  // Sync edit title when session or title changes
  useEffect(() => {
    setEditTitle(displayTitle);
  }, [displayTitle, sessionUuid]);

  // Auto focus and select input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Click outside listener for menu
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsMenuOpen(false);
        setShowDeleteConfirm(false);
      }
    };
    if (isMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isMenuOpen]);

  const handleSaveRename = async () => {
    const clean = editTitle.trim();
    if (!clean || clean === displayTitle) {
      setIsEditing(false);
      setEditTitle(displayTitle);
      return;
    }

    if (!sessionUuid) {
      setIsEditing(false);
      return;
    }

    try {
      const res = await renameChat(sessionUuid, clean);
      if (res?.status === "success" || res?.success) {
        if (setChatHistory) {
          setChatHistory((prev) =>
            prev.map((item) =>
              item.session_uuid === sessionUuid
                ? { ...item, judul: clean, title: clean }
                : item
            )
          );
        }
      }
    } catch (err) {
      console.error("Gagal rename session header:", err);
    } finally {
      setIsEditing(false);
    }
  };

  const handleTogglePin = async () => {
    if (!sessionUuid) return;
    setIsMenuOpen(false);
    try {
      const res = await pinChat(sessionUuid, isPinned);
      if (res?.status === "success" || res?.success) {
        if (setChatHistory) {
          setChatHistory((prev) => {
            const updated = prev.map((item) =>
              item.session_uuid === sessionUuid
                ? { ...item, is_pinned: !isPinned }
                : item
            );
            return [...updated].sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0));
          });
        }
      }
    } catch (err) {
      console.error("Gagal pin session:", err);
    }
  };

  const handleExportMarkdown = () => {
    setIsMenuOpen(false);
    if (!messages || messages.length === 0) {
      if (toast?.info) toast.info(language === "en" ? "No messages to export" : "Belum ada pesan untuk diekspor");
      return;
    }

    let md = `# ${displayTitle}\n\n`;
    md += `*Diekspor dari CAKRA AI pada ${new Date().toLocaleString()}*\n\n---\n\n`;

    messages.forEach((msg) => {
      const role = msg.sender === "user" ? "👤 **Pengguna**" : "🤖 **CAKRA AI**";
      const content = msg.text || msg.content || "";
      md += `${role}\n\n${content}\n\n---\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const filename = `${displayTitle.replace(/[^a-zA-Z0-9_-]/g, "_")}.md`;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    if (toast?.success) toast.success(language === "en" ? `Exported ${filename}` : `Berhasil mengunduh ${filename}`);
  };

  const handleCopyChat = async () => {
    setIsMenuOpen(false);
    if (!messages || messages.length === 0) {
      if (toast?.info) toast.info(language === "en" ? "No messages to copy" : "Belum ada pesan untuk disalin");
      return;
    }

    let text = `${displayTitle}\n\n`;
    messages.forEach((msg) => {
      const role = msg.sender === "user" ? "Pengguna" : "CAKRA AI";
      const content = msg.text || msg.content || "";
      text += `[${role}]\n${content}\n\n`;
    });

    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      if (toast?.success) toast.success(t.copied);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Gagal menyalin chat:", err);
    }
  };

  const handleDeleteSession = async () => {
    if (!sessionUuid) return;
    try {
      const npp = authUser?.npp || authUser?.username;
      await deleteChat(sessionUuid, npp);
      if (setChatHistory) {
        setChatHistory((prev) => prev.filter((item) => item.session_uuid !== sessionUuid));
      }
      setIsMenuOpen(false);
      setShowDeleteConfirm(false);
      if (handleClearChat) handleClearChat();
      if (toast?.success) toast.success(language === "en" ? "Chat deleted" : "Percakapan berhasil dihapus");
    } catch (err) {
      console.error("Gagal menghapus session:", err);
    }
  };

  return (
    <div className="relative flex items-center select-none" ref={menuRef}>
      {/* Title / Inline Rename */}
      {isEditing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSaveRename();
          }}
          className="flex items-center"
        >
          <input
            ref={inputRef}
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={handleSaveRename}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setIsEditing(false);
                setEditTitle(displayTitle);
              }
            }}
            className={`text-sm font-semibold px-2 py-1 rounded-md border outline-none max-w-[220px] sm:max-w-[320px] md:max-w-[420px] transition-all shadow-sm ${
              darkMode
                ? "bg-[#1e232d] text-white border-blue-500/60 focus:border-blue-400"
                : "bg-white text-gray-900 border-blue-500 focus:border-blue-600"
            }`}
          />
        </form>
      ) : (
        <div
          onClick={() => {
            if (sessionUuid) setIsEditing(true);
          }}
          className={`group flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg cursor-pointer transition-all ${
            darkMode
              ? "hover:bg-white/[0.06] text-gray-200 hover:text-white"
              : "hover:bg-black/[0.05] text-gray-800 hover:text-gray-900"
          }`}
          title={sessionUuid ? (language === "en" ? "Click to rename" : "Klik untuk mengubah nama") : ""}
        >
          <span className="text-sm font-semibold tracking-tight truncate max-w-[180px] sm:max-w-[280px] md:max-w-[380px]">
            {displayTitle}
          </span>
          {isPinned && (
            <Pin
              size={12}
              className="text-blue-400 fill-blue-400 flex-shrink-0 rotate-45"
            />
          )}
        </div>
      )}

      {/* Chevron Dropdown Trigger */}
      {sessionUuid && (
        <button
          type="button"
          onClick={() => {
            setIsMenuOpen(!isMenuOpen);
            setShowDeleteConfirm(false);
          }}
          className={`p-1 ml-0.5 rounded-md transition-all ${
            isMenuOpen
              ? darkMode
                ? "bg-white/10 text-white"
                : "bg-black/10 text-gray-900"
              : darkMode
              ? "text-gray-400 hover:text-white hover:bg-white/[0.06]"
              : "text-gray-500 hover:text-gray-900 hover:bg-black/[0.05]"
          }`}
          title="Opsi percakapan"
        >
          <ChevronDown
            size={15}
            className={`transition-transform duration-200 ${isMenuOpen ? "rotate-180" : ""}`}
          />
        </button>
      )}

      {/* Floating Popover Menu (Claude.ai style) */}
      {isMenuOpen && (
        <div
          className={`absolute left-0 top-full mt-1.5 w-56 rounded-xl shadow-2xl border py-1.5 z-50 backdrop-blur-md animate-in fade-in zoom-in-95 duration-150 ${
            darkMode
              ? "bg-[#181c24]/95 border-gray-800 text-gray-200"
              : "bg-white/95 border-gray-200 text-gray-800"
          }`}
        >
          {/* Option: Pin / Unpin */}
          <button
            onClick={handleTogglePin}
            className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-medium transition-colors ${
              darkMode ? "hover:bg-white/[0.08]" : "hover:bg-gray-100"
            }`}
          >
            {isPinned ? (
              <>
                <PinOff size={14} className="text-gray-400" />
                <span>{t.unpin}</span>
              </>
            ) : (
              <>
                <Pin size={14} className="text-gray-400" />
                <span>{t.pin}</span>
              </>
            )}
          </button>

          {/* Option: Rename */}
          <button
            onClick={() => {
              setIsMenuOpen(false);
              setIsEditing(true);
            }}
            className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-medium transition-colors ${
              darkMode ? "hover:bg-white/[0.08]" : "hover:bg-gray-100"
            }`}
          >
            <Edit3 size={14} className="text-gray-400" />
            <span>{t.rename}</span>
          </button>

          {/* Option: Export Markdown */}
          <button
            onClick={handleExportMarkdown}
            className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-medium transition-colors ${
              darkMode ? "hover:bg-white/[0.08]" : "hover:bg-gray-100"
            }`}
          >
            <Download size={14} className="text-gray-400" />
            <span>{t.export}</span>
          </button>

          {/* Option: Copy / Share */}
          <button
            onClick={handleCopyChat}
            className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-medium transition-colors ${
              darkMode ? "hover:bg-white/[0.08]" : "hover:bg-gray-100"
            }`}
          >
            {isCopied ? (
              <>
                <Check size={14} className="text-green-400" />
                <span className="text-green-400">Tersalin!</span>
              </>
            ) : (
              <>
                <Copy size={14} className="text-gray-400" />
                <span>{t.share}</span>
              </>
            )}
          </button>

          <div className={`my-1 border-t ${darkMode ? "border-gray-800" : "border-gray-200"}`} />

          {/* Option: Delete */}
          {showDeleteConfirm ? (
            <div className="px-3 py-2 space-y-2">
              <p className="text-[11px] text-red-400 leading-tight">
                {t.deleteConfirm}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDeleteSession}
                  className="flex-1 px-2.5 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors"
                >
                  {t.delete}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                    darkMode ? "bg-gray-800 hover:bg-gray-700 text-gray-300" : "bg-gray-200 hover:bg-gray-300 text-gray-700"
                  }`}
                >
                  Batal
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <Trash2 size={14} />
              <span>{t.delete}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
