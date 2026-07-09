import React, { useState, useRef, useEffect, useMemo } from "react";
import { useChatStore, API_BASE, getUploadUrl } from "../../stores/chatStore";
import { uploadDocuments } from "../../services/endpoints";
import useToast from "../../hooks/useToast";
import cakraLogo from "../../assets/cakra.png";
import { styles, lightColors, darkColors } from "./chatPage.styles";
import ChatArea from "./components/ChatArea";
import GuestWelcome from "../../components/ui/GuestWelcome";
import Sidebar from "./components/Sidebar";
import { useNavigate, useParams } from "react-router-dom";
import { useChatAuthStore } from "../../stores/authStore";
import HeaderDropdownMenu from "./components/HeaderDropdownMenu";
import NotificationBell from "../../components/NotificationBell"; // 👈 W16: Notification center
import PreviewImageModal from "./components/modals/PreviewImageModal";
import ContextIsolationModal from "./components/modals/ContextIsolationModal";
import GhostWriterModal from "./components/modals/GhostWriterModal";
import RightSidebar from "./components/RightSidebar";
import ChatInputArea from "./components/ChatInputArea";
import EmailTriageTab from "../corporate/EmailTriageTab";
import DocumentGeneratorTab from "../corporate/DocumentGeneratorTab";
import VendorAnalyzerTab from "../corporate/VendorAnalyzerTab";
import PdfInterrogator from "./components/PdfInterrogator";

// ============================================================
// MAIN COMPONENT
// ============================================================

import { useChatLogic } from "./hooks/useChatLogic";

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function ChatPage({ isGuest,
  isLoggedIn: propsIsLoggedIn,
  userData: propsUserData,
  getGreeting,
  corporateMode }) {
  const chatLogic = useChatLogic({
    isGuest,
    isLoggedIn: propsIsLoggedIn,
    userData: propsUserData,
    getGreeting,
  });
  const {
    activeIsolatedDocId, activeIsolatedTitle, activeSessionId, artifactContent, artifacts, authUser, baselineHeightRef, bottomRef, chatHistory, chatMode, chatModeRef, currentIsLoggedIn, currentThinking, currentUserData, darkMode, defaultGetGreeting, detectLang, docContent, docSearchQuery, documents, documentsTotal, fetchDocumentsList, fileInputRef, handleChatModeChange, handleClearChat, handleDownloadAllArtifacts, handleDownloadArtifact, handleDragLeave, handleDragOver, handleDrop, handleFileChange, handleFileClick, handleKeyDown, handleOpenArtifact, handlePaste, handleSubmit, handleThinkingModeChange, hasSidebar, input, isArtifactLoading, isAuthenticated, isDocLoading, isDragOver, isEmptyChat, isLoading, isLoadingDocuments, isMobile, isMultiLine, isResizingRightSidebar, isStreaming, isStreamingText, isThinking, isThinkingMode, isThinkingModeRef, isUploadingFile, lastAssistantIndex, lastLoadedSessionRef, loadChatSession, logout, mainMarginLeft, mainMarginRight, messageSearchInputRef, messages, messagesContainerRef, msgSearchQuery, navigate, previewArtifact, previewDoc, previewImage, removeFilePreview, rightSidebarWidth, selectedFiles, selectedMode, sessionAttachments, setChatHistory, setChatMode, setContextIsolation, setDarkMode, setDocContent, setDocSearchQuery, setInput, setIsArtifactLoading, setIsDocLoading, setIsDragOver, setIsMobile, setIsMultiLine, setIsThinkingMode, setIsUploadingFile, setMsgSearchQuery, setPreviewArtifact, setPreviewDoc, setPreviewImage, setRightSidebarWidth, setSelectedFiles, setSelectedMode, setShowDocumentList, setShowMsgSearch, setShowRightSidebar, setShowScrollBottom, setSidebarOpen, setStagedAttachments, showDocumentList, showMsgSearch, showRightSidebar, showScrollBottom, showWelcome, sidebarOpen, singleLineWidthRef, stagedAttachments, startResizingRightSidebar, storeChatMode, textareaRef, theme, toast, toggleRightSidebar, triggerLogout, validateFile, wasLeftSidebarOpenRef
  } = chatLogic;

  return (
    <div style={{ ...styles.root, background: theme.rootBg }}>
      {/* ── BACKDROP MOBILE ── */}
      {isMobile && hasSidebar && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            backdropFilter: "blur(4px)",
            zIndex: 35, // Sidebar adalah 40
            animation: "fadeInUp 0.3s ease-out",
          }}
        />
      )}

      {/* 1. KEMBALIKAN ANIMASI CAKRA BERPIKIR & STREAMING REVEAL */}
      <style>{`
        @keyframes cakraSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes logoFloat {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-6px) rotate(3deg); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes geminiReveal {
          from { opacity: 0; transform: translateY(3px); filter: blur(2px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
        /* Kelas pulse/kedut berpikir asisten */
        .thinking-pulse {
          animation: geminiReveal 0.6s ease-in-out infinite alternate;
          opacity: 0.6;
        }
        .assistant-content-container p, .assistant-content-container pre {
          animation: geminiReveal 0.35s ease-out forwards;
        }
        textarea {
        }
        textarea::-webkit-scrollbar {
          width: 6px;
          background: transparent;
        }
        textarea::-webkit-scrollbar-track {
          background: transparent;
        }
        textarea::-webkit-scrollbar-thumb {
          background: ${darkMode ? "#4b5563" : "#cbd5e1"};
          border-radius: 3px;
        }
        textarea::-webkit-scrollbar-thumb:hover {
          background: ${darkMode ? "#6b7280" : "#94a3b8"};
        }
        textarea::-webkit-scrollbar-button {
          display: none !important;
          width: 0 !important;
          height: 0 !important;
          -webkit-appearance: none !important;
        }
        * { box-sizing: border-box; }
        .custom-scroll-gemini::-webkit-scrollbar { width: 8px; background-color: transparent; }
        .custom-scroll-gemini::-webkit-scrollbar-thumb {
          background-color: ${darkMode ? "rgba(255, 255, 255, 0.15)" : "rgba(0, 0, 0, 0.15)"};
          border-radius: 20px;
        }
        .custom-scroll-gemini::-webkit-scrollbar-button { display: none !important; width: 0 !important; height: 0 !important; -webkit-appearance: none !important; }
        .custom-scroll-gemini::-webkit-scrollbar-corner { background: transparent; }

        /* ── ANIMASI SHIMMER & BOUNCE ── */
        @keyframes skeletonShimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .skeleton-shimmer {
          background: ${darkMode ? "linear-gradient(90deg, #1e1e20 25%, #2a2a2d 50%, #1e1e20 75%)" : "linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)"};
          background-size: 200% 100%;
          animation: skeletonShimmer 1.5s infinite linear;
        }
        @keyframes dotBounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1.0); }
        }
        @keyframes shimmerFlow {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {!isGuest && currentIsLoggedIn && (
        <Sidebar
          isOpen={sidebarOpen}
          setIsOpen={setSidebarOpen}
          isMobile={isMobile}
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          theme={theme}
          clearChat={handleClearChat}
          showDocumentList={showDocumentList}
          setShowDocumentList={setShowDocumentList}
          userData={currentUserData}
          triggerLogout={triggerLogout}
          loadChatSession={loadChatSession}
          currentSessionId={activeSessionId}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          cakraLogo={cakraLogo}
          navigate={navigate}
        />
      )}

      <main
        style={{
          ...styles.main,
          background: theme.mainBg,
          marginLeft: mainMarginLeft,
          transition: "margin-left 0.3s ease-in-out",
        }}
      >
        <header style={{
          ...styles.header,
          display: corporateMode === 'mail' ? 'none' : 'flex',
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          paddingLeft: "12px",
          paddingRight: "12px",

          // 🔥 KUNCI TRANSPARAN: Gak ada background, gak ada border sama sekali!
          background: "transparent",
          borderBottom: "none",
          boxShadow: "none",

          // Posisi tetap di atas melayang
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 30,
          height: "56px",
          transition: "width 0.3s ease-in-out",
        }}>

          {/* ── BLOK KIRI: Hamburger Menu ── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0px' }}>
            {/* ☰ HAMBURGER MENU MOBILE */}
            {isMobile && hasSidebar && (
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: theme.iconColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "6px",
                  borderRadius: "8px",
                }}
                title="Buka Menu"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
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

            {!hasSidebar && (
              <img
                // src={cakraLogo}
                // alt="CAKRA AI"
                style={{ height: "40px", width: "auto", objectFit: "contain" }}
              />
            )}
          </div>
          {/* 🔥 MODIFIKASI HEADER ACTIONS: Bungkus tombol login & tema ke dalam Kebab Dropdown */}
          <div
            style={{
              ...styles.headerActions,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {/* ✚ TOMBOL NEW CHAT MOBILE */}
            {isMobile && hasSidebar && (
              <button
                onClick={handleClearChat}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: theme.iconColor,
                  transition: "background 0.2s",
                  outline: "none",
                }}
                title="Chat Baru"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
            )}

            {/* 🔍 INPUT PENCARIAN DI NAVBAR */}
            {showMsgSearch && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: darkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)",
                  borderRadius: '20px',
                  padding: '4px 12px',
                  marginRight: '4px',
                  border: `1px solid ${darkMode ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)"}`,
                }}
              >
                <input
                  ref={messageSearchInputRef}
                  type="text"
                  placeholder="Cari kata kunci..."
                  value={msgSearchQuery}
                  onChange={(e) => setMsgSearchQuery(e.target.value)}
                  style={{
                    border: "none",
                    background: "transparent",
                    outline: "none",
                    color: theme.textColor,
                    fontSize: "13px",
                    width: "160px"
                  }}
                />
              </div>
            )}

            {/* 🔍 TOMBOL CARI (Dipindah ke kiri File) */}
            {messages.length > 0 && (
              <button
                onClick={() => {
                  if (showMsgSearch) {
                    setShowMsgSearch(false);
                    setMsgSearchQuery("");
                  } else {
                    setShowMsgSearch(true);
                    setTimeout(() => {
                      messageSearchInputRef.current?.focus();
                    }, 100);
                  }
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: theme.iconColor,
                  transition: "background 0.2s",
                  outline: "none",
                }}
                onMouseEnter={(e) =>
                (e.currentTarget.style.background = darkMode
                  ? "rgba(255,255,255,0.05)"
                  : "rgba(0,0,0,0.05)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
                title="Cari kata kunci dalam percakapan ini (Ctrl+F)"
              >
                {/* 🔥 ICON SVG MINIMALIS MODERN */}
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor" // ← SAKTI: Otomatis ngikutin warna theme.iconColor dari button parent-nya
                  strokeWidth="2.3"      // ← Tingkat ketebalan garis biar makin tegas
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ opacity: 0.85 }} // Biar gak terlalu mencolok benderang
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
              </button>
            )}

            {/* 📁 TOMBOL SESSION FILES (Dipindah ke kanan Search) */}
            {messages.length > 0 && (
              <button
                onClick={toggleRightSidebar}
                style={{
                  background: showRightSidebar ? (darkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)") : "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: showRightSidebar ? "#6366f1" : theme.iconColor,
                  transition: "all 0.2s",
                  outline: "none",
                }}
                onMouseEnter={(e) => {
                  if (!showRightSidebar) e.currentTarget.style.background = darkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
                }}
                onMouseLeave={(e) => {
                  if (!showRightSidebar) e.currentTarget.style.background = "transparent";
                }}
                title="File Sesi Ini"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
              </button>
            )}
            {/* 👇 W16: Notification Bell */}
            {!isGuest}
            <HeaderDropdownMenu
              isGuest={isGuest}
              onLogin={() => {
                const currentSession = useChatStore.getState().sessionUuid;
                if (currentSession && currentSession !== "new") {
                  localStorage.setItem("cakra_last_session", currentSession);
                }
                navigate("/login");
              }}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
              theme={theme}
            />
          </div>
        </header>

        {/* WRAPPER FOR SPLIT SCREEN */}
        <div style={{ flex: 1, display: "flex", flexDirection: "row", overflow: "hidden", marginTop: 0 }}>
          <PdfInterrogator darkMode={darkMode} />
          <div
            style={{
              flex: 1,
              position: "relative",
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              overflow: "hidden",
              marginRight: mainMarginRight,
              transition: "margin-right 0.3s ease-in-out",
            }}
          >
            <div
              style={{
                flex: 1,
                minHeight: 0,
                opacity: showWelcome && !corporateMode ? 0 : 1,
                transition: "opacity 0.2s ease",
                pointerEvents: showWelcome && !corporateMode ? "none" : "auto",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {corporateMode === 'mail' && <EmailTriageTab theme={theme} darkMode={darkMode} userData={currentUserData} />}
              {corporateMode === 'notadinas' && <DocumentGeneratorTab theme={theme} darkMode={darkMode} userData={currentUserData} />}
              {corporateMode === 'vendor' && <VendorAnalyzerTab theme={theme} darkMode={darkMode} userData={currentUserData} />}

              {!corporateMode && (
                <>


                  <ChatArea
                    key={activeSessionId || 'new'}
                    messages={messages}
                    isStreaming={isStreaming}
                    theme={theme}
                    darkMode={darkMode}
                    bottomRef={bottomRef}
                    messagesContainerRef={messagesContainerRef}
                    setInput={setInput}
                    isThinking={isThinking}
                    currentThinking={currentThinking}
                    isStreamingText={isStreamingText}
                    lastAssistantIndex={lastAssistantIndex}
                    searchQuery={msgSearchQuery}
                    isLoading={isLoading}
                    onAtBottomChange={(isAtBottom) => setShowScrollBottom(!isAtBottom)}
                    onFileClick={handleFileClick}
                    setPreviewImage={setPreviewImage}
                    onOpenArtifact={handleOpenArtifact}
                    handleDownloadAllArtifacts={handleDownloadAllArtifacts}
                  />
                </>
              )}
            </div>

            {showWelcome && !corporateMode && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  transform: "translateY(-8%)",
                  zIndex: 10,
                  animation: "fadeInUp 0.4s ease-out",
                  pointerEvents: "none",
                }}
              >
                <div style={{ pointerEvents: "auto" }}>
                  <GuestWelcome
                    isLoggedIn={currentIsLoggedIn}
                    userData={{
                      fullname:
                        currentUserData?.name ||
                        currentUserData?.fullname ||
                        "Pegawai",
                      npp: currentUserData?.npp || "NPP -----",
                    }}
                    getGreeting={getGreeting || defaultGetGreeting}
                    theme={theme}
                    darkMode={darkMode}
                    isMobile={isMobile}
                  />
                </div>
                <div
                  style={{
                    width: "100%",
                    maxWidth: "700px",
                    padding: "0 20px",
                    marginTop: "0px",
                    pointerEvents: "auto",
                  }}
                >
                  <ChatInputArea
                    theme={theme}
                    darkMode={darkMode}
                    isBottom={true}
                    showScrollBottom={showScrollBottom}
                    showWelcome={showWelcome}
                    messages={messages}
                    messagesContainerRef={messagesContainerRef}
                    activeIsolatedTitle={activeIsolatedTitle}
                    setContextIsolation={setContextIsolation}
                    selectedFiles={selectedFiles}
                    removeFilePreview={removeFilePreview}
                    handleSubmit={handleSubmit}
                    handlePaste={handlePaste}
                    handleDragOver={handleDragOver}
                    handleDragLeave={handleDragLeave}
                    handleDrop={handleDrop}
                    isDragOver={isDragOver}
                    fileInputRef={fileInputRef}
                    handleFileChange={handleFileChange}
                    isGuest={isGuest}
                    currentIsLoggedIn={currentIsLoggedIn}
                    isMultiLine={isMultiLine}
                    isStreaming={isStreaming}
                    isUploadingFile={isUploadingFile}
                    textareaRef={textareaRef}
                    input={input}
                    setInput={setInput}
                    handleKeyDown={handleKeyDown}
                    chatMode={chatMode}
                    handleChatModeChange={handleChatModeChange}
                    isThinkingMode={isThinkingMode}
                    handleThinkingModeChange={handleThinkingModeChange}
                    styles={styles}
                  />
                </div>
              </div>
            )}


            {/* Hanya render input di bawah jika chat sudah ada dan bukan corporate mode */}
            {!showWelcome && !corporateMode && (
              <ChatInputArea
                theme={theme}
                darkMode={darkMode}
                isBottom={true}
                showScrollBottom={showScrollBottom}
                showWelcome={showWelcome}
                messages={messages}
                messagesContainerRef={messagesContainerRef}
                activeIsolatedTitle={activeIsolatedTitle}
                setContextIsolation={setContextIsolation}
                selectedFiles={selectedFiles}
                removeFilePreview={removeFilePreview}
                handleSubmit={handleSubmit}
                handlePaste={handlePaste}
                handleDragOver={handleDragOver}
                handleDragLeave={handleDragLeave}
                handleDrop={handleDrop}
                isDragOver={isDragOver}
                fileInputRef={fileInputRef}
                handleFileChange={handleFileChange}
                isGuest={isGuest}
                currentIsLoggedIn={currentIsLoggedIn}
                isMultiLine={isMultiLine}
                isStreaming={isStreaming}
                isUploadingFile={isUploadingFile}
                textareaRef={textareaRef}
                input={input}
                setInput={setInput}
                handleKeyDown={handleKeyDown}
                chatMode={chatMode}
                handleChatModeChange={handleChatModeChange}
                isThinkingMode={isThinkingMode}
                handleThinkingModeChange={handleThinkingModeChange}
                styles={styles}
              />
            )}
          </div>
        </div>

      </main>

      {/* 🔒 W7: Modal Pilihan Dokumen Regulasi (Context Isolation) */}
      <ContextIsolationModal
        showModal={showDocumentList}
        onClose={() => setShowDocumentList(false)}
        documents={documents}
        documentsTotal={documentsTotal}
        fetchDocumentsList={fetchDocumentsList}
        isLoadingDocuments={isLoadingDocuments}
        activeIsolatedDocId={activeIsolatedDocId}
        onSelectDocument={setContextIsolation}
        theme={theme}
        darkMode={darkMode}
      />
      {false && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.5)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "fadeInUp 0.2s ease-out",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: darkMode ? "#1e1e20" : "#ffffff",
              color: theme.textColor,
              width: "100%",
              maxWidth: "550px",
              borderRadius: "16px",
              border: `1px solid ${theme.borderColor}`,
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.3)",
              display: "flex",
              flexDirection: "column",
              maxHeight: "80vh",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "16px 20px",
                borderBottom: `1px solid ${theme.borderColor}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
                Daftar Dokumen Regulasi
              </h3>
              <button
                onClick={() => setShowDocumentList(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: theme.secondaryText,
                  cursor: "pointer",
                  fontSize: "18px",
                  fontWeight: "bold",
                }}
              >
                ✕
              </button>
            </div>

            <div
              style={{
                padding: "16px 20px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                flex: 1,
                overflowY: "auto",
              }}
            >
              <input
                type="text"
                placeholder="Cari nama dokumen atau nomor..."
                value={docSearchQuery}
                onChange={(e) => setDocSearchQuery(e.target.value)}
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: `1px solid ${theme.inputBorder}`,
                  background: theme.inputBg,
                  color: theme.textColor,
                  outline: "none",
                  fontSize: "14px",
                  width: "100%",
                }}
              />

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  marginTop: "4px",
                }}
                className="custom-scroll-gemini"
              >
                {isLoadingDocuments ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: "20px",
                      color: theme.secondaryText,
                    }}
                  >
                    Memuat dokumen...
                  </div>
                ) : documents.filter(
                  (doc) =>
                    (doc.title || "")
                      .toLowerCase()
                      .includes(docSearchQuery.toLowerCase()) ||
                    (doc.nomor || "")
                      .toLowerCase()
                      .includes(docSearchQuery.toLowerCase()),
                ).length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: "20px",
                      color: theme.secondaryText,
                    }}
                  >
                    Tidak ada dokumen ditemukan.
                  </div>
                ) : (
                  documents
                    .filter(
                      (doc) =>
                        (doc.title || "")
                          .toLowerCase()
                          .includes(docSearchQuery.toLowerCase()) ||
                        (doc.nomor || "")
                          .toLowerCase()
                          .includes(docSearchQuery.toLowerCase()),
                    )
                    .map((doc) => {
                      const isIsolated = activeIsolatedDocId === doc.id;
                      return (
                        <div
                          key={doc.id}
                          style={{
                            padding: "12px 16px",
                            borderRadius: "10px",
                            background: isIsolated
                              ? darkMode
                                ? "rgba(99, 102, 241, 0.15)"
                                : "rgba(37, 99, 235, 0.08)"
                              : darkMode
                                ? "#2a2a2d"
                                : "#f9fafb",
                            border: `1px solid ${isIsolated ? (darkMode ? "#6366f1" : "#2563eb") : theme.borderColor}`,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: "12px",
                            transition: "all 0.15s ease",
                          }}
                        >
                          <div
                            style={{ minWidth: 0, flex: 1, textAlign: "left" }}
                          >
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: "13.5px",
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              {doc.title}
                            </div>
                            <div
                              style={{
                                fontSize: "11px",
                                color: theme.secondaryText,
                                marginTop: "2px",
                              }}
                            >
                              No: {doc.nomor || "-"} | Tipe: {doc.jenis_dokumen || "-"}
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              setContextIsolation(doc.id, doc.title);
                              setShowDocumentList(false);
                            }}
                            style={{
                              padding: "6px 12px",
                              borderRadius: "20px",
                              border: "none",
                              background: isIsolated ? "#ef4444" : "#6366f1",
                              color: "#ffffff",
                              fontSize: "12px",
                              fontWeight: 600,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                              flexShrink: 0,
                            }}
                          >
                            {isIsolated ? "Batal Fokus" : "Fokus"}
                          </button>
                        </div>
                      );
                    })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {/* 📁 RIGHT SIDEBAR SESSION FILES */}
      <RightSidebar
        isMobile={isMobile}
        theme={theme}
        darkMode={darkMode}
        previewDoc={previewDoc}
        setPreviewDoc={setPreviewDoc}
        docContent={docContent}
        isDocLoading={isDocLoading}
        previewArtifact={previewArtifact}
        setPreviewArtifact={setPreviewArtifact}
        artifactContent={artifactContent}
        isArtifactLoading={isArtifactLoading}
        rightSidebarWidth={rightSidebarWidth}
        showRightSidebar={showRightSidebar}
        isResizingRightSidebar={isResizingRightSidebar}
        startResizingRightSidebar={startResizingRightSidebar}
        artifacts={artifacts}
        sessionAttachments={sessionAttachments}
        handleOpenArtifact={handleOpenArtifact}
        handleDownloadArtifact={handleDownloadArtifact}
        handleDownloadAllArtifacts={handleDownloadAllArtifacts}
        setPreviewImage={setPreviewImage}
        setShowRightSidebar={setShowRightSidebar}
      />

      {/* 🖼️ IMAGE PREVIEW MODAL */}
      <PreviewImageModal
        previewImage={previewImage}
        onClose={() => setPreviewImage(null)}
      />

      {/* ✍️ GHOSTWRITER MODAL */}
      <GhostWriterModal darkMode={darkMode} theme={theme} />
    </div>
  );
}
