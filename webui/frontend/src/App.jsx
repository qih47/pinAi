import React, { useState, useEffect, useRef, useCallback } from "react";

// Komponen
import MessageRenderer from "./components/MessageRenderer";
import PdfButtons from "./components/PdfButtons";
import FileUploadPanel from "./components/FileUploadPanel";
import FilePreviewPanel from "./components/FilePreviewPanel";
import DocumentListPanel from "./components/DocumentListPanel";
import Sidebar from "./components/Sidebar";

// Utils
import { copyToClipboard } from "./utils/copyToClipboard";

// Konfigurasi API
const API_BASE = "http://192.168.11.80:5000";

function App() {
  // =========================================================================
  // STATE MANAGEMENT
  // =========================================================================

  // Chat State
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);

  // File & Document State
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [tempFileId, setTempFileId] = useState(null);
  const [showDocumentList, setShowDocumentList] = useState(false);

  // UI State
  const [currentMode, setCurrentMode] = useState("normal");
  const [notification, setNotification] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isUserScrollingUp, setIsUserScrollingUp] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Auth State
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [userData, setUserData] = useState(null);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);

  // Model State
  const [modelList, setModelList] = useState([]);
  const [selectedModel, setSelectedModel] = useState("qwen3:8b");

  // System State
  const [backendStatus, setBackendStatus] = useState("connected");
  const [isInitializing, setIsInitializing] = useState(true);

  // =========================================================================
  // REF MANAGEMENT
  // =========================================================================

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const wheelTimeoutRef = useRef(null);
  const scrollTimeoutRef = useRef(null);
  const autoScrollEnabled = useRef(true);
  const typingAnimationRef = useRef(null);
  const isUserScrolling = useRef(false);

  // =========================================================================
  // AUTO-SCROLL LOGIC
  // =========================================================================

  // Reset auto-scroll saat user kirim pesan
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.sender === "user") {
      autoScrollEnabled.current = true;
      isUserScrolling.current = false;
    }
  }, [messages]);

  // Track scroll behavior user
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

      // user naik
      if (distanceFromBottom > 150) {
        if (!isUserScrolling.current) {
          isUserScrolling.current = true;
          autoScrollEnabled.current = false;

          if (typingAnimationRef.current) {
            clearInterval(typingAnimationRef.current);
            typingAnimationRef.current = null;
          }
        }
      }

      // user balik ke bawah
      if (distanceFromBottom < 20) {
        isUserScrolling.current = false;
        autoScrollEnabled.current = true;
      }
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-scroll ketika ada message baru atau AI selesai mengetik
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const aiMessages = messages.filter((m) => m.sender === "ai");
    const lastAiMessage = aiMessages[aiMessages.length - 1];
    const isAiTyping = lastAiMessage?.isTyping === true;

    // AI sedang mengetik → AUTO (tanpa smooth)
    if (isAiTyping && autoScrollEnabled.current && !isUserScrolling.current) {
      if (typingAnimationRef.current) {
        clearInterval(typingAnimationRef.current);
      }

      typingAnimationRef.current = setInterval(() => {
        if (autoScrollEnabled.current && !isUserScrolling.current) {
          container.scrollTop = container.scrollHeight;
        }
      }, 100);

      return () => {
        if (typingAnimationRef.current) {
          clearInterval(typingAnimationRef.current);
          typingAnimationRef.current = null;
        }
      };
    }

    // AI selesai → smooth sekali
    if (!isAiTyping && autoScrollEnabled.current && !isUserScrolling.current) {
      if (typingAnimationRef.current) {
        clearInterval(typingAnimationRef.current);
        typingAnimationRef.current = null;
      }

      setTimeout(() => {
        if (autoScrollEnabled.current && !isUserScrolling.current) {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: "smooth",
          });
        }
      }, 100);
    }
  }, [messages]);

  // Cleanup interval
  useEffect(() => {
    return () => {
      if (typingAnimationRef.current) {
        clearInterval(typingAnimationRef.current);
      }
    };
  }, []);

  // =========================================================================
  // INITIALIZATION & SESSION MANAGEMENT
  // =========================================================================

  // Check backend & load documents
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

  // Cek session saat aplikasi pertama kali load
  useEffect(() => {
    const checkSession = async () => {
      const token = localStorage.getItem("session_token");
      const lastSessionId = localStorage.getItem("lastSessionId");

      try {
        if (token) {
          const response = await fetch(
            `${API_BASE}/api/verify-session?token=${token}`
          );
          const result = await response.json();

          if (response.ok && result.status === "success") {
            setUserData(result.data);
            setIsLoggedIn(true);

            if (lastSessionId) {
              await loadChatSession(lastSessionId);
            }
          } else {
            localStorage.clear();
          }
        }
      } catch (error) {
        console.error("Initialization failed", error);
      } finally {
        setTimeout(() => {
          setIsInitializing(false);
        }, 500);
      }
    };

    checkSession();
  }, []);

  // Simpan sessionId ke localStorage setiap kali berubah
  useEffect(() => {
    if (currentSessionId) {
      localStorage.setItem("lastSessionId", currentSessionId);
    } else {
      localStorage.removeItem("lastSessionId");
    }
  }, [currentSessionId]);

  // Fetch model list
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/available-models`);
        const result = await res.json();
        if (result.status === "success") {
          setModelList(result.data);
        }
      } catch (err) {
        console.error("Gagal ambil model list:", err);
      }
    };
    fetchModels();
  }, []);

  // =========================================================================
  // UTILITY FUNCTIONS
  // =========================================================================

  // Menampilkan notifikasi
  const showNotification = useCallback((message, type = "info") => {
    setNotification({ id: Date.now(), message, type });
    setTimeout(() => setNotification(null), 3000);
  }, []);

  // Mendapatkan greeting berdasarkan waktu
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return "Selamat Pagi";
    if (hour < 15) return "Selamat Siang";
    if (hour < 18) return "Selamat Sore";
    return "Selamat Malam";
  };

  // =========================================================================
  // DOCUMENT MANAGEMENT
  // =========================================================================

  // Load documents dari backend
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

  // Preview file sebelum upload
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

  // Konfirmasi upload file
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

  // Batalkan upload file
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

  // Load chat session berdasarkan session UUID
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

  // Buat chat baru
  const handleNewChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  // Ganti mode chat (normal/document/search)
  const switchMode = (mode) => {
    const nextMode = currentMode === mode ? "normal" : mode;
    setCurrentMode(nextMode);
  };

  // =========================================================================
  // MESSAGE HANDLING
  // =========================================================================

  // Kirim pesan ke backend
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    autoScrollEnabled.current = true;
    const userMessage = input.trim();
    setInput("");

    // Tambah pesan user ke state
    const userMsgId = Date.now();
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        sender: "user",
        text: userMessage,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]);

    setIsLoading(true);
    const aiMsgId = Date.now() + 1;

    // Tambah placeholder AI message
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
      // Siapkan payload untuk API
      const payload = {
        message: userMessage,
        mode: currentMode,
        model: selectedModel,
        npp: userData?.username,
        session_uuid: currentSessionId,
        fullname: userData?.fullname,
      };

      if (uploadedFiles.length > 0 && currentMode === "normal") {
        payload.file_id = uploadedFiles[uploadedFiles.length - 1].id;
      }

      // Kirim ke API
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Update session ID jika ini chat pertama
      if (data.session_uuid && !currentSessionId) {
        setCurrentSessionId(data.session_uuid);

        const newChatEntry = {
          session_uuid: data.session_uuid,
          judul: userMessage.substring(0, 50),
          created_at: new Date().toISOString(),
        };

        setChatHistory((prev) => [newChatEntry, ...prev]);
      }

      // Update AI message dengan response
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

      // Simulasi typing animation
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

  // Handle keyboard event untuk enter key
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // =========================================================================
  // AUTHENTICATION FUNCTIONS
  // =========================================================================

  // Submit login form
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
        };

        setIsLoggedIn(true);
        setUserData(newUser);

        localStorage.setItem("session_token", result.data.token);
        localStorage.setItem("userSession", JSON.stringify(newUser));
        localStorage.setItem("isLoggedIn", "true");

        showNotification(`Selamat datang, ${newUser.fullname}!`, "success");

        setShowLoginModal(false);
        setLoginForm({ username: "", password: "" });
        setLoginError("");
      } else {
        setLoginError(result.message || "Login gagal");
      }
    } catch (error) {
      console.error("Login Error:", error);
      setLoginError("Server login tidak merespon");
    }
  };

  // Trigger logout modal
  const triggerLogout = () => {
    setIsLogoutModalOpen(true);
  };

  // Eksekusi logout
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
    }
  };

  // =========================================================================
  // RENDER LOADING SCREEN
  // =========================================================================

  if (isInitializing) {
    return (
      <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-white dark:bg-[#232326] transition-colors">
        <img
          src="./src/assets/cakra.png"
          alt="Loading..."
          className="w-20 h-20 animate-spin"
        />
        <h2 className="mt-6 text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-500 bg-clip-text text-transparent animate-bounce">
          CAKRA AI
        </h2>
        <p className="text-gray-400 dark:text-gray-300 text-sm mt-2">
          Menyiapkan ruang kerja Anda...
        </p>
      </div>
    );
  }

  // =========================================================================
  // MAIN RENDER
  // =========================================================================

  return (
    <div className="border-t border-t-[#E0E0E0] dark:border-t-[#1A1A1C] bg-[#F7F8FC] dark:bg-[#232326] flex h-screen overflow-hidden text-gray-900 dark:text-gray-200 transition-colors duration-300">
      {/* Sidebar hanya muncul jika sudah login */}
      {isLoggedIn && (
        <Sidebar
          backendStatus={backendStatus}
          isOpen={isSidebarOpen}
          setIsOpen={setIsSidebarOpen}
          setIsLoggedIn={setIsLoggedIn}
          userData={userData}
          handleLogout={handleLogout}
          setShowDocumentList={setShowDocumentList}
          setCurrentSessionId={setCurrentSessionId}
          currentSessionId={currentSessionId}
          loadChatSession={loadChatSession}
          clearChat={handleNewChat}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          triggerLogout={triggerLogout}
        />
      )}
      {!isLoggedIn && (
        <div className="absolute top-4 left-4 flex items-center z-50">
          {/* Logo di pojok kiri atas, spin hanya sekali ketika reload */}
          <img
            src="./src/assets/cakra.png"
            alt="CAKRA AI Logo"
            className="w-10 h-10 object-cover rounded-full"
            style={{
              animation: "spin-once 2s cubic-bezier(0.4,0,0.2,1) 1",
            }}
          />
        </div>
      )}
      {/* Model Selector - Hanya muncul jika sudah login */}
      {isLoggedIn && (
        <div
          className="absolute top-4 z-30 flex items-center transition-all duration-300 ease-in-out"
          style={{
            left: isSidebarOpen ? "295px" : "75px",
          }}
        >
          <div className="border-t border-t-[#E0E0E0] dark:border-t-[#1A1A1C] bg-[#F7F8FC] dark:bg-[#1A1A1C] relative flex items-center border border-gray-200 dark:border-[#27272a] rounded-full px-4 py-1.5 shadow-sm transition-all duration-300">
            <div className="w-2 h-2 bg-blue-500 rounded-full mr-2 animate-pulse"></div>

            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-1 text-sm font-semibold text-gray-700 dark:text-gray-200 focus:outline-none"
              style={{ transition: "color 0.3s" }}
            >
              {modelList.find((m) => m.id === selectedModel)?.name ||
                "Select Model"}
              <svg
                className={`w-4 h-4 transition-transform ${
                  isDropdownOpen ? "rotate-180" : ""
                }`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {isDropdownOpen && (
              <div className="absolute top-full left-0 mt-2 w-56 rounded-xl bg-white dark:bg-[#1A1A1C] border border-gray-200 dark:border-[#27272a] shadow-xl overflow-hidden z-50 animate-in fade-in zoom-in duration-200">
                <div className="px-4 py-2 border-b border-gray-50 dark:border-[#232326] bg-gray-50/50 dark:bg-[#232326]/50">
                  <span className="text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
                    Engine System
                  </span>
                </div>

                <div className="max-h-60 overflow-y-auto">
                  {modelList.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        setSelectedModel(m.id);
                        setIsDropdownOpen(false);
                      }}
                      className={`w-full px-4 py-3 flex items-center justify-between text-left transition
                        ${
                          selectedModel === m.id
                            ? "bg-blue-50/70 dark:bg-blue-600/10 text-blue-700 dark:text-blue-300"
                            : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#232326]"
                        }`}
                    >
                      <span className="text-sm font-medium">{m.name}</span>

                      {selectedModel === m.id && (
                        <svg
                          className="w-4 h-4 text-blue-600 dark:text-blue-400"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Content Container */}
      <div
        className={`flex flex-col flex-1 h-full transition-all duration-300 ${
          isLoggedIn ? (isSidebarOpen ? "ml-60" : "ml-15") : "ml-0"
        }`}
      >
        {/* HEADER AREA: Tombol Login/Logout */}
        <div className="absolute right-4 z-20">
          {!isLoggedIn && (
            <div className="absolute top-2 right-2 z-20">
              <button
                onClick={() => setShowLoginModal(true)}
                className="px-5 py-1 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-full font-semibold shadow-lg hover:bg-blue-700 transition-all"
              >
                Login
              </button>
            </div>
          )}

          {/* MODAL LOGIN */}
          {showLoginModal && (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm">
              <div className="bg-white dark:bg-[#232326] rounded-2xl shadow-2xl p-8 relative border border-gray-100 dark:border-[#232326]">
                <button
                  onClick={() => setShowLoginModal(false)}
                  className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  ✕
                </button>

                <div className="text-center mb-8">
                  <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/40 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
                    👤
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800 dark:text-blue-200">
                    Login CAKRA AI
                  </h2>
                  <p className="text-gray-500 dark:text-gray-400 text-sm">
                    Gunakan username dan password ESS
                  </p>
                </div>

                <form onSubmit={handleLoginSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Username
                    </label>
                    <input
                      type="text"
                      required
                      className="w-full px-4 py-2 border border-gray-300 dark:border-[#232326] rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white dark:bg-[#1a1a1c] text-gray-900 dark:text-gray-100"
                      value={loginForm.username}
                      onChange={(e) =>
                        setLoginForm({ ...loginForm, username: e.target.value })
                      }
                      placeholder="username"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Password
                    </label>
                    <input
                      type="password"
                      required
                      className="w-full px-4 py-2 border border-gray-300 dark:border-[#232326] rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white dark:bg-[#1a1a1c] text-gray-900 dark:text-gray-100"
                      value={loginForm.password}
                      onChange={(e) =>
                        setLoginForm({ ...loginForm, password: e.target.value })
                      }
                      placeholder="••••••"
                    />
                  </div>

                  {loginError && (
                    <p className="text-red-500 text-xs mt-1 animate-pulse">
                      {loginError}
                    </p>
                  )}

                  <button
                    type="submit"
                    className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-bold hover:opacity-90 transition-opacity mt-4"
                  >
                    Masuk Sekarang
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>

        {/* Hidden file input & Modals */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFilePreview}
          accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
          className="hidden"
        />

        {showFileUpload && (
          <FileUploadPanel
            fileInputRef={fileInputRef}
            setShowFileUpload={setShowFileUpload}
          />
        )}

        {showPreview && (
          <FilePreviewPanel
            previewFile={previewFile}
            cancelUpload={cancelUpload}
            confirmUpload={confirmUpload}
          />
        )}

        {showDocumentList && (
          <DocumentListPanel
            documents={documents}
            setShowDocumentList={setShowDocumentList}
          />
        )}

        {/* Area Pesan */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto px-4 py-6 bg-white dark:bg-[#232326] transition-colors duration-300"
        >
          <div className="max-w-3xl mx-auto">
            {messages.length === 0 ? (
              // Welcome Screen
              <div className="flex flex-col items-center justify-center h-full text-center py-60">
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-3 transition-colors duration-300">
                  {isLoggedIn
                    ? `${getGreeting()}, ${userData.fullname}`
                    : "Hai, saya CAKRA (Pindad AI)"}
                </h2>

                <p className="text-gray-600 dark:text-gray-300 max-w-md mb-8 transition-colors duration-300">
                  {isLoggedIn
                    ? "Ada yang bisa saya bantu hari ini?"
                    : "Saya bisa membantu menjawab pertanyaan anda..."}
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg mb-8">
                  {[
                    "Berikan informasi terkait PT Pindad",
                    "Tahapan rekrutmen di PT Pindad seperti apa?",
                    "Apa itu daerah terlarang, tertutup dan terbatas di PT Pindad?",
                    "Apakah masyarakat umum bisa membeli produk pindad?",
                  ].map((suggestion, idx) => (
                    <button
                      key={idx}
                      onClick={() => setInput(suggestion)}
                      className="text-left p-4 bg-white dark:bg-[#2E2E33] border border-gray-200 dark:border-[#232326] rounded-xl hover:border-blue-300 hover:bg-blue-50 dark:hover:bg-blue-700/10 transition-colors text-sm text-gray-700 dark:text-gray-200"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              // Chat Messages
              <div className="space-y-6">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.sender === "user"
                        ? "justify-end pl-12"
                        : "justify-start pr-12"
                    }`}
                  >
                    {/* --- PESAN USER --- */}
                    {msg.sender === "user" && (
                      <div className="bg-blue-600 dark:bg-[#2E2E33] text-white rounded-4xl px-4 py-1 ml-auto flex items-center justify-center mt-5">
                        <MessageRenderer
                          text={msg.text}
                          showNotification={showNotification}
                          isTyping={msg.isTyping}
                          isAI={false}
                        />
                      </div>
                    )}

                    {/* --- PESAN AI --- */}
                    {msg.sender === "ai" && (
                      <div className="max-w-3xl ml-0 md:ml-4">
                        {/* PdfButtons dan Logo nangkring di atas MessageRenderer sesuai request sebelumnya */}
                        <React.Fragment>
                          <PdfButtons
                            pdfInfo={msg.pdfInfo}
                            isFromDocument={msg.isFromDocument}
                            isTyping={msg.isTyping}
                          />

                          <div
                            className={`flex items-start mb-2 mt-5 ${
                              !isLoading ? "" : "hidden"
                            }`}
                          >
                            <div className="flex-shrink-0 w-8 h-8 xs:mr-5 -ml-1">
                              <img
                                src="./src/assets/cakra.png"
                                alt="CAKRA Loading"
                                className={`w-8 h-8 object-cover rounded-full ${
                                  msg.isTyping ? "animate-spin" : ""
                                }`}
                                style={{ animationDuration: "2s" }}
                              />
                            </div>
                            <span
                              className={`text-gray-400 dark:text-gray-300 text-xs flex items-center justify-center ml-2${
                                !isLoading ? "" : "hidden"
                              }`}
                              style={{ alignSelf: "center" }}
                            >
                              CAKRA AI
                            </span>
                          </div>
                        </React.Fragment>

                        <MessageRenderer
                          text={msg.text}
                          showNotification={showNotification}
                          isTyping={msg.isTyping}
                          isAI={true}
                        />
                      </div>
                    )}
                  </div>
                ))}

                {/* Loading Indicator */}
                {isLoading && (
                  <div className="flex justify-start items-center py-2 animate-pulse">
                    <div className="flex items-center">
                      {/* Container Logo dengan Animasi Spin */}
                      <div className="flex-shrink-0 w-8 h-8 mr-3">
                        <img
                          src="./src/assets/cakra.png"
                          alt="CAKRA Loading"
                          className="w-8 h-8 object-cover rounded-full animate-spin"
                          style={{ animationDuration: "2s" }}
                        />
                      </div>

                      {/* Teks Loading opsional agar user tahu AI sedang memproses */}
                      <span className="text-xs text-gray-400 dark:text-gray-300 font-medium tracking-wide">
                        CAKRA lagi mikir nih...
                      </span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="bg-white dark:bg-[#232326] px-4 py-4 transition-colors duration-300">
          <div className="max-w-3xl mx-auto rounded-4xl">
            {/* Label Mode */}
            {currentMode !== "normal" && (
              <div className="flex items-center space-x-2 mb-2">
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    currentMode === "document"
                      ? "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-300"
                      : "bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-300"
                  }`}
                >
                  {currentMode === "document"
                    ? "📄 Document Mode"
                    : "🌐 Search Mode"}
                </span>
              </div>
            )}

            <div className="relative">
              <div
                className={`rounded-3xl transition-all duration-300 ${
                  isLoggedIn ? "p-3" : "px-3 py-2"
                } bg-[#F7F8FC] dark:bg-[#2E2E33]`}
              >
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyPress}
                  disabled={isLoading}
                  placeholder={
                    currentMode === "document"
                      ? "Tanya apapun terkait dokumen PT Pindad..."
                      : "Tanya CAKRA AI..."
                  }
                  className="w-full border-none bg-transparent resize-none focus:outline-none text-gray-900 dark:text-gray-100 ml-3 mt-1"
                  rows="1"
                  style={{ minHeight: "30px", maxHeight: "120px" }}
                  onInput={(e) => {
                    e.target.style.height = "auto";
                    e.target.style.height =
                      Math.min(e.target.scrollHeight, 120) + "px";
                  }}
                />

                <div
                  className={`flex items-center ${
                    isLoggedIn ? "mt-2 justify-between" : "mt-0 justify-end"
                  }`}
                >
                  {/* Mode Selector (Hanya untuk yang login) */}
                  {isLoggedIn && (
                    <div className="flex space-x-2 animate-fade-in">
                      <button
                        onClick={() => switchMode("document")}
                        className={`px-3 py-1 text-sm rounded-full transition-colors flex items-center gap-1.5 ${
                          currentMode === "document"
                            ? "bg-blue-600 text-white shadow-sm"
                            : "bg-gray-200 dark:bg-[#232326] hover:bg-gray-300 dark:hover:bg-[#29293a] text-gray-800 dark:text-gray-200"
                        }`}
                      >
                        <span className="text-xs">📄</span> Document
                      </button>

                      <button
                        onClick={() => switchMode("search")}
                        className={`px-3 py-1 text-sm rounded-full transition-colors flex items-center gap-1.5 ${
                          currentMode === "search"
                            ? "bg-purple-600 text-white shadow-sm"
                            : "bg-gray-200 dark:bg-[#232326] hover:bg-gray-300 dark:hover:bg-[#29293a] text-gray-800 dark:text-gray-200"
                        }`}
                      >
                        <span className="text-xs">🌐</span> Search
                      </button>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => setShowFileUpload(true)}
                      className="p-1.5 text-gray-500 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                    >
                      <span className="text-lg">📁</span>
                    </button>

                    <button
                      onClick={sendMessage}
                      disabled={isLoading || !input.trim()}
                      className={`px-4 py-1.5 rounded-xl font-medium transition-all ${
                        isLoading || !input.trim()
                          ? "bg-gray-200 dark:bg-[#29293a] text-gray-400 cursor-not-allowed"
                          : "bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:opacity-90 shadow-md active:scale-95"
                      }`}
                    >
                      {isLoading ? (
                        <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                      ) : (
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="w-4 h-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Notification Toast */}
        {notification && (
          <div
            className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-lg shadow-lg text-white font-medium transition-opacity duration-300 ${
              notification.type === "success"
                ? "bg-green-500"
                : notification.type === "error"
                ? "bg-red-500"
                : "bg-blue-500"
            }`}
          >
            {notification.message}
          </div>
        )}

        {/* Logout Modal */}
        {isLogoutModalOpen && (
          <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in">
            <div className="bg-white dark:bg-[#18181e] rounded-3xl p-6 max-w-sm w-full mx-4 shadow-2xl animate-zoom-in border border-gray-100 dark:border-[#232326]">
              <div className="text-center">
                <div className="w-16 h-16 bg-red-50 dark:bg-red-900/30 text-red-500 dark:text-red-400 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
                  ⚠️
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  Konfirmasi Keluar
                </h3>
                <p className="text-gray-500 dark:text-gray-300 mt-2 text-sm leading-relaxed">
                  Anda yakin ingin keluar? dalam mode guest anda tidak bisa
                  melihat dokumen peraturan PT Pindad.
                </p>
              </div>

              <div className="flex space-x-3 mt-8">
                <button
                  onClick={() => setIsLogoutModalOpen(false)}
                  className="flex-1 px-4 py-3 bg-gray-100 dark:bg-[#232326] text-gray-700 dark:text-gray-200 rounded-2xl font-semibold hover:bg-gray-200 dark:hover:bg-[#29293a] transition-all active:scale-95"
                >
                  Batal
                </button>
                <button
                  onClick={handleLogout}
                  className="flex-1 px-4 py-3 bg-red-600 text-white rounded-2xl font-semibold hover:bg-red-700 transition-all shadow-lg shadow-red-200 active:scale-95"
                >
                  Ya, Keluar
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
