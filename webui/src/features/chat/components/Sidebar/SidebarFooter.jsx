import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { translations } from "../../../../utils/translations";
import { getApiBase } from "../../../../services/endpoints";
import { useChatStore } from "../../../../stores/chatStore";
import { Settings, Globe, Palette, Sun, Moon, Monitor, Check, X, LogOut, LogIn } from "lucide-react";

const LANGUAGE_OPTIONS = [
  { code: 'en', nativeName: 'English (United States)', englishName: 'English (United States)' },
  { code: 'id', nativeName: 'Indonesia (Indonesia)', englishName: 'Indonesian (Indonesia)' },
];

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
  userData,
  language,
  setLanguage,
  openSettingsModal
}) {
  const t = translations[language]?.settings || translations.id.settings;

  const [showLanguageModal, setShowLanguageModal] = useState(false);
  const [showThemeModal, setShowThemeModal] = useState(false);

  // Close modals on Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        setShowLanguageModal(false);
        setShowThemeModal(false);
      }
    };
    if (showLanguageModal || showThemeModal) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [showLanguageModal, showThemeModal]);

  const currentThemeSetting = typeof window !== 'undefined'
    ? localStorage.getItem("cakra-theme-setting") || (darkMode ? "dark" : "light")
    : (darkMode ? "dark" : "light");

  const THEME_OPTIONS = [
    {
      key: 'light',
      name: t.light || (language === 'en' ? 'Light' : 'Terang'),
      desc: t.themeLightDesc || (language === 'en' ? 'Clean & bright appearance' : 'Tampilan terang dan jernih'),
      icon: Sun,
    },
    {
      key: 'dark',
      name: t.dark || (language === 'en' ? 'Dark' : 'Gelap'),
      desc: t.themeDarkDesc || (language === 'en' ? 'Easy on the eyes' : 'Nyaman di mata saat redup'),
      icon: Moon,
    },
    {
      key: 'system',
      name: t.system || (language === 'en' ? 'System' : 'Sistem'),
      desc: t.themeSystemDesc || (language === 'en' ? 'Sync with device settings' : 'Otomatis ikuti tema perangkat'),
      icon: Monitor,
    },
  ];

  return (
    <div
      className={`relative flex items-center border-t z-20 flex-shrink-0 ${darkMode ? 'border-[#2a2a2d]' : 'border-gray-200'} ${!isOpen
          ? "p-1 justify-center"
          : "justify-center py-3 px-3 p-4"
        }`}
      style={{
        height: "60px",
        background: darkMode ? "#1E1E22" : theme?.sidebarBg || "#F7F8FC",
      }}
    >
      {showLogoutPopup && (
        <div
          ref={popupRef}
          className={`absolute bottom-full left-2 mb-2 w-56 rounded-xl shadow-2xl py-2 z-50 transition-all border ${darkMode ? "bg-[#232326] border-gray-800" : "bg-white border-gray-200"}`}
          style={{
            left: !isOpen ? "100%" : "8px",
            marginLeft: !isOpen ? "8px" : "0px",
            bottom: !isOpen ? "8px" : "100%",
          }}
        >
          <div className="px-4 py-3">
            <p className="text-[11px] text-gray-400 mb-1">
              {t.account}
            </p>
            <p className={`text-sm font-bold truncate ${darkMode ? "text-white" : "text-gray-800"}`}>
              {profileName}
            </p>
            <p className={`text-xs truncate mt-0.5 ${darkMode ? "text-gray-400" : "text-gray-500"}`}>
              {userData?.email || `${userData?.npp || 'user'}@pindad.co.id`}
            </p>
          </div>

          <div className={`py-1 border-t ${darkMode ? "border-gray-800" : "border-gray-100"}`}>
            {/* Settings */}
            <button
              onClick={() => {
                setShowLogoutPopup(false);
                openSettingsModal();
              }}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 transition-colors ${darkMode ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"}`}
            >
              <Settings size={17} strokeWidth={2} className="flex-shrink-0" />
              <span className="text-sm font-medium flex-1 text-left">{t.settingsTitle}</span>
            </button>

            {/* Language */}
            <button
              onClick={() => {
                setShowLogoutPopup(false);
                setShowLanguageModal(true);
              }}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 transition-colors ${darkMode ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"}`}
            >
              <Globe size={17} strokeWidth={2} className="flex-shrink-0" />
              <div className="flex-1 flex items-center justify-between text-left min-w-0">
                <span className="text-sm font-medium truncate">{t.language}</span>
                <span className={`text-xs ml-2 flex-shrink-0 ${darkMode ? "text-gray-400" : "text-gray-500"}`}>
                  {language === 'id' ? 'Indonesia' : 'English'}
                </span>
              </div>
            </button>

            {/* Theme */}
            <button
              onClick={() => {
                setShowLogoutPopup(false);
                setShowThemeModal(true);
              }}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 transition-colors ${darkMode ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"}`}
            >
              <Palette size={17} strokeWidth={2} className="flex-shrink-0" />
              <div className="flex-1 flex items-center justify-between text-left min-w-0">
                <span className="text-sm font-medium truncate">{t.theme}</span>
                <span className={`text-xs ml-2 flex-shrink-0 capitalize ${darkMode ? "text-gray-400" : "text-gray-500"}`}>
                  {currentThemeSetting === 'system' ? (t.system || 'System') : (darkMode ? (t.dark || 'Dark') : (t.light || 'Light'))}
                </span>
              </div>
            </button>
          </div>

          {userData?.npp ? (
            <button
              onClick={() => {
                setShowLogoutPopup(false);
                triggerLogout();
              }}
              className={`w-full flex items-center space-x-3 px-4 py-3 text-red-500 transition-colors border-t ${darkMode ? "hover:bg-red-900/10 border-gray-800" : "hover:bg-red-50 border-gray-100"}`}
            >
              <LogOut size={18} strokeWidth={2} className="flex-shrink-0" />
              <span className="text-sm font-medium">{t.logout}</span>
            </button>
          ) : (
            <button
              onClick={() => {
                setShowLogoutPopup(false);
                window.dispatchEvent(new CustomEvent('cakra_open_login'));
              }}
              className={`w-full flex items-center space-x-3 px-4 py-3 text-blue-500 font-semibold transition-colors border-t ${darkMode ? "hover:bg-blue-500/10 border-gray-800" : "hover:bg-blue-50 border-gray-100"}`}
            >
              <LogIn size={18} strokeWidth={2} className="flex-shrink-0" />
              <span className="text-sm font-medium">{language === 'en' ? 'Log In' : 'Masuk Pegawai'}</span>
            </button>
          )}
        </div>
      )}

      {/* ── MODAL: CHOOSE YOUR LANGUAGE (CLAUDE STYLE) ── */}
      {showLanguageModal && typeof document !== "undefined" && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm animate-in fade-in duration-150"
          onClick={() => setShowLanguageModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className={`w-full max-w-md rounded-2xl p-6 border shadow-2xl animate-in zoom-in-95 duration-150 ${
              darkMode ? 'bg-[#18181b] border-zinc-800 text-white' : 'bg-white border-gray-200 text-gray-900'
            }`}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold tracking-tight">
                {t.chooseLanguage || (language === 'en' ? 'Choose your language' : 'Pilih bahasa Anda')}
              </h2>
              <button
                onClick={() => setShowLanguageModal(false)}
                className={`p-1.5 rounded-lg transition-colors ${
                  darkMode ? 'hover:bg-zinc-800 text-gray-400 hover:text-white' : 'hover:bg-gray-100 text-gray-500 hover:text-black'
                }`}
              >
                <X size={18} />
              </button>
            </div>

            {/* Language List: Compact cards */}
            <div className="grid grid-cols-1 gap-2.5">
              {LANGUAGE_OPTIONS.map((opt) => {
                const isSelected = language === opt.code;
                return (
                  <button
                    key={opt.code}
                    onClick={() => {
                      setLanguage(opt.code);
                      setShowLanguageModal(false);
                    }}
                    className={`p-3.5 rounded-xl text-left transition-all relative flex items-center justify-between ${
                      isSelected
                        ? darkMode
                          ? 'bg-[#27272a] text-white ring-1 ring-zinc-700'
                          : 'bg-blue-50 text-blue-900 border border-blue-200'
                        : darkMode
                        ? 'hover:bg-zinc-850/80 text-gray-300 hover:text-white border border-transparent'
                        : 'hover:bg-gray-50 text-gray-700 hover:text-gray-900 border border-transparent'
                    }`}
                  >
                    <div>
                      <span className="text-xs font-semibold leading-tight block">{opt.nativeName}</span>
                      <span className={`text-[11px] mt-0.5 leading-tight block ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                        {opt.englishName}
                      </span>
                    </div>
                    {isSelected && <Check size={16} className="text-blue-400 flex-shrink-0 ml-2" strokeWidth={2.5} />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* ── MODAL: CHOOSE YOUR THEME ── */}
      {showThemeModal && typeof document !== "undefined" && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm animate-in fade-in duration-150"
          onClick={() => setShowThemeModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className={`w-full max-w-md rounded-2xl p-6 border shadow-2xl animate-in zoom-in-95 duration-150 ${
              darkMode ? 'bg-[#18181b] border-zinc-800 text-white' : 'bg-white border-gray-200 text-gray-900'
            }`}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold tracking-tight">
                {t.chooseTheme || (language === 'en' ? 'Choose your theme' : 'Pilih tema Anda')}
              </h2>
              <button
                onClick={() => setShowThemeModal(false)}
                className={`p-1.5 rounded-lg transition-colors ${
                  darkMode ? 'hover:bg-zinc-800 text-gray-400 hover:text-white' : 'hover:bg-gray-100 text-gray-500 hover:text-black'
                }`}
              >
                <X size={18} />
              </button>
            </div>

            {/* Theme Options */}
            <div className="grid grid-cols-1 gap-2.5">
              {THEME_OPTIONS.map((opt) => {
                const isSelected = currentThemeSetting === opt.key;
                const IconComponent = opt.icon;
                return (
                  <button
                    key={opt.key}
                    onClick={() => {
                      if (opt.key === 'light') setDarkMode(false);
                      else if (opt.key === 'dark') setDarkMode(true);
                      else if (opt.key === 'system') setDarkMode('system');
                      setShowThemeModal(false);
                    }}
                    className={`p-3.5 rounded-xl text-left transition-all flex items-center justify-between ${
                      isSelected
                        ? darkMode
                          ? 'bg-[#27272a] text-white ring-1 ring-zinc-700'
                          : 'bg-blue-50 text-blue-900 border border-blue-200'
                        : darkMode
                        ? 'hover:bg-zinc-850/80 text-gray-300 hover:text-white border border-transparent'
                        : 'hover:bg-gray-50 text-gray-700 hover:text-gray-900 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          isSelected
                            ? darkMode ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600'
                            : darkMode ? 'bg-zinc-800 text-gray-400' : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        <IconComponent size={18} strokeWidth={2} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold leading-tight">{opt.name}</p>
                        <p className={`text-[11px] mt-0.5 leading-tight ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                          {opt.desc}
                        </p>
                      </div>
                    </div>
                    {isSelected && <Check size={16} className="text-blue-400 flex-shrink-0 ml-2" strokeWidth={2.5} />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>,
        document.body
      )}

      <div
        className={`flex items-center cursor-pointer flex-1 min-w-0 ${!isOpen ? "justify-center" : ""}`}
        onClick={() => setShowLogoutPopup(!showLogoutPopup)}
      >
        <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0 border border-gray-700 bg-gray-800 flex items-center justify-center shadow-inner">
          {userData?.profile_photo_url ? (
            <>
              <img
                src={`${getApiBase()}${userData.profile_photo_url}`}
                alt="Profile"
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  if (e.currentTarget.nextSibling) {
                    e.currentTarget.nextSibling.style.display = "flex";
                  }
                }}
              />
              <div className="hidden w-full h-full bg-gradient-to-tr from-blue-600 to-purple-600 items-center justify-center text-xs font-bold text-white">
                {profileName && profileName !== "Pegawai Pindad"
                  ? profileName.substring(0, 2).toUpperCase()
                  : "AI"}
              </div>
            </>
          ) : userData?.npp ? (
            <>
              <img
                src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.npp}.jpg`}
                alt="Profile"
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  if (e.currentTarget.nextSibling) {
                    e.currentTarget.nextSibling.style.display = "flex";
                  }
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
          title={language === 'en' ? 'Settings & Account' : 'Pengaturan & Akun'}
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
