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
  const [isHintsCollapsed, setIsHintsCollapsed] = useState(false);
  const [isPillHovered, setIsPillHovered] = useState(false);
  const attachmentMenuRef = useRef(null);
  const t = translations[language]?.chatInput || translations.id.chatInput;
  const tHints = translations[language]?.chat?.hints || translations.id.chat.hints;
  const openNextcloudModal = useNextcloudStore(state => state.openModal);
  const activeWizard = useChatStore(state => state.activeWizard);
  const activeModeTag = useChatStore(state => state.activeModeTag);
  const setActiveModeTag = useChatStore(state => state.setActiveModeTag);
  const activeIsolatedDocId = useChatStore(state => state.activeIsolatedDocId);

  // Auto-expand hints whenever activeModeTag changes
  useEffect(() => {
    if (activeModeTag) {
      setIsHintsCollapsed(false);
    }
  }, [activeModeTag]);

  const isBannerActive = Boolean((activeIsolatedTitle || activeIsolatedDocId) && (chatMode === 'focus' || chatMode === 'compliance' || chatMode === 'redteam'));
  const shouldShowHints = Boolean(!showWelcome && messages && messages.length > 0 && activeModeTag && !isHintsCollapsed && !activeWizard && !isBannerActive && !isStreaming);

  const [hintsMounted, setHintsMounted] = useState(shouldShowHints);
  const [isHintsExiting, setIsHintsExiting] = useState(false);

  useEffect(() => {
    if (shouldShowHints) {
      setHintsMounted(true);
      setIsHintsExiting(false);
    } else if (hintsMounted) {
      setIsHintsExiting(true);
      const timer = setTimeout(() => {
        setHintsMounted(false);
        setIsHintsExiting(false);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [shouldShowHints, hintsMounted]);

  // Pada mode mobile, selalu gunakan layout bertingkat (textarea di atas, buttons di bawah)
  // Pada mode desktop, tetap responsif mengikuti state isMultiLine
  const showMultilineLayout = isMobile || isMultiLine;

  const renderFloatingActiveModePillBadge = () => {
    const effectiveTag = activeModeTag || (chatMode && chatMode !== 'auto' && chatMode !== 'flash' && chatMode !== 'guest' ? chatMode : null);
    if (!effectiveTag) return null;

    // Teks dinamis saat di-hover (apabila chat aktif dan ada hint)
    const canToggleHints = !showWelcome && messages && messages.length > 0 && Boolean(activeModeTag);
    let displayLabel = effectiveTag === "code"
      ? tHints.code
      : effectiveTag === "websearch"
        ? (tHints.websearchTag || "Web search")
        : effectiveTag === "documents"
          ? tHints.documents
          : effectiveTag === "diagram"
            ? tHints.diagram
            : effectiveTag === "chart"
              ? tHints.chart
              : effectiveTag === "create_file"
                ? tHints.createFile
                : effectiveTag === "smart_mail"
                  ? tHints.smartMail
                  : tHints.focus;

    if (canToggleHints && isPillHovered) {
      displayLabel = isHintsCollapsed
        ? (tHints.showHint || "Munculkan hint")
        : (tHints.hideHint || "Hide hint");
    }

    return (
      <div
        onClick={() => {
          if (canToggleHints) {
            setIsHintsCollapsed(prev => !prev);
          }
        }}
        onMouseEnter={() => setIsPillHovered(true)}
        onMouseLeave={() => setIsPillHovered(false)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 10px",
          borderRadius: "10px",
          fontSize: "12px",
          fontWeight: "500",
          background: darkMode
            ? isPillHovered && canToggleHints
              ? "rgba(50, 50, 58, 0.98)"
              : "rgba(35, 35, 42, 0.95)"
            : isPillHovered && canToggleHints
              ? "rgba(220, 224, 230, 0.98)"
              : "rgba(235, 238, 242, 0.95)",
          border: darkMode
            ? "1px solid rgba(255, 255, 255, 0.14)"
            : "1px solid rgba(0, 0, 0, 0.10)",
          color: darkMode ? "#ffffff" : "#111827",
          flexShrink: 0,
          userSelect: "none",
          alignSelf: "center",
          cursor: canToggleHints ? "pointer" : "default",
          transition: "all 0.18s cubic-bezier(0.4, 0, 0.2, 1)",
          marginLeft: "2px",
          marginRight: "2px",
        }}
        title={canToggleHints ? (isHintsCollapsed ? (tHints.showHintTitle || "Klik untuk memunculkan hint") : (tHints.hideHintTitle || "Klik untuk menyembunyikan hint")) : undefined}
      >
        {effectiveTag === "code" && <Code2 size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "websearch" && <Globe size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "documents" && <FileText size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "diagram" && <Workflow size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "chart" && <BarChart3 size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "create_file" && <FilePlus size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "smart_mail" && <Mail size={14} className="opacity-90 flex-shrink-0" />}
        {effectiveTag === "focus" && <Target size={14} className="opacity-90 flex-shrink-0" />}
        <span style={{ letterSpacing: "0.01em", transition: "opacity 0.15s ease" }}>
          {displayLabel}
        </span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setActiveModeTag(null);
            if (chatMode && chatMode !== 'auto') {
              handleChatModeChange('auto');
            }
          }}
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
            marginLeft: "3px"
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = 1)}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = 0.7)}
          title="Hapus mode"
        >
          <X size={13} />
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

  const isDockedBottom = isBottom && !showWelcome;

  return (
    <div
      style={{
        ...styles.inputArea,
        background: isDockedBottom
          ? `linear-gradient(to bottom, transparent 0%, ${darkMode ? 'rgba(21,21,23,0.35)' : 'rgba(255,255,255,0.35)'} 12%, ${darkMode ? 'rgba(21,21,23,0.88)' : 'rgba(255,255,255,0.88)'} 30%, ${theme.inputAreaBg || (darkMode ? '#151517' : '#ffffff')} 58%, ${theme.inputAreaBg || (darkMode ? '#151517' : '#ffffff')} 100%)`
          : "transparent",
        position: isDockedBottom ? "absolute" : "relative",
        bottom: isDockedBottom ? 0 : undefined,
        left: isDockedBottom ? 0 : undefined,
        right: isDockedBottom ? 0 : undefined,
        marginLeft: isDockedBottom ? undefined : "auto",
        marginRight: isDockedBottom ? undefined : "auto",
        width: "100%",
        maxWidth: undefined,
        padding: isDockedBottom
          ? isMobile
            ? "10px 16px 16px"
            : "14px 24px 16px"
          : "0",
        marginTop: isDockedBottom ? undefined : undefined,
        flexShrink: 0,
        zIndex: isDockedBottom ? 11 : undefined,
        pointerEvents: isDockedBottom ? "none" : "auto",
        boxSizing: "border-box",
      }}
    >
      <div style={{ ...styles.inputContainer, width: "100%", boxSizing: "border-box", pointerEvents: "auto" }}>

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

        {/* Keyframe Slide Down Exit */}
        <style>{`
          @keyframes cakraSlideDownExit {
            0% {
              opacity: 1;
              transform: translateY(0);
            }
            100% {
              opacity: 0;
              transform: translateY(14px);
            }
          }
        `}</style>

        {/* 💡 UPWARD HINT SUGGESTIONS DI ATAS TEXT INPUT (Spring Bounce saat muncul, Slide Down saat hide) */}
        {hintsMounted && (
          <div
            className="w-full mb-1.5 no-scrollbar"
            style={{
              paddingLeft: isMobile ? "6px" : "10px",
              paddingRight: isMobile ? "6px" : "10px",
              animation: isHintsExiting ? "cakraSlideDownExit 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards" : undefined,
              pointerEvents: isHintsExiting ? "none" : "auto",
              overflow: "visible",
              scrollbarWidth: "none",
              msOverflowStyle: "none",
            }}
          >
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
              isUpward={true}
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

            {/* 🏷️ ACTIVE MODE PILL DI DALAM INPUT AREA (Desktop single line) */}
            {!showMultilineLayout && renderFloatingActiveModePillBadge()}

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
              {/* Kiri: Plus Button + Preset Pill saat multiline */}
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
                {showMultilineLayout && renderFloatingActiveModePillBadge()}
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
            isUpward={false}
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
