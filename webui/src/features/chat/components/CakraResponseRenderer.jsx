import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThoughtAccordion from './ThoughtAccordion';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

// =========================================================================
// 📥 1. CODE BLOCK HEADER (Dengan Logic Copy & Download Sempurna)
// =========================================================================
function CodeBlockHeader({ lang, code }) {
    const [showToast, setShowToast] = React.useState(false);
    const [toastMsg, setToastMsg] = React.useState('');

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
            setToastMsg('Kode berhasil disalin! 📋');
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2000);
        } catch (err) {
            setToastMsg('Gagal menyalin kode! ❌');
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2000);
        }
    };

    const handleDownload = () => {
        try {
            const extensionMap = {
                javascript: 'js', jsx: 'jsx', typescript: 'ts', tsx: 'tsx',
                html: 'html', css: 'css', python: 'py', sql: 'sql',
                php: 'php', java: 'java', kotlin: 'kt', bash: 'sh'
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

    const actionBtnStyle = {
        background: 'rgba(255, 255, 255, 0.03)',
        color: '#cbd5e1',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '5px',
        padding: '4px 10px',
        fontSize: '11px',
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        fontWeight: 500,
        fontFamily: "'Inter', sans-serif",
        transition: 'all 0.15s ease-in-out'
    };

    const toastFloatingStyle = {
        position: 'fixed',
        top: '24px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: '#1e293b',
        color: '#e2e8f0',
        padding: '10px 20px',
        borderRadius: '8px',
        fontSize: '13px',
        fontWeight: 500,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(99, 102, 241, 0.3)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
    };

    return (
        <div style={{
            background: '#1a1a1c',
            padding: '10px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            borderTopLeftRadius: '10px',
            borderTopRightRadius: '10px',
            position: 'relative'
        }}>
            <span style={{ color: '#38bdf8', fontSize: '11px', fontWeight: 700, fontFamily: "'Inter', sans-serif", letterSpacing: '0.8px' }}>
                {lang.toUpperCase()}
            </span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button type="button" onClick={handleDownload} title="Unduh Kode" style={actionBtnStyle}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <span>Unduh</span>
                </button>
                <button type="button" onClick={handleCopy} title="Salin Kode" style={actionBtnStyle}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                    </svg>
                    <span>Salin</span>
                </button>
            </div>
            {showToast && <div style={toastFloatingStyle}>{toastMsg}</div>}
        </div>
    );
}

// =========================================================================
// 🔮 2. MAIN COMPONENT: CAKRA RESPONSE RENDERER
// =========================================================================
const CakraResponseRenderer = ({ rawContent, isStreaming, darkMode, theme }) => {
    if (!rawContent) return null;

    const thinkStartTag = "<think>";
    const thinkEndTag = "</think>";

    const startIdx = rawContent.indexOf(thinkStartTag);
    const endIdx = rawContent.indexOf(thinkEndTag);

    let thinkingBlock = "";
    let finalResponseBlock = rawContent;

    // ── STRATIFIKASI STATE MACHINE PARSING INDEKS ─────────────────────────────
    if (startIdx !== -1) {
        if (endIdx !== -1 && endIdx > startIdx) {
            thinkingBlock = rawContent.substring(startIdx + thinkStartTag.length, endIdx);
            const beforeThink = rawContent.substring(0, startIdx);
            const afterThink = rawContent.substring(endIdx + thinkEndTag.length);
            finalResponseBlock = `${beforeThink}${afterThink}`;
        } else {
            thinkingBlock = rawContent.substring(startIdx + thinkStartTag.length);
            finalResponseBlock = rawContent.substring(0, startIdx);
        }
    }

    const markdownComponents = useMemo(() => ({
        p({ children, ...props }) {
            return <p style={{ marginTop: 0, marginBottom: '16px', lineHeight: '1.7', whiteSpace: 'normal' }} {...props}>{children}</p>;
        },
        code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const cleanCode = String(children).replace(/\n$/, '');

            return !inline && match ? (
                <div key={`code-block-${match[1]}`} style={{ borderRadius: '10px', overflow: 'hidden', margin: '8px 0', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                    <CodeBlockHeader lang={match[1]} code={cleanCode} />
                    <SyntaxHighlighter
                        children={cleanCode}
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                            margin: 0,
                            padding: '16px',
                            background: '#222225',
                            fontSize: '13px',
                            lineHeight: '1.6',
                            fontFamily: "'Fira Code', 'Courier New', monospace"
                        }}
                        {...props}
                    />
                </div>
            ) : (
                <code className={className} style={{ background: darkMode ? '#2d2d30' : '#e5e7eb', color: darkMode ? '#f3f4f6' : '#1f2937', padding: '3px 6px', borderRadius: '4px', fontFamily: "monospace", fontSize: '14px' }} {...props}>
                    {children}
                </code>
            );
        }
    }), [darkMode]);

    return (
        <div className="cakra-response-wrapper" style={{ width: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* 🧠 1. ACCORDION PENALARAN INTERNAL: Ditaruh di paling atas sesuai urutan datangnya token stream */}
            {thinkingBlock.trim() && (
                <ThoughtAccordion 
                    thought={thinkingBlock} 
                    darkMode={darkMode} 
                    theme={theme} 
                />
            )}

            {/* 📝 2. RENDER UTAMA JAWABAN: Tampil mengalir tepat di bawah proses berpikir */}
            {finalResponseBlock.trim() && (
                <div style={{ width: '100%', transition: 'all 0.3s' }}>
                    <ReactMarkdown
                        children={finalResponseBlock}
                        components={markdownComponents}
                        remarkPlugins={[remarkGfm]}
                    />
                </div>
            )}
        </div>
    );
};

export default CakraResponseRenderer;