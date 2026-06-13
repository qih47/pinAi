import React, { useState, useRef, useEffect } from 'react';
import { getHeaderDropdownMenuStyles } from '../chatPage.styles';
import { useChatStore } from '../../../stores/chatStore';

export default function HeaderDropdownMenu({ isGuest, onLogin, darkMode, setDarkMode, theme }) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

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
              <span>🔑</span> Masuk
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
              <span>{darkMode ? '☀️' : '🌙'}</span>
              <span>{darkMode ? 'Terang' : 'Gelap'}</span>
            </div>
          </button>

          {messages.length > 0 && (
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
                  <span>📝</span>
                  <span>Ekspor Markdown</span>
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
                  <span>🖨️</span>
                  <span>Cetak / PDF</span>
                </div>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
