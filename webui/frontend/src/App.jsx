import React, { useState, useEffect, useRef, useCallback } from "react";
// Komponen
import MessageRenderer from "./components/MessageRenderer";
import PdfButtons from "./components/PdfButtons";
import FileUploadPanel from "./components/FileUploadPanel";
import FilePreviewPanel from "./components/FilePreviewPanel";
import DocumentListPanel from "./components/DocumentListPanel";
// Utils
import { copyToClipboard } from "./utils/copyToClipboard";
import Sidebar from "./components/Sidebar";
const API_BASE = "http://192.168.11.80:5000";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState("connected");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [tempFileId, setTempFileId] = useState(null);
  const [currentMode, setCurrentMode] = useState("normal");
  const [showDocumentList, setShowDocumentList] = useState(false);
  const [notification, setNotification] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const [isUserScrollingUp, setIsUserScrollingUp] = useState(false);
  const wheelTimeoutRef = useRef(null); // <-- TAMBAHKAN INI
  const scrollTimeoutRef = useRef(null);

  // Effect untuk reset auto-scroll ketika user kirim pesan
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    const isUserMessage = lastMessage?.sender === "user";

    if (isUserMessage) {
      autoScrollEnabled.current = true;
    }
  }, [messages]);

  // AUTO-SCROLL FIX - FINAL SOLUTION
  const autoScrollEnabled = useRef(true);
  const typingAnimationRef = useRef(null);

  // Effect untuk track scroll behavior user
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

      // User sedang scroll manual jika jarak dari bottom > 150px
      if (distanceFromBottom > 150) {
        autoScrollEnabled.current = false;
      }
      // User kembali ke bottom
      else if (distanceFromBottom < 20) {
        autoScrollEnabled.current = true;
      }
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Effect untuk auto-scroll ketika ada message baru atau AI selesai mengetik
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container || !autoScrollEnabled.current) return;

    // Cari message AI terakhir yang sedang tidak mengetik
    const aiMessages = messages.filter((msg) => msg.sender === "ai");
    const lastAiMessage = aiMessages[aiMessages.length - 1];
    const isAiTyping = lastAiMessage?.isTyping === true;

    // Jika AI sedang mengetik, scroll dengan interval
    if (isAiTyping) {
      if (typingAnimationRef.current) {
        clearInterval(typingAnimationRef.current);
      }

      typingAnimationRef.current = setInterval(() => {
        if (autoScrollEnabled.current) {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: "smooth",
          });
        }
      }, 100); // Scroll setiap 100ms selama typing

      return () => {
        if (typingAnimationRef.current) {
          clearInterval(typingAnimationRef.current);
        }
      };
    }
    // Jika AI selesai mengetik, scroll sekali
    else {
      if (typingAnimationRef.current) {
        clearInterval(typingAnimationRef.current);
        typingAnimationRef.current = null;
      }

      // Scroll ke bottom dengan delay kecil
      setTimeout(() => {
        if (autoScrollEnabled.current) {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: "smooth",
          });
        }
      }, 100);
    }
  }, [messages]);

  // Tambahkan cleanup untuk interval
  useEffect(() => {
    return () => {
      if (typingAnimationRef.current) {
        clearInterval(typingAnimationRef.current);
      }
    };
  }, []);

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

  const showNotification = useCallback((message, type = "info") => {
    setNotification({ id: Date.now(), message, type });
    setTimeout(() => setNotification(null), 3000);
  }, []);

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

  const switchMode = (mode) => {
    const nextMode = currentMode === mode ? "normal" : mode;
    setCurrentMode(nextMode);
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    autoScrollEnabled.current = true;
    const userMessage = input.trim();
    setInput("");
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
      const payload = { message: userMessage, mode: currentMode };
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

  const clearChat = () => {
    if (messages.length > 0 && window.confirm("Clear all messages?")) {
      setMessages([]);
      setUploadedFiles([]);
    }
  };

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  // Di dalam function App()
  const [isLoggedIn, setIsLoggedIn] = useState(false); // Default false (belum login)
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [userData, setUserData] = useState(null);

  // Handler Login
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    const { username, password } = loginForm;

    try {
      const response = await fetch("http://192.168.11.80:5000/api/login", {
        // Sesuaikan IP backend kamu
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

        // SIMPAN KE LOCALSTORAGE (Agar tidak hilang saat reload)
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
      setLoginError("Server login tidak merespon");
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return "Selamat Pagi";
    if (hour < 15) return "Selamat Siang";
    if (hour < 18) return "Selamat Sore";
    return "Selamat Malam";
  };

  return (
    // Di dalam return() App.js

    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar hanya muncul jika sudah login */}
      {isLoggedIn && (
        <Sidebar
          backendStatus={backendStatus}
          isOpen={isSidebarOpen}
          setIsOpen={setIsSidebarOpen}
          setIsLoggedIn={setIsLoggedIn}
          userData={userData}
        />
      )}

      {/* Content Container */}
      <div
        className={`flex flex-col flex-1 h-full transition-all duration-300 ${
          isLoggedIn ? (isSidebarOpen ? "ml-60" : "ml-15") : "ml-0" // Tanpa margin jika tidak login
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
              <div className="bg-white rounded-2xl shadow-2xl p-8 relative">
                <button
                  onClick={() => setShowLoginModal(false)}
                  className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>

                <div className="text-center mb-8">
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
                    👤
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800">
                    Login CAKRA AI
                  </h2>
                  <p className="text-gray-500 text-sm">
                    Gunakan username dan password ESS
                  </p>
                </div>

                <form onSubmit={handleLoginSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Username
                    </label>
                    <input
                      type="text"
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      value={loginForm.username}
                      onChange={(e) =>
                        setLoginForm({ ...loginForm, username: e.target.value })
                      }
                      placeholder="username"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Password
                    </label>
                    <input
                      type="password"
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
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

        {/* Sisa konten (messagesContainerRef, Input Area, dll) tetap di bawah sini */}

        {/* Hidden file input & Modals tetap di sini */}
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

        {/* Area Pesan: Ditambah flex-1 dan overflow-y-auto */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto px-4 py-6"
          style={{
            background: "#FFFFFF",
          }}
        >
          <div className="max-w-3xl mx-auto">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                {/* Konten Welcome Screen Lu Tetap Sama */}
                <div className="w-20 h-20 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center mb-6">
                  <span className="text-3xl">🤖</span>
                </div>
                {/* LOGIKA SAPAAN DINAMIS */}
                <h2 className="text-2xl font-semibold text-gray-900 mb-3">
                  {isLoggedIn
                    ? `${getGreeting()}, ${userData.fullname}`
                    : "Hai, saya CAKRA (Pindad AI)"}
                </h2>

                <p className="text-gray-600 max-w-md mb-8">
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
                      className="text-left p-4 bg-white border border-gray-200 rounded-xl hover:border-blue-300 hover:bg-blue-50 transition-colors text-sm text-gray-700"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setShowFileUpload(true)}
                  className="flex items-center space-x-2 px-4 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl hover:opacity-90 transition-opacity"
                >
                  <span className="text-lg">📁</span>
                  <div className="text-left">
                    <p className="font-medium">Upload file untuk dianalisa</p>
                    <p className="text-sm opacity-90">
                      PDF, gambar, dokumen text
                    </p>
                  </div>
                </button>
              </div>
            ) : (
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
                    <div
                      className={`${
                        msg.sender === "user"
                          ? "bg-blue-600 text-white rounded-4xl px-4 py-2 ml-auto flex items-center justify-center"
                          : "max-w-3xl ml-4"
                      }`}
                    >
                      <MessageRenderer
                        text={msg.text}
                        showNotification={showNotification}
                        isTyping={msg.isTyping}
                        isAI={msg.sender === "ai"}
                      />
                      {msg.sender === "ai" && (
                        <PdfButtons
                          pdfInfo={msg.pdfInfo}
                          isFromDocument={msg.isFromDocument}
                          isTyping={msg.isTyping}
                        />
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="flex max-w-3xl items-start">
                      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mr-3 overflow-hidden">
                        <img
                          src="./src/assets/cakra.png"
                          alt="CAKRA"
                          className="w-8 h-8 object-cover"
                        />
                      </div>
                      <div className="px-4 py-3 bg-white border border-gray-200 rounded-2xl rounded-tl-none">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div
                            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.1s" }}
                          ></div>
                          <div
                            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.2s" }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* Input Area: Sekarang tetap di bawah karena container di atasnya flex-1 */}
        <div className="bg-white px-4 py-4">
          <div
            className="max-w-3xl mx-auto rounded-4xl"
            style={{
              background: "#F7F8FC",
            }}
          >
            {/* Bagian Mode & Textarea Lu Tetap Sama */}
            {currentMode !== "normal" && (
              <div className="flex items-center space-x-2 mb-2">
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    currentMode === "document"
                      ? "bg-blue-100 text-blue-800"
                      : "bg-purple-100 text-purple-800"
                  }`}
                >
                  {currentMode === "document"
                    ? "📄 Document Mode"
                    : "🌐 Search Mode"}
                </span>
              </div>
            )}
            <div className="relative">
              <div className="rounded-3xl p-3">
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
                  className="w-full border-none bg-transparent resize-none focus:outline-none text-gray-900 ml-3 mt-2"
                  rows="1"
                  style={{ minHeight: "30px", maxHeight: "120px" }}
                  onInput={(e) => {
                    e.target.style.height = "auto";
                    e.target.style.height =
                      Math.min(e.target.scrollHeight, 120) + "px";
                  }}
                />
                <div
                  className={`flex items-center mt-2 ${
                    isLoggedIn ? "justify-between" : "justify-end"
                  }`}
                >
                  {/* Bagian Mode (Hanya muncul jika Login) */}
                  {isLoggedIn && (
                    <div className="flex space-x-2 animate-fade-in">
                      <button
                        onClick={() => switchMode("document")}
                        className={`px-3 py-1 text-sm rounded-full transition-colors flex items-center gap-1.5 ${
                          currentMode === "document"
                            ? "bg-blue-600 text-white shadow-sm"
                            : "bg-gray-200 hover:bg-gray-300 text-gray-800"
                        }`}
                      >
                        <span className="text-xs">📄</span> Document
                      </button>

                      <button
                        onClick={() => switchMode("search")}
                        className={`px-3 py-1 text-sm rounded-full transition-colors flex items-center gap-1.5 ${
                          currentMode === "search"
                            ? "bg-purple-600 text-white shadow-sm"
                            : "bg-gray-200 hover:bg-gray-300 text-gray-800"
                        }`}
                      >
                        <span className="text-xs">🌐</span> Search
                      </button>
                    </div>
                  )}

                  {/* Bagian Aksi (Selalu di Kanan) */}
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setShowFileUpload(true)}
                      className="p-2 text-gray-600 hover:text-blue-600 transition-colors"
                    >
                      <span className="text-xl">📁</span>
                    </button>

                    <button
                      onClick={sendMessage}
                      disabled={isLoading || !input.trim()}
                      className={`px-4 py-1 rounded-xl font-medium transition-colors ${
                        isLoading || !input.trim()
                          ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                          : "bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:opacity-90"
                      }`}
                    >
                      {isLoading ? (
                        <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                      ) : (
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="w-5 h-5"
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
      </div>
    </div>
  );
}

export default App;
