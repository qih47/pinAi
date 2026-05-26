import React from "react";

export default function FloatingButtons({
  messagesContainerRef,
  isAtBottom,
  isAiTypingRef,
  startAutoScroll,
  autoScrollEnabled,
  isUserScrolling,
}) {
  const handleScrollClick = () => {
    const container = messagesContainerRef.current;
    if (!container) return;

    if (isAtBottom) {
      // Jika sudah di bawah, scroll ke paling atas
      container.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      // Scroll ke paling bawah
      container.scrollTo({
        top: container.scrollHeight,
        behavior: "smooth",
      });
      // Reset state auto-scroll
      autoScrollEnabled.current = true;
      isUserScrolling.current = false;
      if (isAiTypingRef.current && typeof startAutoScroll === "function") {
        startAutoScroll();
      }
    }
  };

  // Logika: Munculkan tombol jika TIDAK di bawah,
  // ATAU jika di bawah tapi sudah scroll jauh dari atas (biar bisa scroll up)
  const shouldShow =
    !isAtBottom ||
    (isAtBottom && messagesContainerRef.current?.scrollTop > 300);

  if (!shouldShow) return null;

  return (
    <div className="flex flex-col items-center pointer-events-none animate-in fade-in zoom-in slide-in-from-bottom-4 duration-300">
      <button
        onClick={handleScrollClick}
        className="pointer-events-auto relative group p-2.5 bg-white/90 dark:bg-[#2e2e33]/90 backdrop-blur-md border border-gray-200 dark:border-gray-700 rounded-full shadow-xl hover:bg-white dark:hover:bg-[#38383d] hover:scale-110 transition-all active:scale-95 flex items-center justify-center"
      >
        {/* Arrow Icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`w-3 h-3 text-gray-600 dark:text-gray-300 transition-transform duration-500 ${
            isAtBottom ? "" : "rotate-180"
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2.5}
            d="M5 15l7-7 7 7"
          />
        </svg>

        {/* Tooltip (Optional but Nice) */}
        <span className="absolute right-full mr-3 px-2 py-1 bg-gray-800 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
          {isAtBottom ? "Scroll ke Atas" : "Pesan Baru"}
        </span>

        {/* Notifikasi Dot (Hanya muncul jika AI sedang ngetik & kita lagi di atas) */}
        {!isAtBottom && isAiTypingRef.current && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-4 w-4 bg-blue-500 border-2 border-white dark:border-[#2e2e33]"></span>
          </span>
        )}
      </button>
    </div>
  );
}
