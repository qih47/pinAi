import React, { useState, useRef, useEffect } from "react";
import { useChatStore, API_BASE } from "../../stores/chatStore";
import { uploadDocuments } from "../../services/endpoints";
import useToast from "../../hooks/useToast";
import cakraLogo from "../../assets/cakra.png";
import { styles, lightColors, darkColors } from "./chatPage.styles";
import ChatArea from "./components/ChatArea";
import GuestWelcome from "../../components/ui/GuestWelcome";
import Sidebar from "./components/Sidebar";
import { useNavigate, useParams } from "react-router-dom";
import { useChatAuthStore } from "../../stores/authStore";
import CustomModeSelector from "./components/CustomModeSelector";
import HeaderDropdownMenu from "./components/HeaderDropdownMenu";
import NotificationBell from "../../components/NotificationBell"; // 👈 W16: Notification center
import PlusButton from "./components/PlusButton";
import SendButton from "./components/SendButton";

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function ChatPage({
  isGuest,
  isLoggedIn: propsIsLoggedIn,
  userData: propsUserData,
  getGreeting,
}) {
  const toast = useToast();
  const [input, setInput] = useState("");
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // 📝 R4: Local Input Draft Persistence
  // Load draft on sessionId change
  useEffect(() => {
    const key = `cakra_draft_${sessionId || "new"}`;
    const savedDraft = sessionStorage.getItem(key);
    setInput(savedDraft || "");
  }, [sessionId]);

  // Save/Remove draft on input change
  useEffect(() => {
    const key = `cakra_draft_${sessionId || "new"}`;
    if (input) {
      sessionStorage.setItem(key, input);
    } else {
      sessionStorage.removeItem(key);
    }
  }, [input, sessionId]);

  const authUser = useChatAuthStore((state) => state.user);
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);
  const logout = useChatAuthStore((state) => state.logout);

  const activeIsolatedTitle = useChatStore(
    (state) => state.activeIsolatedTitle,
  );
  const setContextIsolation = useChatStore(
    (state) => state.setContextIsolation,
  );
  const activeIsolatedDocId = useChatStore(
    (state) => state.activeIsolatedDocId,
  );
  const documents = useChatStore((state) => state.documents || []);
  const isLoadingDocuments = useChatStore(
    (state) => state.isLoadingDocuments || false,
  );
  const fetchDocumentsList = useChatStore((state) => state.fetchDocumentsList);

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // STATE: Deteksi apakah textarea sudah multi-line untuk urusan layout form
  const [isMultiLine, setIsMultiLine] = useState(false);
  // Tambah ref di bawah useState chatMode:
  // 🔒 Ambil state chatMode global dari Zustand store
  const storeChatMode = useChatStore((state) => state.chatMode || "auto");

  // Gunakan storeChatMode sebagai jaminan nilai inisialisasi saat komponen di-remount!
  const [chatMode, setChatMode] = useState(storeChatMode);
  const chatModeRef = useRef(storeChatMode);
  // Buat fungsi wrapper untuk memantau perubahan chatMode:
  const handleChatModeChange = (val) => {
    chatModeRef.current = val;
    setChatMode(val);
    // Menyimpan pilihan mode langsung ke Zustand store setelah dipilih oleh pengguna
    useChatStore.setState({ chatMode: val });
  };
  // REF: Capture tinggi baseline 1 baris saat mount pertama
  const baselineHeightRef = useRef(0);

  const stagedAttachments = useChatStore((state) => state.stagedAttachments);
  const setStagedAttachments = useChatStore(
    (state) => state.setStagedAttachments,
  );

  const currentIsLoggedIn =
    propsIsLoggedIn !== undefined ? propsIsLoggedIn : isAuthenticated;
  const currentUserData = propsUserData || {
    name: authUser?.name || "Pegawai Pindad",
    npp: authUser?.npp || "NPP ------",
    divisi: authUser?.divisi || "Pegawai Resmi",
    role: authUser?.role || "user",
  };

  const activeSessionId = sessionId && sessionId !== "new" ? sessionId : null;

  const removeFilePreview = (indexToRemove) => {
    setSelectedFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const validateFile = (file) => {
    const allowedTypes = ["application/pdf"];
    const isImage = file.type.startsWith("image/");
    const isValidType = isImage || allowedTypes.includes(file.type);
    if (!isValidType) {
      toast.error(
        `Format file "${file.name}" tidak didukung. Hanya gambar atau PDF.`,
      );
      return false;
    }
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      toast.error(`Ukuran file "${file.name}" melebihi batas 10 MB.`);
      return false;
    }
    return true;
  };

  // 2. TAMPILKAN PRATINJAU LOKAL (TIDAK LANGSUNG DIUNGGAH KE SERVER)
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    const limit = isGuest || !currentIsLoggedIn ? 1 : 5;
    const availableSlots = limit - selectedFiles.length;

    const validFiles = files.filter(validateFile);
    if (validFiles.length === 0) return;

    const targets = validFiles.slice(0, availableSlots);

    if (targets.length === 0 && files.length > 0) {
      toast.warning(`Slot penuh! Maksimal ${limit} file.`);
      return;
    }

    setSelectedFiles((prev) => [...prev, ...targets]);
  };

  // 2. TEMPEL GAMBAR (PASTE): Masuk ke state lokal untuk pratinjau, bukan ke port API langsung
  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageItems = Array.from(items).filter((item) =>
      item.type.startsWith("image/"),
    );
    if (imageItems.length === 0) return;
    e.preventDefault();

    const limit = isGuest || !currentIsLoggedIn ? 1 : 5;
    const availableSlots = limit - selectedFiles.length;
    const targets = imageItems.slice(0, availableSlots);

    const newFiles = [];
    for (const item of targets) {
      const file = item.getAsFile();
      if (file) {
        const uniqueFile = new File(
          [file],
          `pasted-image-${Date.now()}-${Math.random().toString(36).substr(2, 9)}.png`,
          {
            type: file.type,
          },
        );
        if (validateFile(uniqueFile)) {
          newFiles.push(uniqueFile);
        }
      }
    }
    if (newFiles.length === 0) return;

    setSelectedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  // 2. SERET DAN LEPAS (DRAG & DROP): Simpan berkas secara lokal, unggah saat mengirim pesan
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    const validFiles = files.filter(validateFile);
    if (validFiles.length === 0) return;

    const limit = isGuest || !currentIsLoggedIn ? 1 : 5;
    const availableSlots = limit - selectedFiles.length;
    const targets = validFiles.slice(0, availableSlots);
    if (targets.length === 0 && files.length > 0) {
      toast.warning(`Slot penuh! Maksimal ${limit} file.`);
      return;
    }

    setSelectedFiles((prev) => [...prev, ...targets]);
  };

  const [darkMode, setDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem("cakra-theme");
    if (savedTheme !== null) return savedTheme === "dark";
    if (window.matchMedia)
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    return false;
  });

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showDocumentList, setShowDocumentList] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const lastLoadedSessionRef = useRef(null);

  const [docSearchQuery, setDocSearchQuery] = useState("");
  const messageSearchInputRef = useRef(null);
  const [showMsgSearch, setShowMsgSearch] = useState(false);
  const [msgSearchQuery, setMsgSearchQuery] = useState("");

  // 🔄 W8: Sinkronisasi mode tema antar tab browser
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === "cakra-theme") {
        setDarkMode(e.newValue === "dark");
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  // ⌨️ W9: Keyboard Shortcuts Handler
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setShowMsgSearch((prev) => !prev);
        setTimeout(() => {
          if (!showMsgSearch) {
            messageSearchInputRef.current?.focus();
          }
        }, 100);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        handleClearChat();
      }
      if (e.key === "Escape") {
        setShowMsgSearch(false);
        setMsgSearchQuery("");
        setShowDocumentList(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showMsgSearch, chatHistory]);

  // Load documents when document list is opened
  useEffect(() => {
    if (showDocumentList) {
      fetchDocumentsList();
    }
  }, [showDocumentList, fetchDocumentsList]);

  const {
    messages,
    isStreaming,
    isLoading,
    currentThinking,
    sendMessage,
    clearChat: storeClearChat,
    loadChatSession: storeLoadChatSession,
  } = useChatStore();

  useEffect(() => {
    if (!sessionId || sessionId === "new") {
      lastLoadedSessionRef.current = null;
      return;
    }
    if (isStreaming) return;
    if (lastLoadedSessionRef.current === sessionId) return;
    lastLoadedSessionRef.current = sessionId;
    storeLoadChatSession(sessionId);
  }, [sessionId, isStreaming, storeLoadChatSession]);

  const loadChatSession = (id) => {
    if (!id || id === "new" || id === sessionId) return;
    lastLoadedSessionRef.current = null;
    navigate(`/chat/${id}`);
  };

  const handleClearChat = () => {
    storeClearChat();
    lastLoadedSessionRef.current = null;
    navigate("/chat/new");
  };

  // SINKRONISASI: Menyelaraskan state lokal ChatPage dengan isi store setelah perubahan rute URL selesai
  useEffect(() => {
    const currentGlobalMode = useChatStore.getState().chatMode || "auto";
    setChatMode(currentGlobalMode);
    chatModeRef.current = currentGlobalMode;
  }, [sessionId]);

  const triggerLogout = () => {
    logout();
    window.location.href = "/login";
  };

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e) => {
      const savedTheme = localStorage.getItem("cakra-theme");
      if (savedTheme === null) setDarkMode(e.matches);
    };
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    localStorage.setItem("cakra-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const theme = darkMode ? darkColors : lightColors;

  const lastAssistantIndex = [...messages]
    .reverse()
    .findIndex((m) => m.role === "assistant");
  const isThinking =
    isStreaming &&
    lastAssistantIndex === 0 &&
    messages[messages.length - 1]?.content === "";
  const isStreamingText =
    isStreaming &&
    lastAssistantIndex === 0 &&
    messages[messages.length - 1]?.content !== "";
  const isEmptyChat = messages.length === 0;
  const showWelcome = isEmptyChat && !isLoading;

  // CAPTURE BASELINE HEIGHT SEKALI SAAT MOUNT
  useEffect(() => {
    if (textareaRef.current && baselineHeightRef.current === 0) {
      textareaRef.current.style.height = "auto";
      baselineHeightRef.current = textareaRef.current.scrollHeight;
    }
  }, []);

  // 3. PENYESUAIAN TINGGI OTOMATIS DINAMIS: Menghitung tinggi DOM asli secara linier tanpa merender ulang komponen (MENCEGAH LOOP DAN FLUKTUASI TINGGI)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    const scrollTop = el.scrollTop;
    el.style.overflow = "hidden";
    el.style.height = "auto";

    const newHeight = Math.min(el.scrollHeight, 450);
    el.style.height = `${newHeight}px`;

    el.style.overflow = newHeight >= 450 ? "auto" : "hidden";
    el.scrollTop = scrollTop;

    const baseline = baselineHeightRef.current;
    if (baseline > 0) {
      const hasNewlines = input.includes("\n");
      const isCurrentlyThick = el.scrollHeight > baseline + 3 || hasNewlines;

      // Gunakan variabel lokal 'isCurrentlyThick' untuk membandingkan dengan state sebelumnya melalui pembaruan fungsional untuk menghindari pembaruan langsung
      setIsMultiLine((prevIsMultiLine) => {
        if (!prevIsMultiLine) {
          // LOGIKA NAIK: Jika aslinya single, tapi sekarang mendeteksi tebal
          return isCurrentlyThick;
        } else {
          // LOGIKA TURUN: Jika aslinya multi, hanya boleh balik single kalau beneran pendek < 65
          if (!isCurrentlyThick && input.length < 65) {
            return false;
          }
          return true; // Tetap mengunci multi-line
        }
      });
    }
  }, [input]); // SINKRONISASI AMAN: Hanya memantau perubahan 'input', mengeluarkan 'isMultiLine' dari dependensi

  // 2. PROSES PENGUNGGAHAN BERKAS DIJALANKAN DI SINI SAAT TOMBOL KIRIM DIKLIK
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (
      (!input.trim() && selectedFiles.length === 0) ||
      isStreaming ||
      isUploadingFile
    )
      return;

    let finalStagedData = [];

    if (selectedFiles.length > 0) {
      setIsUploadingFile(true);

      let uploadSessionUuid =
        activeSessionId || useChatStore.getState().sessionUuid;
      if (!uploadSessionUuid || uploadSessionUuid === "new") {
        const created = await useChatStore
          .getState()
          .createNewSession(isGuest ? null : currentUserData?.npp);
        if (created) {
          uploadSessionUuid = created;
          if (!isGuest && currentIsLoggedIn) {
            lastLoadedSessionRef.current = created;
            navigate(`/chat/${created}`, { replace: true });
          }
        }
      }

      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append("files", file));
      if (uploadSessionUuid) formData.append("session_uuid", uploadSessionUuid);

      try {
        toast.info("Mengunggah berkas...");
        const result = await uploadDocuments(formData);

        if (result.status === "success") {
          finalStagedData = result.data;
          setStagedAttachments(result.data); // Tetap simpan ke store untuk backup state
          toast.success("Berkas berhasil diunggah!");
        } else {
          throw new Error("Gagal mengunggah berkas");
        }
      } catch (err) {
        console.error(err);
        toast.error(
          "Gagal memproses pengiriman karena terjadi kesalahan saat mengunggah berkas.",
        );
        setIsUploadingFile(false);
        return; // Hentikan pipeline agar chat tidak terkirim pincang tanpa file
      } finally {
        setIsUploadingFile(false);
      }
    }

    // PERBAIKAN UTAMA: Meneruskan data berkas yang berhasil diunggah langsung ke fungsi sendMessage
    sendMessage(
      input,
      isGuest ? null : currentUserData?.npp,
      isGuest
        ? null
        : (newSessionObj) => {
          setChatHistory((prev) => [newSessionObj, ...prev]);
          lastLoadedSessionRef.current = newSessionObj.session_uuid;
          navigate(`/chat/${newSessionObj.session_uuid}`, { replace: true });
        },
      finalStagedData, // Meneruskan data lampiran berkas secara langsung
      chatModeRef.current, // PARAMETER MODE: 'auto' | 'documents' (untuk dikirim ke backend)
      toast,
    );

    setInput("");
    setSelectedFiles([]);
    setStagedAttachments([]);
    setIsMultiLine(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const defaultGetGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return "SELAMAT PAGI";
    if (hour < 15) return "SELAMAT SIANG";
    if (hour < 19) return "SELAMAT SORE";
    return "SELAMAT MALAM";
  };

  // ============================================================
  // PATCH: renderInputForm — satu textarea, layout via wrapper
  // Single line: [+][textarea][Auto ▾][↑] dalam satu row
  // Multi line:  textarea full width di atas, toolbar bawah
  // ============================================================

  const renderInputForm = (isBottom = false) => (
    <div
      style={{
        ...styles.inputArea,
        background: isBottom
          ? `linear-gradient(to bottom, transparent 0%, ${theme.inputAreaBg} 30%)`
          : "transparent",
        // ✅ Satu instance, posisi dinamis
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
              const isPDF = file.name.endsWith(".pdf");
              return (
                <div
                  key={idx}
                  style={{
                    position: "relative",
                    width: "64px",
                    height: "64px",
                    borderRadius: "12px",
                    overflow: "hidden",
                    background: darkMode ? "#2d2d30" : "#f3f4f6",
                    border: `1px solid ${darkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {isPDF ? (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: "1px",
                      }}
                    >
                      <span style={{ fontSize: "24px" }}>📄</span>
                      <span
                        style={{
                          fontSize: "9px",
                          fontWeight: 700,
                          color: "#ef4444",
                          maxWidth: "52px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        PDF
                      </span>
                    </div>
                  ) : (
                    <img
                      src={URL.createObjectURL(file)}
                      alt="preview"
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                      }}
                    />
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
            flexDirection: "column", // selalu column — baris textarea + baris toolbar
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
            accept=".pdf,image/*"
            style={{ display: "none" }}
          />

          {/* ── BARIS 1: wrapper textarea + plus (single) ── */}
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "flex-end", // semua nempel di bawah saat textarea tinggi
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

            {/* [FIX UTAMA] Satu textarea — ref tidak pernah pindah */}
            <textarea
              ref={textareaRef}
              value={input}
              disabled={isStreaming}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isStreaming
                  ? "CAKRA sedang berpikir..."
                  : activeIsolatedTitle
                    ? "Tanyakan perihal isi dokumen ini..."
                    : "Tanyakan apa saja..."
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
                {/* 🛡️ SENSOR OTENTIKASI: Hanya muncul jika user beneran login pegawai */}
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
                {/* 🛡️ SENSOR OTENTIKASI: Hanya muncul jika user beneran login pegawai */}
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

  const hasSidebar = !isGuest && currentIsLoggedIn;
  const mainMarginLeft = hasSidebar ? (sidebarOpen ? "18rem" : "4rem") : "0";

  return (
    <div style={{ ...styles.root, background: theme.rootBg }}>
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
          scrollbar-width: thin;
          scrollbar-color: ${darkMode ? "#4b5563" : "#9ca3af"} transparent;
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
          display: none;
          width: 0;
          height: 0;
        }
        * { box-sizing: border-box; }
        .custom-scroll-gemini::-webkit-scrollbar { width: 8px; background-color: transparent; }
        .custom-scroll-gemini::-webkit-scrollbar-thumb {
          background-color: ${darkMode ? "rgba(255, 255, 255, 0.15)" : "rgba(0, 0, 0, 0.15)"};
          border-radius: 20px;
        }

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
        <header style={styles.header}>
          <div style={styles.modelSelector}>
            {!hasSidebar && (
              <img
                src={cakraLogo}
                alt="CAKRA AI"
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
            {messages.length > 0 && (
              <button
                onClick={() => {
                  setShowMsgSearch((prev) => !prev);
                  setTimeout(() => {
                    if (!showMsgSearch) messageSearchInputRef.current?.focus();
                  }, 100);
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
                🔍
              </button>
            )}
            {/* 👇 W16: Notification Bell */}
            {!isGuest && <NotificationBell />}
            <HeaderDropdownMenu
              isGuest={isGuest}
              onLogin={() => navigate("/login")}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
              theme={theme}
            />
          </div>
        </header>

        <div
          style={{
            flex: 1,
            position: "relative",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              flex: 1,
              minHeight: 0,
              opacity: showWelcome ? 0 : 1,
              transition: "opacity 0.2s ease",
              pointerEvents: showWelcome ? "none" : "auto",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* 🔍 Message Search Bar */}
            {showMsgSearch && (
              <div
                style={{
                  ...styles.msgSearchContainer,
                  background: theme.inputBg,
                  borderBottomColor: theme.borderColor,
                }}
              >
                <span style={{ fontSize: "14px", color: theme.secondaryText }}>
                  🔍
                </span>
                <input
                  ref={messageSearchInputRef}
                  type="text"
                  placeholder="Cari kata kunci dalam percakapan ini..."
                  value={msgSearchQuery}
                  onChange={(e) => setMsgSearchQuery(e.target.value)}
                  style={{
                    flex: 1,
                    border: "none",
                    background: "transparent",
                    outline: "none",
                    color: theme.textColor,
                    fontSize: "14px",
                  }}
                />
                <button
                  onClick={() => {
                    setShowMsgSearch(false);
                    setMsgSearchQuery("");
                  }}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: theme.secondaryText,
                    cursor: "pointer",
                    fontSize: "14px",
                    fontWeight: "bold",
                    padding: "4px 8px",
                  }}
                >
                  ✕
                </button>
              </div>
            )}

            <ChatArea
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
            />
          </div>

          {showWelcome && (
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
                {renderInputForm(true)}
              </div>
            </div>
          )}
        </div>

        {/* Hanya render input di bawah jika chat sudah ada */}
        {!showWelcome && renderInputForm(true)}
      </main>

      {/* 🔒 W7: Modal Pilihan Dokumen Regulasi (Context Isolation) */}
      {showDocumentList && (
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
                    (doc.judul || "")
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
                        (doc.judul || "")
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
                              {doc.judul}
                            </div>
                            <div
                              style={{
                                fontSize: "11px",
                                color: theme.secondaryText,
                                marginTop: "2px",
                              }}
                            >
                              No: {doc.nomor || "-"} | Tipe: {doc.tipe}
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              setContextIsolation(doc.id, doc.judul);
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
    </div>
  );
}
