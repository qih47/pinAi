import React, { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";

const Sidebar = ({
  clearChat,
  showDocumentList,
  setShowDocumentList,
  isOpen,
  setIsOpen,
  userData,
  loadChatSession,
  currentSessionId,
  chatHistory,
  setChatHistory,
  triggerLogout,
  cakraLogo,
  navigate,
  darkMode,       // Props tema murni dari ChatPage
  setDarkMode,     // Setter tema murni dari ChatPage
  theme
}) => {
  const [hoveredChatId, setHoveredChatId] = useState(null);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [tempTitle, setTempTitle] = useState("");
  const menuRef = useRef(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);

  // Ambil actions fetch native langsung dari store murni lo, bolo
  const chatStore = useChatStore();

  // Ambil variabel nama & divisi cadangan dari operan props atau samakan dengan struktur store lo
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
      const currentChat = chatHistory.find(c => c.session_uuid === sessionUuid);
      const isPinnedCurrentValue = currentChat ? currentChat.is_pinned : false;

      // SUNTIK KEDUA PARAMETER-NYA KE ACTIONS STORE LU BOLO
      const result = await chatStore.pinChat(sessionUuid, isPinnedCurrentValue);

      if (result.status === "success") {
        setChatHistory((prev) => {
          const newHistory = prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, is_pinned: !chat.is_pinned }
              : chat
          );
          return [...newHistory].sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0));
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
      // SINKRON: Panggil action dari chatStore bawaan lo
      const result = await chatStore.renameChat(sessionUuid, tempTitle);
      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, judul: tempTitle }
              : chat
          )
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

      // SINKRON PERBAIKAN: Oper session_uuid beserta NPP user aktif lo ke store global
      const result = await chatStore.deleteChat(sessionToDelete, userData?.npp);

      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.filter((c) => c.session_uuid !== sessionToDelete)
        );

        // INDRA PENGINGAT RUTE: Jika chat yang dihapus adalah chat yang lagi dibuka
        if (currentSessionId === sessionToDelete) {
          clearChat();             // Bersihkan state messages & sessionUuid di store jadi null instant
          navigate('/chat/new');   // Tendang rute URL browser langsung ke halaman baru, bolo!
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
      if (userData?.npp && userData.npp !== 'NPP ------' && !hasFetchedRef.current) {
        hasFetchedRef.current = true; // ← set flag sebelum fetch
        try {
          const result = await chatStore.fetchChatHistory(userData.npp);
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

  // Fetch history chat pake NPP, panggil langsung dari actions store lo bolo
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
      // 🔥 Hapus class border statis bawaan Tailwind yang kaku bolo
      className={`fixed left-0 top-0 h-screen flex flex-col transition-all duration-300 z-40 ${isOpen ? "w-72" : "w-16"
        }`}
      style={{
        // 🔥 MODE DARK: Gak hitam pekat bray, tapi abu silver arang (#1E1E22) biar beda dari ChatPage lo!
        background: darkMode ? '#1E1E22' : (theme?.sidebarBg || '#F7F8FC'),
        color: theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937'),

        // 🔥 DYNAMIC BORDER: Pas mode dark TANPA BORDER, pas mode light SILVER INDAH!
        borderRight: darkMode ? 'none' : '1px solid #E5E7EB'
      }}
    >
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className="p-3 p-4 relative flex flex-col justify-center"
        style={{
          // 🔥 Pas mode dark tanpa border bawah, pas light mode dapet silver tipis kalem
          borderBottom: darkMode ? 'none' : '1px solid #E5E7EB'
        }}
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

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="absolute transition-all duration-300 p-1 hover:bg-gray-200 dark:hover:bg-gray-800 rounded"
          style={{
            color: theme?.iconColor,
            top: isOpen ? "20px" : "12px",
            right: isOpen ? "12px" : "auto",
            left: isOpen ? "auto" : "50%",
            transform: isOpen ? "none" : "translateX(-50%)",
            opacity: isOpen ? 1 : (isHovered ? 1 : 0),
            pointerEvents: isOpen ? "auto" : (isHovered ? "auto" : "none")
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
      </div>

      <div
        className={`p-3 space-y-3 ${!isOpen && "flex flex-col items-center"}`}
      >
        <button
          onClick={clearChat}
          className="flex items-center rounded-full hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors group overflow-hidden text-[14px]"
          style={{
            padding: isOpen ? "8px 12px" : "8px",
            width: isOpen ? "100%" : "auto",
            gap: isOpen ? "12px" : "0"
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
            gap: isOpen ? "12px" : "0"
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
          style={{ color: theme?.secondaryText || '#6b7280' }}
        >
          Semua Chat
        </div>

        {chatHistory.length > 0 ? (
          [...chatHistory]
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
                // 🔥 FIX TEXT BIRU ACTIVE: Perbaikan total warna text & background active yang kebalik bawaan orok lo!
                className={`group relative flex items-center px-3 py-2 text-sm rounded-full cursor-pointer transition-all ${currentSessionId === chat.session_uuid
                    ? "bg-blue-100 text-blue-600 font-bold dark:bg-blue-500/50 dark:text-blue-600"
                    : "hover:bg-gray-200 dark:hover:bg-gray-800 font-medium"
                  } ${isDeletingId === chat.session_uuid ? "animate-delete" : ""
                  }`}
                style={{
                  color: currentSessionId === chat.session_uuid
                    ? (darkMode ? '#60a5fa' : '#2563eb') // 🔥 Biru menyala terang benderang menyesuaikan mode!
                    : theme?.textColor
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
                    chat.judul || "Chat Baru"
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
                            : chat.session_uuid
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
        className={`relative flex items-center p-3 ${
          !isOpen
            ? "p-1 items-center absolute left-0 right-0 justify-center"
            : "justify-center items-center py-3 px-2"
        }`}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "60px",
          // 🔥 Pas dark mode background-nya menyatu sempurna tanpa sekat border hitam!
          background: darkMode ? '#1E1E22' : (theme?.sidebarBg || '#F7F8FC'),
          borderTop: darkMode ? 'none' : '1px solid #E5E7EB'
        }}
      >
        {showLogoutPopup && (
          <div
            ref={popupRef}
            className="absolute bottom-full left-2 mb-2 w-52 rounded-xl shadow-2xl py-2 z-50 transition-all bg-white border border-gray-200 dark:bg-[#232326] dark:border-gray-800"
            style={{
              left: !isOpen ? "100%" : "8px",
              marginLeft: !isOpen ? "8px" : "0px",
              bottom: !isOpen ? "8px" : "100%"
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
              <p className="text-[10px] uppercase font-bold tracking-wider text-gray-400 mb-1">Pilihan Tema</p>
              <div className="flex bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg text-[11px]">
                <button
                  onClick={() => setDarkMode(false)}
                  className={`flex-1 py-1 text-center rounded-md font-medium transition-all ${!darkMode ? 'bg-white text-black shadow-sm' : 'text-gray-500 hover:text-black dark:text-gray-400'}`}
                >
                  ☀️ Light
                </button>
                <button
                  onClick={() => setDarkMode(true)}
                  className={`flex-1 py-1 text-center rounded-md font-medium transition-all ${darkMode ? 'bg-white dark:bg-gray-700 text-black dark:text-white shadow-sm' : 'text-gray-500 hover:text-black dark:text-gray-400'}`}
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
            <span className="text-xs font-medium truncate w-32 ml-3" style={{ color: theme?.textColor }}>
              {profileName}
            </span>
            <span className="text-[9px] text-left ml-3" style={{ color: theme?.secondaryText || '#6b7280' }}>
              {profileDivisi}
            </span>
          </div>
        </div>

        {isOpen && (
          <button
            // 🔥 FIX WARNA GERIGI: Ganti text-gray-400 statis bawaan ke theme.iconColor murni biar sinkron saat dark/light!
            className="hover:text-blue-500 ml-auto absolute right-3 top-0 bottom-0 my-auto h-fit p-1 transition-colors"
            style={{ color: theme?.iconColor || '#9ca3af' }}
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
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
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