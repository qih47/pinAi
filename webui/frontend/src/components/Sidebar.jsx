import React, { useState, useRef, useEffect } from "react";

const Sidebar = ({
  backendStatus,
  clearChat,
  setShowDocumentList,
  isOpen,
  setIsOpen,
  userData,
  handleLogout,
  loadChatSession,
  currentSessionId,
  chatHistory,
  setChatHistory,
  triggerLogout,
}) => {
  const [hoveredChatId, setHoveredChatId] = useState(null);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [tempTitle, setTempTitle] = useState("");
  const menuRef = useRef(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);

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
    e.stopPropagation(); // Biar gak trigger loadChatSession
    try {
      const res = await fetch(
        `http://192.168.11.80:5000/api/chat/pin/${sessionUuid}`,
        {
          method: "POST",
        }
      );
      const result = await res.json();
      if (result.status === "success") {
        // Update local state chatHistory
        setChatHistory((prev) =>
          prev.map((chat) =>
            chat.session_uuid === sessionUuid
              ? { ...chat, is_pinned: !chat.is_pinned }
              : chat
          )
        );
        setActiveMenuId(null);
      }
    } catch (err) {
      console.error("Gagal menyematkan chat:", err);
    }
  };

  const handleRename = async (sessionUuid) => {
    if (!tempTitle.trim()) return;
    try {
      const res = await fetch(
        `http://192.168.11.80:5000/api/chat/rename/${sessionUuid}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ judul: tempTitle }),
        }
      );
      const result = await res.json();
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

  // Fungsi untuk memicu modal muncul
  const confirmDelete = (e, sessionUuid) => {
    e.stopPropagation();
    setSessionToDelete(sessionUuid);
    setShowDeleteModal(true);
    setActiveMenuId(null); // Tutup popup menu titik tiga
  };

  // Fungsi eksekusi hapus yang dipanggil dari dalam modal
  const [isDeletingId, setIsDeletingId] = useState(null); // Tambah ini di deretan state atas

  const executeDelete = async () => {
    if (!sessionToDelete) return;

    try {
      // 1. Trigger animasi di UI dulu
      setIsDeletingId(sessionToDelete);
      setShowDeleteModal(false);

      // 2. Tunggu sebentar biar animasinya kelihatan (400ms sesuai durasi CSS)
      await new Promise((resolve) => setTimeout(resolve, 400));

      // 3. Baru panggil API dan hapus dari state
      const res = await fetch(
        `http://192.168.11.80:5000/api/chat/delete/${sessionToDelete}`,
        {
          method: "POST",
        }
      );
      const result = await res.json();

      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.filter((c) => c.session_uuid !== sessionToDelete)
        );
        if (currentSessionId === sessionToDelete) clearChat();
      }
    } catch (err) {
      console.error("Gagal menghapus:", err);
    } finally {
      setIsDeletingId(null);
      setSessionToDelete(null);
    }
  };

  // Fetch history chat saat user login (userData tersedia)
  useEffect(() => {
    const fetchHistory = async () => {
      if (userData?.username) {
        try {
          const res = await fetch(
            `http://192.168.11.80:5000/api/chat-history/${userData.username}`
          );
          const result = await res.json();
          if (result.status === "success") {
            setChatHistory(result.data);
          }
        } catch (err) {
          console.error("Gagal ambil history chat:", err);
        }
      }
    };
    fetchHistory();
  }, [userData]);
  // Tambah state ini buat deteksi hover pas lagi ciut
  const [isHovered, setIsHovered] = useState(false);
  // Tambah state untuk toggle popup logout
  const [showLogoutPopup, setShowLogoutPopup] = useState(false);
  const popupRef = useRef(null);

  // Close popup saat klik di luar
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
      className={`fixed left-0 top-0 h-screen flex flex-col transition-all duration-300 z-40 
      ${isOpen ? "w-70" : "w-15"} 
      bg-[#F7F8FC] dark:bg-[#1A1A1C] border-r border-[#E0E0E0] dark:border-[#2E2E33] text-black dark:text-white`}
    >
      {/* Header - Tambah trigger hover di sini */}
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className="p-3 p-4 border-black-700 relative flex flex-col justify-center dark:border-gray-700"
      >
        <div className="flex items-center">
          {/* Logo dengan transisi ukuran saat collapse */}
          <img
            src="./src/assets/cakra.png"
            alt="CAKRA AI Logo"
            className={`rounded-full object-cover transition-all duration-300 ${
              isOpen ? "w-10 h-10" : "w-7 h-7"
            } ${!isOpen && isHovered ? "opacity-0" : "opacity-100"}`}
          />
          <h1
            className={`font-bold text-lg text-black whitespace-nowrap transition-all duration-300 ml-2 dark:text-white ${
              !isOpen ? "opacity-0 pointer-events-none w-0" : "opacity-100"
            }`}
          >
            CAKRA AI
          </h1>
        </div>

        {/* Tombol Toggle - Muncul saat hover dalam kondisi collapse */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`absolute transition-all duration-300 p-1 hover:bg-black-700 rounded text-black-400 hover:text-black dark:text-gray-400 dark:hover:text-white ${
            isOpen
              ? "top-5 right-3 opacity-100"
              : `top-3 left-1/2 -translate-x-1/2 ${
                  isHovered
                    ? "opacity-100 scale-110"
                    : "opacity-0 pointer-events-none"
                }`
          }`}
          title={isOpen ? "Ciutkan" : "Lebarkan"}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-black dark:text-white"
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
      {/* Menu - Tombol New Chat */}
      <div
        className={`p-3 space-y-3 ${!isOpen && "flex flex-col items-center"}`}
      >
        <button
          onClick={clearChat}
          className={`flex items-center rounded-full hover:bg-gray-200 transition-colors group overflow-hidden text-[14px] dark:hover:bg-gray-800 ${
            isOpen ? "p-2 w-full space-x-3" : "p-2 justify-center"
          }`}
          title="New Chat"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-black-400 group-hover:text-blue-400 flex-shrink-0 dark:text-gray-400"
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
            className={`font-medium whitespace-nowrap transition-opacity duration-300 dark:text-white ${
              !isOpen ? "hidden" : "opacity-100"
            }`}
          >
            New Chat
          </span>
        </button>

        <button
          onClick={() => setShowDocumentList(true)}
          className={`flex items-center rounded-full hover:bg-gray-200 transition-colors group overflow-hidden text-[14px] dark:hover:bg-gray-800 ${
            isOpen ? "p-2 w-full space-x-3" : "p-2 justify-center"
          }`}
          title="Documents"
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            📄
          </span>
          <span
            className={`font-medium text-black-200 whitespace-nowrap transition-opacity duration-300 dark:text-gray-200 ${
              !isOpen ? "hidden" : "opacity-100"
            }`}
          >
            Documents
          </span>
        </button>
      </div>
      {/* History Sections */}
      <div
        className={`flex-1 overflow-y-auto px-2 py-2 space-y-0.5 transition-opacity duration-300 no-scrollbar ${
          !isOpen ? "opacity-0 pointer-events-none hidden" : "opacity-100"
        }`}
        style={{
          msOverflowStyle: "none" /* IE/Edge */,
          scrollbarWidth: "none" /* Firefox */,
        }}
      >
        {/* SEKSI SEMUA CHAT */}
        <div className="px-3 py-1 text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-1 dark:text-gray-400">
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
                onClick={() => loadChatSession(chat.session_uuid)}
                className={`group relative flex items-center px-3 py-2 text-sm rounded-full cursor-pointer transition-all ${
                  currentSessionId === chat.session_uuid
                    ? "bg-blue-200 text-blue-600 font-bold dark:bg-blue-900/40 dark:text-blue-400"
                    : "text-gray-600 hover:bg-gray-200 font-bold dark:text-gray-300 dark:hover:bg-gray-800"
                } ${
                  isDeletingId === chat.session_uuid ? "animate-delete" : ""
                }`}
                title={chat.judul}
              >
                {/* Ikon Lebih Kecil & Rapat */}
                <span className="mr-2 text-[12px] opacity-70 flex-shrink-0">
                  {chat.is_pinned ? "📌" : "💬"}
                </span>

                {/* Judul Chat dengan Font Lebih Kecil */}
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

                {/* Tombol Menu Titik Tiga (Muncul saat hover) */}
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
                      className="h-3 w-3 text-gray-500 dark:text-gray-400"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                    </svg>
                  </button>
                )}

                {/* Popup Menu Tetap Sama */}
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
      {/* Footer Profile */}
      <div
        className={`border-t border-t-[#E0E0E0] dark:border-t-[#1A1A1C] bg-[#F7F8FC] dark:bg-[#1A1A1C] border-black-700 relative flex flex-col dark:border-gray-700 ${
          !isOpen
            ? "p-1 items-center absolute left-0 right-0 justify-center"
            : "justify-center items-center p-2 p-3"
        }`}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
        }}
      >
        {/* POPUP MENU */}
        {showLogoutPopup && (
          <div
            ref={popupRef}
            className={`absolute bottom-full left-2 mb-2 w-48 rounded-xl shadow-2xl py-2 z-50 transition-all bg-[#F7F8FC] dark:bg-[#232326]  ${
              !isOpen && "left-full ml-2 bottom-2"
            }`}

          >
            <div className="px-4 py-2 ">
              <p className="text-xs text-black-400 dark:text-gray-400">
                Akun Anda
              </p>
              <p className="text-xs font-semibold truncate dark:text-white">
                {userData?.fullname || "Loading..."}
              </p>
            </div>

            {/* Logout */}
            <button
              onClick={() => {
                setShowLogoutPopup(false);
                triggerLogout();
              }}
              className="w-full flex items-center space-x-3 px-4 py-1 text-red-400 hover:bg-gray-100 transition-colors dark:hover:bg-gray-900 border-t border-t-[#E0E0E0] dark:border-t-[#1A1A1C]"
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
          className="flex items-center cursor-pointer w-full"
          onClick={() => setShowLogoutPopup(!showLogoutPopup)}
        >
          <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0 ml-2 border border-gray-700 bg-gray-800 flex items-center justify-center shadow-inner">
            {userData?.username ? (
              <>
                <img
                  src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.username}.jpg`}
                  alt="Profile"
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                    e.currentTarget.nextSibling.style.display = "flex";
                  }}
                />
                <div className="hidden w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold text-white">
                  {userData?.fullname
                    ? userData.fullname.substring(0, 2).toUpperCase()
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
            className={`flex flex-col min-w-0 transition-all duration-300 ${
              !isOpen ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
            }`}
          >
            <span className="text-xs font-medium truncate w-40 ml-3 dark:text-white">
              {userData?.fullname || "Loading..."}
            </span>
            <span className="text-[9px] text-black-500 text-left ml-3 dark:text-gray-400">
              {userData?.divisi || "Guest"}
            </span>
          </div>
        </div>

        {isOpen && (
          <button
            className="text-black-500 group-hover:text-black ml-auto absolute right-3 bottom-2 dark:text-gray-400 dark:hover:text-white"
            onClick={() => setShowLogoutPopup(!showLogoutPopup)}
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
                d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z"
              />
            </svg>
          </button>
        )}
        {/* MODAL CUSTOM DELETE */}
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
