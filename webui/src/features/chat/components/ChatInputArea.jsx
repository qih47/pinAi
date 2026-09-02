import React, { useState, useRef, useEffect } from "react";
import PlusButton from "./PlusButton";
import CustomModeSelector from "./CustomModeSelector";
import SendButton from "./SendButton";
import { useChatStore } from "../../../stores/chatStore";
import ScrollBottomButton from "./ChatInputArea/ScrollBottomButton";
import IsolatedDocBanner from "./ChatInputArea/IsolatedDocBanner";
import AttachmentPreview from "./ChatInputArea/AttachmentPreview";
import useNextcloudStore from "../../../stores/nextcloudStore";
import { Paperclip, Cloud, Globe, FileText, Code2, Target, X, BarChart3, Workflow, FilePlus, Mail } from "lucide-react";
import VoiceButton from "./ChatInputArea/VoiceButton";
import PlusActionMenu from "./ChatInputArea/PlusActionMenu";
import { translations } from "../../../utils/translations";
import InteractiveWizardWidget from "./InteractiveWizardWidget";
import HintSuggestions from "./HintSuggestions";

export default function ChatInputArea({
  theme,
  darkMode,
  isBottom = false,
  isMobile = false,
  showScrollBottom,
  showWelcome,
  messages,
  messagesContainerRef,
  activeIsolatedTitle,
  setContextIsolation,
  selectedFiles,
  removeFilePreview,
  handleSubmit,
  handleSelectHint,
  handlePaste,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  isDragOver,
  fileInputRef,
  handleFileChange,
  isGuest,
  currentIsLoggedIn,
  isMultiLine,
  isStreaming,
  isUploadingFile,
  inputShake,
  textareaRef,
  input,
  setInput,
  handleKeyDown,
  chatMode,
  handleChatModeChange,
  isThinkingMode,
  handleThinkingModeChange,
  styles,
  language
}) {
  const [isAttachmentMenuOpen, setIsAttachmentMenuOpen] = useState(false);
  const attachmentMenuRef = useRef(null);
  const t = translations[language]?.chatInput || translations.id.chatInput;
  const tHints = translations[language]?.chat?.hints || translations.id.chat.hints;
  const openNextcloudModal = useNextcloudStore(state => state.openModal);
  const activeWizard = useChatStore(state => state.activeWizard);
  const activeModeTag = useChatStore(state => state.activeModeTag);
  const setActiveModeTag = useChatStore(state => state.setActiveModeTag);

  // Pada mode mobile, selalu gunakan layout bertingkat (textarea di atas, buttons di bawah)
  // Pada mode desktop, tetap responsif mengikuti state isMultiLine
  const showMultilineLayout = isMobile || isMultiLine;

  const renderActiveModePill = () => {
    if (!activeModeTag) return null;
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "7px",
          padding: "4px 10px",
          borderRadius: "10px",
          fontSize: "13px",
          fontWeight: "500",
          background: darkMode ? "#1f1f23" : "#e5e7eb",
          color: darkMode ? "#ffffff" : "#111827",
          flexShrink: 0,
          userSelect: "none",
          alignSelf: "center",
          marginLeft: "2px",
          marginRight: "2px"
        }}
      >
        {activeModeTag === "code" && <Code2 size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "websearch" && <Globe size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "documents" && <FileText size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "diagram" && <Workflow size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "chart" && <BarChart3 size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "create_file" && <FilePlus size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "smart_mail" && <Mail size={15} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "focus" && <Target size={15} className="opacity-90 flex-shrink-0" />}
        <span style={{ letterSpacing: "0.01em" }}>
          {activeModeTag === "code"
            ? tHints.code
            : activeModeTag === "websearch"
              ? tHints.websearch
              : activeModeTag === "documents"
                ? tHints.documents
                : activeModeTag === "diagram"
                  ? tHints.diagram
                  : activeModeTag === "chart"
                    ? tHints.chart
                    : activeModeTag === "create_file"
                      ? tHints.createFile
                      : activeModeTag === "smart_mail"
                        ? tHints.smartMail
                        : tHints.focus}
        </span>
        <button
          type="button"
          onClick={() => setActiveModeTag(null)}
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            color: "inherit",
            padding: "0 2px",
            display: "flex",
            alignItems: "center",
            opacity: 0.7,
            transition: "opacity 0.2s",
            marginLeft: "2px"
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = 1)}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = 0.7)}
          title="Hapus mode"
        >
          <X size={14} />
        </button>
      </div>
    );
  };

  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target) &&
        !event.target.closest(".cakra-plus-trigger")
      ) {
        setIsAttachmentMenuOpen(false);
      }
    }
    if (isAttachmentMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isAttachmentMenuOpen]);

  return (
    <div
      style={{
        ...styles.inputArea,
        background: isBottom
          ? `linear-gradient(to bottom, transparent 0%, ${theme.inputAreaBg} 30%)`
          : "transparent",
        position: isBottom ? "relative" : "absolute",
        bottom: isBottom ? undefined : "10%",
        left: isBottom ? undefined : "0",
        right: isBottom ? undefined : "0",
        marginLeft: isBottom ? undefined : "auto",
        marginRight: isBottom ? undefined : "auto",
        width: "100%",
        maxWidth: isBottom ? undefined : "700px",
        padding: isBottom
          ? isMobile
            ? "8px 16px 16px"
            : "8px 24px 16px"
          : isMobile
            ? "0 16px"
            : "0 20px",
        marginTop: isBottom ? undefined : undefined,
        flexShrink: 0,
        zIndex: isBottom ? undefined : 11,
        pointerEvents: "auto",
        boxSizing: "border-box",
      }}
    >
      <div style={{ ...styles.inputContainer, width: "100%", boxSizing: "border-box" }}>

        <ScrollBottomButton
          isBottom={isBottom}
          showScrollBottom={showScrollBottom}
          showWelcome={showWelcome}
          messages={messages}
          messagesContainerRef={messagesContainerRef}
          darkMode={darkMode}
        />

        <IsolatedDocBanner
          activeIsolatedTitle={activeIsolatedTitle}
          setContextIsolation={setContextIsolation}
          darkMode={darkMode}
          chatMode={chatMode}
          language={language}
        />

        <AttachmentPreview
          selectedFiles={selectedFiles}
          removeFilePreview={removeFilePreview}
          darkMode={darkMode}
          theme={theme}
        />

        {/* 🪄 WIZARD INTERAKTIF DOCKED DI ATAS TEXT INPUT (Hanya muncul saat stream sudah selesai) */}
        {activeWizard && !isStreaming && (
          <div className="w-full mb-3 animate-fadeIn flex justify-center">
            <InteractiveWizardWidget
              data={activeWizard.data}
              messageIndex={activeWizard.messageIndex}
              darkMode={darkMode}
              language={language}
            />
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          onPaste={handlePaste}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={inputShake ? "shake-animation" : ""}
          style={{
            ...styles.inputForm,
            background: darkMode ? "rgba(30, 30, 34, 0.75)" : "rgba(255, 255, 255, 0.75)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            borderColor: isDragOver
              ? darkMode
                ? "#6366f1"
                : "#2563eb"
              : theme.inputBorder,
            borderWidth: isDragOver ? "2px" : "1px",
            borderStyle: isDragOver ? "dashed" : "solid",
            boxShadow: darkMode ? "0 4px 30px rgba(0,0,0,0.3)" : "0 4px 30px rgba(0,0,0,0.08)",
            borderRadius: showMultilineLayout ? "24px" : "28px",
            display: "flex",
            flexDirection: "column",
            paddingTop: isMobile ? "6px" : "8px",
            paddingBottom: isMobile ? "6px" : "8px",
            paddingLeft: isMobile ? "8px" : "8px",
            paddingRight: isMobile ? "8px" : "12px",
            minHeight: "56px",
            height: "auto",
            transition: "border-color 0.15s ease",
            position: "relative",
            gap: "4px",
          }}
        >
          {/* 🌟 POPUP MENU PLUS SEUKURAN TEXT INPUT DENGAN SPACE ELEGAN 🌟 */}
          <PlusActionMenu
            ref={menuRef}
            isOpen={isAttachmentMenuOpen}
            onClose={() => setIsAttachmentMenuOpen(false)}
            fileInputRef={fileInputRef}
            openNextcloudModal={openNextcloudModal}
            isGuest={isGuest}
            currentIsLoggedIn={currentIsLoggedIn}
            darkMode={darkMode}
            language={language}
            setActiveModeTag={setActiveModeTag}
            textareaRef={textareaRef}
          />

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            multiple={!(isGuest || !currentIsLoggedIn)}
            accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.py,.js,.jsx,.ts,.tsx,.html,.css,.json,.yaml,.yml,.xml,.php,.java,.cpp,.c,.h,.sh,.bash,.md,.dart,.swift,image/*"
            style={{ display: "none" }}
          />

          {/* ── BARIS 1: wrapper textarea + plus (hanya single line di desktop) ── */}
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "flex-end",
              gap: "8px",
              width: "100%",
            }}
          >
            {/* Plus button — kiri, hanya di desktop single line */}
            {!showMultilineLayout && (
              <div className="cakra-plus-trigger" style={{ flexShrink: 0, paddingBottom: "0px" }}>
                <PlusButton
                  onClick={() => setIsAttachmentMenuOpen(prev => !prev)}
                  disabled={isUploadingFile}
                  selectedFiles={selectedFiles}
                  darkMode={darkMode}
                  isStreaming={isStreaming}
                  language={language}
                />
              </div>
            )}

            {/* 🏷️ ACTIVE MODE PILL DI DALAM INPUT AREA (Hanya saat desktop single line) */}
            {!showMultilineLayout && renderActiveModePill()}

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                activeIsolatedTitle
                  ? t.askDoc
                  : t.askCakra
              }
              rows={1}
              style={{
                flex: 1,
                color: theme.textColor,
                background: "transparent",
                border: "none",
                outline: "none",
                resize: "none",
                paddingLeft: "8px",
                paddingRight: "8px",
                paddingTop: "8px",
                paddingBottom: "8px",
                fontSize: "15px",
                lineHeight: "1.5",
                fontFamily: "inherit",
                minHeight: "36px",
                height: "auto",
                maxHeight: "450px",
                overflowY: "hidden",
                wordWrap: "break-word",
                overflowWrap: "break-word",
                whiteSpace: "pre-wrap",
              }}
            />

            {/* Kanan single line: Auto + Send (hanya di desktop single line) */}
            {!showMultilineLayout && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  flexShrink: 0,
                }}
              >
                {isUploadingFile && (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#6366f1",
                      fontStyle: "italic",
                    }}
                  >
                    Mengunggah...
                  </span>
                )}
                {currentIsLoggedIn && (
                  <CustomModeSelector
                    value={chatMode}
                    onChange={handleChatModeChange}
                    disabled={false}
                    darkMode={darkMode}
                    thinking={isThinkingMode}
                    onThinkingChange={handleThinkingModeChange}
                    language={language}
                  />
                )}

                <VoiceButton
                  darkMode={darkMode}
                  disabled={isStreaming || isUploadingFile}
                  onTranscriptionSuccess={(text) => {
                    setInput(prev => prev ? `${prev} ${text}` : text);
                  }}
                />

                <SendButton
                  isStreaming={isStreaming}
                  isUploadingFile={isUploadingFile}
                  input={input}
                  selectedFiles={selectedFiles}
                  theme={theme}
                  onStop={() => useChatStore.getState().stopStream()}
                  language={language}
                />
              </div>
            )}
          </div>

          {/* ── BARIS 2: toolbar bottom — tampil saat mode mobile atau desktop multiline ── */}
          {showMultilineLayout && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                paddingLeft: isMobile ? "2px" : "4px",
                paddingRight: isMobile ? "2px" : "4px",
                paddingTop: isMobile ? "4px" : "2px",
              }}
            >
              {/* Kiri: Plus + Preset Pill saat multiline */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                <div className="cakra-plus-trigger" style={{ display: 'flex', gap: '4px' }}>
                  <PlusButton
                    onClick={() => setIsAttachmentMenuOpen(prev => !prev)}
                    disabled={isUploadingFile}
                    selectedFiles={selectedFiles}
                    darkMode={darkMode}
                    isStreaming={isStreaming}
                    language={language}
                  />
                </div>

                {showMultilineLayout && renderActiveModePill()}
              </div>

              {/* Kanan: Auto + Send */}
              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                {isUploadingFile && (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#6366f1",
                      fontStyle: "italic",
                    }}
                  >
                    Mengunggah...
                  </span>
                )}
                {currentIsLoggedIn && (
                  <CustomModeSelector
                    value={chatMode}
                    onChange={handleChatModeChange}
                    disabled={false}
                    darkMode={darkMode}
                    thinking={isThinkingMode}
                    onThinkingChange={handleThinkingModeChange}
                    language={language}
                  />
                )}

                <VoiceButton
                  darkMode={darkMode}
                  disabled={isStreaming || isUploadingFile}
                  onTranscriptionSuccess={(text) => {
                    setInput(prev => prev ? `${prev} ${text}` : text);
                  }}
                />

                <SendButton
                  isStreaming={isStreaming}
                  isUploadingFile={isUploadingFile}
                  input={input}
                  selectedFiles={selectedFiles}
                  theme={theme}
                  onStop={() => useChatStore.getState().stopStream()}
                  language={language}
                />
              </div>
            </div>
          )}

          {/* Drag drop overlay */}
          {isDragOver && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: darkMode
                  ? "rgba(99, 102, 241, 0.15)"
                  : "rgba(37, 99, 235, 0.1)",
                border: `2px dashed ${darkMode ? "#6366f1" : "#2563eb"}`,
                borderRadius: "16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                pointerEvents: "none",
                zIndex: 10,
              }}
            >
              <span
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: darkMode ? "#a5b4fc" : "#1e3a8a",
                  background: darkMode
                    ? "rgba(99, 102, 241, 0.9)"
                    : "rgba(37, 99, 235, 0.9)",
                  padding: "8px 16px",
                  borderRadius: "8px",
                }}
              >
                📂 Lepas file di sini
              </span>
            </div>
          )}
        </form>

        {/* 💡 SMART HINT & ACTION SUGGESTIONS (Hanya tampil di layar awal sebelum ada chat) */}
        {(showWelcome || !messages || messages.length === 0) && (
          <HintSuggestions
            input={input}
            setInput={setInput}
            activeModeTag={activeModeTag}
            setActiveModeTag={setActiveModeTag}
            onSelectHint={handleSelectHint}
            darkMode={darkMode}
            theme={theme}
            isStreaming={isStreaming}
            isGuest={isGuest}
            language={language}
            isMobile={isMobile}
          />
        )}

        {isBottom && !showWelcome && messages && messages.length > 0 && (
          <div className="flex justify-center px-4 pt-1">
            <p className="text-[10px] text-gray-400 font-medium tracking-wide">
              {t.disclaimer}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
