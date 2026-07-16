import React, { useState, useRef, useEffect } from "react";
import { translations } from "../../../utils/translations";
import { useChatStore } from "../../../stores/chatStore";
import apiClient from "../../../services/apiClient";

export default function SettingsModal({
  isOpen,
  onClose,
  darkMode,
  theme,
  themeSetting,
  language,
  setLanguage,
  setDarkMode,
  userData,
  triggerLogout
}) {
  const [activeTab, setActiveTab] = useState("general");
  const store = useChatStore();
  const t = translations[language]?.settings || translations.id.settings;
  const ttsVoice = store.ttsVoice;
  const setTtsVoice = store.setTtsVoice;
  const autoReadAloud = store.autoReadAloud;
  const setAutoReadAloud = store.setAutoReadAloud;
  const ttsSpeed = store.ttsSpeed || 'normal';
  const setTtsSpeed = store.setTtsSpeed;

  const audioRef = useRef(null);
  const [isPlayingTest, setIsPlayingTest] = useState(false);
  const [isVoiceDropdownOpen, setIsVoiceDropdownOpen] = useState(false);
  const [isLanguageDropdownOpen, setIsLanguageDropdownOpen] = useState(false);
  const voiceDropdownRef = useRef(null);
  const languageDropdownRef = useRef(null);

  // Edit Account State
  const [isEditingAccount, setIsEditingAccount] = useState(false);
  const [editEmail, setEditEmail] = useState("");
  const [editPhoto, setEditPhoto] = useState(null);
  const [editPhotoPreview, setEditPhotoPreview] = useState(null);
  const [editFullname, setEditFullname] = useState("");
  const [editPreferredName, setEditPreferredName] = useState("");
  const [isSubmittingProfile, setIsSubmittingProfile] = useState(false);

  // Change Password State
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);

  // Initialize edit fields
  useEffect(() => {
    if (userData) {
      setEditEmail(userData.email || "");
      setEditFullname(userData.fullname || userData.nama || userData.name || "");
      setEditPreferredName(userData.preferred_name || "");
    }
  }, [userData]);

  // Close on Escape key or outside click for dropdown
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    const handleClickOutside = (e) => {
      if (voiceDropdownRef.current && !voiceDropdownRef.current.contains(e.target)) {
        setIsVoiceDropdownOpen(false);
      }
      if (languageDropdownRef.current && !languageDropdownRef.current.contains(e.target)) {
        setIsLanguageDropdownOpen(false);
      }
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      window.addEventListener("mousedown", handleClickOutside);
        return () => {
        window.removeEventListener("keydown", handleKeyDown);
        window.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [isOpen, onClose]);

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setIsSubmittingProfile(true);
    
    const formData = new FormData();
    formData.append('token', localStorage.getItem('cakra_token') || '');
    if (editEmail) formData.append('email', editEmail);
    if (editFullname) formData.append('fullname', editFullname);
    if (editPreferredName) formData.append('preferred_name', editPreferredName);
    if (editPhoto) formData.append('photo', editPhoto);

    try {
      const response = await apiClient.put('/user/profile', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      if (response.data?.status === 'success') {
        setIsEditingAccount(false);
        window.location.reload();
      }
    } catch (err) {
      console.error("Gagal update profil", err);
      alert("Gagal memperbarui profil.");
    } finally {
      setIsSubmittingProfile(false);
    }
  };

  const handlePasswordUpdate = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmNewPassword) {
      alert("Password baru dan konfirmasi tidak cocok.");
      return;
    }
    setIsSubmittingPassword(true);
    
    try {
      const response = await apiClient.put('/user/password', {
        token: localStorage.getItem('cakra_token') || '',
        old_password: oldPassword,
        new_password: newPassword
      });
      if (response.data?.status === 'success') {
        alert("Password berhasil diubah!");
        setIsChangingPassword(false);
        setOldPassword("");
        setNewPassword("");
        setConfirmNewPassword("");
      }
    } catch (err) {
      console.error("Gagal update password", err);
      alert(err.response?.data?.detail || "Gagal memperbarui password.");
    } finally {
      setIsSubmittingPassword(false);
    }
  };

  if (!isOpen) return null;

  const tabs = [
    { id: "general", label: t.general, icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"></circle>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
      </svg>
    ) },
    { id: "account", label: t.account, icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
        <circle cx="12" cy="7" r="4"></circle>
      </svg>
    ) },
    { id: "about", label: t.about, icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
    ) }
  ];

  const handleTestVoice = async () => {
    if (isPlayingTest) return;
    setIsPlayingTest(true);
    
    // Sample text for the test
    const sampleText = ttsVoice.startsWith('id') 
      ? "Halo, ini adalah contoh suara saya menggunakan teknologi kecerdasan buatan."
      : "Hello, this is a sample of my voice using artificial intelligence technology.";

    try {
      const response = await apiClient.post('/voice/tts', {
        text: sampleText,
        voice: ttsVoice,
        speed: ttsSpeed
      }, { responseType: 'blob' });

      const url = URL.createObjectURL(response.data);
      
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
        audioRef.current.onended = () => {
          setIsPlayingTest(false);
          URL.revokeObjectURL(url);
        };
      }
    } catch (err) {
      console.error("Failed to test voice:", err);
      setIsPlayingTest(false);
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case "general":
        return (
          <div className="space-y-8 max-w-2xl">
            <h2 className="text-xl font-bold mb-6">{t.general}</h2>
            
            {/* Theme */}
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.theme}</h3>
              </div>
              <div className={`flex rounded-full p-1 border ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-gray-100 border-gray-200'}`}>
                <button
                  onClick={() => setDarkMode(false)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${themeSetting === 'light' ? (darkMode ? 'bg-gray-700 text-white shadow-sm' : 'bg-white text-gray-900 shadow-sm') : (darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900')}`}
                >
                  {t.light}
                </button>
                <button
                  onClick={() => setDarkMode(true)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${themeSetting === 'dark' ? (darkMode ? 'bg-gray-700 text-white shadow-sm' : 'bg-white text-gray-900 shadow-sm') : (darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900')}`}
                >
                  {t.dark}
                </button>
                <button
                  onClick={() => setDarkMode('system')}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${themeSetting === 'system' ? (darkMode ? 'bg-gray-700 text-white shadow-sm' : 'bg-white text-gray-900 shadow-sm') : (darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900')}`}
                >
                  {t.system}
                </button>
              </div>
            </div>

            {/* Language */}
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.language}</h3>
              </div>
              <div className="relative" ref={languageDropdownRef}>
                <button
                  onClick={() => setIsLanguageDropdownOpen(!isLanguageDropdownOpen)}
                  className={`flex items-center justify-between text-sm border rounded-lg px-3 py-2 outline-none min-w-[160px] transition-all ${darkMode ? 'bg-[#18181b] border-gray-700 hover:border-gray-500 text-gray-200' : 'bg-gray-50 border-gray-300 hover:border-gray-400 text-gray-700'} ${isLanguageDropdownOpen ? (darkMode ? 'border-gray-500 ring-2 ring-gray-700' : 'border-gray-400 ring-2 ring-gray-200') : ''}`}
                >
                  <span>{language === 'en' ? 'English (US)' : 'Bahasa Indonesia'}</span>
                  <svg className={`w-4 h-4 transition-transform duration-200 ${isLanguageDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {isLanguageDropdownOpen && (
                  <div className={`absolute right-0 mt-2 w-[160px] rounded-xl shadow-xl border overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200 ${darkMode ? 'bg-[#18181b] border-gray-700 shadow-black/50' : 'bg-white border-gray-200 shadow-gray-200/50'}`}>
                    <div className="py-2">
                      <button
                        onClick={() => { setLanguage('en'); setIsLanguageDropdownOpen(false); }}
                        className={`w-full text-left px-4 py-2 text-sm transition-colors ${language === 'en' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                      >
                        English (US)
                      </button>
                      <button
                        onClick={() => { setLanguage('id'); setIsLanguageDropdownOpen(false); }}
                        className={`w-full text-left px-4 py-2 text-sm transition-colors ${language === 'id' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                      >
                        Bahasa Indonesia
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Auto Read Aloud */}
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.autoReadAloud}</h3>
                <p className={`text-xs mt-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{t.autoReadAloudDesc}</p>
              </div>
              <button
                onClick={() => setAutoReadAloud(!autoReadAloud)}
                className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${autoReadAloud ? 'bg-blue-500' : (darkMode ? 'bg-gray-600' : 'bg-gray-300')}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoReadAloud ? 'translate-x-5' : 'translate-x-1'}`} />
              </button>
            </div>

            {/* Voice Settings */}
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.voiceSelection}</h3>
                <p className={`text-xs mt-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{t.voiceSelectionDesc}</p>
              </div>
              <div className="flex items-center space-x-3">
                <button 
                  onClick={handleTestVoice}
                  disabled={isPlayingTest}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors disabled:opacity-50 ${darkMode ? 'border-gray-700 hover:bg-gray-800 text-gray-200' : 'border-gray-300 hover:bg-gray-100 text-gray-700'}`}
                >
                  {isPlayingTest ? t.playing : t.testVoice}
                </button>
                <div className="relative" ref={voiceDropdownRef}>
                  <button
                    onClick={() => setIsVoiceDropdownOpen(!isVoiceDropdownOpen)}
                    className={`flex items-center justify-between text-sm border rounded-lg px-3 py-2 outline-none min-w-[180px] transition-all ${darkMode ? 'bg-[#18181b] border-gray-700 hover:border-gray-500 text-gray-200' : 'bg-gray-50 border-gray-300 hover:border-gray-400 text-gray-700'} ${isVoiceDropdownOpen ? (darkMode ? 'border-gray-500 ring-2 ring-gray-700' : 'border-gray-400 ring-2 ring-gray-200') : ''}`}
                  >
                    <span>
                      {ttsVoice === 'id-ID-ArdiNeural' && `Ardi (${t.male})`}
                      {ttsVoice === 'id-ID-GadisNeural' && `Gadis (${t.female})`}
                      {ttsVoice === 'en-US-ChristopherNeural' && `Christopher (${t.male})`}
                      {ttsVoice === 'en-US-AriaNeural' && `Aria (${t.female})`}
                    </span>
                    <svg className={`w-4 h-4 transition-transform duration-200 ${isVoiceDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {isVoiceDropdownOpen && (
                    <div className={`absolute right-0 mt-2 w-[220px] rounded-xl shadow-xl border overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200 ${darkMode ? 'bg-[#18181b] border-gray-700 shadow-black/50' : 'bg-white border-gray-200 shadow-gray-200/50'}`}>
                      <div className="py-2">
                        <div className={`px-3 py-1.5 text-xs font-semibold uppercase tracking-wider ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                          Indonesian
                        </div>
                        <button
                          onClick={() => { setTtsVoice('id-ID-ArdiNeural'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors ${ttsVoice === 'id-ID-ArdiNeural' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          Ardi ({t.male})
                        </button>
                        <button
                          onClick={() => { setTtsVoice('id-ID-GadisNeural'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors ${ttsVoice === 'id-ID-GadisNeural' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          Gadis ({t.female})
                        </button>

                        <div className={`px-3 py-1.5 mt-1 text-xs font-semibold uppercase tracking-wider ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                          English (US)
                        </div>
                        <button
                          onClick={() => { setTtsVoice('en-US-ChristopherNeural'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors ${ttsVoice === 'en-US-ChristopherNeural' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          Christopher ({t.male})
                        </button>
                        <button
                          onClick={() => { setTtsVoice('en-US-AriaNeural'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors ${ttsVoice === 'en-US-AriaNeural' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          Aria ({t.female})
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            {/* Voice Speed */}
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.voiceSpeed}</h3>
              </div>
              <div className={`flex rounded-full p-1 border ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-gray-100 border-gray-200'}`}>
                <button
                  onClick={() => setTtsSpeed('slow')}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${ttsSpeed === 'slow' ? (darkMode ? 'bg-gray-700 text-white shadow-sm' : 'bg-white text-gray-900 shadow-sm') : (darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900')}`}
                >
                  {t.speedSlow}
                </button>
                <button
                  onClick={() => setTtsSpeed('normal')}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${ttsSpeed === 'normal' ? (darkMode ? 'bg-gray-700 text-white shadow-sm' : 'bg-white text-gray-900 shadow-sm') : (darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900')}`}
                >
                  {t.speedNormal}
                </button>
                <button
                  onClick={() => setTtsSpeed('fast')}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${ttsSpeed === 'fast' ? (darkMode ? 'bg-gray-700 text-white shadow-sm' : 'bg-white text-gray-900 shadow-sm') : (darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900')}`}
                >
                  {t.speedFast}
                </button>
              </div>
            </div>
            
            <audio ref={audioRef} className="hidden" />
          </div>
        );
      case "account":
        if (isEditingAccount) {
          return (
            <div className="space-y-6 max-w-2xl">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold">{t.editAccount || "Ubah Akun"}</h2>
                <button 
                  onClick={() => setIsEditingAccount(false)}
                  className={`text-sm ${darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-black'}`}
                >
                  Batal
                </button>
              </div>

              <form onSubmit={handleProfileUpdate} className="space-y-5">
                <div className="flex flex-col items-center mb-6">
                  <div className="w-20 h-20 rounded-full overflow-hidden flex-shrink-0 border border-gray-700 bg-gray-800 flex items-center justify-center mb-3">
                    {editPhotoPreview || userData?.profile_photo_url ? (
                      <img
                        src={editPhotoPreview || (userData?.profile_photo_url ? `http://192.168.11.80:8000${userData.profile_photo_url}` : '')}
                        alt="Profile"
                        className="w-full h-full object-cover"
                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                      />
                    ) : userData?.npp ? (
                      <img
                        src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.npp}.jpg`}
                        alt="Profile"
                        className="w-full h-full object-cover"
                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                      />
                    ) : (
                      <span className={`font-bold ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>AI</span>
                    )}
                  </div>
                  <label className={`cursor-pointer px-4 py-1.5 text-xs font-medium rounded-full transition-colors ${darkMode ? 'bg-gray-800 hover:bg-gray-700 text-white' : 'bg-gray-200 hover:bg-gray-300 text-black'}`}>
                    Upload Foto
                    <input 
                      type="file" 
                      accept="image/*" 
                      className="hidden" 
                      onChange={(e) => {
                        const file = e.target.files[0];
                        if (file) {
                          setEditPhoto(file);
                          setEditPhotoPreview(URL.createObjectURL(file));
                        }
                      }}
                    />
                  </label>
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>{t.fullNameLabel}</label>
                  <input 
                    type="text" 
                    value={editFullname}
                    onChange={(e) => setEditFullname(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-black'}`}
                    placeholder={t.fullNamePlaceholder}
                  />
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>{t.preferredNameLabel}</label>
                  <input 
                    type="text" 
                    value={editPreferredName}
                    onChange={(e) => setEditPreferredName(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-black'}`}
                    placeholder={t.preferredNamePlaceholder}
                  />
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>{t.emailLabel}</label>
                  <input 
                    type="email" 
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300 text-black'}`}
                    placeholder={t.emailPlaceholder}
                  />
                </div>

                <div className="pt-4 flex justify-end">
                  <button 
                    type="submit" 
                    disabled={isSubmittingProfile}
                    className={`px-5 py-2 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'} ${isSubmittingProfile ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {isSubmittingProfile ? 'Menyimpan...' : 'Simpan Perubahan'}
                  </button>
                </div>
              </form>
            </div>
          );
        }

        if (isChangingPassword) {
          return (
            <div className="space-y-6 max-w-2xl">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold">{t.changePassword || "Ubah Password"}</h2>
                <button 
                  onClick={() => setIsChangingPassword(false)}
                  className={`text-sm ${darkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-black'}`}
                >
                  Batal
                </button>
              </div>

              <form onSubmit={handlePasswordUpdate} className="space-y-5">
                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>{t.oldPassword}</label>
                  <input
                    type="password"
                    required
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-gray-800 border-gray-700 text-white focus:border-blue-500' : 'bg-white border-gray-300 text-black focus:border-blue-500'} outline-none transition-colors`}
                  />
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>{t.newPassword}</label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-gray-800 border-gray-700 text-white focus:border-blue-500' : 'bg-white border-gray-300 text-black focus:border-blue-500'} outline-none transition-colors`}
                  />
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>{t.verifyNewPassword}</label>
                  <input
                    type="password"
                    required
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-gray-800 border-gray-700 text-white focus:border-blue-500' : 'bg-white border-gray-300 text-black focus:border-blue-500'} outline-none transition-colors`}
                  />
                </div>

                <div className="pt-4 flex justify-end">
                  <button 
                    type="submit" 
                    disabled={isSubmittingPassword}
                    className={`px-5 py-2 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'} ${isSubmittingPassword ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {isSubmittingPassword ? 'Memperbarui...' : 'Simpan Password'}
                  </button>
                </div>
              </form>
            </div>
          );
        }

        return (
          <div className="space-y-8 max-w-2xl">
            <h2 className="text-xl font-bold mb-6">{t.account}</h2>
            
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 rounded-full overflow-hidden flex-shrink-0 border border-gray-700 bg-gray-800 flex items-center justify-center">
                  {userData?.profile_photo_url ? (
                    <img
                      src={`http://192.168.11.80:8000${userData.profile_photo_url}`}
                      alt="Profile"
                      className="w-full h-full object-cover"
                      onError={(e) => { e.currentTarget.style.display = "none"; }}
                    />
                  ) : userData?.npp ? (
                    <img
                      src={`https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${userData.npp}.jpg`}
                      alt="Profile"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : (
                    <span className={`font-bold ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>AI</span>
                  )}
                </div>
                <div>
                  <h3 className="font-medium text-[15px]">{userData?.name || userData?.nama || "User"}</h3>
                  <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{userData?.email || `${userData?.npp || 'user'}@pindad.co.id`}</p>
                </div>
              </div>
              <button 
                onClick={() => setIsEditingAccount(true)}
                className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-gray-800 hover:bg-gray-700 text-white' : 'bg-gray-200 hover:bg-gray-300 text-black'}`}
              >
                {t.editAccount}
              </button>
            </div>

            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.passwordManagement}</h3>
              </div>
              <button 
                onClick={() => setIsChangingPassword(true)}
                className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-gray-800 hover:bg-gray-700 text-white' : 'bg-gray-200 hover:bg-gray-300 text-black'}`}
              >
                {t.changePassword}
              </button>
            </div>

            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.accountManagement}</h3>
              </div>
              <button 
                onClick={() => {
                  onClose();
                  if (triggerLogout) triggerLogout();
                  else window.location.href = '/login';
                }}
                className="px-4 py-1.5 text-sm font-medium rounded-full border border-red-900/50 text-red-500 hover:bg-red-500/10 transition-colors"
              >
                {t.logoutAccount}
              </button>
            </div>
          </div>
        );
      case "about":
        return (
          <div className="space-y-6 max-w-2xl">
            <h2 className="text-xl font-bold mb-6">{t.about}</h2>
            <div className={`prose max-w-none text-sm leading-relaxed ${darkMode ? 'prose-invert text-gray-300' : 'text-gray-600'}`}>
              <p>
                <strong>CAKRA AI</strong> {t.aboutText1.replace("CAKRA AI ", "")}
              </p>
              <p>
                {t.aboutText2}
              </p>
              <br />
              <h3 className={`text-[15px] font-semibold mt-4 mb-2 ${darkMode ? 'text-white' : 'text-gray-900'}`}>{t.feedbackEmail}</h3>
              <p className={`cursor-pointer hover:underline ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>support@cakra.ai</p>
            </div>
            
            <div className={`flex items-center justify-between py-4 mt-8 border-t ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <h3 className="font-medium text-[14px]">{t.suggestions}</h3>
              <button className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center space-x-2 ${darkMode ? 'bg-white text-black hover:bg-gray-200' : 'bg-black text-white hover:bg-gray-800'}`}>
                <span>📝</span>
                <span>{t.suggestions}</span>
              </button>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
      {/* Modal Container */}
      <div 
        className="w-[90%] max-w-4xl h-[80vh] rounded-2xl flex overflow-hidden shadow-2xl relative animate-slide-up"
        style={{ background: darkMode ? '#27272a' : '#ffffff', color: darkMode ? '#e5e7eb' : '#1f2937' }}
      >
        {/* Close button (X) */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full hover:bg-gray-700/50 transition-colors z-10"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>

        {/* Sidebar */}
        <div className={`w-64 flex-shrink-0 border-r ${darkMode ? 'border-gray-700/50' : 'border-gray-200'} flex flex-col py-6`}
             style={{ background: darkMode ? '#18181b' : '#f9fafb' }}>
          
          <div className="px-6 mb-8 mt-2">
            <h2 className={`text-[11px] font-bold uppercase tracking-wider ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              {t.settingsTitle}
            </h2>
          </div>
          
          <div className="flex-1 overflow-y-auto px-3 space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${
                  activeTab === tab.id 
                    ? (darkMode ? 'bg-gray-800 text-white' : 'bg-gray-200 text-black')
                    : (darkMode ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50' : 'text-gray-600 hover:bg-gray-100')
                }`}
              >
                <span className="opacity-70">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto p-10 pt-16">
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
