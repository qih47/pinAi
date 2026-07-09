import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThoughtAccordion from './ThoughtAccordion';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeBlockHeader from './CodeBlockHeader';
import ChatActionWidgets from './ChatActionWidgets';
import { Suspense, lazy } from 'react';

const LazyMermaidViewer = lazy(() => import('./MermaidViewer'));
const LazySmartMailWidget = lazy(() => import('./SmartMailChatWidget'));

const highlightText = (text, query) => {
    if (!query || typeof text !== 'string') return text;
    const parts = text.split(new RegExp(`(${query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')})`, 'gi'));
    return parts.map((part, index) =>
        part.toLowerCase() === query.toLowerCase()
            ? <mark key={index} style={{ background: '#fef08a', color: '#854d0e', borderRadius: '2px', padding: '0 2px' }}>{part}</mark>
            : part
    );
};

const recursiveHighlight = (children, query) => {
    if (!query) return children;
    return React.Children.map(children, child => {
        if (typeof child === 'string') {
            return highlightText(child, query);
        }
        if (React.isValidElement(child) && child.props.children) {
            return React.cloneElement(child, {
                children: recursiveHighlight(child.props.children, query)
            });
        }
        return child;
    });
};

// =========================================================================
// 🔮 CAKRA MARKDOWN TABLE (SMART FORM EXPORTER)
// =========================================================================
const MarkdownTable = ({ children, darkMode, theme, searchQuery, ...props }) => {
    const tableRef = React.useRef(null);
    const [copied, setCopied] = React.useState(false);

    const handleCopy = () => {
        if (!tableRef.current) return;
        const range = document.createRange();
        range.selectNode(tableRef.current);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        try {
            document.execCommand('copy');
            window.getSelection().removeAllRanges();
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch(err) {
            console.error("Gagal menyalin tabel:", err);
        }
    };

    return (
        <div className="relative group my-4 rounded-lg overflow-hidden border" style={{ borderColor: theme?.borderColor || '#e5e7eb' }}>
            <button 
                onClick={handleCopy}
                title="Salin Tabel (Bisa dipaste ke Excel/Spreadsheet)"
                className={`absolute right-2 top-2 z-10 px-2.5 py-1.5 flex items-center gap-1.5 rounded-lg text-xs font-semibold backdrop-blur-sm transition-all opacity-0 group-hover:opacity-100 ${darkMode ? 'bg-slate-800/90 text-slate-200 hover:bg-slate-700 hover:text-white border border-slate-600 shadow-md' : 'bg-white/90 text-slate-600 hover:bg-slate-50 hover:text-slate-900 shadow-[0_2px_8px_rgba(0,0,0,0.08)] border border-slate-200'}`}
            >
                {copied ? (
                    <>
                        <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                        <span>Tersalin!</span>
                    </>
                ) : (
                    <>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                        <span>Salin Data</span>
                    </>
                )}
            </button>
            <div className="overflow-x-auto">
                <table ref={tableRef} className="w-full text-left border-collapse" style={{ fontSize: '13.5px' }} {...props}>
                    {recursiveHighlight(children, searchQuery)}
                </table>
            </div>
        </div>
    );
};

// =========================================================================
// 🔮 MAIN COMPONENT: CAKRA RESPONSE RENDERER
// =========================================================================
const CakraResponseRenderer = ({ rawContent, thinkingContent, isStreaming, darkMode, theme, searchQuery = '', statusMessage, middleContent }) => {
    const thinkStartTag = "<think>";
    const thinkEndTag = "</think>";

    // 🔧 FIX: bungkus parsing index/substring dengan useMemo agar hanya
    // dihitung ulang saat rawContent benar-benar berubah, bukan setiap render
    const { thinkingBlock, finalResponseBlock } = useMemo(() => {
        const thinking = thinkingContent || "";
        const final = rawContent || "";

        return { thinkingBlock: thinking, finalResponseBlock: final };
    }, [rawContent, thinkingContent]);

    const markdownComponents = useMemo(() => ({
        // 1. PARAGRAF (Spasi yang proporsional)
        p({ children, ...props }) {
            return <p style={{ marginTop: 0, marginBottom: '14px', fontSize: '15px', lineHeight: '1.75', whiteSpace: 'normal', color: darkMode ? '#f1f5f9' : '#334155' }} {...props}>{recursiveHighlight(children, searchQuery)}</p>;
        },

        // 2. HEADINGS (Mengembalikan ukuran judul yang ke-reset oleh Tailwind!)
        h1({ children, ...props }) {
            return <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '24px', marginBottom: '12px', lineHeight: '1.3', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h1>;
        },
        h2({ children, ...props }) {
            return <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '24px', marginBottom: '12px', lineHeight: '1.3', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h2>;
        },
        h3({ children, ...props }) {
            return <h3 style={{ fontSize: '1.125rem', fontWeight: 600, marginTop: '20px', marginBottom: '8px', lineHeight: '1.4', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h3>;
        },
        h4({ children, ...props }) {
            return <h4 style={{ fontSize: '1rem', fontWeight: 600, marginTop: '16px', marginBottom: '8px', lineHeight: '1.4', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h4>;
        },

        // 3. LISTS (Indentasi & Jarak Presisi)
        ol({ children, ...props }) {
            // marginLeft menggeser seluruh blok angka agak ke kanan
            // paddingLeft memberi ruang aman biar angkanya gak kepotong
            return <ol style={{ marginLeft: '18px', paddingLeft: '12px', listStyleType: 'decimal', marginTop: '8px', marginBottom: '16px' }} {...props}>{recursiveHighlight(children, searchQuery)}</ol>;
        },
        ul({ children, ...props }) {
            return <ul style={{ marginLeft: '18px', paddingLeft: '12px', listStyleType: 'disc', marginTop: '8px', marginBottom: '16px' }} {...props}>{recursiveHighlight(children, searchQuery)}</ul>;
        },
        li({ children, className, ...props }) {
            // Deteksi jika ini adalah task list item (checklist) dari remark-gfm
            if (className === 'task-list-item') {
                return (
                    <li className="flex items-start gap-2 mb-2 group" style={{ listStyleType: 'none', paddingLeft: 0, marginLeft: '-18px' }} {...props}>
                        <div className="mt-1 flex-shrink-0 cursor-pointer">
                            {/* Input di-handle di bawah */}
                            {recursiveHighlight(children, searchQuery)}
                        </div>
                    </li>
                );
            }
            return <li style={{ marginBottom: '12px', fontSize: '15px', lineHeight: '1.75', paddingLeft: '8px', color: darkMode ? '#f1f5f9' : '#334155' }} {...props}>{recursiveHighlight(children, searchQuery)}</li>;
        },
        input({ type, checked, disabled, ...props }) {
            if (type === 'checkbox') {
                return (
                    <input 
                        type="checkbox" 
                        defaultChecked={checked}
                        className="w-[18px] h-[18px] text-indigo-600 bg-white border-gray-300 rounded cursor-pointer mr-3 align-middle focus:ring-indigo-500 transition-all dark:bg-gray-800 dark:border-gray-600 shadow-sm"
                        style={{ cursor: 'pointer' }}
                        onChange={(e) => {
                             const el = e.target;
                             const parentLi = el.closest('li');
                             if (parentLi) {
                                 if (el.checked) {
                                     parentLi.style.opacity = "0.6";
                                     parentLi.style.textDecoration = "line-through";
                                 } else {
                                     parentLi.style.opacity = "1";
                                     parentLi.style.textDecoration = "none";
                                 }
                             }
                        }}
                    />
                );
            }
            return <input type={type} checked={checked} disabled={disabled} {...props} />;
        },

        // 4. TEKS BOLD & KUTIPAN (BLOCKQUOTE)
        strong({ children, ...props }) {
            return <strong style={{ fontWeight: 700, color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</strong>;
        },
        blockquote({ children, node, ...props }) {
            // Helper untuk nge-ekstrak raw text dari AST node buat ngecek tag konflik
            const getText = (n) => {
                if (n.type === 'text') return n.value || '';
                if (n.children) return n.children.map(getText).join('');
                return '';
            };
            const textContent = getText(node);

            // Jika ada tag konflik, render UI peringatan yang mencolok dan bisa di-klik (collapsible)
            if (textContent.includes('[!CONFLICT_ALERT]')) {
                // Hapus string '[!CONFLICT_ALERT]' dari tampilan
                const cleanContent = textContent.replace('[!CONFLICT_ALERT]', '').trim();
                return (
                    <details className="my-5 border border-red-500/40 bg-red-500/10 rounded-xl overflow-hidden shadow-[0_0_15px_rgba(239,68,68,0.1)] group cursor-pointer transition-all">
                        <summary className="bg-red-500/20 px-4 py-2.5 border-b border-red-500/20 flex items-center gap-2 select-none hover:bg-red-500/30">
                            <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <span className="font-bold text-red-500 text-[13px] tracking-wide uppercase flex-1">Bentrok Aturan Terdeteksi</span>
                            <svg className="w-4 h-4 text-red-500 transition-transform group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </summary>
                        <div className="p-4 text-[13.5px] text-red-400 font-medium leading-relaxed [&>p]:m-0">
                            {recursiveHighlight(children, searchQuery)}
                        </div>
                    </details>
                );
            }

            return (
                <blockquote style={{ borderLeft: `4px solid ${darkMode ? '#6366f1' : '#3b82f6'}`, padding: '8px 16px', margin: '16px 0', background: darkMode ? 'rgba(99, 102, 241, 0.1)' : 'rgba(59, 130, 246, 0.05)', borderRadius: '0 8px 8px 0', fontStyle: 'italic', color: theme?.secondaryText || '#6b7280' }} {...props}>
                    {recursiveHighlight(children, searchQuery)}
                </blockquote>
            );
        },

        // 5. TABEL (Dengan Header Background & Copy to Clipboard)
        table({ children, ...props }) {
            return <MarkdownTable children={children} darkMode={darkMode} theme={theme} searchQuery={searchQuery} {...props} />;
        },
        thead({ children, ...props }) {
            return <thead style={{ background: darkMode ? '#334155' : '#f8fafc' }} {...props}>{recursiveHighlight(children, searchQuery)}</thead>;
        },
        th({ children, ...props }) {
            return <th style={{ padding: '10px 14px', border: `1px solid ${theme?.borderColor || '#e5e7eb'}`, textAlign: 'left', fontWeight: 600, color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</th>;
        },
        td({ children, ...props }) {
            return <td style={{ padding: '10px 14px', border: `1px solid ${theme?.borderColor || '#e5e7eb'}` }} {...props}>{recursiveHighlight(children, searchQuery)}</td>;
        },
        span({ children, ...props }) {
            return <span {...props}>{recursiveHighlight(children, searchQuery)}</span>;
        },

        // Override pre supaya komponen custom (SyntaxHighlighter & MermaidViewer) nggak dibungkus tag <pre> bawaan yang merusak flexbox layout
        pre({ children, ...props }) {
            return <div className="markdown-pre-wrapper" {...props}>{children}</div>;
        },

        // 6. BLOK KODE (Tetap seperti milik lu aslinya, super aman)
        code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const cleanCode = String(children).replace(/\n$/, '');

            if (!inline && match && match[1] === 'mermaid') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat engine diagram...</div>}>
                        <LazyMermaidViewer chartCode={cleanCode} darkMode={darkMode} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'smartmail') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat editor email...</div>}>
                        <LazySmartMailWidget initialData={cleanCode} darkMode={darkMode} theme={theme} />
                    </Suspense>
                );
            }

            return !inline && match ? (
                <div key={`code-block-${match[1]}`} style={{ borderRadius: '10px', overflow: 'hidden', margin: '12px 0', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
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
                <code className={className} style={{ background: darkMode ? 'rgba(192, 132, 252, 0.15)' : 'rgba(126, 34, 206, 0.08)', color: darkMode ? '#c084fc' : '#7e22ce', padding: '3px 6px', borderRadius: '6px', fontFamily: "'Fira Code', 'Courier New', monospace", fontSize: '13.5px', border: `1px solid ${darkMode ? 'rgba(192, 132, 252, 0.2)' : 'rgba(126, 34, 206, 0.15)'}` }} {...props}>
                    {children}
                </code>
            );
        }
    }), [darkMode, theme, searchQuery]);

    // 🛠️ FIX AMAN: guard render kosong dipindah ke bawah useMemo agar
    // hooks tidak dipanggil secara kondisional (Rules of Hooks)
    if (!thinkingBlock.trim() && !finalResponseBlock.trim() && !middleContent) {
        return <div style={{ minHeight: '20px' }} />;
    }

    return (
        <div className="cakra-response-wrapper" style={{ width: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* 🧠 1. AKORDION PENALARAN INTERNAL: Ditempatkan di bagian paling atas sesuai urutan masuknya token stream */}
            {thinkingBlock.trim() && (
                <ThoughtAccordion
                    thought={thinkingBlock}
                    darkMode={darkMode}
                    theme={theme}
                    statusMessage={statusMessage}
                    isStreaming={isStreaming}
                />
            )}

            {middleContent}

            {/* 📝 2. RENDER UTAMA JAWABAN: Ditampilkan tepat di bawah proses berpikir */}
            {finalResponseBlock.trim() && (() => {
                // Hapus sintaks widget agar tidak tampil sebagai teks biasa di chat bubble
                const sanitizedResponseBlock = finalResponseBlock
                    .replace(/\[ACTION:(.*?)\]/g, '')
                    .replace(/\[GHOSTWRITER\]/ig, '')
                    .replace(/\[LINEAGE\]/ig, '')
                    .trim();

                return (
                    <div style={{ width: '100%', transition: 'all 0.3s' }}>
                        <ReactMarkdown
                            children={sanitizedResponseBlock}
                            components={markdownComponents}
                            remarkPlugins={[remarkGfm]}
                        />
                        <ChatActionWidgets rawContent={finalResponseBlock} />
                    </div>
                );
            })()}
        </div>
    );
};

export default React.memo(CakraResponseRenderer);