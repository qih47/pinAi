import React from "react";
import MessageRenderer from "../MessageRenderer";
import PdfButtons from "../PdfButtons";
import GuestWelcome from "../ui/GuestWelcome";

// Fungsi Helper Ukuran File
const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
};

export default function MessageList({
  messagesContainerRef,
  messages,
  isLoading,
  expandedMessages,
  toggleExpand,
  handleCopy,
  showNotification,
  cakraLogo,
  isLoggedIn,
  userData,
  getGreeting,
  setInput,
}) {
  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-white dark:bg-[#232326] transition-colors duration-300">
      {/* AREA SCROLLABLE */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto px-4 custom-scrollbar py-6"
        style={{ overflowAnchor: "none", scrollBehavior: "auto" }}
      >
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <GuestWelcome
              isLoggedIn={isLoggedIn}
              userData={userData}
              getGreeting={getGreeting}
              setInput={setInput}
            />
          ) : (
            <div className="space-y-6">
              {messages.map((msg, index) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  } w-full`}
                >
                  {msg.sender === "user" ? (
                    <UserMessage
                      msg={msg}
                      expandedMessages={expandedMessages}
                      toggleExpand={toggleExpand}
                      handleCopy={handleCopy}
                      showNotification={showNotification}
                    />
                  ) : (
                    /* HANYA TAMPILKAN AI MESSAGE JIKA SUDAH ADA TEKS ATAU SEDANG TYPING */
                    /* Kita proteksi di sini supaya bubble kosong nggak muncul pas awal banget */
                    (msg.text || msg.isTyping) && (
                      <AiMessage
                        msg={msg}
                        isLoading={isLoading}
                        cakraLogo={cakraLogo}
                        handleCopy={handleCopy}
                        showNotification={showNotification}
                      />
                    )
                  )}
                </div>
              ))}

              {/* LOADER AI: Hanya muncul jika AI bener-bener lagi fetch (sebelum typing dimulai) */}
              {isLoading &&
                !messages.some((m) => m.sender === "ai" && m.isTyping) && (
                  <div className="flex justify-start items-center py-4 px-1 ml-1">
                    <div className="flex items-center">
                      <img
                        src={cakraLogo}
                        className="w-7 h-7 object-cover rounded-full animate-spin mr-3 opacity-80"
                        style={{ animationDuration: "2s" }}
                        alt="loading"
                      />
                      <span className="text-[13px] text-gray-400 dark:text-gray-500 font-medium animate-pulse tracking-wide">
                        CAKRA lagi mikir...
                      </span>
                    </div>
                  </div>
                )}

              {/* Spacer bawah */}
              <div className="h-10 w-full" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- SUB-KOMPONEN USER MESSAGE (BUBBLE TERPISAH) ---
function UserMessage({
  msg,
  expandedMessages,
  toggleExpand,
  handleCopy,
  showNotification,
}) {
  const isLongText = msg.text?.length > 100;

  return (
    <div className="flex flex-col items-end mt-5 group w-full">
      {/* --- BUBBLE CHAT --- */}
      <div
        onClick={() => toggleExpand(msg.id)}
        className={`
          relative cursor-pointer
          bg-blue-600 dark:bg-[#2A2A2E]
          text-gray-100
          rounded-3xl
          px-4 py-3
          shadow-sm
          transition-all duration-300 ease-in-out
          overflow-hidden
          ${expandedMessages[msg.id] ? "max-w-[90%]" : "max-w-[300px]"}
        `}
      >
        {/* --- ATTACHMENTS (Di dalam bubble) --- */}
        {msg.attachments && msg.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {msg.attachments.map((file, i) => (
              <div key={i} className="relative group/file">
                {file.type?.startsWith("image/") || file.type === "image" ? (
                  <div className="relative rounded-xl overflow-hidden border border-white/10">
                    <img
                      src={file.url}
                      className="max-w-[150px] max-h-[150px] object-cover"
                      alt="img"
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2 bg-blue-700/50 dark:bg-gray-700/50 p-2 rounded-xl">
                    <span className="text-xs">📄</span>
                    <span className="text-[10px] truncate max-w-[100px]">
                      {file.name}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* --- TOMBOL EXPAND (Arrow pojok kanan atas) --- */}
        {isLongText && (
          <div className="absolute top-2 right-2 text-gray-100 dark:text-gray-300 text-xs cursor-pointer group/expand">
            <div className="p-1 transition-all duration-150 group-hover/expand:bg-blue-500 dark:group-hover/expand:bg-gray-500 rounded-full">
              {expandedMessages[msg.id] ? (
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path
                    d="M6 12l4-4 4 4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path
                    d="M6 8l4 4 4-4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
          </div>
        )}

        {/* --- TEXT CONTENT --- */}
        <div
          className={`text-sm leading-relaxed ${isLongText ? "pr-6" : ""} ${
            expandedMessages[msg.id] ? "" : "line-clamp-3"
          }`}
        >
          <MessageRenderer
            text={msg.text}
            showNotification={showNotification}
            isTyping={msg.isTyping}
            isAI={false}
          />
        </div>
      </div>

      {/* --- TOMBOL COPY (Di bawah bubble) --- */}
      <div className="mt-1 mr-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleCopy(msg.text, showNotification);
          }}
          className="p-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 hover:text-blue-500 transition-all shadow-sm border border-gray-200 dark:border-gray-700"
          title="Copy text"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
        </button>
      </div>
    </div>
  );
}

// --- SUB-KOMPONEN AI MESSAGE ---
function AiMessage({
  msg,
  isLoading,
  cakraLogo,
  handleCopy,
  showNotification,
}) {
  return (
    <div className="max-w-[95%] md:max-w-[90%] group">
      <div className="flex items-center gap-2 mb-2">
        <div className="relative">
          <img
            src={cakraLogo}
            className={`w-7 h-7 rounded-full object-cover border border-gray-100 dark:border-gray-800 ${
              msg.isTyping ? "animate-spin" : ""
            }`}
            style={{ animationDuration: "3s" }}
            alt="logo"
          />
          {msg.isTyping && (
            <span className="absolute -bottom-0.5 -right-0.5 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
            </span>
          )}
        </div>
        <span className="text-[10px] text-gray-500 dark:text-gray-400 font-bold uppercase tracking-[0.2em]">
          Cakra AI
        </span>
      </div>

      <div className="pl-9">
        {" "}
        {/* Padding agar sejajar dengan logo */}
        <MessageRenderer text={msg.text} isAI={true} isTyping={msg.isTyping} />
        <PdfButtons
          pdfInfo={msg.pdfInfo}
          isFromDocument={msg.isFromDocument}
          isTyping={msg.isTyping}
        />
        {!msg.isTyping && (
          <button
            onClick={() => handleCopy(msg.text, showNotification)}
            className="mt-3 opacity-0 group-hover:opacity-100 p-1.5 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-gray-400 hover:text-blue-500 border border-gray-200 dark:border-gray-700 transition-all"
          >
            <svg
              width="12"
              height="12"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              viewBox="0 0 24 24"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
