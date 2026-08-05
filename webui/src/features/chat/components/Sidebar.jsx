import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useChatStore } from "@/stores/chatStore";
import SidebarHeader from "./Sidebar/SidebarHeader";
import SessionList from "./Sidebar/SessionList";
import SidebarFooter from "./Sidebar/SidebarFooter";
import SearchModal from "./modals/SearchModal";
import SettingsModal from "./SettingsModal";

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
  language,
  setLanguage,
  themeSetting,
  theme,
}) => {
  const [activeMenuId, setActiveMenuId] = useState(null);
  const menuRef = useRef(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [deleteModalPos, setDeleteModalPos] = useState({ top: 100, left: 268 });
  const [sessionSearchQuery, setSessionSearchQuery] = useState("");
  const sidebarSearchInputRef = useRef(null);
  const [isHovered, setIsHovered] = useState(false);
  const [showLogoutPopup, setShowLogoutPopup] = useState(false);
  const popupRef = useRef(null);
  const [isDeletingId, setIsDeletingId] = useState(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

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
        setIsSearchModalOpen(true);
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
    if (e && e.stopPropagation) e.stopPropagation();
    if (typeof window !== "undefined") {
      const itemEl = document.getElementById(`session-item-${sessionUuid}`);
      const targetEl = itemEl || (e && e.currentTarget);
      if (targetEl) {
        const rect = targetEl.getBoundingClientRect();
        const topPos = Math.max(16, Math.min(rect.top - 20, window.innerHeight - 220));
        setDeleteModalPos({ top: topPos, left: 268 });
      }
    }
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
    <>
      <div
      className={`fixed left-0 top-0 h-[100dvh] flex flex-col overflow-hidden transition-all duration-300 z-40 ${isMobile
          ? (isOpen ? "w-64 translate-x-0" : "w-64 -translate-x-full")
          : (isOpen ? "w-64 translate-x-0" : "w-16 translate-x-0")
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
        darkMode={darkMode}
        clearChat={clearChat}
        showDocumentList={showDocumentList}
        setShowDocumentList={setShowDocumentList}
        userData={userData}
        navigate={navigate}
        setIsSearchModalOpen={setIsSearchModalOpen}
        language={language}
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
        language={language}
        showDocumentList={showDocumentList}
        setShowDocumentList={setShowDocumentList}
        userData={userData}
        navigate={navigate}
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
        language={language}
        setLanguage={setLanguage}
        openSettingsModal={() => setIsSettingsModalOpen(true)}
      />
      </div>

      {/* DELETE CHAT MODAL (PORTAL OUTSIDE SIDEBAR, FLOATING RIGHT OF SELECTED TITLE) */}
      {showDeleteModal && typeof document !== "undefined" && createPortal(
        <div 
          className="fixed inset-0 z-[9999] bg-transparent"
          onClick={() => {
            setShowDeleteModal(false);
            setSessionToDelete(null);
          }}
        >
          <div 
            style={{ 
              position: "fixed", 
              top: `${deleteModalPos.top}px`, 
              left: `${deleteModalPos.left}px` 
            }}
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-gray-800 rounded-2xl p-5 w-72 shadow-2xl border border-gray-200 dark:border-gray-700 transform animate-in fade-in zoom-in-95 duration-200"
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mb-3 dark:bg-red-900/30">
                <span className="text-lg">🗑️</span>
              </div>
              <h3 className="text-base font-bold text-gray-900 dark:text-white">
                Hapus Chat?
              </h3>
              <p className="text-xs text-gray-500 mt-1 mb-4 dark:text-gray-400">
                Tindakan ini tidak dapat dibatalkan. Riwayat chat ini akan hilang selamanya.
              </p>
              <div className="flex gap-2 w-full">
                <button
                  onClick={() => {
                    setShowDeleteModal(false);
                    setSessionToDelete(null);
                  }}
                  className="flex-1 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-medium transition-colors dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                >
                  Batal
                </button>
                <button
                  onClick={executeDelete}
                  className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-medium transition-colors shadow-md shadow-red-200 dark:shadow-none"
                >
                  Ya, Hapus
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* SEARCH MODAL */}
      <SearchModal
        isOpen={isSearchModalOpen}
        onClose={() => setIsSearchModalOpen(false)}
        chatHistory={chatHistory}
        loadChatSession={(uuid) => {
          loadChatSession(uuid);
          setIsSearchModalOpen(false);
        }}
        darkMode={darkMode}
        theme={theme}
        language={language}
      />

      <SettingsModal 
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        darkMode={darkMode}
        theme={theme}
        themeSetting={themeSetting}
        language={language}
        setLanguage={setLanguage}
        setDarkMode={setDarkMode}
        userData={userData}
        triggerLogout={triggerLogout}
      />
    </>
  );
};

export default Sidebar;
