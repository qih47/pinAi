import React from "react";
import PlusButton from "./PlusButton";
import CustomModeSelector from "./CustomModeSelector";
import SendButton from "./SendButton";
import { useChatStore } from "../../../stores/chatStore";
import ScrollBottomButton from "./ChatInputArea/ScrollBottomButton";
import IsolatedDocBanner from "./ChatInputArea/IsolatedDocBanner";
import AttachmentPreview from "./ChatInputArea/AttachmentPreview";

export default function ChatInputArea({
  theme,
  darkMode,
  isBottom = false,
  showScrollBottom,
  showWelcome,
  messages,
  messagesContainerRef,
  activeIsolatedTitle,
  setContextIsolation,
  selectedFiles,
  removeFilePreview,
  handleSubmit,
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
  textareaRef,
  input,
  setInput,
  handleKeyDown,
  chatMode,
  handleChatModeChange,
  isThinkingMode,
  handleThinkingModeChange,
  styles,
}) {
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
        padding: isBottom ? undefined : "0 20px",
        marginTop: isBottom ? undefined : undefined,
        flexShrink: 0,
        zIndex: isBottom ? undefined : 11,
        pointerEvents: "auto",
      }}
    >
      <div style={styles.inputContainer}>
        
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
        />

        <AttachmentPreview
          selectedFiles={selectedFiles}
          removeFilePreview={removeFilePreview}
          darkMode={darkMode}
          theme={theme}
        />

        <form
          onSubmit={handleSubmit}
          onPaste={handlePaste}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
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
            display: "flex",
            flexDirection: "column",
            paddingTop: "8px",
            paddingBottom: "8px",
            paddingLeft: "8px",
            paddingRight: "12px",
            minHeight: "56px",
            height: "auto",
            transition: "border-color 0.15s ease",
            position: "relative",
            gap: "4px",
          }}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            multiple={!(isGuest || !currentIsLoggedIn)}
            accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.py,.js,.jsx,.ts,.tsx,.html,.css,.json,.yaml,.yml,.xml,.php,.java,.cpp,.c,.h,.sh,.bash,.md,.dart,.swift,image/*"
            style={{ display: "none" }}
          />

          {/* ── BARIS 1: wrapper textarea + plus (single) ── */}
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "flex-end",
              gap: "8px",
              width: "100%",
            }}
          >
            {/* Plus button — kiri, selalu align bottom */}
            {!isMultiLine && (
              <div style={{ flexShrink: 0, paddingBottom: "0px" }}>
                <PlusButton
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploadingFile}
                  selectedFiles={selectedFiles}
                  darkMode={darkMode}
                  isStreaming={isStreaming}
                />
              </div>
            )}

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                activeIsolatedTitle
                  ? "Tanyakan perihal isi dokumen ini..."
                  : "Tanya CAKRA"
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

            {/* Kanan single line: Auto + Send */}
            {!isMultiLine && (
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
                  />
                )}
                <SendButton
                  isStreaming={isStreaming}
                  isUploadingFile={isUploadingFile}
                  input={input}
                  selectedFiles={selectedFiles}
                  theme={theme}
                  onStop={() => useChatStore.getState().stopStream()}
                />
              </div>
            )}
          </div>

          {/* ── BARIS 2: toolbar multiline — hanya tampil saat isMultiLine ── */}
          {isMultiLine && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                paddingLeft: "4px",
                paddingRight: "4px",
                paddingTop: "2px",
              }}
            >
              {/* Kiri: Plus */}
              <PlusButton
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingFile}
                selectedFiles={selectedFiles}
                darkMode={darkMode}
                isStreaming={isStreaming}
              />

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
                  />
                )}
                <SendButton
                  isStreaming={isStreaming}
                  isUploadingFile={isUploadingFile}
                  input={input}
                  selectedFiles={selectedFiles}
                  theme={theme}
                  onStop={() => useChatStore.getState().stopStream()}
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

        {isBottom && (
          <div
            style={{
              ...styles.inputFooter,
              color: theme.secondaryText,
              marginTop: "8px",
            }}
          >
            CAKRA AI dapat membuat kesalahan. Pertimbangkan untuk memeriksa
            informasi penting.
          </div>
        )}
      </div>
    </div>
  );
}
