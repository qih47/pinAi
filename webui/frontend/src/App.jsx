import { useState, useEffect, useRef } from "react";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const [showFileUpload, setShowFileUpload] = useState(false);

  const API_BASE = "http://192.168.11.80:5000";

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check backend on load
  useEffect(() => {
    checkBackend();
  }, []);

  const checkBackend = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setBackendStatus(res.ok ? "connected" : "error");
    } catch {
      setBackendStatus("disconnected");
    }
  };

  // Handle file upload
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Sembunyikan panel upload
    setShowFileUpload(false);

    const formData = new FormData();
    formData.append("file", file);

    // Tampilkan pesan "uploading"
    setMessages((prev) => [
      ...prev,
      {
        sender: "system",
        text: `📁 Uploading "${file.name}"...`,
        isSystem: true,
      },
    ]);

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (res.ok) {
        // Update pesan upload
        setMessages((prev) =>
          prev.map((msg) =>
            msg.text.includes("Uploading") && msg.sender === "system"
              ? {
                  sender: "system",
                  text: `✅ File "${data.filename}" uploaded successfully!\n\nYou can now ask questions about this file.`,
                  isSystem: true,
                }
              : msg
          )
        );

        // Simpan info file
        setUploadedFiles((prev) => [
          ...prev,
          {
            id: data.file_id,
            name: data.filename,
            type: data.file_type,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            sender: "system",
            text: `❌ Upload failed: ${data.error}`,
            isSystem: true,
            isError: true,
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "system",
          text: `❌ Upload error: ${err.message}`,
          isSystem: true,
          isError: true,
        },
      ]);
    }
  };

  // Main chat function
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setMessages((prev) => [
      ...prev,
      {
        sender: "user",
        text: userMessage,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]);
    setInput("");
    setIsLoading(true);

    try {
      // Cek apakah ada file yang diupload
      const hasFiles = uploadedFiles.length > 0;
      const lastFileId = hasFiles
        ? uploadedFiles[uploadedFiles.length - 1].id
        : null;

      // Chat dengan backend
      const payload = { message: userMessage };
      if (lastFileId) {
        payload.file_id = lastFileId;
      }

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: data.reply,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: `Sorry, I encountered an error: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          isError: true,
        },
      ]);
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

  // File upload panel component
  const FileUploadPanel = () => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Upload File</h3>
          <button
            onClick={() => setShowFileUpload(false)}
            className="p-1 hover:bg-gray-100 rounded-lg"
          >
            ✕
          </button>
        </div>

        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 hover:bg-blue-50 cursor-pointer transition-colors"
        >
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-3">
              <span className="text-2xl">📁</span>
            </div>
            <p className="font-medium text-gray-900">Click to select file</p>
            <p className="text-sm text-gray-500 mt-1">
              PDF, PNG, JPG, TXT up to 16MB
            </p>
            <p className="text-xs text-gray-400 mt-2">Or drag and drop here</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          {[
            { type: "PDF", desc: "Document text extraction", icon: "📄" },
            { type: "Image", desc: "OCR text recognition", icon: "🖼️" },
            { type: "TXT", desc: "Plain text reading", icon: "📝" },
            { type: "DOCX", desc: "Word document", icon: "📘" },
          ].map((item, idx) => (
            <div key={idx} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-2">
                <span className="text-lg">{item.icon}</span>
                <div>
                  <p className="font-medium text-sm">{item.type}</p>
                  <p className="text-xs text-gray-500">{item.desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-gray-500 mt-4 text-center">
          After uploading, ask questions about the file
        </p>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
        className="hidden"
      />

      {/* File upload modal */}
      {showFileUpload && <FileUploadPanel />}

      {/* Header - SIMPLIFIED, TANPA UPLOAD BUTTON */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <img src="./src/assets/cakra.png" alt="CAKRA AI Logo" className="w-10 h-10 rounded-full object-cover" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">CAKRA AI</h1>
              <div className="flex items-center space-x-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    backendStatus === "connected"
                      ? "bg-green-500"
                      : backendStatus === "disconnected"
                      ? "bg-red-500"
                      : "bg-yellow-500"
                  }`}
                ></span>
                <span className="text-xs text-gray-500">
                  {backendStatus === "connected"
                    ? "Connected"
                    : "Connecting..."}{" "}
                  • Qwen3-VL 8B
                </span>
              </div>
            </div>
          </div>

          {/* HANYA BUTTON CLEAR CHAT */}
          <div className="flex items-center space-x-2">
            <button
              onClick={clearChat}
              className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500"
              title="New chat"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-20 h-20 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center mb-6">
                <span className="text-3xl">🤖</span>
              </div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-3">
                Hai saya CAKRA (Pindad AI)
              </h2>
              <p className="text-gray-600 max-w-md mb-8">
                Saya bisa membantu menjawab pertanyaan anda, memberikan informasi terkait rekrutmen, peraturan perusahaan,
                dan lain lain. Kamu juga bisa mengupload file untuk dianalisa.
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
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`flex max-w-3xl ${
                      msg.sender === "user" ? "flex-row-reverse" : "flex-row"
                    } items-start`}
                  >
                    <div
                      className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium ${
                        msg.sender === "user"
                          ? "bg-blue-600 ml-3"
                          : msg.sender === "system"
                          ? "bg-gray-500 ml-3"
                          : "mr-3"
                      }`}
                    >
                      {msg.sender === "user"
                        ? "You"
                        : msg.sender === "system"
                        ? "📁"
                        : (
                          <img
                            src="src/assets/cakra.png"
                            alt="CAKRA"
                            className="w-8 h-8 object-cover rounded-full"
                          />
                        )}
                    </div>
                    <div
                      className={`px-4 py-3 rounded-2xl ${
                        msg.sender === "user"
                          ? "bg-blue-600 text-white rounded-tr-none"
                          : msg.sender === "system"
                          ? "bg-gray-100 text-gray-800 rounded-tl-none border border-gray-200"
                          : "bg-white border border-gray-200 text-gray-800 rounded-tl-none"
                      } ${msg.isError ? "border-red-200 bg-red-50" : ""}`}
                    >
                      <div className="whitespace-pre-wrap break-words">
                        {msg.text}
                      </div>
                      {msg.timestamp && (
                        <div
                          className={`text-xs mt-2 ${
                            msg.sender === "user"
                              ? "text-blue-200"
                              : "text-gray-500"
                          }`}
                        >
                          {msg.timestamp}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex max-w-3xl items-start">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium mr-3 overflow-hidden">
                      <img src="src/assets/cakra.png" alt="CAKRA" className="w-8 h-8 object-cover" />
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

      {/* Input Area - DENGAN UPLOAD BUTTON */}
      <div className="border-t border-gray-200 bg-white px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={isLoading}
              placeholder={
                uploadedFiles.length > 0
                  ? `Ask about "${
                      uploadedFiles[uploadedFiles.length - 1].name
                    }" or type a message...`
                  : "Message CAKRA AI or upload a file..."
              }
              className="w-full border border-gray-300 rounded-2xl px-4 py-3 pr-28 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
              rows="1"
              style={{ minHeight: "52px", maxHeight: "120px" }}
            />

            <div className="absolute right-2 bottom-2 flex items-center space-x-2">
              {/* UPLOAD BUTTON DI SINI */}
              <button
                onClick={() => setShowFileUpload(true)}
                disabled={isLoading}
                className="p-2 text-gray-600 hover:text-blue-600 disabled:opacity-50 transition-colors"
                title="Upload file"
              >
                <span className="text-xl">📁</span>
              </button>

              {/* SEND BUTTON */}
              <button
                onClick={sendMessage}
                disabled={isLoading || !input.trim()}
                className={`px-4 py-2 rounded-xl font-medium transition-colors ${
                  isLoading || !input.trim()
                    ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                    : "bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:opacity-90"
                }`}
              >
                {isLoading ? (
                  <svg
                    className="w-5 h-5 animate-spin"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
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

          <p className="text-xs text-gray-500 mt-2 text-center">
            Press Enter to send • Upload files and ask questions naturally
            {uploadedFiles.length > 0 &&
              ` • ${uploadedFiles.length} file(s) uploaded`}
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
