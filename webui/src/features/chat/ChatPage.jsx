import React, { useState, useRef, useEffect } from 'react';
import { useChatStore, API_BASE } from '../../stores/chatStore';
import cakraLogo from '../../assets/cakra.png';
import { styles, lightColors, darkColors } from './chatPage.styles';
import ChatArea from './components/ChatArea';
import GuestWelcome from '../../components/ui/GuestWelcome';
import Sidebar from './components/Sidebar';
import { useNavigate, useParams } from 'react-router-dom';
import { useChatAuthStore } from '../../stores/authStore';

export default function ChatPage({ isGuest, isLoggedIn: propsIsLoggedIn, userData: propsUserData, getGreeting }) {
  const [input, setInput] = useState('');
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const authUser = useChatAuthStore((state) => state.user);
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);
  const logout = useChatAuthStore((state) => state.logout);

  const activeIsolatedTitle = useChatStore((state) => state.activeIsolatedTitle);
  const setContextIsolation = useChatStore((state) => state.setContextIsolation);

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // STATE: Deteksi apakah textarea sudah multi-line untuk urusan layout form
  const [isMultiLine, setIsMultiLine] = useState(false);
  const [chatMode, setChatMode] = useState('auto');
  // REF: Capture tinggi baseline 1 baris saat mount pertama
  const baselineHeightRef = useRef(0);

  const stagedAttachments = useChatStore((state) => state.stagedAttachments);
  const setStagedAttachments = useChatStore((state) => state.setStagedAttachments);

  const currentIsLoggedIn = propsIsLoggedIn !== undefined ? propsIsLoggedIn : isAuthenticated;
  const currentUserData = propsUserData || {
    name: authUser?.name || 'Pegawai Pindad',
    npp: authUser?.npp || 'NPP ------',
    divisi: authUser?.divisi || 'Pegawai Resmi',
    role: authUser?.role || 'user'
  };

  const activeSessionId = sessionId && sessionId !== 'new' ? sessionId : null;

  const removeFilePreview = (indexToRemove) => {
    setSelectedFiles(prev => prev.filter((_, idx) => idx !== indexToRemove));
  };

  // 🔥 2. RENDER LOCAL SAJA (TIDAK LANGSUNG UPLOAD KE SERVER)
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    const limit = isGuest || !currentIsLoggedIn ? 1 : 5;
    const availableSlots = limit - selectedFiles.length;
    const targets = files.slice(0, availableSlots);

    if (targets.length === 0) {
      alert(`Slot penuh! Maksimal ${limit} file.`);
      return;
    }

    setSelectedFiles(prev => [...prev, ...targets]);
  };

  // 🔥 2. PASTE IMAGE: Masuk state local untuk preview, bukan ke API port 5000
  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageItems = Array.from(items).filter(item => item.type.startsWith('image/'));
    if (imageItems.length === 0) return;
    e.preventDefault();

    const limit = isGuest || !currentIsLoggedIn ? 1 : 5;
    const availableSlots = limit - selectedFiles.length;
    const targets = imageItems.slice(0, availableSlots);

    const newFiles = [];
    for (const item of targets) {
      const file = item.getAsFile();
      if (file) {
        const uniqueFile = new File([file], `pasted-image-${Date.now()}-${Math.random().toString(36).substr(2, 9)}.png`, {
          type: file.type
        });
        newFiles.push(uniqueFile);
      }
    }
    if (newFiles.length === 0) return;

    setSelectedFiles(prev => [...prev, ...newFiles]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  // 🔥 2. DRAG DROP: Simpan file fisik di web dulu, upload pas klik kirim
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files).filter(file =>
      file.type.startsWith('image/') || file.type === 'application/pdf'
    );
    if (files.length === 0) {
      alert("Hanya bisa upload gambar atau PDF");
      return;
    }

    const limit = isGuest || !currentIsLoggedIn ? 1 : 5;
    const availableSlots = limit - selectedFiles.length;
    const targets = files.slice(0, availableSlots);
    if (targets.length === 0) {
      alert(`Slot penuh! Maksimal ${limit} file.`);
      return;
    }

    setSelectedFiles(prev => [...prev, ...targets]);
  };

  const [darkMode, setDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem('cakra-theme');
    if (savedTheme !== null) return savedTheme === 'dark';
    if (window.matchMedia) return window.matchMedia('(prefers-color-scheme: dark)').matches;
    return false;
  });

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showDocumentList, setShowDocumentList] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const lastLoadedSessionRef = useRef(null);

  const {
    messages,
    isStreaming,
    isLoading,
    currentThinking,
    sendMessage,
    clearChat: storeClearChat,
    loadChatSession: storeLoadChatSession
  } = useChatStore();

  useEffect(() => {
    if (!sessionId || sessionId === 'new') {
      lastLoadedSessionRef.current = null;
      return;
    }
    if (isStreaming) return;
    if (lastLoadedSessionRef.current === sessionId) return;
    lastLoadedSessionRef.current = sessionId;
    storeLoadChatSession(sessionId);
  }, [sessionId, isStreaming, storeLoadChatSession]);

  const loadChatSession = (id) => {
    if (!id || id === 'new' || id === sessionId) return;
    lastLoadedSessionRef.current = null;
    navigate(`/chat/${id}`);
  };

  const handleClearChat = () => {
    storeClearChat();
    lastLoadedSessionRef.current = null;
    navigate('/chat/new');
  };

  useEffect(() => {
    if (!isGuest && currentIsLoggedIn && sessionId && sessionId !== 'new') {
      localStorage.setItem('cakra_last_session', sessionId);
    }
  }, [sessionId, isGuest, currentIsLoggedIn]);

  const triggerLogout = () => {
    logout();
    window.location.href = '/login';
  };

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      const savedTheme = localStorage.getItem('cakra-theme');
      if (savedTheme === null) setDarkMode(e.matches);
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  useEffect(() => {
    localStorage.setItem('cakra-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const theme = darkMode ? darkColors : lightColors;

  const lastAssistantIndex = [...messages].reverse().findIndex(m => m.role === 'assistant');
  const isThinking = isStreaming && lastAssistantIndex === 0 && messages[messages.length - 1]?.content === '';
  const isStreamingText = isStreaming && lastAssistantIndex === 0 && messages[messages.length - 1]?.content !== '';
  const isEmptyChat = messages.length === 0;
  const showWelcome = isEmptyChat && !isLoading;

  // CAPTURE BASELINE HEIGHT SEKALI SAAT MOUNT
  useEffect(() => {
    if (textareaRef.current && baselineHeightRef.current === 0) {
      textareaRef.current.style.height = 'auto';
      baselineHeightRef.current = textareaRef.current.scrollHeight;
    }
  }, []);

  // 🔥 3. DINAMIS AUTO HEIGHT FIX: Kalkulasi tinggi DOM asli secara linear tanpa remounting komponen
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset paksa ke titik nol
      const currentScrollHeight = textareaRef.current.scrollHeight;

      // Berikan tinggi aktualDOM langsung ke element style textarea
      textareaRef.current.style.height = `${currentScrollHeight}px`;

      const baseline = baselineHeightRef.current;
      if (baseline > 0) {
        setIsMultiLine(currentScrollHeight > baseline + 3);
      }
    }
  }, [input]);

  // 🔥 2. PROSES UPLOAD DIJALANKAN DI SINI SAAT TOMBOL SEND DI-KLIK
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if ((!input.trim() && selectedFiles.length === 0) || isStreaming || isUploadingFile) return;

    let finalStagedData = [];

    if (selectedFiles.length > 0) {
      setIsUploadingFile(true);

      let uploadSessionUuid = activeSessionId || useChatStore.getState().sessionUuid;
      if (!uploadSessionUuid || uploadSessionUuid === 'new') {
        const created = await useChatStore.getState().createNewSession(
          isGuest ? null : currentUserData?.npp
        );
        if (created) {
          uploadSessionUuid = created;
          if (!isGuest && currentIsLoggedIn) {
            lastLoadedSessionRef.current = created;
            navigate(`/chat/${created}`, { replace: true });
          }
        }
      }

      const formData = new FormData();
      selectedFiles.forEach(file => formData.append("files", file));
      if (uploadSessionUuid) formData.append("session_uuid", uploadSessionUuid);

      try {
        const response = await fetch(`${API_BASE}/api/chat/documents/upload`, {
          method: "POST",
          body: formData,
        });
        if (!response.ok) throw new Error("Gagal mengunggah berkas");
        const result = await response.json();

        if (result.status === "success") {
          finalStagedData = result.data;
          setStagedAttachments(result.data); // Tetap simpan ke store untuk backup state
        }
      } catch (err) {
        console.error(err);
        alert("Gagal memproses pengiriman karena upload file error, bolo!");
        setIsUploadingFile(false);
        return; // Hentikan pipeline agar chat tidak terkirim pincang tanpa file
      } finally {
        setIsUploadingFile(false);
      }
    }

    // 🔥 PERBAIKAN ESENSIAL: Oper parameter data file terupload langsung ke fungsi sendMessage
    sendMessage(
      input,
      isGuest ? null : currentUserData?.npp,
      isGuest ? null : (newSessionObj) => {
        setChatHistory(prev => [newSessionObj, ...prev]);
        lastLoadedSessionRef.current = newSessionObj.session_uuid;
        navigate(`/chat/${newSessionObj.session_uuid}`, { replace: true });
      },
      finalStagedData, // Injeksi langsung datanya kesini, bolo!
      chatMode // 🔥 PARAMETER MODE: 'auto' | 'documents' (siap dikirim ke backend)
    );

    setInput('');
    setSelectedFiles([]);
    setStagedAttachments([]);
    setIsMultiLine(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const defaultGetGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return 'SELAMAT PAGI';
    if (hour < 15) return 'SELAMAT SIANG';
    if (hour < 19) return 'SELAMAT SORE';
    return 'SELAMAT MALAM';
  };

  const CustomModeSelector = ({ value, onChange, disabled, darkMode }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);
  
    useEffect(() => {
      const handleClickOutside = (event) => {
        if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
          setIsOpen(false);
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);
  
    const options = [
      { value: 'auto', label: 'Auto' },
      { value: 'documents', label: 'Documents' }
    ];
  
    const selectedOption = options.find(opt => opt.value === value);
  
    return (
      <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-block' }}>
        <button
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          style={{
            background: darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
            border: 'none',
            borderRadius: '20px',
            padding: '6px 20px',
            fontSize: '13px',
            fontWeight: 500,
            color: darkMode ? '#e2e8f0' : '#1f2937',
            cursor: disabled ? 'not-allowed' : 'pointer',
            outline: 'none',
            transition: 'all 0.15s',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            opacity: disabled ? 0.5 : 1
          }}
          onMouseEnter={(e) => {
            if (!disabled) {
              e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)';
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)';
          }}
        >
          <span>{selectedOption?.label}</span>
          <svg 
            width="12" 
            height="12" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2"
            style={{ 
              transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s'
            }}
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
  
        {isOpen && (
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: '4px',
            background: darkMode ? '#1e1e20' : '#ffffff',
            border: `1px solid ${darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
            borderRadius: '8px',
            boxShadow: darkMode 
              ? '0 4px 12px rgba(0,0,0,0.5)' 
              : '0 4px 12px rgba(0,0,0,0.15)',
            minWidth: '120px',
            zIndex: 1000,
            overflow: 'hidden',
            animation: 'fadeInUp 0.15s ease-out'
          }}>
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: value === option.value 
                    ? (darkMode ? 'rgba(99, 102, 241, 0.15)' : 'rgba(99, 102, 241, 0.1)')
                    : 'transparent',
                  border: 'none',
                  color: darkMode ? '#e2e8f0' : '#1f2937',
                  fontSize: '13px',
                  fontWeight: value === option.value ? 600 : 400,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  transition: 'background 0.1s'
                }}
                onMouseEnter={(e) => {
                  if (value !== option.value) {
                    e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = value === option.value 
                    ? (darkMode ? 'rgba(99, 102, 241, 0.15)' : 'rgba(99, 102, 241, 0.1)')
                    : 'transparent';
                }}
              >
                <span>{option.label}</span>
                {value === option.value && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  const PlusButton = () => (
    <button
      type="button"
      onClick={() => fileInputRef.current?.click()}
      disabled={isStreaming || isUploadingFile}
      style={{
        background: selectedFiles.length > 0
          ? (darkMode ? 'rgba(99, 102, 241, 0.2)' : 'rgba(37, 99, 235, 0.1)')
          : 'transparent',
        border: 'none',
        borderRadius: '50%',
        width: '36px',
        height: '36px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        color: selectedFiles.length > 0 ? (darkMode ? '#818cf8' : '#2563eb') : (darkMode ? '#9ca3af' : '#6b7280'),
        cursor: isStreaming ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s ease'
      }}
      onMouseEnter={(e) => { if (!isStreaming) e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = selectedFiles.length > 0 ? (darkMode ? 'rgba(99, 102, 241, 0.2)' : 'rgba(37, 99, 235, 0.1)') : 'transparent'; }}
      title="Lampirkan Berkas (PDF / Gambar) atau Paste (Ctrl+V) atau Drag-Drop"
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    </button>
  );

  const SendButton = () => (
    <button
      type="submit"
      disabled={isStreaming || isUploadingFile || (!input.trim() && selectedFiles.length === 0)}
      style={{
        ...styles.sendBtn,
        background: theme.sendBtnBg,
        color: theme.sendBtnText,
        opacity: isStreaming || isUploadingFile || (!input.trim() && selectedFiles.length === 0) ? 0.35 : 1,
        cursor: (isStreaming || isUploadingFile) ? 'not-allowed' : 'pointer',
        border: 'none',
        borderRadius: '50%',
        width: '36px',
        height: '36px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
      }}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="19" x2="12" y2="5" />
        <polyline points="5 12 12 5 19 12" />
      </svg>
    </button>
  );

  const renderInputForm = (isCentered = false) => (
    <div style={{
      ...styles.inputArea,
      background: isCentered ? 'transparent' : `linear-gradient(to bottom, transparent 0%, ${theme.inputAreaBg} 30%)`,
      padding: isCentered ? '0' : undefined,
      flexShrink: 0,
      width: '100%',
      maxWidth: isCentered ? '700px' : undefined,
      marginTop: isCentered ? '24px' : undefined
    }}>
      <div style={styles.inputContainer}>
        {activeIsolatedTitle && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: darkMode ? 'rgba(99, 102, 241, 0.15)' : 'rgba(37, 99, 235, 0.08)',
            border: `1px solid ${darkMode ? '#6366f1' : '#2563eb'}`,
            borderRadius: '12px',
            padding: '8px 16px',
            marginBottom: '10px',
            fontSize: '13px',
            fontWeight: 500,
            color: darkMode ? '#a5b4fc' : '#1e3a8a'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
              <span>🔒</span>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Mode Fokus: Menanyai isi <strong>{activeIsolatedTitle}</strong>
              </span>
            </div>
            <button
              type="button"
              onClick={() => setContextIsolation(null, null)}
              style={{ background: 'transparent', border: 'none', color: darkMode ? '#9ca3af' : '#4b5563', cursor: 'pointer', fontWeight: 'bold' }}
            >
              ✕
            </button>
          </div>
        )}

        {/* 🔥 FIX RENDER PREVIEW DI ATAS FORM: Diubah menjadi thumbnail rounded ala Gemini sejati */}
        {selectedFiles.length > 0 && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '10px',
            marginBottom: '12px',
            padding: '4px 6px',
            width: '100%'
          }}>
            {selectedFiles.map((file, idx) => {
              const isPDF = file.name.endsWith('.pdf');
              return (
                <div key={idx} style={{
                  position: 'relative',
                  width: '64px',
                  height: '64px',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  background: darkMode ? '#2d2d30' : '#f3f4f6',
                  border: `1px solid ${darkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {isPDF ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
                      <span style={{ fontSize: '24px' }}>📄</span>
                      <span style={{
                        fontSize: '9px',
                        fontWeight: 700,
                        color: '#ef4444',
                        maxWidth: '52px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>PDF</span>
                    </div>
                  ) : (
                    <img
                      src={URL.createObjectURL(file)}
                      alt="preview"
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => removeFilePreview(idx)}
                    style={{
                      position: 'absolute',
                      top: '2px',
                      right: '2px',
                      background: 'rgba(0,0,0,0.6)',
                      border: 'none',
                      borderRadius: '50%',
                      width: '16px',
                      height: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#ffffff',
                      fontSize: '9px',
                      cursor: 'pointer',
                      fontWeight: 'bold',
                      zIndex: 2
                    }}
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* 🔥 SASIS UTAMA FORM TUNGGAL: Menggunakan textarea mutlak di luar conditional re-mount React */}
        <form
          onSubmit={handleSubmit}
          onPaste={handlePaste}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          style={{
            ...styles.inputForm,
            background: theme.inputBg,
            borderColor: isDragOver ? (darkMode ? '#6366f1' : '#2563eb') : theme.inputBorder,
            borderWidth: isDragOver ? '2px' : '1px',
            borderStyle: isDragOver ? 'dashed' : 'solid',
            boxShadow: theme.inputShadow,
            display: 'flex',
            flexDirection: isMultiLine ? 'column' : 'row',
            alignItems: isMultiLine ? 'stretch' : 'center',
            justifyContent: 'space-between',
            paddingBottom: '8px',
            paddingTop: '8px',
            paddingLeft: '8px',
            paddingRight: '12px',
            minHeight: '56px',
            height: 'auto',
            transition: 'all 0.15s ease',
            position: 'relative',
            gap: '8px'
          }}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            multiple={!(isGuest || !currentIsLoggedIn)}
            accept=".pdf,image/*"
            style={{ display: 'none' }}
          />

          {/* Sasis Textarea Tunggal Abadi: Mampu meninggi dinamis penuh dari minHeight ke maxHeight tanpa terpotong */}
          <textarea
            ref={textareaRef}
            value={input}
            disabled={isStreaming}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "CAKRA sedang berpikir..." : (activeIsolatedTitle ? "Tanyakan perihal isi dokumen ini..." : "Tanyakan apa saja...")}
            rows={1}
            style={{
              flex: isMultiLine ? 'none' : 1,
              width: isMultiLine ? '100%' : 'auto',
              color: theme.textColor,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              resize: 'none',
              paddingLeft: '8px',
              paddingRight: '8px',
              paddingTop: '8px',
              paddingBottom: '8px',
              fontSize: '15px',
              lineHeight: '1.5',
              fontFamily: 'inherit',
              minHeight: '36px',
              height: 'auto',
              maxHeight: '450px', // 🔥 Kunci Max Height Tinggi Sesuai Keinginan Lo Di Sini Bolo!
              overflowY: 'auto',
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
              whiteSpace: 'pre-wrap',
              order: 0
            }}
          />

          {/* 🔥 FIX: Semua tombol di-render flat (tidak conditional) agar CustomModeSelector tidak unmount/remount saat isMultiLine berubah */}
          
          {/* Plus Button untuk Single-line (kiri) */}
          <div style={{ 
            order: -1, 
            flexShrink: 0,
            display: isMultiLine ? 'none' : 'flex',
            alignItems: 'center'
          }}>
            <PlusButton />
          </div>

          {/* Plus Button untuk Multi-line (baris bawah kiri) */}
          {isMultiLine && (
            <div style={{ 
              order: 1, 
              width: '100%',
              paddingTop: '4px',
              display: 'flex',
              alignItems: 'center'
            }}>
              <PlusButton />
            </div>
          )}

          {/* CustomModeSelector - SELALU di-render (tidak conditional) agar state chatMode tidak reset */}
          <div style={{ 
            order: isMultiLine ? 2 : 1,
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <CustomModeSelector
              value={chatMode}
              onChange={setChatMode}
              disabled={isStreaming}
              darkMode={darkMode}
            />
          </div>

          {/* Send Button + Upload Status */}
          <div style={{ 
            order: isMultiLine ? 3 : 2,
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px',
            flexShrink: 0
          }}>
            {isUploadingFile && <span style={{ fontSize: '11px', color: '#6366f1', fontStyle: 'italic' }}>Mengunggah...</span>}
            <SendButton />
          </div>

          {/* DRAG DROP OVERLAY */}
          {isDragOver && (
            <div style={{
              position: 'absolute',
              inset: 0,
              background: darkMode ? 'rgba(99, 102, 241, 0.15)' : 'rgba(37, 99, 235, 0.1)',
              border: `2px dashed ${darkMode ? '#6366f1' : '#2563eb'}`,
              borderRadius: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
              zIndex: 10
            }}>
              <span style={{
                fontSize: '14px',
                fontWeight: 600,
                color: darkMode ? '#a5b4fc' : '#1e3a8a',
                background: darkMode ? 'rgba(99, 102, 241, 0.9)' : 'rgba(37, 99, 235, 0.9)',
                padding: '8px 16px',
                borderRadius: '8px'
              }}>
                📂 Lepas file di sini
              </span>
            </div>
          )}
        </form>
        {!isCentered && (
          <div style={{ ...styles.inputFooter, color: theme.secondaryText, marginTop: '8px' }}>
            CAKRA AI dapat membuat kesalahan. Pertimbangkan untuk memeriksa informasi penting.
          </div>
        )}
      </div>
    </div>
  );

  const hasSidebar = !isGuest && currentIsLoggedIn;
  const mainMarginLeft = hasSidebar ? (sidebarOpen ? '18rem' : '4rem') : '0';

  return (
    <div style={{ ...styles.root, background: theme.rootBg }}>
      {/* 1. KEMBALIKAN ANIMASI CAKRA BERPIKIR & STREAMING REVEAL */}
      <style>{`
        @keyframes cakraSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes logoFloat {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-6px) rotate(3deg); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes geminiReveal {
          from { opacity: 0; transform: translateY(3px); filter: blur(2px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
        /* Kelas pulse/kedut berpikir asisten */
        .thinking-pulse {
          animation: geminiReveal 0.6s ease-in-out infinite alternate;
          opacity: 0.6;
        }
        .assistant-content-container p, .assistant-content-container pre {
          animation: geminiReveal 0.35s ease-out forwards;
        }
        textarea {
          scrollbar-width: thin;
          scrollbar-color: ${darkMode ? '#4b5563' : '#9ca3af'} transparent;
        }
        textarea::-webkit-scrollbar {
          width: 6px;
          background: transparent;
        }
        textarea::-webkit-scrollbar-track {
          background: transparent;
        }
        textarea::-webkit-scrollbar-thumb {
          background: ${darkMode ? '#4b5563' : '#cbd5e1'};
          border-radius: 3px;
        }
        textarea::-webkit-scrollbar-thumb:hover {
          background: ${darkMode ? '#6b7280' : '#94a3b8'};
        }
        textarea::-webkit-scrollbar-button {
          display: none;
          width: 0;
          height: 0;
        }
        * { box-sizing: border-box; }
        .custom-scroll-gemini::-webkit-scrollbar { width: 8px; background-color: transparent; }
        .custom-scroll-gemini::-webkit-scrollbar-thumb {
          background-color: ${darkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)'};
          border-radius: 20px;
        }
      `}</style>

      {!isGuest && currentIsLoggedIn && (
        <Sidebar
          isOpen={sidebarOpen}
          setIsOpen={setSidebarOpen}
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          theme={theme}
          clearChat={handleClearChat}
          showDocumentList={showDocumentList}
          setShowDocumentList={setShowDocumentList}
          userData={currentUserData}
          triggerLogout={triggerLogout}
          loadChatSession={loadChatSession}
          currentSessionId={activeSessionId}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          cakraLogo={cakraLogo}
          navigate={navigate}
        />
      )}

      <main style={{
        ...styles.main,
        background: theme.mainBg,
        marginLeft: mainMarginLeft,
        transition: 'margin-left 0.3s ease-in-out'
      }}>
        <header style={styles.header}>
          <div style={styles.modelSelector}>
            {!hasSidebar && (
              <img
                src={cakraLogo}
                alt="CAKRA AI"
                style={{ height: '40px', width: 'auto', objectFit: 'contain' }}
              />
            )}
          </div>
          <div style={styles.headerActions}>
            {isGuest && (
              <button onClick={() => navigate('/login')} style={{ ...styles.loginBtn, color: theme.textColor, borderColor: theme.borderColor }}>Masuk</button>
            )}
          </div>
        </header>

        <div style={{
          flex: 1,
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden'
        }}>
          <div style={{
            flex: 1,
            minHeight: 0,
            opacity: showWelcome ? 0 : 1,
            transition: 'opacity 0.2s ease',
            pointerEvents: showWelcome ? 'none' : 'auto',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <ChatArea
              messages={messages}
              isStreaming={isStreaming}
              theme={theme}
              darkMode={darkMode}
              bottomRef={bottomRef}
              messagesContainerRef={messagesContainerRef}
              setInput={setInput}
              isThinking={isThinking}
              currentThinking={currentThinking}
              isStreamingText={isStreamingText}
              lastAssistantIndex={lastAssistantIndex}
            />
          </div>

          {showWelcome && (
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              transform: 'translateY(-8%)',
              zIndex: 10,
              animation: 'fadeInUp 0.4s ease-out',
              pointerEvents: 'none'
            }}>
              <div style={{ pointerEvents: 'auto' }}>
                <GuestWelcome
                  isLoggedIn={currentIsLoggedIn}
                  userData={{
                    fullname: currentUserData?.name || currentUserData?.fullname || "Pegawai",
                    npp: currentUserData?.npp || "NPP -----"
                  }}
                  getGreeting={getGreeting || defaultGetGreeting}
                  theme={theme}
                />
              </div>
              <div style={{
                width: '100%',
                maxWidth: '700px',
                padding: '0 20px',
                marginTop: '24px',
                pointerEvents: 'auto'
              }}>
                {renderInputForm(true)}
              </div>
            </div>
          )}
        </div>

        {!showWelcome && renderInputForm(false)}
      </main>
    </div>
  );
}