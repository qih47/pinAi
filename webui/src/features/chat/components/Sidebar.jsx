import React, { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import SessionExpiryStatus from "../../../components/SessionExpiryStatus"; // 👈 W11: Session expiry display
import { useSessionTitle } from "../../../hooks/useSessionTitle"; // 👈 W14: LLM Title Indicator

const TypewriterTitle = ({ text }) => {
  const [displayedText, setDisplayedText] = useState("");

  useEffect(() => {
    setDisplayedText("");
    if (!text) return;
    
    let i = 0;
    const timer = setInterval(() => {
      setDisplayedText(text.slice(0, i + 1));
      i++;
      if (i >= text.length) clearInterval(timer);
    }, 50);
    return () => clearInterval(timer);
  }, [text]);

  return <span>{displayedText}</span>;
};

const Sidebar = ({
  clearChat,
  showDocumentList,
  setShowDocumentList,
  isOpen,
  setIsOpen,
  isMobile,
  userData,
  loadChatSession,
  currentSessionId,
  chatHistory,
  setChatHistory,
  triggerLogout,
  cakraLogo,
  navigate,
  darkMode, // Props tema murni dari ChatPage
  setDarkMode, // Setter tema murni dari ChatPage
  theme,
}) => {
  const [hoveredChatId, setHoveredChatId] = useState(null);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [tempTitle, setTempTitle] = useState("");
  const menuRef = useRef(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [sessionSearchQuery, setSessionSearchQuery] = useState("");
  const sidebarSearchInputRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsOpen(true);
        setTimeout(() => {
          sidebarSearchInputRef.current?.focus();
        }, 100);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setIsOpen]);

  // Ambil method fetch secara langsung dari Zustand store
  const pinChat = useChatStore((state) => state.pinChat);
  const renameChat = useChatStore((state) => state.renameChat);
  const deleteChat = useChatStore((state) => state.deleteChat);
  const fetchChatHistory = useChatStore((state) => state.fetchChatHistory);

  // W14: LLM Title Generation Indicator
  const { isTitleGenerating } = useSessionTitle(
    chatHistory,
    setChatHistory,
    currentSessionId,
    true // Always enabled
  );

  // Ambil variabel nama dan divisi cadangan dari props atau sesuaikan dengan struktur store
  const profileName = userData?.fullname || userData?.name || "Pegawai Pindad";
  const profileDivisi = userData?.divisi || "Pegawai Resmi";

  // Close menu saat klik di luar
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const togglePinChat = async (e, sessionUuid) => {
    e.stopPropagation();
    try {
      // Cari data chat saat ini untuk tahu dia lagi di-pin atau kagak
      const currentChat = chatHistory.find(
        (c) => c.session_uuid === sessionUuid,
      );
      const isPinnedCurrentValue = currentChat ? currentChat.is_pinned : false;

      // Meneruskan kedua parameter tersebut ke method store
      const result = await pinChat(sessionUuid, isPinnedCurrentValue);

      if (result.status === "success") {
        setChatHistory((prev) => {
          const newHistory = prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, is_pinned: !chat.is_pinned }
              : chat,
          );
          return [...newHistory].sort(
            (a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0),
          );
        });
        setActiveMenuId(null);
      }
    } catch (err) {
      console.error("Gagal menyematkan chat:", err);
    }
  };

  const handleRename = async (sessionUuid) => {
    if (!tempTitle.trim()) return;
    try {
      // SINKRONISASI: Memanggil method dari chatStore
      const result = await renameChat(sessionUuid, tempTitle);
      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, judul: tempTitle }
              : chat,
          ),
        );
        setEditingSessionId(null);
      }
    } catch (err) {
      console.error("Gagal rename chat:", err);
    }
  };

  const confirmDelete = (e, sessionUuid) => {
    e.stopPropagation();
    setSessionToDelete(sessionUuid);
    setShowDeleteModal(true);
    setActiveMenuId(null);
  };

  const [isDeletingId, setIsDeletingId] = useState(null);

  const executeDelete = async () => {
    if (!sessionToDelete) return;

    try {
      setIsDeletingId(sessionToDelete);
      setShowDeleteModal(false);

      await new Promise((resolve) => setTimeout(resolve, 400));

      // SINKRONISASI PERBAIKAN: Meneruskan session_uuid dan NPP pengguna aktif ke store global
      const result = await deleteChat(sessionToDelete, userData?.npp);

      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.filter((c) => c.session_uuid !== sessionToDelete),
        );

        // INDRA PENGINGAT RUTE: Jika chat yang dihapus adalah chat yang sedang dibuka
        if (currentSessionId === sessionToDelete) {
          clearChat(); // Bersihkan state messages dan sessionUuid di store secara instan
          navigate("/chat/new"); // Mengarahkan rute URL browser langsung ke halaman obrolan baru
        }
      }
    } catch (err) {
      console.error("Gagal menghapus:", err);
    } finally {
      setIsDeletingId(null);
      setSessionToDelete(null);
    }
  };

  // =========================================================================
  // SEKTOR AMAN SIDEBAR: Fetch murni sekali pakai, anti-infinite loop!
  // =========================================================================
  const hasFetchedRef = useRef(false); // ← tambah di atas

  useEffect(() => {
    const initHistory = async () => {
      if (
        userData?.npp &&
        userData.npp !== "NPP ------" &&
        !hasFetchedRef.current
      ) {
        hasFetchedRef.current = true; // ← set flag sebelum fetch
        try {
          const result = await fetchChatHistory(userData.npp);
          if (result.status === "success") {
            setChatHistory(result.data);
          }
        } catch (err) {
          hasFetchedRef.current = false; // ← reset kalau gagal biar bisa retry
          console.error("Gagal memuat riwayat awal:", err);
        }
      }
    };
    initHistory();
  }, [userData?.npp]);

  // Mengambil riwayat obrolan menggunakan NPP, memanggil langsung dari method store
  // useEffect(() => {
  //   const fetchHistory = async () => {
  //     // Cek dulu apakah history sudah ada untuk mencegah fetch berulang
  //     if (userData?.npp && chatHistory.length === 0) {
  //       try {
  //         const result = await chatStore.fetchChatHistory(userData.npp);
  //         if (result.status === "success") {
  //           setChatHistory(result.data);
  //         }
  //       } catch (err) {
  //         console.error("Gagal ambil history chat:", err);
  //       }
  //     }
  //   };

  //   fetchHistory();
  //   // Gunakan userData?.npp agar cuma jalan pas NPP berubah saja
  // }, [userData?.npp]);

  const [isHovered, setIsHovered] = useState(false);
  const [showLogoutPopup, setShowLogoutPopup] = useState(false);
  const popupRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popupRef.current && !popupRef.current.contains(event.target)) {
        setShowLogoutPopup(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div
      // Menghapus kelas border statis bawaan Tailwind
      className={`fixed left-0 top-0 h-[100dvh] flex flex-col transition-all duration-300 z-40 ${
        isMobile 
          ? (isOpen ? "w-72 translate-x-0" : "w-72 -translate-x-full")
          : (isOpen ? "w-72 translate-x-0" : "w-16 translate-x-0")
      }`}
      style={{
        // MODE GELAP: Menggunakan warna arang (#1E1E22) agar kontras dengan ChatPage
        background: darkMode ? "#1E1E22" : theme?.sidebarBg || "#F7F8FC",
        color: theme?.textColor || (darkMode ? "#e2e8f0" : "#1f2937"),

        // 🔥 DYNAMIC BORDER: Diperbaiki agar di mode dark pun ada batas pemisah tipis yang rapi!
        borderRight: darkMode ? "1px solid #2a2a2d" : "1px solid #E5E7EB",
      }}
    >
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className="p-3 p-5 relative flex flex-col justify-center"
        // style={{
        //   borderBottom: darkMode ? "1px solid #2a2a2d" : "1px solid #E5E7EB",
        // }}
      >
        <div className="flex items-center">
          <img
            src={cakraLogo}
            alt="CAKRA AI Logo"
            className={`rounded-full object-cover transition-all duration-300 ${isOpen ? "w-10 h-10" : "w-7 h-7"
              } ${!isOpen && isHovered ? "opacity-0" : "opacity-100"}`}
          />
          <h1
            className={`font-bold text-lg whitespace-nowrap transition-all duration-300 ml-2 ${!isOpen ? "opacity-0 pointer-events-none w-0" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            CAKRA AI
          </h1>
        </div>

        {/* Hide collapse button on mobile, let backdrop and hamburger handle it */}
        {!isMobile && (
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="absolute transition-all duration-300 p-1 hover:bg-gray-200 dark:hover:bg-gray-800 rounded"
            style={{
              color: theme?.iconColor,
              top: isOpen ? "20px" : "12px",
              right: isOpen ? "12px" : "auto",
              left: isOpen ? "auto" : "50%",
              transform: isOpen ? "none" : "translateX(-50%)",
              opacity: isOpen ? 1 : isHovered ? 1 : 0,
              pointerEvents: isOpen ? "auto" : isHovered ? "auto" : "none",
            }}
            title={isOpen ? "Ciutkan" : "Lebarkan"}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="4" width="18" height="16" rx="2.5" />
              <rect x="3" y="4" width="6" height="16" rx="2.5" />
            </svg>
          </button>
        )}
      </div>

      <div
        className={`p-3 space-y-3 ${!isOpen && "flex flex-col items-center"}`}
      >
        {/* 👇 W11: Session Expiry Status Display */}
        <SessionExpiryStatus />

        <button
          onClick={clearChat}
          className="flex items-center rounded-full hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors group overflow-hidden text-[14px]"
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title="New Chat"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 group-hover:text-blue-500 flex-shrink-0"
            style={{ color: theme?.iconColor }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
            />
          </svg>
          <span
            className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            New Chat
          </span>
        </button>

        <button
          onClick={() => setShowDocumentList(!showDocumentList)}
          className="flex items-center rounded-full hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors group overflow-hidden text-[14px]"
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0",
          }}
          title="Documents"
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            📄
          </span>
          <span
            className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
              }`}
            style={{ color: theme?.textColor }}
          >
            Documents
          </span>
        </button>

        {/* W17: Admin Audit Log link — visible only to admin users */}
        {userData?.role === 'admin' && (
          <button
            onClick={() => navigate('/admin/audit-logs')}
            className="flex items-center rounded-full hover:bg-red-100/10 transition-colors group overflow-hidden text-[14px]"
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title="Audit Logs (Admin)"
          >
            <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
              🛡️
            </span>
            <span
              className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: '#ef4444', fontSize: '13px' }}
            >
              Audit Logs
            </span>
          </button>
        )}

        {/* W13 & W15: Cache & Performance Dashboard — visible only to admin users */}
        {userData?.role === 'admin' && (
          <button
            onClick={() => navigate('/admin/cache-stats')}
            className="flex items-center rounded-full hover:bg-indigo-100/10 transition-colors group overflow-hidden text-[14px]"
            style={{
              padding: isOpen ? "8px 12px" : "8px",
              width: isOpen ? "100%" : "auto",
              gap: isOpen ? "12px" : "0",
            }}
            title="Cache & Performance (Admin)"
          >
            <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
              ⚡
            </span>
            <span
              className={`font-medium whitespace-nowrap transition-opacity duration-300 ${!isOpen ? "hidden" : "opacity-100"
                }`}
              style={{ color: '#818cf8', fontSize: '13px' }}
            >
              Cache & Index
            </span>
          </button>
        )}
      </div>

      <div
        className={`flex-1 overflow-y-auto px-2 py-2 space-y-0.5 transition-opacity duration-300 no-scrollbar ${!isOpen ? "opacity-0 pointer-events-none hidden" : "opacity-100"
          }`}
        style={{
          msOverflowStyle: "none",
          scrollbarWidth: "none",
        }}
      >
        <div
          className="px-3 py-1 text-[11px] font-bold uppercase tracking-widest mb-1"
          style={{ color: theme?.secondaryText || "#6b7280" }}
        >
          Semua Chat
        </div>

        {isOpen && (
          <div className="px-3 mb-2 relative">
            <input
              ref={sidebarSearchInputRef}
              type="text"
              placeholder="Cari riwayat chat... (Ctrl+K)"
              value={sessionSearchQuery}
              onChange={(e) => setSessionSearchQuery(e.target.value)}
              className="w-full text-xs rounded-lg px-2.5 py-1.5 outline-none border transition-colors"
              style={{
                background: darkMode ? "#252528" : "#F3F4F6",
                borderColor: darkMode ? "#2A2A2D" : "#E5E7EB",
                color: theme?.textColor || (darkMode ? "#e2e8f0" : "#1f2937"),
              }}
            />
            {sessionSearchQuery && (
              <button
                onClick={() => setSessionSearchQuery("")}
                className="absolute right-5 top-1/2 -translate-y-1/2 text-[10px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            )}
          </div>
        )}

        {chatHistory.length > 0 ? (
          [...chatHistory]
            .filter((c) =>
              (c.judul || "Chat Baru")
                .toLowerCase()
                .includes(sessionSearchQuery.toLowerCase()),
            )
            .sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0))
            .map((chat) => (
              <div
                key={chat.session_uuid}
                onMouseEnter={() => setHoveredChatId(chat.session_uuid)}
                onMouseLeave={() => setHoveredChatId(null)}
                onClick={() => {
                  loadChatSession(chat.session_uuid);
                  setActiveMenuId(null);
                }}
                // PERBAIKAN WARNA TEKS AKTIF: Penyesuaian warna teks dan latar belakang untuk chat yang sedang aktif agar lebih terbaca
                className={`group relative flex items-center px-3 py-2 text-sm rounded-xl cursor-pointer transition-all ${currentSessionId === chat.session_uuid
                    ? "bg-blue-500/10 text-blue-400 font-semibold border-l-2 border-blue-500"
                    : "hover:bg-gray-200/50 dark:hover:bg-white/5 font-medium"
                  } ${isDeletingId === chat.session_uuid ? "animate-delete" : ""
                  }`}
                style={{
                  color:
                    currentSessionId === chat.session_uuid
                      ? darkMode
                        ? "#60a5fa"
                        : "#2563eb" // Menggunakan warna biru menyala menyesuaikan mode
                      : darkMode
                        ? "#94a3b8"
                        : "#4b5563",
                }}
                title={chat.judul}
              >
                <span className="mr-2 text-[12px] opacity-70 flex-shrink-0">
                  {chat.is_pinned ? "📌" : "💬"}
                </span>

                <span className="truncate flex-1 text-left pr-4 text-[13px] leading-relaxed">
                  {editingSessionId === chat.session_uuid ? (
                    <input
                      autoFocus
                      className="w-full bg-white border border-blue-400 rounded px-1 outline-none text-black text-xs py-0 dark:bg-gray-800 dark:text-white"
                      value={tempTitle}
                      onChange={(e) => setTempTitle(e.target.value)}
                      onBlur={() => handleRename(chat.session_uuid)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(chat.session_uuid);
                        if (e.key === "Escape") setEditingSessionId(null);
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span className="truncate">
                        {chat._titleUpdated ? (
                          <TypewriterTitle text={chat.judul} />
                        ) : (
                          chat.judul || "Chat Baru"
                        )}
                      </span>
                      {/* W14: LLM Title Generation shimmer indicator */}
                      {isTitleGenerating(chat.session_uuid) && (
                        <span
                          title="Generating better title..."
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px',
                            fontSize: '9px',
                            color: '#a78bfa',
                            background: 'rgba(139,92,246,0.12)',
                            border: '1px solid rgba(139,92,246,0.25)',
                            borderRadius: '8px',
                            padding: '1px 5px',
                            flexShrink: 0,
                            animation: 'pulse 1.5s ease-in-out infinite',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          ✨
                        </span>
                      )}
                    </span>
                  )}
                </span>

                {(hoveredChatId === chat.session_uuid ||
                  activeMenuId === chat.session_uuid) && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveMenuId(
                          activeMenuId === chat.session_uuid
                            ? null
                            : chat.session_uuid,
                        );
                      }}
                      className="absolute right-1 p-1 hover:bg-gray-300 rounded transition-colors dark:hover:bg-gray-700"
                    >
                      <svg
                        className="h-3 w-3"
                        style={{ color: theme?.secondaryText }}
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                      </svg>
                    </button>
                  )}

                {activeMenuId === chat.session_uuid && (
                  <div
                    ref={menuRef}
                    className="absolute right-0 top-7 w-32 bg-white border border-gray-200 rounded-md shadow-lg z-[100] py-1 text-[11px] dark:bg-gray-800 dark:border-gray-700"
                  >
                    <button
                      onClick={(e) => togglePinChat(e, chat.session_uuid)}
                      className="w-full text-left px-3 py-1.5 hover:bg-gray-100 flex justify-between items-center dark:hover:bg-gray-700 dark:text-gray-200"
                    >
                      <span>{chat.is_pinned ? "Lepas" : "Pin"}</span>
                      <span>📌</span>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingSessionId(chat.session_uuid);
                        setTempTitle(chat.judul || "");
                        setActiveMenuId(null);
                      }}
                      className="w-full text-left px-3 py-1.5 hover:bg-gray-100 flex justify-between items-center dark:hover:bg-gray-700 dark:text-gray-200"
                    >
                      <span>Rename</span>
                      <span>✏️</span>
                    </button>
                    <button
                      onClick={(e) => confirmDelete(e, chat.session_uuid)}
                      className="w-full text-left px-3 py-1.5 hover:bg-red-50 text-red-600 flex justify-between items-center font-semibold dark:hover:bg-red-900/20"
                    >
                      <span>Hapus</span>
                      <span>🗑️</span>
                    </button>
                  </div>
                )}
              </div>
            ))
        ) : (
          <div className="text-[11px] text-gray-400 px-3 py-4 italic">
            Belum ada history
          </div>
        )}
      </div>

      <div
        className={`relative flex items-center p-4 ${!isOpen
            ? "p-1 items-center absolute left-0 right-0 justify-center"
            : "justify-center items-center py-3 px-3"
          }`}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "60px",
          // 🔥 Pas dark mode background-nya menyatu sempurna tanpa sekat border hitam!
          background: darkMode ? "#1E1E22" : theme?.sidebarBg || "#F7F8FC",
          // borderTop: darkMode ? "1px solid #2a2a2d" : "1px solid #E5E7EB",
        }}
      >
        {showLogoutPopup && (
          <div
            ref={popupRef}
            className="absolute bottom-full left-2 mb-2 w-52 rounded-xl shadow-2xl py-2 z-50 transition-all bg-white border border-gray-200 dark:bg-[#232326] dark:border-gray-800"
            style={{
              left: !isOpen ? "100%" : "8px",
              marginLeft: !isOpen ? "8px" : "0px",
              bottom: !isOpen ? "8px" : "100%",
            }}
          >
            <div className="px-4 py-2">
              <p className="text-xs text-gray-400 dark:text-gray-400">
                Akun Anda
              </p>
              <p className="text-xs font-semibold truncate dark:text-white">
                {profileName}
              </p>
            </div>

            <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-800 space-y-1">
              <p className="text-[10px] uppercase font-bold tracking-wider text-gray-400 mb-1">
                Pilihan Tema
              </p>
              <div className="flex bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg text-[11px]">
                <button
                  onClick={() => setDarkMode(false)}
                  className={`flex-1 py-1 text-center rounded-md font-medium transition-all ${!darkMode ? "bg-white text-black shadow-sm" : "text-gray-500 hover:text-black dark:text-gray-400"}`}
                >
                  ☀️ Light
                </button>
                <button
                  onClick={() => setDarkMode(true)}
                  className={`flex-1 py-1 text-center rounded-md font-medium transition-all ${darkMode ? "bg-white dark:bg-gray-700 text-black dark:text-white shadow-sm" : "text-gray-500 hover:text-black dark:text-gray-400"}`}
                >
                  🌙 Dark
                </button>
              </div>
            </div>

            <button
              onClick={() => {
                setShowLogoutPopup(false);
                triggerLogout();
              }}
              className="w-full flex items-center space-x-3 px-4 py-2 text-red-500 hover:bg-gray-100 transition-colors dark:hover:bg-gray-900 border-t border-gray-100 dark:border-gray-800"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              <span className="text-sm font-medium">Keluar (Logout)</span>
            </button>
          </div>
        )}

        <div
          className="flex items-center cursor-pointer flex-1 min-w-0"
          onClick={() => setShowLogoutPopup(!showLogoutPopup)}
        >
          <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0 border border-gray-700 bg-gray-800 flex items-center justify-center shadow-inner">
            {userData?.npp ? (
              <>
                <img
                  src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.npp}.jpg`}
                  alt="Profile"
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                    e.currentTarget.nextSibling.style.display = "flex";
                  }}
                />
                <div className="hidden w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold text-white">
                  {profileName !== "Pegawai Pindad"
                    ? profileName.substring(0, 2).toUpperCase()
                    : "AI"}
                </div>
              </>
            ) : (
              <div className="flex w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold text-white">
                AI
              </div>
            )}
          </div>
          <div
            className={`flex flex-col min-w-0 transition-all duration-300 ${!isOpen ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
              }`}
          >
            <span
              className="text-xs font-medium whitespace-normal break-words ml-3"
              style={{ color: theme?.textColor }}
            >
              {profileName}
            </span>
            <span
              className="text-[9px] text-left ml-3"
              style={{ color: theme?.secondaryText || "#6b7280" }}
            >
              {profileDivisi}
            </span>
          </div>
        </div>

        {isOpen && (
          <button
            // PENYESUAIAN WARNA PENGATURAN: Mengubah warna abu-abu statis menjadi theme.iconColor agar sinkron saat pergantian tema
            className="hover:text-blue-500 ml-auto absolute right-3 top-0 bottom-0 my-auto h-fit p-1 transition-colors"
            style={{ color: theme?.iconColor || "#9ca3af" }}
            onClick={() => setShowLogoutPopup(!showLogoutPopup)}
            title="Pengaturan & Akun"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 animate-[spin_20s_linear_infinite]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        )}

        {showDeleteModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl p-6 w-80 shadow-2xl transform animate-in zoom-in-95 duration-200 dark:bg-gray-800">
              <div className="flex flex-col items-center text-center">
                <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4 dark:bg-red-900/30">
                  <span className="text-xl">🗑️</span>
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Hapus Chat?
                </h3>
                <p className="text-sm text-gray-500 mt-2 dark:text-gray-400">
                  Chat ini akan dihapus dari riwayat Anda. Tindakan ini tidak
                  dapat dibatalkan.
                </p>
              </div>

              <div className="flex space-x-3 mt-6">
                <button
                  onClick={() => setShowDeleteModal(false)}
                  className="flex-1 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-medium transition-colors dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Batal
                </button>
                <button
                  onClick={executeDelete}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium transition-colors shadow-lg shadow-red-200 dark:shadow-none"
                >
                  Hapus
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
