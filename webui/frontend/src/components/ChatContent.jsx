// src/components/ChatContent.jsx
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import cakraLogo from "../assets/cakra.png";

// Layout Components
import MainLayout from "./layout/MainLayout";
import HeaderBar from "./layout/HeaderBar";
import MessageList from "./layout/MessageList";
import InputArea from "./layout/InputArea";
import FloatingButtons from "./layout/FloatingButtons";

// Modals
import LoginModal from "./modals/LoginModal";
import LogoutModal from "./modals/LogoutModal";

// UI
import NotificationToast from "./ui/NotificationToast";
import GuestWelcome from "./ui/GuestWelcome";

// Konfigurasi API
const API_BASE = "http://192.168.11.80:5000";

function ChatContent({ isNew, isGuest }) {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // =========================================================================
  // STATE MANAGEMENT
  // =========================================================================
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);

  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [tempFileId, setTempFileId] = useState(null);
  const [showDocumentList, setShowDocumentList] = useState(false);

  const [currentMode, setCurrentMode] = useState("normal");
  const [notification, setNotification] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [userData, setUserData] = useState(null);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const currentRole =
    userData?.role || localStorage.getItem("userRole") || "GUEST";

  const [modelList, setModelList] = useState([]);
  const [selectedModel, setSelectedModel] = useState("qwen3:8b");

  const [backendStatus, setBackendStatus] = useState("connected");
  const [isInitializing, setIsInitializing] = useState(true);

  // =========================================================================
  // REF MANAGEMENT
  // =========================================================================
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const autoScrollEnabled = useRef(true);
  const typingAnimationRef = useRef(null);
  const isUserScrolling = useRef(false);
  const isAiTypingRef = useRef(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [canScroll, setCanScroll] = useState(false);

  // =========================================================================
  // SHARED UTILS & HANDLERS
  // =========================================================================
  const showNotification = useCallback((message, type = "info") => {
    setNotification({ id: Date.now(), message, type });
    setTimeout(() => setNotification(null), 3000);
  }, []);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return "Selamat Pagi";
    if (hour < 15) return "Selamat Siang";
    if (hour < 18) return "Selamat Sore";
    return "Selamat Malam";
  };

  // =========================================================================
  // AUTO-SCROLL LOGIC
  // =========================================================================
  const startAutoScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;
    if (typingAnimationRef.current) clearInterval(typingAnimationRef.current);
    typingAnimationRef.current = setInterval(() => {
      if (autoScrollEnabled.current && !isUserScrolling.current) {
        container.scrollTop = container.scrollHeight;
      } else {
        clearInterval(typingAnimationRef.current);
        typingAnimationRef.current = null;
      }
    }, 50);
  };

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.sender === "user") {
      autoScrollEnabled.current = true;
      isUserScrolling.current = false;
    }
  }, [messages]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      setIsAtBottom(distanceFromBottom < 100);
      setShowScrollTop(scrollTop > 400);
      setShowScrollBottom(distanceFromBottom > 200);
      if (distanceFromBottom > 100) {
        if (!isUserScrolling.current) {
          isUserScrolling.current = true;
          autoScrollEnabled.current = false;
        }
      }
      if (distanceFromBottom < 100) {
        if (isUserScrolling.current) {
          isUserScrolling.current = false;
          autoScrollEnabled.current = true;
          container.scrollTop = container.scrollHeight;
          if (isAiTypingRef.current) startAutoScroll();
        }
      }
    };
    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const lastMessage = messages[messages.length - 1];
    const isTypingNow = lastMessage?.sender === "ai" && lastMessage?.isTyping;
    isAiTypingRef.current = isTypingNow;
    if (isTypingNow && autoScrollEnabled.current && !isUserScrolling.current) {
      startAutoScroll();
    } else if (!isTypingNow) {
      if (typingAnimationRef.current) clearInterval(typingAnimationRef.current);
      if (autoScrollEnabled.current && !isUserScrolling.current) {
        setTimeout(() => {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: "smooth",
          });
        }, 100);
      }
    }
    return () => {
      if (typingAnimationRef.current) clearInterval(typingAnimationRef.current);
    };
  }, [messages]);

  useEffect(() => {
    return () => {
      if (typingAnimationRef.current) clearInterval(typingAnimationRef.current);
    };
  }, []);

  const checkScrollable = () => {
    const container = messagesContainerRef.current;
    if (container) {
      const isScrollable = container.scrollHeight > container.clientHeight;
      setCanScroll(isScrollable);
    }
  };

  useEffect(() => {
    checkScrollable();
  }, [messages]);

  // =========================================================================
  // SESSION SYNC DARI URL
  // =========================================================================
  useEffect(() => {
    if (
      sessionId === "new" ||
      sessionId === "guest" ||
      (sessionId === "guest" && isGuest)
    ) {
      setMessages([]);
      setCurrentSessionId(null);
      return;
    }
    if (sessionId && sessionId !== currentSessionId) {
      if (sessionId === currentSessionId) return;
      loadChatSession(sessionId);
      setCurrentSessionId(sessionId);
    }
  }, [sessionId, currentSessionId, isGuest]);

  // =========================================================================
  // INITIALIZATION & SESSION MANAGEMENT
  // =========================================================================
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        setBackendStatus(res.ok ? "connected" : "error");
      } catch {
        setBackendStatus("disconnected");
      }
    };
    checkBackend();
    loadDocuments();
  }, []);

  useEffect(() => {
    const checkSession = async () => {
      const token = localStorage.getItem("session_token");
      try {
        if (token) {
          const response = await fetch(
            `${API_BASE}/api/verify-session?token=${token}`
          );
          const result = await response.json();
          if (response.ok && result.status === "success") {
            setUserData(result.data);
            setIsLoggedIn(true);
          } else {
            localStorage.clear();
          }
        }
      } catch (error) {
        console.error("Initialization failed", error);
      } finally {
        setTimeout(() => setIsInitializing(false), 500);
      }
    };
    checkSession();
  }, []);

  useEffect(() => {
    if (currentSessionId) {
      localStorage.setItem("lastSessionId", currentSessionId);
    } else {
      localStorage.removeItem("lastSessionId");
    }
  }, [currentSessionId]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/available-models`);
        const result = await res.json();
        if (result.status === "success") setModelList(result.data);
      } catch (err) {
        console.error("Gagal ambil model list:", err);
      }
    };
    fetchModels();
  }, []);

  // =========================================================================
  // DOCUMENT MANAGEMENT
  // =========================================================================
  const loadDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch (err) {
      console.error("Error loading documents:", err);
    }
  };

  // =========================================================================
  // FILE UPLOAD FUNCTIONS
  // =========================================================================
  const handleFilePreview = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/upload-preview`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setTempFileId(data.file_id);
        setPreviewFile({
          name: data.filename,
          type: data.file_type,
          size: data.size,
          previewText: data.preview_text,
        });
        setShowPreview(true);
      } else {
        showNotification(`Preview failed: ${data.error}`, "error");
      }
    } catch (err) {
      showNotification(`Preview error: ${err.message}`, "error");
    }
  };

  const confirmUpload = async () => {
    if (!tempFileId) return;
    try {
      const res = await fetch(`${API_BASE}/api/confirm-upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: tempFileId }),
      });
      const data = await res.json();
      if (res.ok) {
        setUploadedFiles((prev) => [
          ...prev,
          { id: data.file_id, name: data.filename, type: data.file_type },
        ]);
        showNotification(`File "${data.filename}" uploaded!`, "success");
        setShowPreview(false);
        setPreviewFile(null);
        setTempFileId(null);
      }
    } catch (err) {
      showNotification(`Upload error: ${err.message}`, "error");
    }
  };

  const cancelUpload = async () => {
    if (tempFileId) {
      await fetch(`${API_BASE}/api/cancel-upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: tempFileId }),
      });
    }
    setShowPreview(false);
    setPreviewFile(null);
    setTempFileId(null);
  };

  // =========================================================================
  // CHAT SESSION FUNCTIONS
  // =========================================================================
  const loadChatSession = async (sessionUuid) => {
    if (!sessionUuid) return;
    setIsLoading(true);
    setCurrentSessionId(sessionUuid);
    try {
      const res = await fetch(`${API_BASE}/api/chat-messages/${sessionUuid}`);
      const result = await res.json();
      if (result.status === "success") {
        setMessages(result.data);
      } else {
        console.error("Sesi tidak ditemukan di database");
      }
    } catch (err) {
      console.error("Gagal ambil history pesan:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
    setInput("");
    setSelectedFiles([]);
    setPreviews([]);
    setUploadedFiles([]);
    if (!isLoggedIn) {
      navigate("/chat/guest");
    } else {
      navigate("/chat/new");
    }
  };

  const switchMode = (mode) => {
    const nextMode = currentMode === mode ? "normal" : mode;
    setCurrentMode(nextMode);
  };

  // =========================================================================
  // MESSAGE HANDLING
  // =========================================================================
  const [expandedMessages, setExpandedMessages] = useState({});
  const toggleExpand = (id) => {
    setExpandedMessages((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [previews, setPreviews] = useState([]);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFiles(files);
  };

  const handleFiles = (files) => {
    const fileArray = Array.from(files);
    fileArray.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const base64Data = e.target.result;
        const newFile = {
          url: base64Data,
          name: file.name,
          type: file.type.startsWith("image/") ? "image" : "pdf",
        };
        setPreviews((prev) => [...prev, newFile]);
        setSelectedFiles((prev) => [...prev, file]);
      };
      reader.readAsDataURL(file);
    });
  };

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files);
    if (selectedFiles.length > 0) handleFiles(selectedFiles);
    e.target.value = null;
  };

  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    const files = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === "file") {
        files.push(items[i].getAsFile());
      }
    }
    if (files.length > 0) handleFiles(files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFiles(files);
  };

  const sendMessage = async () => {
    if ((!input.trim() && selectedFiles.length === 0) || isLoading) return;
    autoScrollEnabled.current = true;
    isUserScrolling.current = false;
    setTimeout(() => {
      messagesContainerRef.current?.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }, 10);

    const userMessage = input.trim();
    const currentPreviews = [...previews];
    setInput("");
    setSelectedFiles([]);
    setPreviews([]);

    const userMsgId = Date.now();
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        sender: "user",
        text: userMessage,
        attachments: currentPreviews,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]);

    setIsLoading(true);
    const aiMsgId = Date.now() + 1;
    setMessages((prev) => [
      ...prev,
      {
        id: aiMsgId,
        sender: "ai",
        text: "",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        isTyping: false,
      },
    ]);

    try {
      const payload = {
        message: userMessage,
        mode: currentMode,
        model: selectedModel,
        npp: userData?.username || null,
        role: currentRole,
        session_uuid: currentSessionId,
        fullname: userData?.fullname,
        attachments: currentPreviews.map((p) => ({
          name: p.name,
          type: p.type,
          data: p.url,
        })),
      };
      if (uploadedFiles.length > 0 && currentMode === "normal") {
        payload.file_id = uploadedFiles[uploadedFiles.length - 1].id;
      }

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.session_uuid && !currentSessionId) {
        setCurrentSessionId(data.session_uuid);
        const newChatEntry = {
          session_uuid: data.session_uuid,
          judul: userMessage.substring(0, 50) || "New Chat",
          created_at: new Date().toISOString(),
          is_pinned: false,
        };
        setChatHistory((prev) => [newChatEntry, ...prev]);
        localStorage.setItem("lastSessionId", data.session_uuid);
        if (isLoggedIn) {
          window.history.replaceState(null, "", `/chat/${data.session_uuid}`);
        }
      }

      const aiResponse = data.reply || "No response from AI.";
      const pdfInfo = data.pdf_info || null;
      const isFromDocument = data.is_from_document || false;

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? {
                ...msg,
                text: aiResponse,
                pdfInfo,
                isFromDocument,
                isTyping: true,
              }
            : msg
        )
      );

      setTimeout(() => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMsgId ? { ...msg, isTyping: false } : msg
          )
        );
      }, aiResponse.length * 15 + 500);
    } catch (err) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? {
                ...msg,
                text: `Error: ${err.message}`,
                isTyping: false,
                isError: true,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // =========================================================================
  // AUTHENTICATION FUNCTIONS
  // =========================================================================
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    const { username, password } = loginForm;
    try {
      const response = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const result = await response.json();
      if (response.ok && result.status === "success") {
        const newUser = {
          username: result.data.username,
          fullname: result.data.fullname,
          divisi: result.data.divisi,
          role: result.data.role,
        };
        setIsLoggedIn(true);
        setUserData(newUser);
        localStorage.setItem("session_token", result.data.token);
        localStorage.setItem("userSession", JSON.stringify(newUser));
        localStorage.setItem("isLoggedIn", "true");
        localStorage.setItem("userRole", result.data.role);
        showNotification(`Selamat datang, ${newUser.fullname}!`, "success");
        setShowLoginModal(false);
        setLoginForm({ username: "", password: "" });
        setLoginError("");
        const currentPath = window.location.pathname;
        if (currentPath === "/chat/guest") {
          navigate("/chat/new");
        }
      } else {
        setLoginError(result.message || "Login gagal");
      }
    } catch (error) {
      console.error("Login Error:", error);
      setLoginError("Server login tidak merespon");
    }
  };

  const triggerLogout = () => {
    setIsLogoutModalOpen(true);
  };

  const handleLogout = async () => {
    const token = localStorage.getItem("session_token");
    try {
      if (token) {
        await fetch(`${API_BASE}/api/logout`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
      }
    } catch (error) {
      console.error("Gagal logout ke server:", error);
    } finally {
      localStorage.clear();
      setIsLoggedIn(false);
      setUserData(null);
      setMessages([]);
      setCurrentSessionId(null);
      setChatHistory([]);
      setInput("");
      setIsLogoutModalOpen(false);
      navigate("/chat/guest");
    }
  };

  // =========================================================================
  // COPY BUBBLE
  // =========================================================================
  const handleCopy = (text, showNotification) => {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => showNotification("Teks berhasil disalin!"))
        .catch(() => fallbackCopyTextToClipboard(text, showNotification));
    } else {
      fallbackCopyTextToClipboard(text, showNotification);
    }
  };

  const fallbackCopyTextToClipboard = (text, showNotification) => {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    textArea.style.top = "0";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      const successful = document.execCommand("copy");
      if (successful) {
        showNotification("Teks berhasil disalin!");
      }
    } catch (err) {
      console.error("Fallback: Oops, unable to copy", err);
    }
    document.body.removeChild(textArea);
  };

  // =========================================================================
  // PASS ALL NECESSARY PROPS TO CHILDREN
  // =========================================================================
  const sharedProps = {
    // State
    messages,
    input,
    setInput,
    isLoading,
    currentSessionId,
    chatHistory,
    uploadedFiles,
    documents,
    showPreview,
    previewFile,
    tempFileId,
    showDocumentList,
    currentMode,
    isLoggedIn,
    userData,
    backendStatus,
    isInitializing,
    modelList,
    selectedModel,
    isSidebarOpen,
    isDropdownOpen,
    notification,
    showLoginModal,
    loginForm,
    loginError,
    showPassword,
    isLogoutModalOpen,
    messagesContainerRef,
    fileInputRef,
    isDragging,
    previews,
    selectedFiles,
    expandedMessages,
    showScrollTop,
    showScrollBottom,
    isAtBottom,
    canScroll,
    isAiTypingRef,
    // Handlers
    startAutoScroll,
    showNotification,
    getGreeting,
    handleNewChat,
    switchMode,
    toggleExpand,
    handleDragOver,
    handleDragLeave,
    onDrop,
    handleFileChange,
    handlePaste,
    handleDrop,
    sendMessage,
    handleKeyPress,
    handleLoginSubmit,
    triggerLogout,
    handleLogout,
    handleCopy,
    confirmUpload,
    cancelUpload,
    setShowDocumentList,
    setIsSidebarOpen,
    setIsDropdownOpen,
    setShowLoginModal,
    setLoginForm,
    setLoginError,
    setShowPassword,
    setIsLogoutModalOpen,
    setPreviews,
    setSelectedFiles,
    setExpandedMessages,
    setMessages,
    setCurrentSessionId,
    setChatHistory,
    setUploadedFiles,
    setDocuments,
    setShowPreview,
    setPreviewFile,
    setTempFileId,
    setSelectedModel,
    navigate,
    cakraLogo,
    API_BASE,
  };

  return (
    <MainLayout {...sharedProps}>
      {/* 1. Header tetap di atas */}
      <HeaderBar {...sharedProps} />

      {/* 2. Area Utama Chat */}
      <div className="flex-1 relative flex flex-col overflow-hidden">
        {/* MessageList sekarang menangani kondisi kosong (GuestWelcome) di dalamnya */}
        <MessageList
          {...sharedProps}
          isAiTypingRef={isAiTypingRef}
          startAutoScroll={startAutoScroll}
        />

        {/* FloatingButtons ditaruh sejajar dengan MessageList supaya absolute-nya bekerja */}
        <FloatingButtons {...sharedProps} />
      </div>

      {/* 3. Input Area di paling bawah */}
      <InputArea {...sharedProps} />

      {/* 4. Overlay & Modals (Tidak memakan space layout) */}
      <LoginModal {...sharedProps} />
      <LogoutModal {...sharedProps} />
      <NotificationToast notification={notification} />

      {/* Preview File Overlay */}
      {showPreview && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          {/* Masukkan logic preview file lu di sini atau buat komponen FilePreviewModal */}
        </div>
      )}
    </MainLayout>
  );
}

export default ChatContent;
