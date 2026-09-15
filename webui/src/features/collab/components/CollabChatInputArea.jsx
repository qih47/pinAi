import React, { useState, useRef, useEffect, useCallback } from "react";
import PlusButton from "../../chat/components/PlusButton";
import SendButton from "../../chat/components/SendButton";
import VoiceButton from "../../chat/components/ChatInputArea/VoiceButton";
import PlusActionMenu from "../../chat/components/ChatInputArea/PlusActionMenu";
import AttachmentPreview from "../../chat/components/ChatInputArea/AttachmentPreview";
import ScrollBottomButton from "../../chat/components/ChatInputArea/ScrollBottomButton";
import CollabHintSuggestions from "./CollabHintSuggestions";
import { translations } from "../../../utils/translations";
import useNextcloudStore from "../../../stores/nextcloudStore";
import {
  AtSign,
  Globe,
  FileText,
  Code2,
  Workflow,
  BarChart3,
  FilePlus,
  Mail,
  Target,
  X
} from "lucide-react";
import cakraLogo from "../../../assets/cakra.png";
import { collabApi } from "../services/collabApi";

export default function CollabChatInputArea({
  roomId,
  theme,
  darkMode = true,
  isMobile = false,
  onSendMessage,
  onTypingChange,
  members = [],
  isSending = false,
  language = "id",
  showScrollBottom = false,
  messages = [],
  messagesContainerRef = null,
}) {
  const [input, setInput] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [isAttachmentMenuOpen, setIsAttachmentMenuOpen] = useState(false);
  const [activeModeTag, setActiveModeTag] = useState(null);
  const [selectedDocContext, setSelectedDocContext] = useState(null);
  const [mentionQuery, setMentionQuery] = useState(null);
  const [mentionIndex, setMentionIndex] = useState(0);

  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const menuRef = useRef(null);
  const typingTimeoutRef = useRef(null);

  const t = translations[language]?.chatInput || translations.id.chatInput;
  const tHints = translations[language]?.chat?.hints || translations.id.chat.hints;
  const openNextcloudModal = useNextcloudStore((state) => state.openModal);

  // Click outside to close PlusActionMenu
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

  // Auto-resize textarea (sama dengan ChatInputArea utama)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 36), 400)}px`;
    }
  }, [input]);

  // Handle typing broadcast throttled
  const notifyTyping = useCallback(
    (isTyping) => {
      if (onTypingChange) {
        onTypingChange(isTyping);
      }
    },
    [onTypingChange]
  );

  // 💡 Kontrol Kemunculan Upward Hint Suggestions (Muncul saat user memilih Tool/Mode dari tombol Plus)
  const shouldShowHints = Boolean(activeModeTag && !isSending);
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

  // Handler saat dokumen dipilih dari daftar suggestions
  const handleSelectDocument = useCallback((docItem) => {
    setSelectedDocContext(docItem);
    setActiveModeTag(null); // Tutup hint upward, dokumen langsung aktif di pill badge
  }, []);

  // Handler saat prompt tool dipilih dari suggestions (Websearch, Code, dll.)
  const handleSelectPrompt = useCallback((promptText, mode) => {
    setInput(`@cakra ${promptText}`);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  // Daftar opsi mention: CAKRA + anggota tim
  const mentionOptions = [
    {
      id: "cakra",
      name: "cakra",
      displayName: "CAKRA (AI Teammate)",
      description: "Panggil CAKRA untuk membantu diskusi tim",
      isAi: true,
    },
    ...members.map((m) => ({
      id: m.npp,
      name: (m.name || m.npp).replace(/\s+/g, ""),
      displayName: `${m.name} (${m.divisi || "PT Pindad"})`,
      description: `NPP: ${m.npp}`,
      isAi: false,
    })),
  ];

  const filteredMentions =
    mentionQuery !== null
      ? mentionOptions.filter(
        (opt) =>
          opt.name.toLowerCase().includes(mentionQuery.toLowerCase()) ||
          opt.displayName.toLowerCase().includes(mentionQuery.toLowerCase())
      )
      : [];

  const handleTextChange = (e) => {
    const val = e.target.value;
    setInput(val);

    if (val.trim()) {
      notifyTyping(true);
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = setTimeout(() => {
        notifyTyping(false);
      }, 2500);
    } else {
      notifyTyping(false);
    }

    // Deteksi karakter '@'
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const lastAt = textBeforeCursor.lastIndexOf("@");

    if (lastAt !== -1) {
      const query = textBeforeCursor.slice(lastAt + 1);
      if (!/\s/.test(query)) {
        setMentionQuery(query);
        setMentionIndex(0);
        return;
      }
    }
    setMentionQuery(null);
  };

  const insertMention = (opt) => {
    if (!textareaRef.current) return;
    const cursorPos = textareaRef.current.selectionStart;
    const textBeforeCursor = input.slice(0, cursorPos);
    const lastAt = textBeforeCursor.lastIndexOf("@");
    const textAfterCursor = input.slice(cursorPos);

    const mentionTag = `@${opt.name} `;
    const newText = input.slice(0, lastAt) + mentionTag + textAfterCursor;
    setInput(newText);
    setMentionQuery(null);

    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const nextPos = lastAt + mentionTag.length;
        textareaRef.current.setSelectionRange(nextPos, nextPos);
      }
    }, 10);
  };

  const handleKeyDown = (e) => {
    if (mentionQuery !== null && filteredMentions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex((prev) => (prev + 1) % filteredMentions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex(
          (prev) => (prev - 1 + filteredMentions.length) % filteredMentions.length
        );
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        insertMention(filteredMentions[mentionIndex]);
        return;
      }
      if (e.key === "Escape") {
        setMentionQuery(null);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    if ((!input.trim() && selectedFiles.length === 0 && !selectedDocContext) || isSending || isUploadingFile) return;
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    notifyTyping(false);

    let processedAttachments = [];
    const filesToUpload = selectedFiles.filter((f) => f.file_obj);
    const alreadyUploaded = selectedFiles.filter((f) => !f.file_obj);

    if (filesToUpload.length > 0 && roomId) {
      try {
        setIsUploadingFile(true);
        const uploaded = await collabApi.uploadAttachments(
          roomId,
          filesToUpload.map((f) => f.file_obj)
        );
        processedAttachments = [...alreadyUploaded, ...uploaded];
      } catch (err) {
        console.error("Gagal mengunggah lampiran:", err);
        alert(err.response?.data?.detail || "Gagal mengunggah lampiran berkas.");
        setIsUploadingFile(false);
        return;
      } finally {
        setIsUploadingFile(false);
      }
    } else {
      processedAttachments = [...selectedFiles];
    }

    const finalAttachments = [...processedAttachments];
    if (selectedDocContext) {
      finalAttachments.push({
        type: "context_doc",
        title: selectedDocContext.title,
        doc_id: selectedDocContext.doc_id,
        filename: selectedDocContext.filename,
        file_path: selectedDocContext.file_path || (selectedDocContext.filename ? `file_peraturan/${selectedDocContext.filename}` : null),
        category: selectedDocContext.category || "Regulasi",
        nomor: selectedDocContext.nomor || "",
        total_pages: selectedDocContext.total_pages || null
      });
    } else if (activeModeTag) {
      finalAttachments.push({
        type: "context_mode",
        mode: activeModeTag
      });
    }

    const modeToUse = activeModeTag || (selectedDocContext ? "documents" : null);

    onSendMessage(input.trim(), finalAttachments, modeToUse);
    setInput("");
    setSelectedFiles([]);
    setActiveModeTag(null);
    setSelectedDocContext(null);
    setMentionQuery(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "36px";
    }
  };

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setIsUploadingFile(true);
    const newAttachments = files.map((file) => ({
      name: file.name,
      size: file.size,
      type: file.type,
      file_obj: file,
      preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
    }));
    setSelectedFiles((prev) => [...prev, ...newAttachments]);
    setIsUploadingFile(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeFilePreview = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const isMultiLine = input.split("\n").length > 1 || input.length > 70;
  const showMultilineLayout = isMobile || isMultiLine;

  const renderFloatingActiveModePillBadge = () => {
    // 1. Dokumen yang dipilih sebagai rujukan konteks aktif
    if (selectedDocContext) {
      return (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "4px 10px",
            borderRadius: "10px",
            fontSize: "12px",
            fontWeight: "500",
            background: darkMode
              ? "rgba(245, 158, 11, 0.15)"
              : "rgba(245, 158, 11, 0.12)",
            border: darkMode
              ? "1px solid rgba(245, 158, 11, 0.35)"
              : "1px solid rgba(245, 158, 11, 0.3)",
            color: darkMode ? "#fbbf24" : "#b45309",
            flexShrink: 0,
            userSelect: "none",
            alignSelf: "center",
            transition: "all 0.18s cubic-bezier(0.4, 0, 0.2, 1)",
            marginLeft: "2px",
            marginRight: "2px",
            maxWidth: isMobile ? "160px" : "260px",
          }}
          title={selectedDocContext.title}
        >
          <FileText size={14} className="opacity-90 flex-shrink-0" />
          <span className="truncate" style={{ letterSpacing: "0.01em" }}>
            {selectedDocContext.title}
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedDocContext(null);
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
              marginLeft: "3px",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = 1)}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = 0.7)}
            title="Hapus rujukan dokumen"
          >
            <X size={13} />
          </button>
        </div>
      );
    }

    if (!activeModeTag) return null;

    const displayLabel =
      activeModeTag === "code"
        ? tHints.code
        : activeModeTag === "websearch"
          ? tHints.websearchTag || "Web search"
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
                    : tHints.focus || activeModeTag;

    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 10px",
          borderRadius: "10px",
          fontSize: "12px",
          fontWeight: "500",
          background: darkMode
            ? "rgba(35, 35, 42, 0.95)"
            : "rgba(235, 238, 242, 0.95)",
          border: darkMode
            ? "1px solid rgba(255, 255, 255, 0.14)"
            : "1px solid rgba(0, 0, 0, 0.10)",
          color: darkMode ? "#ffffff" : "#111827",
          flexShrink: 0,
          userSelect: "none",
          alignSelf: "center",
          transition: "all 0.18s cubic-bezier(0.4, 0, 0.2, 1)",
          marginLeft: "2px",
          marginRight: "2px",
        }}
      >
        {activeModeTag === "code" && <Code2 size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "websearch" && <Globe size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "documents" && <FileText size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "diagram" && <Workflow size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "chart" && <BarChart3 size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "create_file" && <FilePlus size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "smart_mail" && <Mail size={14} className="opacity-90 flex-shrink-0" />}
        {activeModeTag === "focus" && <Target size={14} className="opacity-90 flex-shrink-0" />}
        <span style={{ letterSpacing: "0.01em" }}>{displayLabel}</span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setActiveModeTag(null);
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
            marginLeft: "3px",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = 1)}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = 0.7)}
          title={t.removeMode || (language === "en" ? "Remove mode" : "Hapus mode")}
        >
          <X size={13} />
        </button>
      </div>
    );
  };

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        maxWidth: "816px",
        margin: "0 auto",
        padding: isMobile ? "0 12px 10px" : "0 20px 14px",
        boxSizing: "border-box",
        zIndex: 20,
      }}
    >
      {/* Pop-up Mention Suggestions */}
      {mentionQuery !== null && filteredMentions.length > 0 && (
        <div
          className="absolute bottom-full left-4 sm:left-6 mb-2 w-72 sm:w-80 rounded-2xl border shadow-2xl overflow-hidden z-50 animate-fadeInUp"
          style={{
            background: darkMode ? "#1b1b1e" : "#ffffff",
            borderColor: darkMode ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
          }}
        >
          <div
            className="px-3.5 py-2 border-b text-[11px] font-semibold flex items-center gap-1.5"
            style={{
              background: darkMode ? "#151518" : "#f8fafc",
              borderColor: darkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
              color: theme.secondaryText || (darkMode ? "#94a3b8" : "#6b7280"),
            }}
          >
            <AtSign size={12} className="text-teal-400" />
            <span>{language === "en" ? "Select Team Member or CAKRA" : "Pilih Anggota Tim atau CAKRA"}</span>
          </div>
          <div className="max-h-48 overflow-y-auto py-1 custom-scrollbar">
            {filteredMentions.map((opt, idx) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => insertMention(opt)}
                className={`w-full text-left px-3.5 py-2 flex items-center gap-2.5 transition-colors ${idx === mentionIndex
                    ? "bg-teal-500/20 text-teal-300"
                    : "hover:bg-white/5"
                  }`}
                style={{ color: theme.textColor }}
              >
                {opt.isAi ? (
                  <div className="w-6 h-6 rounded-lg bg-teal-500/10 flex items-center justify-center p-0.5 shrink-0 border border-teal-500/20">
                    <img
                      src={cakraLogo}
                      alt="CAKRA"
                      className="w-full h-full object-contain"
                    />
                  </div>
                ) : (
                  <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 border border-white/10 bg-gradient-to-br from-teal-600 to-emerald-700 text-white">
                    {opt.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold truncate flex items-center gap-1.5">
                    <span>{opt.displayName}</span>
                    {opt.isAi && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-teal-950 text-teal-300 border border-teal-700/60 font-medium">
                        AI
                      </span>
                    )}
                  </div>
                  <div
                    className="text-[10px] truncate"
                    style={{
                      color:
                        theme.secondaryText ||
                        (darkMode ? "#94a3b8" : "#6b7280"),
                    }}
                  >
                    {opt.description}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={handleFileChange}
        style={{ display: "none" }}
      />

      {/* Plus Action Menu Popup */}
      <PlusActionMenu
        ref={menuRef}
        isOpen={isAttachmentMenuOpen}
        onClose={() => setIsAttachmentMenuOpen(false)}
        fileInputRef={fileInputRef}
        openNextcloudModal={openNextcloudModal}
        isGuest={false}
        currentIsLoggedIn={true}
        darkMode={darkMode}
        language={language}
        setActiveModeTag={setActiveModeTag}
        textareaRef={textareaRef}
      />

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

      {/* 📎 ATTACHMENT PREVIEW DI LUAR TEXT INPUT (Persis seperti Chat Utama) */}
      <AttachmentPreview
        selectedFiles={selectedFiles}
        removeFilePreview={removeFilePreview}
        darkMode={darkMode}
        theme={theme}
      />

      {/* 💡 UPWARD HINT SUGGESTIONS DI ATAS TEXT INPUT (Muncul otomatis saat memilih Tool dari menu Plus) */}
      {hintsMounted && (
        <div
          className="w-full mb-2 no-scrollbar"
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
          <CollabHintSuggestions
            activeModeTag={activeModeTag}
            input={input}
            onSelectDocument={handleSelectDocument}
            onSelectPrompt={handleSelectPrompt}
            darkMode={darkMode}
            theme={theme}
            language={language}
            isMobile={isMobile}
          />
        </div>
      )}

      {/* ── BENTUK KAPSUL MELAYANG IDENTIK DENGAN ChatInputArea.jsx UTAMA ── */}
      <div
        className="cakra-input-form relative"
        style={{
          display: "flex",
          flexDirection: "column",
          borderRadius: showMultilineLayout ? 20 : 28,
          background: darkMode ? "#1e1e21" : "#ffffff",
          boxShadow: darkMode
            ? "0 4px 24px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.08)"
            : "0 4px 20px rgba(0,0,0,0.07), 0 0 0 1px rgba(0,0,0,0.08)",
          padding: showMultilineLayout ? "10px 14px 10px 14px" : "8px 12px 8px 14px",
          transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          boxSizing: "border-box",
        }}
      >
        {/* ⬇️ TOMBOL TO BOTTOM (SCROLL KE BAWAH) IDENTIK DENGAN CHAT UTAMA */}
        <ScrollBottomButton
          isBottom={true}
          showScrollBottom={showScrollBottom}
          showWelcome={false}
          messages={messages}
          messagesContainerRef={messagesContainerRef}
          darkMode={darkMode}
        />

        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: "8px",
            width: "100%",
          }}
        >
          {/* Plus button — kiri (Lampiran/Menu) */}
          {!showMultilineLayout && (
            <div
              className="cakra-plus-trigger"
              style={{ flexShrink: 0, paddingBottom: "2px" }}
            >
              <PlusButton
                onClick={() => setIsAttachmentMenuOpen((prev) => !prev)}
                disabled={isUploadingFile}
                selectedFiles={selectedFiles}
                darkMode={darkMode}
                isStreaming={isSending}
                language={language}
              />
            </div>
          )}

          {/* 🏷️ ACTIVE MODE PILL DI DALAM INPUT AREA (Desktop single line) */}
          {!showMultilineLayout && renderFloatingActiveModePillBadge()}

          {/* Textarea Utama */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder={t.txtAmsg || "Tulis Pesan..."}
            rows={1}
            style={{
              flex: 1,
              color: theme.textColor,
              background: "transparent",
              border: "none",
              outline: "none",
              resize: "none",
              paddingLeft: "6px",
              paddingRight: "6px",
              paddingTop: "6px",
              paddingBottom: "6px",
              fontSize: "15px",
              lineHeight: "1.5",
              fontFamily: "inherit",
              minHeight: "36px",
              height: "auto",
              maxHeight: "350px",
              overflowY: "auto",
              wordWrap: "break-word",
              overflowWrap: "break-word",
              whiteSpace: "pre-wrap",
            }}
          />

          {/* Kanan single line: Voice + Send Button (Mode selector di-hide sesuai instruksi) */}
          {!showMultilineLayout && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                flexShrink: 0,
                paddingBottom: "2px",
              }}
            >
              <VoiceButton
                darkMode={darkMode}
                disabled={isSending || isUploadingFile}
                onTranscriptionSuccess={(transcription) => {
                  setInput((prev) =>
                    prev ? `${prev} ${transcription}` : transcription
                  );
                }}
              />

              <SendButton
                isStreaming={isSending}
                isUploadingFile={isUploadingFile}
                input={input}
                selectedFiles={selectedFiles}
                theme={theme}
                onClick={handleSubmit}
                language={language}
              />
            </div>
          )}
        </div>

        {/* Multiline Layout Toolbar Bottom (Saat pesan panjang / multiline) */}
        {showMultilineLayout && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              width: "100%",
              paddingTop: "6px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div className="cakra-plus-trigger">
                <PlusButton
                  onClick={() => setIsAttachmentMenuOpen((prev) => !prev)}
                  disabled={isUploadingFile}
                  selectedFiles={selectedFiles}
                  darkMode={darkMode}
                  isStreaming={isSending}
                  language={language}
                />
              </div>
              {renderFloatingActiveModePillBadge()}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <VoiceButton
                darkMode={darkMode}
                disabled={isSending || isUploadingFile}
                onTranscriptionSuccess={(transcription) => {
                  setInput((prev) =>
                    prev ? `${prev} ${transcription}` : transcription
                  );
                }}
              />

              <SendButton
                isStreaming={isSending}
                isUploadingFile={isUploadingFile}
                input={input}
                selectedFiles={selectedFiles}
                theme={theme}
                onClick={handleSubmit}
                language={language}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Teks Disclaimer Bawah (Sama Persis dengan ChatPage Utama) ── */}
      <div
        style={{
          textAlign: "center",
          marginTop: "6px",
          fontSize: "11px",
          color: theme.secondaryText || (darkMode ? "#64748b" : "#94a3b8"),
          letterSpacing: "0.1px",
        }}
      >
        {t.disclaimer || (language === "en" ? "CAKRA can make mistakes. Consider verifying important information." : "CAKRA dapat membuat kesalahan. Selalu periksa kembali informasi penting atau hasil perhitungan.")}
      </div>
    </div>
  );
}
