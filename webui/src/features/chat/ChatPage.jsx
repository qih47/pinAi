import React, { useState, useRef, useEffect } from 'react';
import { useChatStore } from '../../stores/chatStore';
import cakraLogo from '../../assets/cakra.png';
import { styles, lightColors, darkColors } from './chatPage.styles';
import ChatArea from './components/ChatArea';
import GuestWelcome from '../../components/ui/GuestWelcome';
import Sidebar from './components/Sidebar'; // import Sidebar
import { useNavigate } from 'react-router-dom';
// 🔥 TIMBAL BALIK: Ambil session otentikasi global dari store terminal login
import { useChatAuthStore } from '../../stores/authStore';

export default function ChatPage({ isGuest, isLoggedIn: propsIsLoggedIn, userData: propsUserData, getGreeting }) {
  const [input, setInput] = useState('');

  // 🔥 AMBIL DATA DARI STORE JIKA PROPS DARI APP NYA KOSONG
  const authUser = useChatAuthStore((state) => state.user);
  const isAuthenticated = useChatAuthStore((state) => state.isAuthenticated);
  const logout = useChatAuthStore((state) => state.logout);

  // Konsolidasikan data user secara dinamis
  const currentIsLoggedIn = propsIsLoggedIn !== undefined ? propsIsLoggedIn : isAuthenticated;
  const currentUserData = propsUserData || {
    name: authUser?.name || 'Pegawai Pindad',
    npp: authUser?.npp || 'NPP ------'
  };

  // =========================================================================
  // 🎨 THEME MANAGEMENT: System-Aware + Persistent
  // =========================================================================
  const [darkMode, setDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem('cakra-theme');
    if (savedTheme !== null) return savedTheme === 'dark';
    if (window.matchMedia) return window.matchMedia('(prefers-color-scheme: dark)').matches;
    return false;
  });

  const [sidebarOpen, setSidebarOpen] = useState(true);   // atau false, terserah
  const [showDocumentList, setShowDocumentList] = useState(false);
  const navigate = useNavigate();

  // Additional states for Sidebar integration
  const [chatHistory, setChatHistory] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);

  const loadChatSession = (sessionId) => {
    setCurrentSessionId(sessionId);
    navigate(`/chat/${sessionId}`);
  };

  const triggerLogout = () => {
    // 🚀 PANGGIL UTUH LOGOUT DARI CYBERPUNK STORE LO, BOLO!
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

  const { messages, isStreaming, sendMessage, clearChat } = useChatStore();
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const messagesContainerRef = useRef(null);

  const toggleTheme = () => setDarkMode(prev => !prev);
  const theme = darkMode ? darkColors : lightColors;

  const lastAssistantIndex = [...messages].reverse().findIndex(m => m.role === 'assistant');
  const isThinking = isStreaming && lastAssistantIndex === 0 && messages[messages.length - 1]?.content === '';
  const isStreamingText = isStreaming && lastAssistantIndex === 0 && messages[messages.length - 1]?.content !== '';

  const isEmptyChat = messages.length === 0;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 220) + 'px';
    }
  }, [input]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const defaultGetGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return 'Selamat Pagi';
    if (hour < 15) return 'Selamat Siang';
    if (hour < 19) return 'Selamat Sore';
    return 'Selamat Malam';
  };

  // 🔥 Komponen input form (digunakan di dua tempat: tengah & bawah)
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
        <form onSubmit={handleSubmit} style={{ ...styles.inputForm, background: theme.inputBg, borderColor: theme.inputBorder, boxShadow: theme.inputShadow }}>
          <textarea
            ref={isCentered ? textareaRef : undefined}
            value={input}
            disabled={isStreaming}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "CAKRA sedang berpikir..." : "Tanyakan apa saja..."}
            rows={1}
            style={{ ...styles.textarea, color: theme.textColor, background: 'transparent' }}
          />
          <div style={styles.inputActions}>
            <button type="button" style={{ ...styles.iconBtn, color: theme.iconColor }} title="Lampiran">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              style={{
                ...styles.sendBtn,
                background: theme.sendBtnBg,
                color: theme.sendBtnText,
                opacity: isStreaming || !input.trim() ? 0.35 : 1,
                cursor: isStreaming || !input.trim() ? 'not-allowed' : 'pointer'
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </button>
          </div>
        </form>
        {!isCentered && (
          <div style={{ ...styles.inputFooter, color: theme.secondaryText }}>
            CAKRA AI dapat membuat kesalahan. Pertimbangkan untuk memeriksa informasi penting.
          </div>
        )}
      </div>
    </div>
  );

  // 🔥 FIX SYNC: Hitung margin kiri main berdasarkan status sidebar
  // w-72 = 18rem, w-16 = 4rem (sesuai class Tailwind di Sidebar.jsx)
  const hasSidebar = !isGuest && currentIsLoggedIn;
  const mainMarginLeft = hasSidebar ? (sidebarOpen ? '18rem' : '4rem') : '0';

  return (
    <div style={{ ...styles.root, background: theme.rootBg }}>
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
        .assistant-content-container p, .assistant-content-container pre {
          animation: geminiReveal 0.35s ease-out forwards;
        }
        textarea::-webkit-scrollbar { width: 6px; }
        textarea::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
        * { box-sizing: border-box; }
        @keyframes dotPulse {
          0%, 20% { opacity: 0; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-2px); }
          100% { opacity: 0; transform: translateY(0); }
        }
        @keyframes fadeText {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
        .custom-scroll-gemini::-webkit-scrollbar {
          width: 8px;
          background-color: transparent;
        }
        .custom-scroll-gemini::-webkit-scrollbar-track {
          background-color: transparent;
        }
        .custom-scroll-gemini::-webkit-scrollbar-thumb {
          background-color: ${darkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)'};
          border-radius: 20px;
          border: 2px solid transparent;
          background-clip: padding-box;
        }
        .custom-scroll-gemini::-webkit-scrollbar-thumb:hover {
          background-color: ${darkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)'};
        }
        .custom-scroll-gemini::-webkit-scrollbar-button {
          display: none !important;
          width: 0;
          height: 0;
        }
      `}</style>

      {/* SIDEBAR — 🔥 HANYA MUNCUL JIKA USER BUKAN GUEST DAN STATUS LOGIN VALID */}
      {!isGuest && currentIsLoggedIn && (
        <Sidebar
          isOpen={sidebarOpen}
          setIsOpen={setSidebarOpen}
          darkMode={darkMode}
          theme={theme}
          clearChat={clearChat}
          showDocumentList={showDocumentList}
          setShowDocumentList={setShowDocumentList}
          userData={currentUserData} 
          triggerLogout={triggerLogout}
          loadChatSession={loadChatSession}
          currentSessionId={currentSessionId}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          cakraLogo={cakraLogo}
          navigate={navigate}
        />
      )}

      {/* 🔥 FIX SYNC: Tambahin marginLeft dinamis + transition 0.3s biar barengan sama sidebar */}
      <main style={{ 
        ...styles.main, 
        background: theme.mainBg,
        marginLeft: mainMarginLeft,
        transition: 'margin-left 0.3s ease-in-out' 
      }}>
        <header style={styles.header}>
          <div style={styles.modelSelector}>
            {/* 🔥 FIX: Sembunyikan logo kalau user udah login (sidebar muncul) */}
            {!hasSidebar && (
              <img
                src={cakraLogo}
                alt="CAKRA AI"
                style={{ height: '40px', width: 'auto', objectFit: 'contain' }}
              />
            )}
          </div>
          <div style={styles.headerActions}>
            <button onClick={toggleTheme} style={{ ...styles.iconBtn, color: theme.iconColor }} title="Toggle tema">
              {darkMode ? '☀️' : '🌙'}
            </button>
            {isGuest && (
              <button onClick={() => navigate('/login')} style={{ ...styles.loginBtn, color: theme.textColor, borderColor: theme.borderColor }}>Masuk</button>
            )}
          </div>
        </header>

        {/* 🔥 CONTENT AREA - FIX LAYOUT */}
        <div style={{
          flex: 1,
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden'
        }}>
          {/* ChatArea - NORMAL FLOW (bukan absolute) */}
          <div style={{
            flex: 1,
            minHeight: 0,
            opacity: isEmptyChat ? 0 : 1,
            transition: 'opacity 0.2s ease',
            pointerEvents: isEmptyChat ? 'none' : 'auto',
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
              isStreamingText={isStreamingText}
              lastAssistantIndex={lastAssistantIndex}
            />
          </div>

          {/* GuestWelcome - ABSOLUTE OVERLAY */}
          {isEmptyChat && (
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
                    fullname: authUser?.fullname || authUser?.name || "Pegawai", 
                    npp: authUser?.npp || "NPP -----"
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

        {/* Input bawah hanya saat ada chat */}
        {!isEmptyChat && renderInputForm(false)}
      </main>
    </div>
  );
}