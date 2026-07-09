import React from "react";

export default function SidebarFooter({
  isOpen,
  darkMode,
  theme,
  showLogoutPopup,
  setShowLogoutPopup,
  popupRef,
  profileName,
  profileDivisi,
  setDarkMode,
  triggerLogout,
  userData
}) {
  return (
    <div
      className={`relative flex items-center p-4 ${!isOpen
          ? "p-1 items-center absolute left-0 right-0 justify-center"
          : "justify-center items-center py-3 px-3"
        }`}
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: "60px",
        background: darkMode ? "#1E1E22" : theme?.sidebarBg || "#F7F8FC",
      }}
    >
      {showLogoutPopup && (
        <div
          ref={popupRef}
          className={`absolute bottom-full left-2 mb-2 w-52 rounded-xl shadow-2xl py-2 z-50 transition-all border ${darkMode ? "bg-[#232326] border-gray-800" : "bg-white border-gray-200"}`}
          style={{
            left: !isOpen ? "100%" : "8px",
            marginLeft: !isOpen ? "8px" : "0px",
            bottom: !isOpen ? "8px" : "100%",
          }}
        >
          <div className="px-4 py-2">
            <p className="text-xs text-gray-400">
              Akun Anda
            </p>
            <p className={`text-xs font-semibold truncate ${darkMode ? "text-white" : "text-gray-800"}`}>
              {profileName}
            </p>
          </div>

          <div className={`px-4 py-2 border-t space-y-1 ${darkMode ? "border-gray-800" : "border-gray-100"}`}>
            <p className="text-[10px] uppercase font-bold tracking-wider text-gray-400 mb-1">
              Pilihan Tema
            </p>
            <div className={`flex p-0.5 rounded-lg text-[11px] ${darkMode ? "bg-gray-800" : "bg-gray-100"}`}>
              <button
                onClick={() => setDarkMode(false)}
                className={`flex-1 py-1 text-center rounded-md font-medium transition-all ${!darkMode ? "bg-white text-black shadow-sm" : "text-gray-500 hover:text-black"}`}
              >
                ☀️ Light
              </button>
              <button
                onClick={() => setDarkMode(true)}
                className={`flex-1 py-1 text-center rounded-md font-medium transition-all ${darkMode ? "bg-gray-700 text-white shadow-sm" : "text-gray-500 hover:text-black"}`}
              >
                🌙 Dark
              </button>
            </div>
          </div>

          <button
            onClick={() => {
              setShowLogoutPopup(false);
              triggerLogout();
            }}
            className={`w-full flex items-center space-x-3 px-4 py-2 text-red-500 transition-colors border-t ${darkMode ? "hover:bg-gray-900 border-gray-800" : "hover:bg-gray-100 border-gray-100"}`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            <span className="text-sm font-medium">Keluar (Logout)</span>
          </button>
        </div>
      )}

      <div
        className="flex items-center cursor-pointer flex-1 min-w-0"
        onClick={() => setShowLogoutPopup(!showLogoutPopup)}
      >
        <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0 border border-gray-700 bg-gray-800 flex items-center justify-center shadow-inner">
          {userData?.npp ? (
            <>
              <img
                src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.npp}.jpg`}
                alt="Profile"
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  e.currentTarget.nextSibling.style.display = "flex";
                }}
              />
              <div className="hidden w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold text-white">
                {profileName !== "Pegawai Pindad"
                  ? profileName.substring(0, 2).toUpperCase()
                  : "AI"}
              </div>
            </>
          ) : (
            <div className="flex w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold text-white">
              AI
            </div>
          )}
        </div>
        <div
          className={`flex flex-col min-w-0 transition-all duration-300 ${!isOpen ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
            }`}
        >
          <span
            className="text-xs font-medium whitespace-normal break-words ml-3"
            style={{ color: theme?.textColor }}
          >
            {profileName}
          </span>
          <span
            className="text-[9px] text-left ml-3"
            style={{ color: theme?.secondaryText || "#6b7280" }}
          >
            {profileDivisi}
          </span>
        </div>
      </div>

      {isOpen && (
        <button
          className="hover:text-blue-500 ml-auto absolute right-3 top-0 bottom-0 my-auto h-fit p-1 transition-colors"
          style={{ color: theme?.iconColor || "#9ca3af" }}
          onClick={() => setShowLogoutPopup(!showLogoutPopup)}
          title="Pengaturan & Akun"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 animate-[spin_20s_linear_infinite]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
