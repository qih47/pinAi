import React, { useState, useRef, useEffect } from "react";
import { translations } from "../../../utils/translations";
import { useChatStore, API_BASE } from "../../../stores/chatStore";
import { getApiBase } from "../../../services/endpoints";
import apiClient from "../../../services/apiClient";
import { useChatAuthStore } from "../../../stores/authStore";
import { Mail, Cloud, Lock, LogOut, CheckCircle2, User, KeyRound, ArrowRight } from "lucide-react";

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
  const checkSession = useChatAuthStore((state) => state.checkSession);
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
  const [showSuggestionForm, setShowSuggestionForm] = useState(false);
  const [communicationStyle, setCommunicationStyle] = useState(
    userData?.communication_style || 'formal_saya_anda'
  );
  const [isStyleDropdownOpen, setIsStyleDropdownOpen] = useState(false);
  const voiceDropdownRef = useRef(null);
  const languageDropdownRef = useRef(null);
  const styleDropdownRef = useRef(null);

  useEffect(() => {
    if (userData?.communication_style) {
      setCommunicationStyle(userData.communication_style);
    }
  }, [userData]);

  const handleStyleChange = async (newStyle) => {
    setCommunicationStyle(newStyle);
    setIsStyleDropdownOpen(false);
    try {
      const token = localStorage.getItem('cakra_token') || '';
      await apiClient.put('/user/settings', {
        token,
        settings: {
          communication_style: newStyle
        }
      });
      const updatedUser = { ...(userData || {}), communication_style: newStyle };
      localStorage.setItem('cakra_user', JSON.stringify(updatedUser));
      useChatAuthStore.setState({ user: updatedUser });
    } catch (err) {
      console.error("Failed to update communication style", err);
    }
  };

  // Edit Account State
  const [isEditingAccount, setIsEditingAccount] = useState(false);
  const [editEmail, setEditEmail] = useState("");
  const [editPhoto, setEditPhoto] = useState(null);
  const [editPhotoPreview, setEditPhotoPreview] = useState(null);
  const [editFullname, setEditFullname] = useState("");
  const [editPreferredName, setEditPreferredName] = useState("");
  const [isSubmittingProfile, setIsSubmittingProfile] = useState(false);

  // Integrations State
  const [integrations, setIntegrations] = useState({ mail_connected: false, cloud_connected: false });
  const [connectingType, setConnectingType] = useState(null); // 'mail' | 'cloud' | null
  const [integrationUser, setIntegrationUser] = useState("");
  const [integrationPass, setIntegrationPass] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);

  const fetchIntegrations = async () => {
    try {
      const token = localStorage.getItem('cakra_token') || '';
      if (!token) return;
      const response = await apiClient.get(`/user/integrations?token=${token}`);
      if (response.data?.status === 'success') {
        setIntegrations(response.data.data);
      }
    } catch (err) {
      console.error("Failed to fetch integrations", err);
    }
  };

  useEffect(() => {
    if (isOpen && activeTab === 'account') {
      fetchIntegrations();
    }
  }, [isOpen, activeTab]);

  const handleConnectSubmit = async (e) => {
    e.preventDefault();
    setIsConnecting(true);
    try {
      const endpoint = connectingType === 'mail' ? '/user/integrations/mail' : '/user/integrations/cloud';
      await apiClient.post(endpoint, {
        token: localStorage.getItem('cakra_token') || '',
        username: integrationUser.trim(),
        password: integrationPass.trim()
      });
      await fetchIntegrations();
      setConnectingType(null);
      setIntegrationUser("");
      setIntegrationPass("");
    } catch (err) {
      alert(err.response?.data?.detail || "Gagal menyambungkan " + connectingType);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async (type) => {
    try {
      const endpoint = type === 'mail' ? '/user/integrations/mail' : '/user/integrations/cloud';
      await apiClient.delete(`${endpoint}?token=${localStorage.getItem('cakra_token') || ''}`);
      await fetchIntegrations();
    } catch (err) {
      console.error("Failed to disconnect", err);
    }
  };

  useEffect(() => {
    if (userData) {
      setEditFullname(userData.fullname || "");
      setEditPreferredName(userData.preferred_name || "");
      setEditEmail(userData.email || "");
    }
  }, [userData]);

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
      if (styleDropdownRef.current && !styleDropdownRef.current.contains(e.target)) {
        setIsStyleDropdownOpen(false);
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
        await checkSession();
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
    {
      id: "general", label: t.general, icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      )
    },
    {
      id: "account", label: t.account, icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      )
    },
    {
      id: "about", label: t.about, icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
      )
    }
  ];

  const handleTestVoice = async () => {
    if (isPlayingTest) return;
    setIsPlayingTest(true);

    try {
      if (ttsVoice.startsWith('id-ID-')) {
        // Gunakan file statis untuk suara Indonesia agar tidak perlu generate
        const response = await apiClient.get(`/voice/test/${ttsVoice}`, {
          responseType: 'blob'
        });
        
        const url = URL.createObjectURL(response.data);
        
        if (audioRef.current) {
          audioRef.current.src = url;
          audioRef.current.play();
          audioRef.current.onended = () => {
            setIsPlayingTest(false);
            URL.revokeObjectURL(url);
          };
          audioRef.current.onerror = (e) => {
            console.error("Gagal memutar contoh suara statis:", e);
            setIsPlayingTest(false);
            URL.revokeObjectURL(url);
          };
        }
      } else {
        // Fallback generate TTS untuk suara bahasa Inggris
        const sampleText = "Hello, this is a sample of my voice using artificial intelligence technology.";
        const response = await apiClient.post('/voice/tts', {
          text: sampleText,
          voice: ttsVoice,
          speed: ttsSpeed
        }, { responseType: 'blob', timeout: 120000 });

        const url = URL.createObjectURL(response.data);

        if (audioRef.current) {
          audioRef.current.src = url;
          audioRef.current.play();
          audioRef.current.onended = () => {
            setIsPlayingTest(false);
            URL.revokeObjectURL(url);
          };
        }
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

            {/* Communication Style / Gaya Bahasa */}
            <div className={`flex items-center justify-between py-4 border-b ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <div>
                <h3 className="font-medium text-[14px]">{t.communicationStyle}</h3>
              </div>
              <div className="relative" ref={styleDropdownRef}>
                <button
                  onClick={() => setIsStyleDropdownOpen(!isStyleDropdownOpen)}
                  className={`flex items-center justify-between text-sm border rounded-lg px-3 py-2 outline-none w-[190px] transition-all ${darkMode ? 'bg-[#18181b] border-gray-700 hover:border-gray-500 text-gray-200' : 'bg-gray-50 border-gray-300 hover:border-gray-400 text-gray-700'} ${isStyleDropdownOpen ? (darkMode ? 'border-gray-500 ring-2 ring-gray-700' : 'border-gray-400 ring-2 ring-gray-200') : ''}`}
                >
                  <span className="truncate text-left">
                    {communicationStyle === 'informal_gue_lo' && t.commStyleCasual}
                    {communicationStyle === 'familiar_aku_kamu' && t.commStyleFriendly}
                    {communicationStyle === 'adaptive_mirroring' && t.commStyleAdaptive}
                    {(!communicationStyle || communicationStyle === 'formal_saya_anda') && t.commStyleFormal}
                  </span>
                  <svg className={`w-4 h-4 ml-2 flex-shrink-0 transition-transform duration-200 ${isStyleDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {isStyleDropdownOpen && (
                  <div className={`absolute right-0 mt-2 w-[190px] rounded-xl shadow-xl border overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200 ${darkMode ? 'bg-[#18181b] border-gray-700 shadow-black/50' : 'bg-white border-gray-200 shadow-gray-200/50'}`}>
                    <div className="py-2">
                      <button
                        onClick={() => handleStyleChange('formal_saya_anda')}
                        className={`w-full text-left px-3.5 py-2 text-sm truncate transition-colors ${(!communicationStyle || communicationStyle === 'formal_saya_anda') ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                      >
                        {t.commStyleFormal}
                      </button>
                      <button
                        onClick={() => handleStyleChange('informal_gue_lo')}
                        className={`w-full text-left px-3.5 py-2 text-sm truncate transition-colors ${communicationStyle === 'informal_gue_lo' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                      >
                        {t.commStyleCasual}
                      </button>
                      <button
                        onClick={() => handleStyleChange('familiar_aku_kamu')}
                        className={`w-full text-left px-3.5 py-2 text-sm truncate transition-colors ${communicationStyle === 'familiar_aku_kamu' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                      >
                        {t.commStyleFriendly}
                      </button>
                      <button
                        onClick={() => handleStyleChange('adaptive_mirroring')}
                        className={`w-full text-left px-3.5 py-2 text-sm truncate transition-colors ${communicationStyle === 'adaptive_mirroring' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                      >
                        {t.commStyleAdaptive}
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
                      {ttsVoice === 'id-ID-Pria1' && `CAKRA (ID) - ${t.male} 1`}
                      {ttsVoice === 'id-ID-Pria2' && `CAKRA (ID) - ${t.male} 2`}
                      {ttsVoice === 'id-ID-Wanita1' && `CAKRA (ID) - ${t.female} 1`}
                      {ttsVoice === 'id-ID-Wanita2' && `CAKRA (ID) - ${t.female} 2`}

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
                        <div className={`px-3 py-1.5 text-xs font-semibold ${darkMode ? 'text-gray-400 bg-gray-800/50' : 'text-gray-500 bg-gray-100'} uppercase tracking-wider`}>
                          Bahasa Indonesia (CAKRA F5)
                        </div>
                        <button
                          onClick={() => { setTtsVoice('id-ID-Pria1'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between ${ttsVoice === 'id-ID-Pria1' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          CAKRA (ID) - {t.male} 1
                        </button>
                        <button
                          onClick={() => { setTtsVoice('id-ID-Pria2'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between ${ttsVoice === 'id-ID-Pria2' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          CAKRA (ID) - {t.male} 2
                        </button>
                        <button
                          onClick={() => { setTtsVoice('id-ID-Wanita1'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between ${ttsVoice === 'id-ID-Wanita1' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          CAKRA (ID) - {t.female} 1
                        </button>
                        <button
                          onClick={() => { setTtsVoice('id-ID-Wanita2'); setIsVoiceDropdownOpen(false); }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between ${ttsVoice === 'id-ID-Wanita2' ? (darkMode ? 'bg-blue-500/10 text-blue-400 font-medium' : 'bg-blue-50 text-blue-600 font-medium') : (darkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-50')}`}
                        >
                          CAKRA (ID) - {t.female} 2
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
                        src={editPhotoPreview || (userData?.profile_photo_url ? `${getApiBase()}${userData.profile_photo_url}` : '')}
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
          <div className="space-y-6 max-w-3xl">
            {/* Header Hero Section */}
            <div className="relative py-2 mb-2">
              <div className="relative flex items-center justify-between z-10">
                <div className="flex items-center space-x-5">
                  <div className={`w-16 h-16 rounded-full overflow-hidden flex-shrink-0 ${darkMode ? 'bg-gray-800' : 'bg-gray-200'} shadow-sm flex items-center justify-center`}>
                    {userData?.profile_photo_url ? (
                      <img
                        src={`${getApiBase()}${userData.profile_photo_url}`}
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
                      <User size={28} className={darkMode ? 'text-gray-500' : 'text-gray-400'} />
                    )}
                  </div>
                  <div>
                    <h3 className={`text-lg font-bold ${darkMode ? 'text-white' : 'text-gray-900'}`}>{userData?.name || userData?.nama || "User"}</h3>
                    <p className={`text-sm mt-0.5 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{userData?.email || `${userData?.npp || 'user'}@pindad.co.id`}</p>
                    <div className="flex items-center mt-2 space-x-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-500/10 text-green-500 border border-green-500/20">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5"></span>
                        Active
                      </span>
                      {userData?.divisi && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${darkMode ? 'bg-gray-700/50 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
                          {userData.divisi}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setIsEditingAccount(true)}
                  className={`px-4 py-2 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-gray-800 hover:bg-gray-700 text-white' : 'bg-gray-200 hover:bg-gray-300 text-gray-900'}`}
                >
                  {t.editAccount}
                </button>
              </div>
            </div>

            {/* Linked Accounts */}
            <div>
              <h3 className={`font-semibold text-sm mb-4 px-1 uppercase tracking-wider ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{t.linkedAccounts}</h3>
              <div className="space-y-2">
                
                {/* Zimbra Mail List Row */}
                <div className="flex flex-col transition-all duration-300">
                  <div className="flex items-center justify-between py-3">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2.5 rounded-xl ${darkMode ? 'bg-blue-500/10 text-blue-400' : 'bg-blue-50 text-blue-600'}`}>
                        <Mail size={20} strokeWidth={1.5} />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h4 className={`font-medium text-[15px] ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>{t.mailPindad}</h4>
                          {integrations.mail_connected && <CheckCircle2 size={16} className="text-green-500" />}
                        </div>
                        <p className={`text-xs mt-0.5 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Smart Mail (Zimbra)</p>
                      </div>
                    </div>
                    <div>
                      {integrations.mail_connected ? (
                        <button onClick={() => handleDisconnect('mail')} className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-gray-800 hover:bg-gray-700 text-gray-300' : 'bg-gray-200 hover:bg-gray-300 text-gray-700'}`}>{t.disconnect}</button>
                      ) : connectingType === 'mail' ? (
                         null
                      ) : (
                        <button onClick={() => { setConnectingType('mail'); setIntegrationUser(userData?.email || (userData?.npp ? `${userData.npp}@pindad.com` : "")); }} className={`px-4 py-1.5 flex items-center justify-center space-x-2 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20' : 'bg-blue-50 text-blue-600 hover:bg-blue-100'}`}>
                          <span>{t.connect}</span>
                          <ArrowRight size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                  {/* Expandable Form */}
                  <div className={`overflow-hidden transition-all duration-300 ${connectingType === 'mail' ? 'max-h-64 mt-2 mb-2 opacity-100 pl-[3.25rem]' : 'max-h-0 opacity-0'}`}>
                    <form onSubmit={handleConnectSubmit} className="space-y-3 max-w-sm">
                      <input type="text" placeholder="Username" value={integrationUser} onChange={e => setIntegrationUser(e.target.value)} required className={`w-full px-3 py-2 text-sm rounded-xl border ${darkMode ? 'bg-gray-900/50 border-gray-700 text-white focus:border-blue-500' : 'bg-white border-gray-200 text-black focus:border-blue-500'} outline-none transition-all`} />
                      <input type="password" placeholder="Password" value={integrationPass} onChange={e => setIntegrationPass(e.target.value)} required className={`w-full px-3 py-2 text-sm rounded-xl border ${darkMode ? 'bg-gray-900/50 border-gray-700 text-white focus:border-blue-500' : 'bg-white border-gray-200 text-black focus:border-blue-500'} outline-none transition-all`} />
                      <div className="flex space-x-2 pt-1">
                        <button type="button" onClick={() => setConnectingType(null)} className={`flex-1 py-1.5 text-sm font-medium rounded-xl transition-colors ${darkMode ? 'bg-gray-700 hover:bg-gray-600 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'}`}>Batal</button>
                        <button type="submit" disabled={isConnecting} className="flex-1 py-1.5 text-sm font-medium rounded-xl bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors shadow-sm">{isConnecting ? "Verifying..." : t.connect}</button>
                      </div>
                    </form>
                  </div>
                </div>

                {/* Nextcloud List Row */}
                <div className="flex flex-col transition-all duration-300">
                  <div className="flex items-center justify-between py-3">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2.5 rounded-xl ${darkMode ? 'bg-indigo-500/10 text-indigo-400' : 'bg-indigo-50 text-indigo-600'}`}>
                        <Cloud size={20} strokeWidth={1.5} />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h4 className={`font-medium text-[15px] ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>{t.cloudPindad}</h4>
                          {integrations.cloud_connected && <CheckCircle2 size={16} className="text-green-500" />}
                        </div>
                        <p className={`text-xs mt-0.5 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Nextcloud WebDAV</p>
                      </div>
                    </div>
                    <div>
                      {integrations.cloud_connected ? (
                        <button onClick={() => handleDisconnect('cloud')} className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-gray-800 hover:bg-gray-700 text-gray-300' : 'bg-gray-200 hover:bg-gray-300 text-gray-700'}`}>{t.disconnect}</button>
                      ) : connectingType === 'cloud' ? (
                         null
                      ) : (
                        <button onClick={() => { setConnectingType('cloud'); setIntegrationUser(userData?.email || (userData?.npp ? `${userData.npp}@pindad.com` : "")); }} className={`px-4 py-1.5 flex items-center justify-center space-x-2 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20' : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'}`}>
                          <span>{t.connect}</span>
                          <ArrowRight size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                  {/* Expandable Form */}
                  <div className={`overflow-hidden transition-all duration-300 ${connectingType === 'cloud' ? 'max-h-64 mt-2 mb-2 opacity-100 pl-[3.25rem]' : 'max-h-0 opacity-0'}`}>
                    <form onSubmit={handleConnectSubmit} className="space-y-3 max-w-sm">
                      <input type="text" placeholder="Username" value={integrationUser} onChange={e => setIntegrationUser(e.target.value)} required className={`w-full px-3 py-2 text-sm rounded-xl border ${darkMode ? 'bg-gray-900/50 border-gray-700 text-white focus:border-indigo-500' : 'bg-white border-gray-200 text-black focus:border-indigo-500'} outline-none transition-all`} />
                      <input type="password" placeholder="Password" value={integrationPass} onChange={e => setIntegrationPass(e.target.value)} required className={`w-full px-3 py-2 text-sm rounded-xl border ${darkMode ? 'bg-gray-900/50 border-gray-700 text-white focus:border-indigo-500' : 'bg-white border-gray-200 text-black focus:border-indigo-500'} outline-none transition-all`} />
                      <div className="flex space-x-2 pt-1">
                        <button type="button" onClick={() => setConnectingType(null)} className={`flex-1 py-1.5 text-sm font-medium rounded-xl transition-colors ${darkMode ? 'bg-gray-700 hover:bg-gray-600 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'}`}>Batal</button>
                        <button type="submit" disabled={isConnecting} className="flex-1 py-1.5 text-sm font-medium rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 transition-colors shadow-sm">{isConnecting ? "Verifying..." : t.connect}</button>
                      </div>
                    </form>
                  </div>
                </div>
              </div>
            </div>

            {/* Security & Danger Zone */}
            <div className="mt-8">
              <h3 className={`font-semibold text-sm mb-4 px-1 uppercase tracking-wider ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Security & Access</h3>
              <div className="space-y-2">
                {/* Ubah Password */}
                <div className={`flex items-center justify-between py-3 transition-colors`}>
                  <div className="flex items-center space-x-4">
                    <div className={`p-2.5 rounded-xl ${darkMode ? 'bg-gray-700/50 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
                      <KeyRound size={20} strokeWidth={1.5} />
                    </div>
                    <div>
                      <h4 className={`font-medium text-[15px] ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>{t.passwordManagement}</h4>
                      <p className={`text-xs mt-0.5 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Perbarui kata sandi akun Cakra Anda</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setIsChangingPassword(true)}
                    className={`px-4 py-2 text-sm font-medium rounded-xl transition-all duration-200 ${darkMode ? 'bg-gray-700 hover:bg-gray-600 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-800'}`}
                  >
                    {t.changePassword}
                  </button>
                </div>
                
                {/* Logout */}
                <div className={`flex items-center justify-between py-3 transition-colors group`}>
                  <div className="flex items-center space-x-4">
                    <div className={`p-2.5 rounded-xl ${darkMode ? 'bg-red-500/10 text-red-400 group-hover:bg-red-500/20 group-hover:text-red-500' : 'bg-red-50 text-red-500 group-hover:bg-red-100'} transition-colors`}>
                      <LogOut size={20} strokeWidth={1.5} />
                    </div>
                    <div>
                      <h4 className={`font-medium text-[15px] ${darkMode ? 'text-red-400' : 'text-red-600'}`}>{t.accountManagement}</h4>
                      <p className={`text-xs mt-0.5 ${darkMode ? 'text-gray-400 group-hover:text-red-400/70' : 'text-gray-500 group-hover:text-red-500/70'}`}>Keluar dari perangkat ini</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      onClose();
                      if (triggerLogout) triggerLogout();
                      else window.location.href = '/login';
                    }}
                    className={`px-4 py-2 text-sm font-medium rounded-full transition-colors ${darkMode ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20' : 'bg-red-50 text-red-600 hover:bg-red-100'}`}
                  >
                    {t.logoutAccount}
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      case "about":
        return (
          <div className="space-y-6 max-w-2xl">
            <h2 className="text-xl font-bold mb-6">{t.about}</h2>
            <div className={`prose max-w-none text-sm leading-relaxed text-justify ${darkMode ? 'prose-invert text-gray-300' : 'text-gray-600'}`}>
              <p>
                <strong>CAKRA AI</strong> {t.aboutText1.replace("CAKRA AI ", "")}
              </p>
              <p>
                {t.aboutText2}
              </p>
              <br />
              <h3 className={`text-[15px] font-semibold mt-4 mb-2 ${darkMode ? 'text-white' : 'text-gray-900'}`}>{t.feedbackEmail}</h3>
              <a href="mailto:qisthih@pindad.com" className={`cursor-pointer hover:underline ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>qisthih@pindad.com</a>
            </div>

            {/* Tombol Saran */}
            <div className={`flex items-center justify-between py-4 mt-8 border-t ${darkMode ? 'border-gray-700/50' : 'border-gray-200'}`}>
              <h3 className="font-medium text-[14px]">{t.suggestions}</h3>
              <button 
                onClick={() => setShowSuggestionForm(true)}
                className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center space-x-2 ${darkMode ? 'bg-white text-black hover:bg-gray-200' : 'bg-black text-white hover:bg-gray-800'}`}
              >
                <span>📝</span>
                <span>{t.suggestions}</span>
              </button>
            </div>

            {/* Popup Form Saran */}
            {showSuggestionForm && (
              <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm" style={{ padding: '20px' }}>
                <div className={`w-full max-w-md p-6 rounded-2xl shadow-2xl ${darkMode ? 'bg-[#1e1e22] text-white border border-gray-800' : 'bg-white text-gray-900 border border-gray-200'}`}>
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-bold">{t.sendSuggestion}</h2>
                    <button 
                      onClick={() => setShowSuggestionForm(false)}
                      className={`p-2 rounded-full transition-colors ${darkMode ? 'hover:bg-white/10' : 'hover:bg-black/5'}`}
                    >
                      ✕
                    </button>
                  </div>
                  <form 
                    onSubmit={async (e) => {
                      e.preventDefault();
                      
                      if (!integrations.mail_connected) {
                        alert(language === 'id' ? "Silakan hubungkan akun Zimbra Anda terlebih dahulu di menu Umum (Integrasi)." : "Please connect your Zimbra account in the General menu first.");
                        setShowSuggestionForm(false);
                        setActiveTab("general");
                        return;
                      }

                      const subject = e.target.subject.value;
                      const message = e.target.message.value;
                      
                      try {
                        const token = localStorage.getItem('cakra_token') || '';
                        const res = await apiClient.post('/corporate/emails/reply', {
                          token: token,
                          to: "qisthih@pindad.com",
                          subject: subject,
                          body: message
                        });
                        
                        if (res.data?.status === 'success') {
                          alert(language === 'id' ? "Saran berhasil dikirim via Zimbra!" : "Suggestion sent successfully via Zimbra!");
                        } else {
                          alert((language === 'id' ? "Gagal mengirim saran: " : "Failed to send: ") + res.data?.detail);
                        }
                      } catch (error) {
                        alert((language === 'id' ? "Gagal mengirim saran: " : "Failed to send: ") + error.message);
                      }
                      
                      setShowSuggestionForm(false);
                    }}
                    className="space-y-4"
                  >
                    <div>
                      <input 
                        type="text" 
                        name="subject"
                        required
                        placeholder={t.suggestionSubjectPlaceholder}
                        className={`w-full px-4 py-3 text-sm rounded-xl border ${darkMode ? 'bg-[#18181b] border-gray-700/50 text-white focus:border-blue-500' : 'bg-gray-50 border-gray-200 focus:border-blue-500'} focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-colors`}
                      />
                    </div>
                    <div>
                      <textarea 
                        name="message"
                        required
                        rows="4"
                        placeholder={t.suggestionMessagePlaceholder}
                        className={`w-full px-4 py-3 text-sm rounded-xl border resize-none ${darkMode ? 'bg-[#18181b] border-gray-700/50 text-white focus:border-blue-500' : 'bg-gray-50 border-gray-200 focus:border-blue-500'} focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-colors`}
                      ></textarea>
                    </div>
                    <div className="flex justify-end pt-2">
                      <button 
                        type="submit"
                        className={`w-full py-3 text-sm font-semibold rounded-xl transition-colors flex justify-center items-center space-x-2 ${darkMode ? 'bg-white text-black hover:bg-gray-200' : 'bg-black text-white hover:bg-gray-800'}`}
                      >
                        <span>✉️</span>
                        <span>{t.openEmailAndSend}</span>
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
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
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${activeTab === tab.id
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
