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
                  <div className="flex justify-start items-center py-2 px-2">
                    <div className="flex items-center px-4 py-2">
                      <img
                        src={cakraLogo}
                        className="w-6 h-6 object-cover rounded-full animate-spin mr-3"
                        style={{ animationDuration: "2s" }}
                        alt="loading"
                      />
                      <span className="text-xs text-gray-500 dark:text-gray-400 font-medium animate-pulse">
                        CAKRA lagi mikir nih...
                      </span>
                    </div>
                  </div>
                )}

              <div className="h-10 w-full" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- SUB-KOMPONEN USER MESSAGE (SUDAH DIPERBAIKI JARAKNYA) ---
function UserMessage({
  msg,
  expandedMessages,
  toggleExpand,
  handleCopy,
  showNotification,
}) {
  const isLongText = msg.text?.length > 100;

  return (
    <div className="flex flex-col items-end mt-5 group w-full mb-5">
      {/* 1. Bubble Attachments */}
      {msg.attachments && msg.attachments.length > 0 && (
        // TAMBAHKAN mb-3 DI SINI UNTUK JARAK KE TEKS DI BAWAHNYA
        <div className="flex flex-col items-end gap-2 max-w-[85%] mb-3">
          {msg.attachments.map((file, i) => (
            <div
              key={i}
              onClick={() => window.open(file.url, "_blank")}
              className="cursor-pointer bg-blue-600 dark:bg-[#2A2A2E] p-2 rounded-2xl border border-white/10 shadow-sm hover:brightness-110 transition-all"
            >
              {file.type?.startsWith("image/") || file.type === "image" ? (
                <div className="relative rounded-xl overflow-hidden">
                  <img
                    src={file.url}
                    className="max-w-[200px] max-h-[200px] object-cover"
                    alt="img"
                  />
                  {file.size && (
                    <span className="absolute bottom-1 right-1 bg-black/50 px-1.5 py-0.5 rounded text-[8px] text-white">
                      {formatFileSize(file.size)}
                    </span>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-3 px-2 py-1 min-w-[160px]">
                  <div className="bg-red-500 p-2 rounded-lg text-white text-xs">
                    📄
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[10px] text-white font-medium truncate max-w-[120px]">
                      {file.name}
                    </span>
                    <span className="text-[8px] text-blue-100/70 uppercase">
                      {formatFileSize(file.size)} •{" "}
                      {file.type?.split("/")[1] || "FILE"}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* --- 2. BUBBLE CHAT TEKS --- */}
      {msg.text && (
        <div className="flex flex-col items-end max-w-full">
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
            {/* ... sisa kode TOMBOL EXPAND dan ISI TEKS tetap sama ... */}
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

          {/* --- 3. TOMBOL COPY --- */}
          <div className="mt-1 mr-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleCopy(msg.text, showNotification);
              }}
              className="p-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 hover:text-blue-500 transition-all shadow-sm border border-gray-200 dark:border-gray-700"
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
      )}
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

          {/* DOT HIJAU PINDAH KE ATAS KIRI */}
          {msg.isTyping && (
            <span className="absolute -top-0.5 -left-0.5 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500 border border-white dark:border-[#232326]"></span>
            </span>
          )}
        </div>
        <span className="text-[10px] text-gray-500 dark:text-gray-400 font-bold uppercase tracking-[0.2em]">
          Cakra AI
        </span>
      </div>

      <div className="pl-9">
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
