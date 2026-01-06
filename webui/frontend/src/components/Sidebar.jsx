import React, { useState, useRef, useEffect } from "react";

const Sidebar = ({
  backendStatus,
  clearChat,
  setShowDocumentList,
  isOpen,
  setIsOpen,
  setIsLoggedIn,
  userData,
}) => {
  // Tambah state ini buat deteksi hover pas lagi ciut
  const [isHovered, setIsHovered] = useState(false);
  // Tambah state untuk toggle popup logout
  const [showLogoutPopup, setShowLogoutPopup] = useState(false);
  const popupRef = useRef(null);

  // Close popup saat klik di luar
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popupRef.current && !popupRef.current.contains(event.target)) {
        setShowLogoutPopup(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div
      className={`fixed left-0 top-0 h-screen bg-white-900 text-black flex flex-col transition-all duration-300 z-40 ${
        isOpen ? "w-60" : "w-15"
      }`}
      style={{ background: "#F7F8FC", borderRight: "1px solid #E0E0E0" }}
    >
      {/* Header - Tambah trigger hover di sini */}
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className="p-3 p-4  border-black-700 relative flex flex-col justify-center"
      >
        <div className="flex items-center">
          {/* Logo dengan transisi ukuran saat collapse */}
          <img
            src="./src/assets/cakra.png"
            alt="CAKRA AI Logo"
            className={`rounded-full object-cover transition-all duration-300 ${
              isOpen ? "w-10 h-10" : "w-7 h-7"
            } ${!isOpen && isHovered ? "opacity-0" : "opacity-100"}`}
          />
          <h1
            className={`font-bold text-lg text-black whitespace-nowrap transition-all duration-300 ml-2 ${
              !isOpen ? "opacity-0 pointer-events-none w-0" : "opacity-100"
            }`}
          >
            CAKRA AI
          </h1>
        </div>

        {/* Tombol Toggle - Muncul saat hover dalam kondisi collapse */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`absolute transition-all duration-300 p-1 hover:bg-black-700 rounded text-black-400 hover:text-black ${
            isOpen
              ? "top-5 right-3 opacity-100"
              : `top-3 left-1/2 -translate-x-1/2 ${
                  isHovered
                    ? "opacity-100 scale-110"
                    : "opacity-0 pointer-events-none"
                }`
          }`}
          title={isOpen ? "Ciutkan" : "Lebarkan"}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-black"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="4" width="18" height="16" rx="2.5" />
            <rect x="3" y="4" width="6" height="16" rx="2.5" />
          </svg>
        </button>
      </div>
      {/* Menu - Tombol New Chat */}
      <div
        className={`p-3 space-y-2 ${!isOpen && "flex flex-col items-center"}`}
      >
        <button
          onClick={clearChat}
          className={`flex items-center rounded-xl hover:bg-black-800 transition-colors group overflow-hidden border border-black-700 ${
            isOpen ? "p-1 w-full space-x-3" : "p-1 justify-center"
          }`}
          title="New Chat"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-black-400 group-hover:text-blue-400 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
            />
          </svg>
          <span
            className={`font-medium whitespace-nowrap transition-opacity duration-300 ${
              !isOpen ? "hidden" : "opacity-100"
            }`}
          >
            New Chat
          </span>
        </button>

        <button
          onClick={() => setShowDocumentList(true)}
          className={`flex items-center rounded-xl hover:bg-black-800 transition-colors group overflow-hidden border border-black-700 ${
            isOpen ? "p-1 w-full space-x-3" : "p-1 justify-center"
          }`}
          title="Documents"
        >
          <span className="h-5 w-5 flex items-center justify-center flex-shrink-0">
            📄
          </span>
          <span
            className={`font-medium text-black-200 whitespace-nowrap transition-opacity duration-300 ${
              !isOpen ? "hidden" : "opacity-100"
            }`}
          >
            Documents
          </span>
        </button>
      </div>
      {/* History Sections */}
      <div
        className={`flex-1 overflow-y-auto px-4 py-2 space-y-4 transition-opacity duration-300 ${
          !isOpen ? "opacity-0 pointer-events-none hidden" : "opacity-100"
        }`}
      >
        <div className="px-0 py-2 border-black-700">
          <div className="flex items-center justify-between cursor-pointer hover:text-blue-400">
            <span className="font-medium">All chats</span>
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
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>
      </div>
      {/* Footer Profile */}
      <div
        className={`border-black-700 relative flex flex-col${
          !isOpen
            ? "p-1 p-1 items-center absolute left-0 right-0 items-center justify-center"
            : "justify-center items-center p-2 p-3"
        }`}
        style={{
          background: "#F7F8FC",
          position: "absolute",
          borderTop: "1px solid #E0E0E0",
          bottom: 0,
          left: 0,
          right: 0,
        }}
      >
        {/* POPUP MENU */}
        {showLogoutPopup && (
          <div
            ref={popupRef}
            className={`absolute bottom-full left-2 mb-2 w-48  rounded-xl shadow-2xl py-2 z-50 transition-all ${
              !isOpen && "left-full ml-2 bottom-2"
            }`}
            style={{
              background: "#ffffff",
              border: "1px solid #E0E0E0",
              borderRadius: "10px",
              boxShadow: "0 0 10px 0 rgba(0, 0, 0, 0.1)",
            }}
          >
            <div className="px-4 py-2 ">
              <p className="text-xs text-black-400">Akun Anda</p>
              <p className="text-sm font-semibold truncate">
                {userData?.fullname || "Loading..."}
              </p>
            </div>

            <button
              onClick={() => setIsLoggedIn(false)}
              className="w-full flex items-center space-x-3 px-4 py-1 text-red-400 hover:bg-gray-100 transition-colors"
              style={{
                borderTop: "1px solid #E0E0E0",
                borderRadius: "10px",
                // boxShadow: "0 0 10px 0 rgba(0, 0, 0, 0.1)",
              }}
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
          className="flex items-center cursor-pointer w-full"
          onClick={() => setShowLogoutPopup(!showLogoutPopup)}
        >
          <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0 ml-2 border border-gray-700 bg-gray-800 flex items-center justify-center shadow-inner">
            {userData?.username ? (
              <>
                <img
                  src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.username}.jpg`}
                  alt="Profile"
                  className="w-full h-full object-cover"
                  // Jika foto di HRIS tidak ditemukan (Error 404), sembunyikan img dan tampilkan inisial
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                    e.currentTarget.nextSibling.style.display = "flex";
                  }}
                />
                <div className="hidden w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold">
                  {userData?.fullname
                    ? userData.fullname.substring(0, 2).toUpperCase()
                    : "AI"}
                </div>
              </>
            ) : (
              <div className="flex w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold">
                AI
              </div>
            )}
          </div>
          <div
            className={`flex flex-col min-w-0 transition-all duration-300 ${
              !isOpen ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
            }`}
          >
            <span className="text-sm font-medium truncate w-40 ml-3">
              {userData?.fullname || "Loading..."}
            </span>
            <span className="text-[9px] text-black-500  text-left ml-3">
              {userData?.divisi || "Guest"}
            </span>
          </div>
        </div>

        {isOpen && (
          <button
            className="text-black-500 group-hover:text-black ml-auto absolute right-3"
            onClick={() => setShowLogoutPopup(!showLogoutPopup)}
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
                d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
