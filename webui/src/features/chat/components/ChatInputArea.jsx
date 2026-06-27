import React from "react";
import PlusButton from "./PlusButton";
import CustomModeSelector from "./CustomModeSelector";
import SendButton from "./SendButton";
import { useChatStore } from "../../../stores/chatStore";

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
        {/* ── BUTTON SCROLL TO BOTTOM FLOATING CENTER ── */}
        {isBottom && showScrollBottom && !showWelcome && messages.length > 0 && (
          <button
            onClick={() => {
              if (messagesContainerRef.current) {
                messagesContainerRef.current.scrollTo({
                  top: 9999999,
                  behavior: "smooth",
                });
              }
            }}
            style={{
              position: "absolute",
              top: "-46px",
              left: "46%",
              transform: "translateX(-50%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "8px 14px",
              borderRadius: "20px",
              fontSize: "13px",
              fontWeight: "500",
              border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)"}`,
              background: darkMode ? "#202123" : "#ffffff",
              color: darkMode ? "#f3f4f6" : '#1f2937',
              boxShadow: darkMode
                ? "0 4px 12px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.2)"
                : "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
              cursor: "pointer",
              zIndex: 999,
              transition: "all 0.2s ease-in-out",
              animation: "fadeSlideIn 0.25s ease-out forwards",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = darkMode ? "#2d2d30" : "#f9fafb";
              e.currentTarget.style.transform = "translateX(-50%) translateY(-2px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = darkMode ? "#202123" : "#ffffff";
              e.currentTarget.style.transform = "translateX(-50%) translateY(0)";
            }}
            title="Lihat pesan baru di bawah"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <polyline points="19 12 12 19 5 12"></polyline>
            </svg>
          </button>
        )}
        
        {/* Isolated doc banner */}
        {activeIsolatedTitle && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: darkMode
                ? "rgba(99, 102, 241, 0.15)"
                : "rgba(37, 99, 235, 0.08)",
              border: `1px solid ${darkMode ? "#6366f1" : "#2563eb"}`,
              borderRadius: "12px",
              padding: "8px 16px",
              marginBottom: "10px",
              fontSize: "13px",
              fontWeight: 500,
              color: darkMode ? "#a5b4fc" : "#1e3a8a",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                minWidth: 0,
              }}
            >
              <span>🔒</span>
              <span
                style={{
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                Mode Fokus: Menanyai isi <strong>{activeIsolatedTitle}</strong>
              </span>
            </div>
            <button
              type="button"
              onClick={() => setContextIsolation(null, null)}
              style={{
                background: "transparent",
                border: "none",
                color: darkMode ? "#9ca3af" : "#4b5563",
                cursor: "pointer",
                fontWeight: "bold",
              }}
            >
              ✕
            </button>
          </div>
        )}

        {/* File preview */}
        {selectedFiles.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              marginBottom: "12px",
              padding: "4px 6px",
              width: "100%",
            }}
          >
            {selectedFiles.map((file, idx) => {
              const fileName = file.name.toLowerCase();
              const isImage = file.type.startsWith("image/");

              const extSplit = fileName.split(".");
              const ext = extSplit.length > 1 ? extSplit.pop().toUpperCase() : "FILE";

              return (
                <div
                  key={idx}
                  style={{
                    position: "relative",
                    width: "120px",
                    height: "120px",
                    borderRadius: "12px",
                    overflow: "hidden",
                    background: darkMode ? "#2a2b2d" : "#f3f4f6",
                    border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                  }}
                >
                  {isImage ? (
                    <img
                      src={URL.createObjectURL(file)}
                      alt="preview"
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        padding: "12px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        height: "100%",
                        width: "100%",
                        boxSizing: "border-box"
                      }}
                    >
                      <div style={{ overflow: "hidden" }}>
                        <div style={{
                          color: darkMode ? "#ffffff" : "#111827",
                          fontSize: "14px",
                          fontWeight: 600,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          marginBottom: "4px",
                          fontFamily: "'Inter', sans-serif"
                        }}>
                          {file.name}
                        </div>
                        <div style={{
                          color: theme.secondaryText,
                          fontSize: "12px",
                          fontWeight: 500
                        }}>
                          {file._lines !== undefined
                            ? `${file._lines} lines`
                            : (file.size > 1024 * 1024
                              ? (file.size / (1024 * 1024)).toFixed(1) + " MB"
                              : (file.size / 1024).toFixed(1) + " KB")}
                        </div>
                      </div>

                      <div style={{
                        alignSelf: "flex-start",
                        border: `1px solid ${darkMode ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.15)"}`,
                        borderRadius: "6px",
                        padding: "2px 6px",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: theme.secondaryText,
                        background: darkMode ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
                        letterSpacing: "0.5px"
                      }}>
                        {ext}
                      </div>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => removeFilePreview(idx)}
                    style={{
                      position: "absolute",
                      top: "2px",
                      right: "2px",
                      background: "rgba(0,0,0,0.6)",
                      border: "none",
                      borderRadius: "50%",
                      width: "16px",
                      height: "16px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#ffffff",
                      fontSize: "9px",
                      cursor: "pointer",
                      fontWeight: "bold",
                      zIndex: 2,
                    }}
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          onPaste={handlePaste}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          style={{
            ...styles.inputForm,
            background: theme.inputBg,
            borderColor: isDragOver
              ? darkMode
                ? "#6366f1"
                : "#2563eb"
              : theme.inputBorder,
            borderWidth: isDragOver ? "2px" : "1px",
            borderStyle: isDragOver ? "dashed" : "solid",
            boxShadow: theme.inputShadow,
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
                  disabled={isStreaming || isUploadingFile}
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
                    disabled={isStreaming}
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
                disabled={isStreaming || isUploadingFile}
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
                    disabled={isStreaming}
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
