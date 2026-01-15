import React from "react";

export default function InputArea({
  currentMode,
  input,
  setInput,
  previews,
  setPreviews,
  selectedFiles,
  setSelectedFiles,
  isDragging,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  fileInputRef,
  handleFileChange,
  sendMessage,
  handleKeyPress,
  handlePaste,
  isLoading,
  isLoggedIn,
  switchMode,
}) {
  return (
    <div className="bg-white dark:bg-[#232326] px-4 pb-6 pt-2 transition-colors duration-300">
      <div className="max-w-3xl mx-auto relative">
        {/* Mode Indicator Overlay */}
        {currentMode !== "normal" && isLoggedIn && (
          <div className="absolute -top-8 left-2 animate-in slide-in-from-bottom-2 duration-300">
            <span
              className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-t-lg ${
                currentMode === "document"
                  ? "bg-blue-600 text-white"
                  : "bg-purple-600 text-white"
              }`}
            >
              {currentMode === "document"
                ? "📄 Document Mode"
                : "🌐 Search Mode"}
            </span>
          </div>
        )}

        {/* Container Utama Input - SEKARANG BISA DIKLIK GUEST */}
        <div
          className={`relative rounded-3xl transition-all duration-300 border ${
            isDragging
              ? "border-blue-500 ring-4 ring-blue-500/10 bg-blue-50/50 dark:bg-blue-900/10"
              : "border-gray-200 dark:border-gray-700 bg-[#F7F8FC] dark:bg-[#2E2E33]"
          } ${!isLoggedIn ? "opacity-100" : ""}`} // Hapus pointer-events-none
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Drop Overlay Hint */}
          {isDragging && (
            <div className="absolute inset-0 z-50 flex items-center justify-center rounded-3xl bg-blue-500/5 backdrop-blur-[1px]">
              <div className="bg-white dark:bg-gray-800 px-4 py-2 rounded-full shadow-xl border border-blue-400 flex items-center gap-2">
                <span className="animate-bounce">📥</span>
                <span className="text-sm font-bold text-blue-600 uppercase">
                  Lepas file
                </span>
              </div>
            </div>
          )}

          {/* File Previews Area */}
          {previews.length > 0 && (
            <div className="flex flex-wrap gap-3 p-3 border-b border-gray-200 dark:border-gray-700/50">
              {previews.map((file, index) => (
                <div
                  key={index}
                  className="relative group w-16 h-16 animate-in zoom-in duration-200"
                >
                  {file.type === "image" ? (
                    <img
                      src={file.url}
                      className="w-full h-full object-cover rounded-xl border border-gray-200 dark:border-gray-600 shadow-sm"
                      alt="Preview"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
                      <span className="text-xl">📄</span>
                      <span className="text-[7px] mt-1 px-1 truncate w-full text-center font-medium text-gray-900 dark:text-gray-100">
                        {file.name}
                      </span>
                    </div>
                  )}
                  <button
                    onClick={() => {
                      setPreviews((prev) => prev.filter((_, i) => i !== index));
                      setSelectedFiles((prev) =>
                        prev.filter((_, i) => i !== index)
                      );
                    }}
                    className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center hover:scale-110 transition-transform shadow-lg border-2 border-white dark:border-[#2E2E33]"
                  >
                    <span className="text-[10px] font-bold">✕</span>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input Area (Textarea) */}
          <div className="flex flex-col p-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              onPaste={handlePaste}
              disabled={isLoading} // Hanya disable saat loading, bukan saat Guest
              placeholder={
                !isLoggedIn
                  ? "Apa yang bisa CAKRA bantu?"
                  : currentMode === "document"
                  ? "Tanya apapun terkait dokumen..."
                  : "Tanya CAKRA AI..."
              }
              className="w-full px-3 py-2 border-none bg-transparent resize-none focus:outline-none text-gray-900 dark:text-gray-100 text-sm leading-relaxed custom-scrollbar"
              rows="1"
              style={{
                minHeight: "44px",
                maxHeight: "150px",
              }}
              onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height =
                  Math.min(e.target.scrollHeight, 150) + "px";
              }}
            />

            {/* Bottom Toolbar */}
            <div className="flex items-center justify-between mt-1 px-1">
              <div className="flex items-center gap-1">
                {/* File Upload Button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current.click()}
                  className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors"
                  title="Upload Files"
                >
                  <svg
                    width="20"
                    height="20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                  >
                    <path
                      d="M12 5v14M5 12h14"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>

                {/* Mode Switchers */}
                {isLoggedIn && (
                  <div className="flex bg-gray-200/50 dark:bg-gray-700/50 p-1 rounded-full ml-1">
                    <button
                      onClick={() => switchMode("document")}
                      className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full transition-all ${
                        currentMode === "document"
                          ? "bg-white dark:bg-gray-600 text-blue-600 shadow-sm"
                          : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-200"
                      }`}
                    >
                      Docs
                    </button>
                    <button
                      onClick={() => switchMode("search")}
                      className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full transition-all ${
                        currentMode === "search"
                          ? "bg-white dark:bg-gray-600 text-purple-600 shadow-sm"
                          : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-200"
                      }`}
                    >
                      Web
                    </button>
                  </div>
                )}
              </div>

              {/* Send Button */}
              <button
                onClick={sendMessage}
                disabled={isLoading || !input.trim()}
                className={`flex items-center justify-center w-10 h-10 rounded-full transition-all ${
                  isLoading || !input.trim()
                    ? "bg-gray-200 dark:bg-gray-700 text-gray-400"
                    : "bg-blue-600 text-white shadow-lg hover:bg-blue-700 active:scale-90"
                }`}
              >
                {isLoading ? (
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                  >
                    <path
                      d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*,.pdf"
          multiple
          className="hidden"
        />

        <p className="text-[10px] text-center text-gray-400 mt-2 dark:text-gray-500">
          CAKRA AI dapat membuat kesalahan. Pertimbangkan untuk memeriksa
          informasi penting.
        </p>
      </div>
    </div>
  );
}
