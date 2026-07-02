import React, { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import SidebarHeader from "./Sidebar/SidebarHeader";
import SessionList from "./Sidebar/SessionList";
import SidebarFooter from "./Sidebar/SidebarFooter";

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
  darkMode,
  setDarkMode,
  theme,
}) => {
  const [activeMenuId, setActiveMenuId] = useState(null);
  const menuRef = useRef(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [sessionSearchQuery, setSessionSearchQuery] = useState("");
  const sidebarSearchInputRef = useRef(null);
  const [isHovered, setIsHovered] = useState(false);
  const [showLogoutPopup, setShowLogoutPopup] = useState(false);
  const popupRef = useRef(null);
  const [isDeletingId, setIsDeletingId] = useState(null);

  const pinChat = useChatStore((state) => state.pinChat);
  const renameChat = useChatStore((state) => state.renameChat);
  const deleteChat = useChatStore((state) => state.deleteChat);
  const fetchChatHistory = useChatStore((state) => state.fetchChatHistory);

  const profileName = userData?.fullname || userData?.name || "Pegawai Pindad";
  const profileDivisi = userData?.divisi || "Pegawai Resmi";

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

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const confirmDelete = (e, sessionUuid) => {
    e.stopPropagation();
    setSessionToDelete(sessionUuid);
    setShowDeleteModal(true);
    setActiveMenuId(null);
  };

  const executeDelete = async () => {
    if (!sessionToDelete) return;

    try {
      setIsDeletingId(sessionToDelete);
      setShowDeleteModal(false);

      await new Promise((resolve) => setTimeout(resolve, 400));

      const result = await deleteChat(sessionToDelete, userData?.npp);

      if (result.status === "success") {
        setChatHistory((prev) =>
          prev.filter((c) => c.session_uuid !== sessionToDelete),
        );

        if (currentSessionId === sessionToDelete) {
          clearChat();
          navigate("/chat/new");
        }
      }
    } catch (err) {
      console.error("Gagal menghapus:", err);
    } finally {
      setIsDeletingId(null);
      setSessionToDelete(null);
    }
  };

  const hasFetchedRef = useRef(false);

  useEffect(() => {
    const initHistory = async () => {
      if (
        userData?.npp &&
        userData.npp !== "NPP ------" &&
        !hasFetchedRef.current
      ) {
        hasFetchedRef.current = true;
        try {
          const result = await fetchChatHistory(userData.npp);
          if (result.status === "success") {
            setChatHistory(result.data);
          }
        } catch (err) {
          hasFetchedRef.current = false;
          console.error("Gagal memuat riwayat awal:", err);
        }
      }
    };
    initHistory();
  }, [userData?.npp]);

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
      className={`fixed left-0 top-0 h-[100dvh] flex flex-col transition-all duration-300 z-40 ${
        isMobile 
          ? (isOpen ? "w-72 translate-x-0" : "w-72 -translate-x-full")
          : (isOpen ? "w-72 translate-x-0" : "w-16 translate-x-0")
      }`}
      style={{
        background: darkMode ? "#1E1E22" : theme?.sidebarBg || "#F7F8FC",
        color: theme?.textColor || (darkMode ? "#e2e8f0" : "#1f2937"),
        borderRight: darkMode ? "1px solid #2a2a2d" : "1px solid #E5E7EB",
      }}
    >
      <SidebarHeader
        isOpen={isOpen}
        setIsOpen={setIsOpen}
        isMobile={isMobile}
        isHovered={isHovered}
        setIsHovered={setIsHovered}
        cakraLogo={cakraLogo}
        theme={theme}
        clearChat={clearChat}
        showDocumentList={showDocumentList}
        setShowDocumentList={setShowDocumentList}
        userData={userData}
        navigate={navigate}
      />

      <SessionList
        isOpen={isOpen}
        chatHistory={chatHistory}
        setChatHistory={setChatHistory}
        currentSessionId={currentSessionId}
        loadChatSession={loadChatSession}
        theme={theme}
        darkMode={darkMode}
        pinChat={pinChat}
        renameChat={renameChat}
        deleteChat={deleteChat}
        menuRef={menuRef}
        activeMenuId={activeMenuId}
        setActiveMenuId={setActiveMenuId}
        sessionSearchQuery={sessionSearchQuery}
        setSessionSearchQuery={setSessionSearchQuery}
        sidebarSearchInputRef={sidebarSearchInputRef}
        confirmDelete={confirmDelete}
        isDeletingId={isDeletingId}
      />

      <SidebarFooter
        isOpen={isOpen}
        darkMode={darkMode}
        theme={theme}
        showLogoutPopup={showLogoutPopup}
        setShowLogoutPopup={setShowLogoutPopup}
        popupRef={popupRef}
        profileName={profileName}
        profileDivisi={profileDivisi}
        setDarkMode={setDarkMode}
        triggerLogout={triggerLogout}
        userData={userData}
      />

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
              <p className="text-sm text-gray-500 mt-2 mb-6 dark:text-gray-400">
                Tindakan ini tidak dapat dibatalkan. Riwayat chat ini akan
                hilang selamanya.
              </p>
              <div className="flex gap-3 w-full">
                <button
                  onClick={() => {
                    setShowDeleteModal(false);
                    setSessionToDelete(null);
                  }}
                  className="flex-1 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-medium transition-colors dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                >
                  Batal
                </button>
                <button
                  onClick={executeDelete}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium transition-colors shadow-lg shadow-red-200 dark:shadow-none"
                >
                  Ya, Hapus
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
