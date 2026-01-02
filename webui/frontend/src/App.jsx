import React, { useState, useEffect, useRef, useCallback } from "react";

// Function untuk copy to clipboard
const copyToClipboard = async (text, showNotification) => {
  try {
    await navigator.clipboard.writeText(text);
    if (showNotification) {
      showNotification("Code copied to clipboard!", "success");
    }
  } catch (err) {
    console.error("Failed to copy text: ", err);
    if (showNotification) {
      showNotification("Failed to copy code", "error");
    }
  }
};

// Function untuk memisahkan code blocks dari teks biasa
const extractCodeBlocks = (text) => {
  if (!text || typeof text !== "string")
    return { textOnly: text, codeBlocks: [] };

  const parts = text.split(/(```[\s\S]*?```)/g);
  const codeBlocks = [];
  const textParts = [];

  parts.forEach((part, index) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const lines = part.split("\n");
      const langMatch = lines[0].match(/```(\w+)/);
      const language = langMatch ? langMatch[1] : "text";
      const codeContent = lines.slice(1, lines.length - 1).join("\n");

      codeBlocks.push({
        index,
        language,
        content: codeContent,
        fullText: part,
      });
    } else if (part.trim()) {
      textParts.push(part);
    }
  });

  return {
    textOnly: textParts.join(""),
    codeBlocks,
    hasCodeBlocks: codeBlocks.length > 0,
  };
};

// Function untuk render teks dengan styling Markdown
const renderStyledText = (text) => {
  if (!text || typeof text !== "string") return text;

  let processedText = text;

  processedText = processedText.replace(
    /\*\*(.*?)\*\*/g,
    "<strong>$1</strong>"
  );
  processedText = processedText.replace(/__(.*?)__/g, "<strong>$1</strong>");
  processedText = processedText.replace(/\*(.*?)\*/g, "<em>$1</em>");
  processedText = processedText.replace(/_(.*?)_/g, "<em>$1</em>");
  processedText = processedText.replace(/~~(.*?)~~/g, "<del>$1</del>");
  processedText = processedText.replace(
    /`([^`]+)`/g,
    '<code class="inline-code">$1</code>'
  );
  processedText = processedText.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 hover:underline">$1</a>'
  );

  return processedText;
};

// Komponen untuk Code Block
const CodeBlockComponent = ({
  language,
  content,
  showNotification,
  isAnimatingBlock,
}) => {
  return (
    <div className="code-block-container my-3">
      <div className="code-header flex justify-between items-center bg-gray-800 text-gray-200 px-3 py-2 rounded-t-lg text-sm">
        <span className="font-medium capitalize">{language || "code"}</span>
        <button
          onClick={() => copyToClipboard(content, showNotification)}
          className="copy-button text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded transition-colors flex items-center gap-1"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-3 w-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          Copy
        </button>
      </div>
      <pre className="hljs bg-gray-900 text-gray-100 p-4 rounded-b-lg overflow-x-auto text-sm">
        <code className={`language-${language}`}>
          {content}
          {isAnimatingBlock && <span className="typing-cursor"></span>}
        </code>
      </pre>
    </div>
  );
};

// Komponen untuk menampilkan teks dengan format list dan styling
function FormattedMessage({ text, showNotification }) {
  if (!text || typeof text !== "string") return null;

  let cleanText = text;
  if (typeof text !== "string") {
    cleanText = String(text);
  }

  cleanText = cleanText
    .replace(/&nbsp;/g, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?div[^>]*>/gi, "\n")
    .replace(/<\/?[^>]+(>|$)/g, "")
    .replace(/^[-_]{3,}\s*$/gm, "")
    .replace(/^\s*[-_]{2,}\s*/gm, "")
    .trim();

  const styledText = renderStyledText(cleanText);
  const lines = styledText.split("\n").filter((line) => line.trim() !== "");

  return (
    <div className="space-y-2">
      {lines.map((line, lineIndex) => {
        const trimmedLine = line.trim();

        const numberMatch = trimmedLine.match(/^(\d+)\.\s+(.+)/);
        const letterMatch = trimmedLine.match(/^([a-z])\.\s+(.+)/i);
        const bulletMatch = trimmedLine.match(/^[-*•]\s+(.+)/);

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

        let content;

        if (numberMatch) {
          const [, number, contentText] = numberMatch;
          const wrappedContent = wrapText(contentText, 65);
          content = (
            <div className="flex">
              <span className="font-semibold min-w-[0.8rem]">{number}.</span>
              <div className="ml-2">
                {wrappedContent.map((wrappedLine, idx) => (
                  <div
                    key={idx}
                    dangerouslySetInnerHTML={{ __html: wrappedLine }}
                  />
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
                  <div
                    key={idx}
                    dangerouslySetInnerHTML={{ __html: wrappedLine }}
                  />
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
                  <div
                    key={idx}
                    dangerouslySetInnerHTML={{ __html: wrappedLine }}
                  />
                ))}
              </div>
            </div>
          );
        } else {
          const wrappedContent = wrapText(trimmedLine, 75);
          content = (
            <div>
              {wrappedContent.map((wrappedLine, idx) => (
                <div
                  key={idx}
                  dangerouslySetInnerHTML={{ __html: wrappedLine }}
                />
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

// Main component untuk render message dengan typing animation
const MessageRenderer = ({ text, showNotification, isTyping = false }) => {
  const [displayText, setDisplayText] = useState("");
  const [isAnimating, setIsAnimating] = useState(false);

  // 1. Ekstrak struktur blok dari teks ASLI (full text)
  const { codeBlocks: originalBlocks } = extractCodeBlocks(text || "");

  useEffect(() => {
    if (!text) return;
    if (isTyping) {
      setIsAnimating(true);
      let i = 0;
      const typingSpeed = 15;
      const typeTimer = setInterval(() => {
        if (i < text.length) {
          setDisplayText(text.slice(0, i + 1));
          i++;
        } else {
          clearInterval(typeTimer);
          setIsAnimating(false);
        }
      }, typingSpeed);
      return () => clearInterval(typeTimer);
    } else {
      setDisplayText(text);
    }
  }, [text, isTyping]);

  // 2. Fungsi pembantu untuk menentukan apa yang tampil
  const renderContent = () => {
    // Jika tidak ada code blocks, render biasa
    if (originalBlocks.length === 0) {
      return (
        <>
          <FormattedMessage
            text={displayText}
            showNotification={showNotification}
          />
          {isAnimating && <span className="typing-cursor"></span>}
        </>
      );
    }

    // Logic untuk membagi tampilan antara teks biasa dan code block yang sedang "diketik"
    const parts = text.split(/(```[\s\S]*?```)/g);
    let currentPos = 0;

    return parts.map((part, index) => {
      const partStart = currentPos;
      const partEnd = currentPos + part.length;
      currentPos = partEnd;

      // Jika progres pengetikan (displayText) belum sampai ke part ini, jangan tampilkan
      if (displayText.length <= partStart) return null;

      // Ambil bagian dari part ini yang sudah "terketik"
      const visiblePart = text.slice(
        partStart,
        Math.min(partEnd, displayText.length)
      );

      if (part.startsWith("```")) {
        // Ini adalah area Code Block
        const lines = visiblePart.split("\n");
        const langMatch = lines[0].match(/```(\w+)/);
        const language = langMatch ? langMatch[1] : "code";

        // Bersihkan konten dari tag ``` dan bahasa
        let content = lines.slice(1).join("\n").replace(/```$/, "");

        const isCurrentlyTypingThisBlock =
          displayText.length > partStart && displayText.length < partEnd;

        return (
          <CodeBlockComponent
            key={index}
            language={language}
            content={content}
            showNotification={showNotification}
            isAnimatingBlock={isCurrentlyTypingThisBlock}
          />
        );
      } else {
        // Ini teks biasa
        return (
          <FormattedMessage
            key={index}
            text={visiblePart}
            showNotification={showNotification}
          />
        );
      }
    });
  };

  return (
    <div className="space-y-3 message-renderer">
      {/* CSS Styles tetap sama */}
      <style>{` ... `}</style>
      {renderContent()}
    </div>
  );
};

// PDF Buttons Component
function PdfButtons({ pdfInfo, isFromDocument, isTyping = false }) {
  const shouldShow =
    isFromDocument === true &&
    pdfInfo &&
    typeof pdfInfo === "object" &&
    pdfInfo.filename &&
    !isTyping;

  if (!shouldShow) return null;

  const API_BASE = "http://192.168.11.80:5000";

  const handleView = () => {
    if (pdfInfo.url) {
      window.open(`${API_BASE}${pdfInfo.url}`, "_blank", "noopener,noreferrer");
    }
  };

  const handleDownload = () => {
    if (pdfInfo.download_url) {
      window.open(
        `${API_BASE}${pdfInfo.download_url}`,
        "_blank",
        "noopener,noreferrer"
      );
    }
  };

  return (
    <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
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
      <div className="flex justify-end mt-2 gap-2">
        {pdfInfo.url && (
          <button
            onClick={handleView}
            className="px-2 py-0.5 text-xs bg-white text-blue-600 border border-blue-300 rounded-full hover:bg-blue-50"
          >
            Lihat
          </button>
        )}
        {pdfInfo.download_url && (
          <button
            onClick={handleDownload}
            className="px-2 py-0.5 text-xs bg-blue-600 text-white rounded-full hover:bg-blue-700"
          >
            Download
          </button>
        )}
      </div>
    </div>
  );
}

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

  const API_BASE = "http://192.168.11.80:5000";

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check backend
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
          {
            id: data.file_id,
            name: data.filename,
            type: data.file_type,
          },
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
      const payload = {
        message: userMessage,
        mode: currentMode,
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
      const aiResponse = data.reply || "No response from AI.";
      const pdfInfo = data.pdf_info || null;
      const isFromDocument = data.is_from_document || false;

      // Set response dengan isTyping true untuk trigger animasi
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? {
                ...msg,
                text: aiResponse,
                pdfInfo: pdfInfo,
                isFromDocument: isFromDocument,
                isTyping: true,
              }
            : msg
        )
      );

      // Matikan isTyping setelah animasi selesai
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

      {/* Header */}
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
                    : backendStatus === "disconnected"
                    ? "Disconnected"
                    : "Checking..."}{" "}
                  • Qwen3 8B
                </span>
              </div>
            </div>
          </div>

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
                  d="M19 21H5a2 2 0 01-2-2V7a2 2 0 012-2h4l2-2h6a2 2 0 012 2v14a2 2 0 01-2 2zM5 7v12h14V7H5zm4 2h6v2H9V9z"
                />
              </svg>
            </button>
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
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto px-4 py-6"
      >
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
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                     className={`${
                      msg.sender === "user"
                        ? "bg-blue-600 text-white rounded-xl px-4 py-1 max-w-xs sm:max-w-sm md:max-w-md ml-auto"
                        : "max-w-3xl"
                    }`}
                  >
                      <MessageRenderer
                        text={msg.text}
                        showNotification={showNotification}
                        isTyping={msg.isTyping}
                      />
                      {msg.sender === "ai" && (
                        <PdfButtons
                          pdfInfo={msg.pdfInfo}
                          isFromDocument={msg.isFromDocument}
                          isTyping={msg.isTyping}
                        />
                      )}
                      {(
                        <div
                          className={`text-xs mt-2 ${
                            msg.sender === "user"
                              ? "text-blue-200"
                              : "text-gray-500"
                          }`}
                        >
                        </div>
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

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white px-4 py-4 sticky bottom-0">
        <div className="max-w-3xl mx-auto">
          {/* Mode indicator */}
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
            <div className="bg-gray-100 rounded-2xl p-3">
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
              <div className="flex items-center justify-between mt-2">
                <div className="flex space-x-2">
                  <button
                    onClick={() => switchMode("document")}
                    className={`px-3 py-1 text-sm rounded-full transition-colors ${
                      currentMode === "document"
                        ? "bg-blue-600 text-white"
                        : "bg-gray-200 hover:bg-gray-400 text-gray-800"
                    }`}
                  >
                    <span className="text-xs">📄</span> Document
                  </button>
                  <button
                    onClick={() => switchMode("search")}
                    className={`px-3 py-1 text-sm rounded-full transition-colors ${
                      currentMode === "search"
                        ? "bg-purple-600 text-white"
                        : "bg-gray-200 hover:bg-gray-400 text-gray-800"
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
                    className={`px-4 py-1 rounded-xl font-medium transition-colors ${
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
  );
}

export default App;
