import React, { useState } from 'react';
import { styles } from '../chatPage.styles';
import { translations } from '../../../utils/translations';

export default function CodeBlockHeader({ lang, code, language = 'id' }) {
  const tGlobal = translations[language] || translations.id;
  const [showToast, setShowToast] = useState(false);
  const [toastMsg, setToastMsg] = useState('');

  const handleCopy = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(code);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = code;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setToastMsg(tGlobal.render.copiedCodeSuccess);
      setShowToast(true);
      setTimeout(() => setShowToast(false), 2000);
    } catch (err) {
      setToastMsg(tGlobal.render.copiedCodeFail);
      setShowToast(true);
      setTimeout(() => setShowToast(false), 2000);
    }
  };

  const handleDownload = () => {
    try {
      const extensionMap = {
        javascript: 'js',
        jsx: 'jsx',
        typescript: 'ts',
        tsx: 'tsx',
        html: 'html',
        css: 'css',
        python: 'py',
        sql: 'sql',
        php: 'php',
        java: 'java',
        kotlin: 'kt',
        bash: 'sh'
      };
      const ext = extensionMap[lang.toLowerCase()] || 'txt';
      const filename = `cakra_code_${Date.now()}.${ext}`;
      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setToastMsg(`Berkas ${filename} berhasil diunduh! 💾`);
      setShowToast(true);
      setTimeout(() => setShowToast(false), 2000);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={styles.codeBlockHeader}>
      <span style={styles.codeBlockHeaderLang}>
        {lang.toUpperCase()}
      </span>
      <div style={styles.codeBlockHeaderBtnGroup}>
        <button
          type="button"
          onClick={handleDownload}
          title={tGlobal.render.downloadCode}
          style={styles.codeBlockHeaderActionBtn}
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span>{tGlobal.render.download}</span>
        </button>
        <button
          type="button"
          onClick={handleCopy}
          title={tGlobal.render.copyCode}
          style={styles.codeBlockHeaderActionBtn}
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
          </svg>
          <span>{tGlobal.render.copy}</span>
        </button>
      </div>
      {showToast && <div style={styles.codeBlockHeaderToast}>{toastMsg}</div>}
    </div>
  );
}
