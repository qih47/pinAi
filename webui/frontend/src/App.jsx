import { useState, useEffect, useRef } from "react";

/**
 * Komponen untuk menampilkan teks dengan format list yang rapi
 */
function FormattedMessage({ text }) {
  // Tambahkan pengecekan tipe dan konversi ke string jika perlu
  if (!text) return null;

  // Pastikan text adalah string sebelum memanggil replace
  let cleanText = text;
  if (typeof text !== "string") {
    cleanText = String(text); // Konversi ke string
  }

  // Parse HTML entities dan clean text
  cleanText = cleanText
    .replace(/&nbsp;/g, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?div[^>]*>/gi, "\n")
    .replace(/<\/?[^>]+(>|$)/g, "")
    // TAMBAH INI:
    .replace(/^[-_]{3,}\s*$/gm, "") // Hapus baris yang cuma "---"
    .replace(/^\s*[-_]{2,}\s*/gm, "") // Hapus "---" di awal baris
    // JANGAN PAKAI YANG INI: .replace(/[\s_-]{3,}/g, ' ')
    .trim();

  // Split menjadi lines
  const lines = cleanText.split("\n").filter((line) => line.trim() !== "");

  return (
    <div className="space-y-2">
      {lines.map((line, lineIndex) => {
        const trimmedLine = line.trim();

        // Deteksi berbagai jenis list
        const numberMatch = trimmedLine.match(/^(\d+)\.\s+(.+)/);
        const letterMatch = trimmedLine.match(/^([a-z])\.\s+(.+)/i);
        const bulletMatch = trimmedLine.match(/^[-*•]\s+(.+)/);
        const numberedParenMatch = trimmedLine.match(/^(\d+)\)\s+(.+)/);
        const letterParenMatch = trimmedLine.match(/^([a-z])\)\s+(.+)/i);
        const doubleNumberedParenMatch = trimmedLine.match(/^(\d+)\)\)\s+(.+)/);
        const tripleNumberedParenMatch =
          trimmedLine.match(/^(\d+)\)\)\)\s+(.+)/);

        // Cek indentasi dengan spasi/tab
        const indentCount = line.length - line.trimStart().length;
        const indentLevel = Math.floor(indentCount / 4);

        // Fungsi untuk wrap text panjang
        const wrapText = (textToWrap, maxLength = 100) => {
          if (!textToWrap || textToWrap.length <= maxLength)
            return [textToWrap];

          const words = textToWrap.split(" ");
          const wrappedLines = [];
          let currentLine = [];
          let currentLength = 0;

          for (const word of words) {
            if (
              currentLength + word.length + 1 <= maxLength ||
              currentLine.length === 0
            ) {
              currentLine.push(word);
              currentLength += word.length + 1;
            } else {
              wrappedLines.push(currentLine.join(" "));
              currentLine = [word];
              currentLength = word.length;
            }
          }

          if (currentLine.length > 0) {
            wrappedLines.push(currentLine.join(" "));
          }

          return wrappedLines;
        };

        // Render berdasarkan tipe
        let content;

        if (numberMatch) {
          const [, number, contentText] = numberMatch;
          const wrappedContent = wrapText(contentText, 65);
          content = (
            <div className="flex">
              <span className="font-semibold min-w-[0.8rem]">{number}.</span>
              <div className="ml-2">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (letterMatch) {
          const [, letter, contentText] = letterMatch;
          const wrappedContent = wrapText(contentText, 60);
          content = (
            <div className="flex ml-4">
              <span className="font-semibold min-w-[1rem]">{letter}.</span>
              <div className="ml-2">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (bulletMatch) {
          const [, contentText] = bulletMatch;
          const wrappedContent = wrapText(contentText, 65);
          content = (
            <div className="flex ml-5">
              <span className="mr-2">•</span>
              <div>
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (numberedParenMatch) {
          const [, number, contentText] = numberedParenMatch;
          const wrappedContent = wrapText(contentText, 60);
          content = (
            <div className="flex ml-6">
              <span className="font-semibold min-w-[1.5rem]">{number})</span>
              <div className="ml-5">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (letterParenMatch) {
          const [, letter, contentText] = letterParenMatch;
          const wrappedContent = wrapText(contentText, 55);
          content = (
            <div className="flex ml-8">
              <span className="font-semibold min-w-[1rem]">{letter})</span>
              <div className="ml-2">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (doubleNumberedParenMatch) {
          const [, number, contentText] = doubleNumberedParenMatch;
          const wrappedContent = wrapText(contentText, 50);
          content = (
            <div className="flex ml-10">
              <span className="font-semibold min-w-[2rem]">{number}))</span>
              <div className="ml-2">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (tripleNumberedParenMatch) {
          const [, number, contentText] = tripleNumberedParenMatch;
          const wrappedContent = wrapText(contentText, 45);
          content = (
            <div className="flex ml-12">
              <span className="font-semibold min-w-[2.5rem]">{number})))</span>
              <div className="ml-2">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div key={idx}>
                    {wrappedLine}
                    {idx < wrappedContent.length - 1 && <br />}
                  </div>
                ))}
              </div>
            </div>
          );
        } else if (indentLevel > 0) {
          // Text dengan indentasi
          const wrappedContent = wrapText(trimmedLine, 75 - indentLevel * 10);
          content = (
            <div className={`ml-${indentLevel * 4}`}>
              {wrappedContent.map((wrappedLine, idx) => (
                <div key={idx}>
                  {wrappedLine}
                  {idx < wrappedContent.length - 1 && <br />}
                </div>
              ))}
            </div>
          );
        } else {
          // Text biasa
          const wrappedContent = wrapText(trimmedLine, 75);
          content = (
            <div>
              {wrappedContent.map((wrappedLine, idx) => (
                <div key={idx}>
                  {wrappedLine}
                  {idx < wrappedContent.length - 1 && <br />}
                </div>
              ))}
            </div>
          );
        }

        return (
          <div key={lineIndex} className="leading-relaxed">
            {content}
          </div>
        );
      })}
    </div>
  );
}

// --- TAMBAH KOMPONEN PDF BUTTONS ---
function PdfButtons({ pdfInfo, isFromDocument, isTyping = false }) {
  // PERUBAHAN: isFromDocument sekarang dari backend yang sudah filtered
  const shouldShow =
    isFromDocument === true &&
    pdfInfo &&
    typeof pdfInfo === "object" &&
    pdfInfo.filename &&
    !isTyping;

  if (!shouldShow) {
    return null;
  }

  const API_BASE = "http://192.168.11.80:5000";

  const handleView = () => {
    if (pdfInfo.url) {
      const previewUrl = `${API_BASE}${pdfInfo.url}`;
      window.open(previewUrl, "_blank", "noopener,noreferrer");
    }
  };

  const handleDownload = () => {
    if (pdfInfo.download_url) {
      const downloadUrl = `${API_BASE}${pdfInfo.download_url}`;
      window.open(downloadUrl, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200 animate-fadeIn">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M14 2H6C4.9 2 4.01 2.9 4.01 4L4 20C4 21.1 4.89 22 5.99 22H18C19.1 22 20 21.1 20 20V8L14 2ZM16 18H8V16H16V18ZM16 14H8V12H16V14ZM13 9V3.5L18.5 9H13Z"
                fill="#1D4ED8"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              Referensi: {pdfInfo.title || pdfInfo.filename}
            </p>
            <div className="text-xs text-gray-600 mt-1">
              {pdfInfo.nomor && <span>No: {pdfInfo.nomor} • </span>}
              {pdfInfo.tanggal && <span>Tanggal: {pdfInfo.tanggal}</span>}
            </div>
            <p className="text-xs text-gray-500 mt-1">{pdfInfo.filename}</p>
          </div>
        </div>
      </div>
      <div className="flex justify-end mt-2">
        <div className="flex flex-col sm:flex-row gap-2">
          {pdfInfo.url && (
            <button
              onClick={handleView}
              className="flex items-center justify-center px-2 py-0.5 text-xs bg-white text-blue-600 border border-blue-300 rounded-full hover:bg-blue-50 transition-colors"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="mr-1"
              >
                <path
                  d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"
                  fill="currentColor"
                />
              </svg>
              Lihat
            </button>
          )}

          {pdfInfo.download_url && (
            <button
              onClick={handleDownload}
              className="flex items-center justify-center px-2 py-0.5 text-xs bg-blue-600 text-white rounded-full hover:bg-blue-700 transition-colors"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="mr-1"
              >
                <path
                  d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"
                  fill="currentColor"
                />
              </svg>
              Download
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [tempFileId, setTempFileId] = useState(null);
  const [currentMode, setCurrentMode] = useState("normal"); // normal, document, search
  const [showDocumentList, setShowDocumentList] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const API_BASE = "http://192.168.11.80:5000";

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check backend on load
  useEffect(() => {
    checkBackend();
    loadDocuments();
  }, []);

  const checkBackend = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setBackendStatus(res.ok ? "connected" : "error");
    } catch {
      setBackendStatus("disconnected");
    }
  };

  const loadDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents);
      }
    } catch (err) {
      console.error("Error loading documents:", err);
    }
  };

  // Helper function untuk membersihkan markdown
  const cleanMarkdown = (text) => {
    if (!text) return text;

    return (
      text
        // Hapus basic markdown
        .replace(/\*\*(.*?)\*\*/g, "$1")
        .replace(/__(.*?)__/g, "$1")
        .replace(/^#{1,6}\s+/gm, "")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        // Rapikan spasi
        .replace(/\n{3,}/g, "\n\n")
        .trim()
    );
  };

  // Helper function untuk animasi ketik
  const typeText = async (text, callback, speed = 15) => {
    // Jangan format di sini - biarkan AI yang format
    const cleanText = cleanMarkdown(text); // Hanya basic cleaning
    let i = 0;
    return new Promise((resolve) => {
      const timer = setInterval(() => {
        if (i < cleanText.length) {
          callback(cleanText.slice(0, i + 1));
          i++;
        } else {
          clearInterval(timer);
          resolve();
        }
      }, speed);
    });
  };

  // Handle file preview
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
        setMessages((prev) => [
          ...prev,
          {
            sender: "system",
            text: `❌ Preview failed: ${data.error}`,
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
          text: `❌ Preview error: ${err.message}`,
          isSystem: true,
          isError: true,
        },
      ]);
    }
  };

  // Confirm upload after preview
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
        // Add to uploaded files
        setUploadedFiles((prev) => [
          ...prev,
          {
            id: data.file_id,
            name: data.filename,
            type: data.file_type,
          },
        ]);

        // Add system message
        setMessages((prev) => [
          ...prev,
          {
            sender: "system",
            text: `✅ File "${data.filename}" uploaded successfully!\n\nYou can now ask questions about this file.`,
            isSystem: true,
          },
        ]);

        setShowPreview(false);
        setPreviewFile(null);
        setTempFileId(null);
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

  // Cancel upload
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

  // Switch mode dengan toggle logic - HAPUS pemanggilan API yang tidak perlu
  const switchMode = async (mode) => {
    // Jika mode yang diklik sedang aktif, kembalikan ke normal
    const nextMode = currentMode === mode ? "normal" : mode;
    setCurrentMode(nextMode);

    // HAPUS SEMUA pemanggilan API ini - tidak diperlukan
    // Hanya ganti state, jangan panggil API

    // Tambahkan pesan sistem untuk memberi tahu mode yang aktif
    if (nextMode !== "normal") {
      setMessages((prev) => [...prev]);
    }
  };

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
      let aiResponse = "";
      let pdfInfo = null; // Inisialisasi pdfInfo
      let isFromDocument = false; // Inisialisasi isFromDocument

      // --- HAPUS SEMUA LOGIKA PENGIRIMAN LANGSUNG KE API DI SINI ---
      // Kita hanya kirim satu kali ke /api/chat, dan biarkan backend yang handle modenya

      const payload = {
        message: userMessage,
        mode: currentMode, // Kirim mode yang sedang aktif
      };

      // Cek apakah ada file aktif untuk mode normal atau document (jika tidak ada file di upload, mungkin tidak perlu file_id)
      // Misalnya, hanya kirim file_id jika mode document dan ada uploaded file
      if (currentMode === "document" && uploadedFiles.length > 0) {
        payload.file_id = uploadedFiles[uploadedFiles.length - 1].id;
      }

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      aiResponse = data.reply || "No response from AI.";
      pdfInfo = data.pdf_info || null;
      isFromDocument = data.is_from_document || false; // Ambil is_from_document dari respons API

      // Tambahkan placeholder untuk animasi ketik
      const tempMessageId = Date.now();
      setMessages((prev) => [
        ...prev,
        {
          id: tempMessageId,
          sender: "ai",
          text: "",
          // --- HAPUS isFromDocument ---
          pdfInfo: pdfInfo,
          isFromDocument: isFromDocument, // <-- HAPUS BARIS INI
          // --- HAPUS SELESAI ---
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          isTyping: true,
        },
      ]);

      // Animasi ketik
      await typeText(aiResponse, (partialText) => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempMessageId
              ? { ...msg, text: partialText, isTyping: true }
              : msg
          )
        );
      });

      // Selesai mengetik
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempMessageId ? { ...msg, isTyping: false } : msg
        )
      );
    } catch (err) {
      // Di dalam catch block:
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: `Sorry, I encountered an error: ${err.message}`,
          // --- HAPUS isFromDocument ---
          pdfInfo: null,
          isFromDocument: false, // <-- HAPUS BARIS INI
          // --- HAPUS SELESAI ---
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
          File will be previewed before upload
        </p>
      </div>
    </div>
  );

  // File preview panel component
  const FilePreviewPanel = () => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">File Preview</h3>
          <button
            onClick={cancelUpload}
            className="p-1 hover:bg-gray-100 rounded-lg"
          >
            ✕
          </button>
        </div>

        {previewFile && (
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">📄</span>
                <div>
                  <p className="font-medium">{previewFile.name}</p>
                  <p className="text-sm text-gray-500">
                    {previewFile.type} • {(previewFile.size / 1024).toFixed(1)}{" "}
                    KB
                  </p>
                </div>
              </div>
            </div>

            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Preview Content:</h4>
              <div className="bg-gray-50 p-3 rounded text-sm max-h-40 overflow-y-auto">
                {previewFile.previewText || "No preview available"}
              </div>
            </div>

            <div className="flex space-x-3 pt-4">
              <button
                onClick={cancelUpload}
                className="flex-1 py-2 px-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmUpload}
                className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Confirm Upload
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // Document list panel component
  const DocumentListPanel = () => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-xl max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Documents</h3>
          <button
            onClick={() => setShowDocumentList(false)}
            className="p-1 hover:bg-gray-100 rounded-lg"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3">
          {documents.length > 0 ? (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="p-4 border rounded-lg hover:bg-gray-50"
              >
                <div className="font-medium">
                  {doc.judul || "Untitled Document"}
                </div>
                <div className="text-sm text-gray-600">
                  {doc.nomor && `No: ${doc.nomor} • `}
                  {doc.tanggal && `Date: ${doc.tanggal} • `}
                  Status: {doc.status}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  File: {doc.filename} • Uploaded:{" "}
                  {new Date(doc.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-gray-500">
              No documents available
            </div>
          )}
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={() => setShowDocumentList(false)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFilePreview}
        accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
        className="hidden"
      />

      {/* File upload modal */}
      {showFileUpload && <FileUploadPanel />}

      {/* File preview modal */}
      {showPreview && <FilePreviewPanel />}

      {/* Document list modal */}
      {showDocumentList && <DocumentListPanel />}

      {/* Header - HANYA LOGO DAN STATUS */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <img
              src="./src/assets/cakra.png"
              alt="CAKRA AI Logo"
              className="w-10 h-10 rounded-full object-cover"
            />
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
                  • Qwen3 8B
                </span>
              </div>
            </div>
          </div>

          {/* Hanya tombol Documents di kanan */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowDocumentList(true)}
              className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              title="Documents"
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
                  d="M21 12a9 9 0 00-9-9H9M9 3v2m3 14v-2m3 2v-2M3 18v-2m6-2a6 6 0 016-6H9M9 12h6"
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
                Saya bisa membantu menjawab pertanyaan anda, memberikan
                informasi terkait rekrutmen, peraturan perusahaan, dan lain
                lain. Kamu juga bisa mengupload file untuk dianalisa.
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
              {messages.map((msg, idx) =>
                msg.sender === "system" ? (
                  <div key={idx} className="message-container system">
                    <div className="message-bubble system">
                      <div className="flex items-center">
                        <span className="mr-2">📁</span>
                        <FormattedMessage text={msg.text} />
                      </div>
                      {msg.timestamp && (
                        <div className="message-timestamp">{msg.timestamp}</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div
                    key={idx}
                    className={`message-container ${
                      msg.sender === "user" ? "user" : "ai"
                    }`}
                  >
                    <div
                      className={`message-bubble ${
                        msg.sender === "user" ? "user" : "ai"
                      }`}
                    >
                      {msg.sender === "ai" ? (
                        <>
                          <FormattedMessage text={msg.text} />

                          {/* PERUBAHAN: Gunakan props yang lebih strict */}
                          <PdfButtons
                            pdfInfo={msg.pdfInfo}
                            isFromDocument={msg.isFromDocument}
                            isTyping={msg.isTyping}
                          />
                        </>
                      ) : (
                        <div className="whitespace-pre-wrap break-words">
                          {msg.text}
                        </div>
                      )}
                      {msg.timestamp && (
                        <div className="message-timestamp">{msg.timestamp}</div>
                      )}
                    </div>
                  </div>
                )
              )}

              {isLoading && (
                <div className="message-container ai">
                  <div className="loading-dots">
                    <div className="loading-dot"></div>
                    <div className="loading-dot"></div>
                    <div className="loading-dot"></div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white px-4 py-4 sticky bottom-0">
        <div className="max-w-3xl mx-auto">
          {/* Di bagian header, setelah status connection */}
          <div className="flex items-center space-x-2 mb-2">
            {currentMode !== "normal" && (
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
            )}
          </div>
          <div className="relative">
            <div className="bg-gray-50 rounded-2xl p-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                disabled={isLoading}
                placeholder={
                  currentMode === "document"
                    ? "Tanya apapun terkait dokumen PT Pindad..."
                    : currentMode === "search"
                    ? "Cari informasi dari Web resmi PT Pindad..."
                    : uploadedFiles.length > 0
                    ? `Ask about "${
                        uploadedFiles[uploadedFiles.length - 1].name
                      }"...`
                    : "Tanya CAKRA AI..."
                }
                className="w-full border-none bg-transparent resize-none focus:outline-none text-gray-900"
                rows="1"
                style={{ minHeight: "52px", maxHeight: "120px" }}
                onInput={(e) => {
                  e.target.style.height = "auto";
                  e.target.style.height =
                    Math.min(e.target.scrollHeight, 120) + "px";
                }}
              />
            </div>

            <div className="flex items-center justify-between mt-2">
              <div className="flex space-x-2">
                <button
                  onClick={() => switchMode("document")}
                  className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                    currentMode === "document"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 hover:bg-gray-200 text-gray-800"
                  }`}
                >
                  <span className="text-xs">📄</span> Document
                </button>
                <button
                  onClick={() => switchMode("search")}
                  className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
                    currentMode === "search"
                      ? "bg-purple-600 text-white"
                      : "bg-gray-100 hover:bg-gray-200 text-gray-800"
                  }`}
                >
                  <span className="text-xs">🌐</span> Search
                </button>
              </div>

              <div className="flex space-x-2">
                <button
                  onClick={() => setShowFileUpload(true)}
                  className="p-2 text-gray-600 hover:text-blue-600 transition-colors"
                  title="Upload file"
                >
                  <span className="text-xl">📁</span>
                </button>
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !input.trim()}
                  className={`p-2 rounded-lg transition-colors ${
                    isLoading || !input.trim()
                      ? "bg-gray-200 text-gray-400"
                      : "bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:opacity-90"
                  }`}
                >
                  {isLoading ? (
                    <svg
                      className="w-5 h-5 animate-spin"
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
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                      ></path>
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
