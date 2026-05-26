import React from "react";

export default function HeaderBar({
  isSidebarOpen,
  modelList,
  selectedModel,
  setSelectedModel,
  isDropdownOpen,
  setIsDropdownOpen,
}) {
  return (
    <div
      className="absolute top-4 z-40 flex items-center transition-all duration-300 ease-in-out"
      style={{
        // Menyesuaikan posisi berdasarkan lebar sidebar lu
        left: isSidebarOpen ? "10px" : "-20px",
        marginLeft: isSidebarOpen ? "1.5rem" : "0.5rem",
      }}
    >
      <div className="relative flex items-center bg-white/80 dark:bg-[#1A1A1C]/80 backdrop-blur-md border border-gray-200 dark:border-[#27272a] rounded-full px-3 py-1.5 shadow-sm transition-all duration-300">
        {/* Status Indicator */}
        <div className="relative flex mr-2">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
          <div className="absolute inset-0 w-2 h-2 bg-blue-400 rounded-full animate-ping opacity-75"></div>
        </div>

        {/* Dropdown Toggle */}
        <button
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          className="flex items-center gap-1.5 text-xs font-bold text-gray-700 dark:text-gray-200 focus:outline-none uppercase tracking-wider"
        >
          <span className="truncate max-w-[100px] md:max-w-none">
            {modelList.find((m) => m.id === selectedModel)?.name ||
              "Select Model"}
          </span>
          <svg
            className={`w-3.5 h-3.5 transition-transform duration-300 ${
              isDropdownOpen ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>

        {/* Dropdown Menu */}
        {isDropdownOpen && (
          <>
            {/* Backdrop transparan untuk menutup dropdown saat klik di luar */}
            <div
              className="fixed inset-0 z-[-1]"
              onClick={() => setIsDropdownOpen(false)}
            />

            <div className="absolute top-full left-0 mt-2 w-64 rounded-2xl bg-white dark:bg-[#1A1A1C] border border-gray-200 dark:border-[#27272a] shadow-2xl overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200">
              <div className="px-4 py-2.5 border-b border-gray-100 dark:border-[#232326] bg-gray-50/50 dark:bg-[#232326]/50">
                <span className="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-[0.2em]">
                  Switch Model
                </span>
              </div>

              <div className="max-h-64 overflow-y-auto custom-scrollbar p-1">
                {modelList.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => {
                      setSelectedModel(m.id);
                      setIsDropdownOpen(false);
                    }}
                    className={`w-full px-3 py-2.5 flex items-center justify-between text-left rounded-xl transition-all mb-1
                      ${
                        selectedModel === m.id
                          ? "bg-blue-50 dark:bg-blue-600/10 text-blue-700 dark:text-blue-400"
                          : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#232326]"
                      }`}
                  >
                    <div className="flex flex-col">
                      <span className="text-sm font-semibold">{m.name}</span>
                      <span className="text-[9px] opacity-60">
                        Optimized for CAKRA Intelligence
                      </span>
                    </div>

                    {selectedModel === m.id && (
                      <div className="bg-blue-600 rounded-full p-0.5">
                        <svg
                          className="w-3 h-3 text-white"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
