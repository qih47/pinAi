// src/components/layout/MainLayout.jsx
import React, { useRef } from "react"; // 1. Pastikan useRef di-import
import Sidebar from "../Sidebar";
import HeaderBar from "./HeaderBar";
import MessageList from "./MessageList";
import InputArea from "./InputArea";
import FloatingButtons from "./FloatingButtons";
import LoginModal from "../modals/LoginModal";
import LogoutModal from "../modals/LogoutModal";
import NotificationToast from "../ui/NotificationToast";

export default function MainLayout({
  // Props Identitas & Auth
  isLoggedIn,
  userData,
  cakraLogo,
  backendStatus,

  // Props Sidebar & Navigasi
  isSidebarOpen,
  setIsSidebarOpen,
  setShowDocumentList,
  currentSessionId,
  loadChatSession,
  handleNewChat,
  chatHistory,
  setChatHistory,
  triggerLogout,
  navigate,

  // Props Chat Logic
  messagesContainerRef,
  messages,
  isLoading,
  expandedMessages,
  toggleExpand,
  handleCopy,
  showNotification,
  currentMode,
  input,
  setInput,
  isAtBottom,
  isAiTypingRef,
  startAutoScroll,

  // Props Input & Files
  previews,
  setPreviews,
  selectedFiles,
  setSelectedFiles,
  isDragging,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  fileInputRef,
  handleFileChange,
  sendMessage,
  handleKeyPress,
  handlePaste,
  switchMode,

  // Props Modals & UI
  showLoginModal,
  setShowLoginModal,
  loginForm,
  setLoginForm,
  loginError,
  handleLoginSubmit,
  isLogoutModalOpen,
  setIsLogoutModalOpen,
  handleLogout,
  showPassword,
  setShowPassword,
  modelList,
  selectedModel,
  setSelectedModel,
  isDropdownOpen,
  setIsDropdownOpen,
  notification,
  getGreeting,

  // Props Ref yang sering bikin error jika undefined
  autoScrollEnabled: propAutoScroll,
  isUserScrolling: propIsUserScrolling,
}) {
  // 2. INTERNAL REFS (Safety Net)
  // Jika parent lupa kirim refs, kita pakai yang internal supaya .current tidak undefined
  const internalAutoScroll = useRef(true);
  const internalIsUserScrolling = useRef(false);

  const finalAutoScroll = propAutoScroll || internalAutoScroll;
  const finalIsUserScrolling = propIsUserScrolling || internalIsUserScrolling;

  return (
    <div className="bg-[#F7F8FC] dark:bg-[#232326] flex h-screen overflow-hidden text-gray-900 dark:text-gray-200 transition-colors duration-300">
      {/* 1. SIDEBAR */}
      {isLoggedIn && (
        <Sidebar
          backendStatus={backendStatus}
          isOpen={isSidebarOpen}
          setIsOpen={setIsSidebarOpen}
          userData={userData}
          setShowDocumentList={setShowDocumentList}
          currentSessionId={currentSessionId}
          loadChatSession={loadChatSession}
          clearChat={handleNewChat}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          triggerLogout={triggerLogout}
          cakraLogo={cakraLogo}
          navigate={navigate}
        />
      )}

      {/* 2. GUEST LOGO (Hanya muncul jika belum login) */}
      {!isLoggedIn && (
        <div className="absolute top-4 left-4 flex items-center z-50">
          <img
            src={cakraLogo}
            alt="Logo"
            className="w-10 h-10 object-cover rounded-full shadow-md"
          />
        </div>
      )}

      {/* 3. MAIN CONTENT AREA */}
      <div
        className={`flex flex-col flex-1 h-full transition-all duration-300 relative w-full ${
          isLoggedIn
            ? isSidebarOpen
              ? "md:ml-64 ml-0"
              : "md:ml-20 ml-0"
            : "ml-0"
        }`}
      >
        {/* HEADER BAR (Model Selector) */}
        {isLoggedIn && (
          <HeaderBar
            isSidebarOpen={isSidebarOpen}
            modelList={modelList}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            isDropdownOpen={isDropdownOpen}
            setIsDropdownOpen={setIsDropdownOpen}
          />
        )}

        {/* LOGIN BUTTON FOR GUEST */}
        {!isLoggedIn && (
          <div className="absolute top-4 right-4 z-50">
            <button
              onClick={() => setShowLoginModal(true)}
              className="px-5 py-1.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-full font-bold shadow-lg hover:shadow-blue-500/20 hover:scale-105 transition-all active:scale-95"
            >
              Login
            </button>
          </div>
        )}

        {/* --- WRAPPER CHAT & FLOATING BUTTON --- */}
        <div className="flex-1 relative overflow-hidden flex flex-col mt-2">
          <MessageList
            messagesContainerRef={messagesContainerRef}
            messages={messages}
            isLoading={isLoading}
            expandedMessages={expandedMessages}
            toggleExpand={toggleExpand}
            handleCopy={handleCopy}
            showNotification={showNotification}
            cakraLogo={cakraLogo}
            isLoggedIn={isLoggedIn}
            userData={userData}
            getGreeting={getGreeting}
            isAtBottom={isAtBottom}
            isAiTypingRef={isAiTypingRef}
            startAutoScroll={startAutoScroll}
            autoScrollEnabled={finalAutoScroll}
            isUserScrolling={finalIsUserScrolling}
            setInput={setInput}
          />
        </div>
        {/* FLOATING ACTION BUTTONS (Scroll to bottom/top) */}
        <div className="relative right-2 z-40">
          <FloatingButtons
            messagesContainerRef={messagesContainerRef}
            isAtBottom={isAtBottom}
            isAiTypingRef={isAiTypingRef}
            startAutoScroll={startAutoScroll}
            autoScrollEnabled={finalAutoScroll}
            isUserScrolling={finalIsUserScrolling}
          />
        </div>
        {/* INPUT AREA */}
        <InputArea
          currentMode={currentMode}
          input={input}
          setInput={setInput}
          previews={previews}
          setPreviews={setPreviews}
          selectedFiles={selectedFiles}
          setSelectedFiles={setSelectedFiles}
          isDragging={isDragging}
          handleDragOver={handleDragOver}
          handleDragLeave={handleDragLeave}
          handleDrop={handleDrop}
          fileInputRef={fileInputRef}
          handleFileChange={handleFileChange}
          sendMessage={sendMessage}
          handleKeyPress={handleKeyPress}
          handlePaste={handlePaste}
          isLoading={isLoading}
          isLoggedIn={isLoggedIn}
          switchMode={switchMode}
        />
      </div>

      {/* 4. MODALS & OVERLAYS */}
      {showLoginModal && (
        <LoginModal
          setShowLoginModal={setShowLoginModal}
          loginForm={loginForm}
          setLoginForm={setLoginForm}
          loginError={loginError}
          handleLoginSubmit={handleLoginSubmit}
          showPassword={showPassword}
          setShowPassword={setShowPassword}
          cakraLogo={cakraLogo}
        />
      )}

      {isLogoutModalOpen && (
        <LogoutModal
          setIsLogoutModalOpen={setIsLogoutModalOpen}
          handleLogout={handleLogout}
        />
      )}

      {notification && <NotificationToast notification={notification} />}
    </div>
  );
}
