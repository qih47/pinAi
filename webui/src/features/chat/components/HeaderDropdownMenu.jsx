import React, { useState, useRef, useEffect } from 'react';
import { getHeaderDropdownMenuStyles } from '../chatPage.styles';
import { useChatStore } from '../../../stores/chatStore';
import { translations } from '../../../utils/translations';
import { LogIn, Sun, Moon, Globe, FileDown, Printer, ChevronDown, ChevronUp } from 'lucide-react';

export default function HeaderDropdownMenu({ isGuest, onLogin, darkMode, setDarkMode, theme, language, setLanguage }) {
  const [isOpen, setIsOpen] = useState(false);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const menuRef = useRef(null);
  
  const t = translations[language]?.dropdown || translations.id.dropdown;

  const messages = useChatStore((state) => state.messages || []);
  const sessionUuid = useChatStore((state) => state.sessionUuid);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const exportToMarkdown = () => {
    if (messages.length === 0) return;
    
    let mdContent = `# Riwayat Percakapan CAKRA AI\n`;
    mdContent += `ID Sesi: ${sessionUuid || 'Sesi Baru'}\n`;
    mdContent += `Tanggal Ekspor: ${new Date().toLocaleString()}\n\n---\n\n`;
    
    messages.forEach((msg) => {
      const role = msg.role === 'user' ? 'Pegawai' : 'CAKRA AI';
      mdContent += `### 👤 ${role}\n\n${msg.content}\n\n`;
      if (msg.attachments && msg.attachments.length > 0) {
        mdContent += `*Lampiran:*\n`;
        msg.attachments.forEach((att) => {
          mdContent += `- ${att.file_name}\n`;
        });
        mdContent += `\n`;
      }
    });

    const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `cakra-chat-${sessionUuid || 'new'}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setIsOpen(false);
  };

  const exportToPDF = () => {
    if (messages.length === 0) return;
    
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    
    let htmlContent = `
      <html>
      <head>
        <title>Riwayat Percakapan CAKRA AI</title>
        <style>
          body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1f2937;
            padding: 40px;
            max-width: 800px;
            margin: 0 auto;
            line-height: 1.6;
          }
          h1 {
            font-size: 24px;
            margin-bottom: 5px;
            color: #111827;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
          }
          .meta {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 30px;
          }
          .message {
            margin-bottom: 25px;
            padding: 15px 20px;
            border-radius: 12px;
          }
          .user {
            background-color: #f3f4f6;
            border-left: 4px solid #9ca3af;
          }
          .assistant {
            background-color: #eff6ff;
            border-left: 4px solid #3b82f6;
          }
          .sender {
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 8px;
            color: #111827;
          }
          .content {
            font-size: 14px;
            white-space: pre-wrap;
          }
          .attachments {
            margin-top: 10px;
            font-size: 12px;
            color: #4b5563;
            font-style: italic;
          }
        </style>
      </head>
      <body>
        <h1>Riwayat Percakapan CAKRA AI</h1>
        <div class="meta">
          ID Sesi: ${sessionUuid || 'Sesi Baru'}<br>
          Tanggal Cetak: ${new Date().toLocaleString()}
        </div>
    `;

    messages.forEach((msg) => {
      const sender = msg.role === 'user' ? '👤 Pegawai' : '🤖 CAKRA AI';
      const cssClass = msg.role === 'user' ? 'user' : 'assistant';
      htmlContent += `
        <div class="message ${cssClass}">
          <div class="sender">${sender}</div>
          <div class="content">${msg.content}</div>
      `;
      if (msg.attachments && msg.attachments.length > 0) {
        htmlContent += `<div class="attachments">Lampiran: `;
        htmlContent += msg.attachments.map(att => att.file_name).join(', ');
        htmlContent += `</div>`;
      }
      htmlContent += `</div>`;
    });

    htmlContent += `
      </body>
      </html>
    `;

    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 500);
    setIsOpen(false);
  };

  const menuStyles = getHeaderDropdownMenuStyles(darkMode);

  return (
    <div ref={menuRef} style={menuStyles.container}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={menuStyles.button}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = darkMode
            ? 'rgba(255,255,255,0.05)'
            : 'rgba(0,0,0,0.05)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="1" />
          <circle cx="12" cy="5" r="1" />
          <circle cx="12" cy="19" r="1" />
        </svg>
      </button>

      {isOpen && (
        <div style={menuStyles.menu}>
          {isGuest && (
            <button
              type="button"
              onClick={() => {
                onLogin();
                setIsOpen(false);
              }}
              style={menuStyles.loginItem}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = darkMode
                  ? 'rgba(255,255,255,0.05)'
                  : 'rgba(0,0,0,0.03)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <LogIn size={15} strokeWidth={2.5} className="opacity-70" /> <span>{t.login}</span>
            </button>
          )}

          {isGuest && <div style={menuStyles.divider} />}

          <button
            type="button"
            onClick={() => {
              setDarkMode(!darkMode);
              setIsOpen(false);
            }}
            style={menuStyles.themeItem}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = darkMode
                ? 'rgba(255,255,255,0.05)'
                : 'rgba(0,0,0,0.03)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {darkMode ? <Sun size={15} strokeWidth={2.5} className="opacity-70" /> : <Moon size={15} strokeWidth={2.5} className="opacity-70" />}
              <span>{darkMode ? t.light : t.dark}</span>
            </div>
          </button>

          {/* 🌐 LANGUAGE PICKER - tampil selalu (guest & logged in jika ada setLanguage) */}
          {setLanguage && (
            <>
              <div style={menuStyles.divider} />
              <div
                style={{ ...menuStyles.themeItem, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                onClick={() => setShowLangPicker(!showLangPicker)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Globe size={15} strokeWidth={2.5} className="opacity-70" />
                  <span>{t.language}</span>
                </div>
                {showLangPicker ? <ChevronUp size={14} className="opacity-50" /> : <ChevronDown size={14} className="opacity-50" />}
              </div>
              {showLangPicker && (
                <div style={{ paddingLeft: '8px', paddingRight: '8px', paddingBottom: '4px' }}>
                  {['id', 'en'].map((lang) => (
                    <button
                      key={lang}
                      type="button"
                      onClick={() => {
                        setLanguage(lang);
                        setShowLangPicker(false);
                        setIsOpen(false);
                      }}
                      style={{
                        ...menuStyles.themeItem,
                        width: '100%',
                        borderRadius: '8px',
                        marginBottom: '2px',
                        background: language === lang
                          ? (darkMode ? 'rgba(99,102,241,0.2)' : 'rgba(99,102,241,0.1)')
                          : 'transparent',
                        border: language === lang
                          ? `1px solid ${darkMode ? 'rgba(99,102,241,0.4)' : 'rgba(99,102,241,0.3)'}`
                          : '1px solid transparent',
                        color: language === lang ? '#818cf8' : (darkMode ? '#e2e8f0' : '#1f2937'),
                        fontWeight: language === lang ? 600 : 400,
                        fontSize: '13px',
                      }}
                      onMouseEnter={(e) => {
                        if (language !== lang) e.currentTarget.style.background = darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)';
                      }}
                      onMouseLeave={(e) => {
                        if (language !== lang) e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      {lang === 'id' ? t.languageId : t.languageEn}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {messages.filter(m => m.role === 'user').length > 0 && (
            <>
              <div style={menuStyles.divider} />
              <button
                type="button"
                onClick={exportToMarkdown}
                style={menuStyles.themeItem}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = darkMode
                    ? 'rgba(255,255,255,0.05)'
                    : 'rgba(0,0,0,0.03)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileDown size={15} strokeWidth={2.5} className="opacity-70" />
                  <span>{t.exportMd}</span>
                </div>
              </button>

              <button
                type="button"
                onClick={exportToPDF}
                style={menuStyles.themeItem}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = darkMode
                    ? 'rgba(255,255,255,0.05)'
                    : 'rgba(0,0,0,0.03)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Printer size={15} strokeWidth={2.5} className="opacity-70" />
                  <span>{t.printPdf}</span>
                </div>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
