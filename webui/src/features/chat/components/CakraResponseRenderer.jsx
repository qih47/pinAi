import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import ThoughtAccordion from './ThoughtAccordion';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeBlockHeader from './CodeBlockHeader';
import ChatActionWidgets from './ChatActionWidgets';
import { Suspense, lazy } from 'react';
import { translations } from '../../../utils/translations';
import { useChatStore } from '../../../stores/chatStore';
import { CheckCircle, Layers } from 'lucide-react';

const LazyMermaidViewer = lazy(() => import('./MermaidViewer'));
const LazySmartMailWidget = lazy(() => import('./SmartMailChatWidget'));
const LazyGanttViewer = lazy(() => import('./GanttViewer'));
const LazyTimelineInfographic = lazy(() => import('./TimelineInfographic'));
const LazyChartViewer = lazy(() => import('./ChartViewer'));
const LazyReactFlowViewer = lazy(() => import('./ReactFlowViewer'));
import DataGridViewer from './DataGridViewer';
const LazyMapViewer = lazy(() => import('./MapViewer'));
const LazyWebSearchWidget = lazy(() => import('./WebSearchWidget'));
const LazyUrlFetchTimelineWidget = lazy(() => import('./UrlFetchTimelineWidget'));
const LazyInteractiveWizardWidget = lazy(() => import('./InteractiveWizardWidget'));

const remarkPluginsList = [remarkGfm, remarkMath];
const rehypePluginsList = [rehypeKatex];

// 🌐 SMART LINKIFIER: Otomatis ubah domain/URL mentah (seperti jdih.setneg.go.id) menjadi tautan aktif
const linkifyRawDomains = (text) => {
    if (!text || typeof text !== 'string') return text;
    const parts = text.split(/(```[\s\S]*?```|`[^`\n]+`|\[[^\]]+\]\([^\)]+\))/g);
    return parts.map((part, idx) => {
        if (idx % 2 === 1) return part; // Jangan ubah kode atau link yang sudah valid
        return part.replace(
            /(?<![\w@/])((?:https?:\/\/)?(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|gov|go\.id|co\.id|ac\.id|id|io|edu|ai)(?:\/[^\s\)\],<"']*)?)/gi,
            (match) => {
                const cleanMatch = match.replace(/[.,;:]$/, '');
                const suffix = match.slice(cleanMatch.length);
                const href = cleanMatch.startsWith('http://') || cleanMatch.startsWith('https://')
                    ? cleanMatch
                    : `https://${cleanMatch}`;
                return `[${cleanMatch}](${href})${suffix}`;
            }
        );
    }).join('');
};

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

// 🧹 Bersihkan meta-tag [!CONFLICT_ALERT] dari isi teks anak blok alert bentrok
const removeConflictAlertPrefix = (children) => {
    return React.Children.map(children, child => {
        if (typeof child === 'string') {
            return child.replace(/\[!CONFLICT_ALERT\]\s*(?:BENTROK ATURAN:?\s*)?/gi, '');
        }
        if (React.isValidElement(child) && child.props.children) {
            return React.cloneElement(child, {
                children: removeConflictAlertPrefix(child.props.children)
            });
        }
        return child;
    });
};

// =========================================================================
// 🔮 CAKRA MARKDOWN TABLE (SMART FORM EXPORTER)
// =========================================================================
const MarkdownTable = ({ children, darkMode, theme, searchQuery, language = 'id', ...props }) => {
    const tableRef = React.useRef(null);
    const [copied, setCopied] = React.useState(false);
    const tGlobal = translations[language] || translations.id;

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
        } catch (err) {
            console.error("Gagal menyalin tabel:", err);
        }
    };

    return (
        <div className="relative group my-4 rounded-lg overflow-hidden border" style={{ borderColor: theme?.borderColor || '#e5e7eb' }}>
            <button
                onClick={handleCopy}
                title={tGlobal.render.copyTable}
                className={`absolute right-2 top-2 z-10 px-2.5 py-1.5 flex items-center gap-1.5 rounded-lg text-xs font-semibold backdrop-blur-sm transition-all opacity-0 group-hover:opacity-100 ${darkMode ? 'bg-slate-800/90 text-slate-200 hover:bg-slate-700 hover:text-white border border-slate-600 shadow-md' : 'bg-white/90 text-slate-600 hover:bg-slate-50 hover:text-slate-900 shadow-[0_2px_8px_rgba(0,0,0,0.08)] border border-slate-200'}`}
            >
                {copied ? (
                    <>
                        <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                        <span>{tGlobal.render.copied}</span>
                    </>
                ) : (
                    <>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                        <span>{tGlobal.render.copyData}</span>
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

const CakraResponseRenderer = ({ rawContent, thinkingContent, isStreaming, darkMode, theme, searchQuery = '', statusMessage, middleContent, language = 'id', messageIndex = null, isLastMessage = false }) => {
    const tGlobal = translations[language] || translations.id;
    const latestProps = React.useRef({ darkMode, theme, searchQuery, isStreaming, language, rawContent });
    latestProps.current = { darkMode, theme, searchQuery, isStreaming, language, rawContent };
    const thinkStartTag = "<think>";
    const thinkEndTag = "</think>";

    const wizardAnswers = useChatStore(state => state.wizardAnswers);
    const setActiveWizard = useChatStore(state => state.setActiveWizard);
    const activeWizard = useChatStore(state => state.activeWizard);

    const { thinkingBlock, finalResponseBlock, wizardBlock } = useMemo(() => {
        const thinking = thinkingContent || "";
        let final = rawContent || "";

        // Samarkan kata 'mermaid' menjadi 'Cakra AI Diagram' agar user tidak bingung,
        // tapi JANGAN ubah ```mermaid agar engine render tetap jalan
        final = final.replace(/\bmermaid\b/gi, (match, offset, string) => {
            const prevChars = string.slice(Math.max(0, offset - 3), offset);
            if (prevChars === '```') {
                return match;
            }
            return match[0] === 'M' ? 'Cakra AI Diagram' : 'cakra ai diagram';
        });

        // 🔧 Konversi simbol LaTeX inline ($\symbol$) ke karakter Unicode
        // agar tidak tampil sebagai teks mentah di chat
        const latexSymbolMap = {
            '\\rightarrow': '→',
            '\\leftarrow': '←',
            '\\Rightarrow': '⇒',
            '\\Leftarrow': '⇐',
            '\\leftrightarrow': '↔',
            '\\Leftrightarrow': '⇔',
            '\\uparrow': '↑',
            '\\downarrow': '↓',
            '\\times': '×',
            '\\div': '÷',
            '\\pm': '±',
            '\\geq': '≥',
            '\\leq': '≤',
            '\\neq': '≠',
            '\\approx': '≈',
            '\\infty': '∞',
            '\\alpha': 'α',
            '\\beta': 'β',
            '\\gamma': 'γ',
            '\\delta': 'δ',
            '\\sum': '∑',
            '\\prod': '∏',
            '\\sqrt': '√',
            '\\cdot': '·',
        };
        // Ganti $\symbol$ atau \symbol (tanpa dollar sign juga)
        final = final.replace(/\$\\([a-zA-Z]+)\$/g, (_, sym) => {
            return latexSymbolMap[`\\${sym}`] || `\\${sym}`;
        });
        // Ganti $\symbol$ dengan spasi (misal "$\rightarrow$ teks")
        final = final.replace(/\$\\([a-zA-Z]+)\$\s*/g, (_, sym) => {
            const unicode = latexSymbolMap[`\\${sym}`];
            return unicode ? `${unicode} ` : `\\${sym} `;
        });
        // 🔧 Bersihkan block math LaTeX $$ ... $$ yang tidak ter-render dengan baik
        final = final.replace(/\$\$([\s\S]*?)\$\$/g, (_, content) => {
            return content.trim();
        });

        // 🎯 EKSTRAK BLOK WIZARD / INTERACTIVE OPTIONS AGAR SELALU DI-RENDER DI BAWAH TEKS JAWABAN
        let wizard = null;
        const wizardMatch = final.match(/```(?:wizard|interactive_options)\s*([\s\S]*?)```/);
        if (wizardMatch) {
            wizard = wizardMatch[1]?.trim();
            final = final.replace(/```(?:wizard|interactive_options)\s*[\s\S]*?```/, '').trim();
        } else {
            // Tangani partial streaming wizard yang belum ditutup ```
            const unclosedMatch = final.match(/```(?:wizard|interactive_options)\s*([\s\S]*)$/);
            if (unclosedMatch) {
                const partial = unclosedMatch[1]?.trim() || '';
                const firstBrace = partial.indexOf('{');
                const lastBrace = partial.lastIndexOf('}');
                if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
                    try {
                        const parsed = JSON.parse(partial.substring(firstBrace, lastBrace + 1));
                        if (parsed && parsed.questions) {
                            wizard = partial.substring(firstBrace, lastBrace + 1);
                        }
                    } catch (e) {}
                }
                // Sembunyikan teks JSON mentah dari atas chat saat sedang streaming
                final = final.replace(/```(?:wizard|interactive_options)\s*[\s\S]*$/, '').trim();
            }
        }

        // 🌐 Otomatis linkify domain mentah agar selalu bisa diklik sebagai tautan
        final = linkifyRawDomains(final);

        return { thinkingBlock: thinking, finalResponseBlock: final, wizardBlock: wizard };
    }, [rawContent, thinkingContent]);


    const markdownComponents = useMemo(() => ({
        // 1. PARAGRAF (Spasi yang proporsional)
        p({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <p style={{ marginTop: 0, marginBottom: '14px', fontSize: '15px', lineHeight: '1.75', whiteSpace: 'normal', color: darkMode ? '#f1f5f9' : '#334155' }} {...props}>{recursiveHighlight(children, searchQuery)}</p>;
        },

        // 2. HEADINGS (Mengembalikan ukuran judul yang ke-reset oleh Tailwind!)
        h1({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '24px', marginBottom: '12px', lineHeight: '1.3', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h1>;
        },
        h2({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '24px', marginBottom: '12px', lineHeight: '1.3', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h2>;
        },
        h3({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <h3 style={{ fontSize: '1.125rem', fontWeight: 600, marginTop: '20px', marginBottom: '8px', lineHeight: '1.4', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h3>;
        },
        h4({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <h4 style={{ fontSize: '1rem', fontWeight: 600, marginTop: '16px', marginBottom: '8px', lineHeight: '1.4', color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</h4>;
        },

        // 3. LISTS (Indentasi & Jarak Presisi)
        ol({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            // marginLeft menggeser seluruh blok angka agak ke kanan
            // paddingLeft memberi ruang aman biar angkanya gak kepotong
            return <ol style={{ marginLeft: '18px', paddingLeft: '12px', listStyleType: 'decimal', marginTop: '8px', marginBottom: '16px' }} {...props}>{recursiveHighlight(children, searchQuery)}</ol>;
        },
        ul({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <ul style={{ marginLeft: '18px', paddingLeft: '12px', listStyleType: 'disc', marginTop: '8px', marginBottom: '16px' }} {...props}>{recursiveHighlight(children, searchQuery)}</ul>;
        },
        li({ children, className, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
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
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
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
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <strong style={{ fontWeight: 700, color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</strong>;
        },
        blockquote({ children, node, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            // Helper untuk nge-ekstrak raw text dari AST node buat ngecek tag konflik
            const getText = (n) => {
                if (n.type === 'text') return n.value || '';
                if (n.children) return n.children.map(getText).join('');
                return '';
            };
            const textContent = getText(node);

            // Jika ada tag konflik, render UI peringatan yang mencolok dan bisa di-klik (collapsible)
            if (textContent.includes('[!CONFLICT_ALERT]')) {
                const cleanedChildren = removeConflictAlertPrefix(children);
                return (
                    <details open className="my-5 border border-red-500/40 bg-red-500/10 rounded-xl overflow-hidden shadow-[0_0_15px_rgba(239,68,68,0.1)] group cursor-pointer transition-all">
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
                            {recursiveHighlight(cleanedChildren, searchQuery)}
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
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <MarkdownTable children={children} darkMode={darkMode} theme={theme} searchQuery={searchQuery} language={language} {...props} />;
        },
        thead({ children, ...props }) {
            const { darkMode, searchQuery } = latestProps.current;
            return <thead style={{ background: darkMode ? '#334155' : '#f8fafc' }} {...props}>{recursiveHighlight(children, searchQuery)}</thead>;
        },
        th({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <th style={{ padding: '10px 14px', border: `1px solid ${theme?.borderColor || '#e5e7eb'}`, textAlign: 'left', fontWeight: 600, color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</th>;
        },
        td({ children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            return <td style={{ padding: '10px 14px', border: `1px solid ${theme?.borderColor || '#e5e7eb'}` }} {...props}>{recursiveHighlight(children, searchQuery)}</td>;
        },
        span({ children, ...props }) {
            const { searchQuery } = latestProps.current;
            return <span {...props}>{recursiveHighlight(children, searchQuery)}</span>;
        },
        hr({ ...props }) {
            const { darkMode } = latestProps.current;
            return <hr style={{ border: 'none', borderTop: `1px solid ${darkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(203, 213, 225, 0.6)'}`, margin: '16px 0' }} {...props} />;
        },

        // 5.5. TAUTAN / LINKS (Elegan & Buka di tab baru)
        a({ children, href, ...props }) {
            const { darkMode, searchQuery } = latestProps.current;
            return (
                <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`inline-flex items-center gap-1 font-medium transition-all duration-200 
                ${darkMode
                            ? 'text-indigo-300 hover:text-indigo-200 bg-indigo-500/10 hover:bg-indigo-500/20 px-1 rounded-sm'
                            : 'text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-1 rounded-sm'}`}
                    {...props}
                >
                    {recursiveHighlight(children, searchQuery)}
                    <svg className="w-3 h-3 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                </a>
            );
        },

        // Override pre supaya komponen custom (SyntaxHighlighter & MermaidViewer) nggak dibungkus tag <pre> bawaan yang merusak flexbox layout
        pre({ children, ...props }) {
            return <div className="markdown-pre-wrapper" {...props}>{children}</div>;
        },

        // 6. BLOK KODE (Tetap seperti milik lu aslinya, super aman)
        code({ node, inline, className, children, ...props }) {
            const { darkMode, theme, searchQuery, isStreaming, language } = latestProps.current;
            const match = /language-(\w+)/.exec(className || '');
            const cleanCode = String(children).replace(/\n$/, '');

            if (!inline && match && match[1] === 'mermaid') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat engine diagram...</div>}>
                        <LazyMermaidViewer chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'gantt') {
                const trimmedCode = cleanCode.trim();
                const isJson = trimmedCode.startsWith('[');

                if (!isJson) {
                    // LLM terkadang salah me-return sintaks Mermaid di blok markdown bernama gantt.
                    // Alihkan ke MermaidViewer agar tidak rusak/hilang.
                    let mermaidCode = cleanCode;
                    if (!/^gantt/i.test(trimmedCode)) {
                        mermaidCode = "gantt\n" + cleanCode;
                    }
                    return (
                        <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat engine diagram...</div>}>
                            <LazyMermaidViewer chartCode={mermaidCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                        </Suspense>
                    );
                }

                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat Gantt Chart...</div>}>
                        <LazyGanttViewer chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'websearch') {
                let searchData = null;
                try {
                    searchData = JSON.parse(cleanCode);
                } catch (e) {
                    try {
                        const firstBrace = cleanCode.indexOf('{');
                        const lastBrace = cleanCode.lastIndexOf('}');
                        if (firstBrace !== -1 && lastBrace !== -1) {
                            searchData = JSON.parse(cleanCode.substring(firstBrace, lastBrace + 1));
                        }
                    } catch (e2) {
                        searchData = null;
                    }
                }
                const { rawContent, isStreaming, darkMode } = latestProps.current;
                let hasStartedResponding = false;
                if (rawContent && rawContent.includes('```websearch')) {
                    const wsIdx = rawContent.indexOf('```websearch');
                    const afterOpen = rawContent.substring(wsIdx + 12);
                    const closeFenceIdx = afterOpen.indexOf('```');
                    if (closeFenceIdx !== -1) {
                        const afterClose = afterOpen.substring(closeFenceIdx + 3).trim();
                        hasStartedResponding = afterClose.length > 0;
                    }
                }

                return (
                    <Suspense fallback={<div className="animate-pulse p-3 border border-[#2d2d2d] bg-[#1e1e1e] rounded-xl text-xs text-gray-400 font-medium my-2">Memuat hasil pencarian...</div>}>
                        <LazyWebSearchWidget searchData={searchData} isStreaming={isStreaming} hasStartedResponding={hasStartedResponding} darkMode={darkMode} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'urlfetch') {
                let fetchPayload = null;
                try {
                    fetchPayload = JSON.parse(cleanCode);
                } catch (e) {
                    try {
                        const firstBrace = cleanCode.indexOf('{');
                        const lastBrace = cleanCode.lastIndexOf('}');
                        if (firstBrace !== -1 && lastBrace !== -1) {
                            fetchPayload = JSON.parse(cleanCode.substring(firstBrace, lastBrace + 1));
                        }
                    } catch (e2) {
                        fetchPayload = null;
                    }
                }
                const { isStreaming, darkMode, rawContent } = latestProps.current;
                const hasTextAfterBlock = rawContent && rawContent.includes('```urlfetch') && rawContent.split('```urlfetch')[1]?.split('```')[1]?.trim().length > 5;
                const hasStartedResponding = Boolean(hasTextAfterBlock || !isStreaming);

                return (
                    <Suspense fallback={<div className="animate-pulse p-2 text-xs text-gray-400 font-medium my-2">Membaca tautan web...</div>}>
                        <LazyUrlFetchTimelineWidget 
                            data={fetchPayload} 
                            isStreaming={isStreaming} 
                            hasStartedResponding={hasStartedResponding} 
                            darkMode={darkMode} 
                        />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'infographic') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat Infografis Timeline...</div>}>
                        <LazyTimelineInfographic chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'smartmail') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat editor email...</div>}>
                        <LazySmartMailWidget initialData={cleanCode} darkMode={darkMode} theme={theme} language={language} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'chart') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat Engine Grafik...</div>}>
                        <LazyChartViewer chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                    </Suspense>
                );
            }

            if (!inline && match && match[1] === 'flowchart') {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat Interactive Diagram...</div>}>
                        <LazyReactFlowViewer chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                    </Suspense>
                );
            }

            if (!inline && match && (match[1] === 'datagrid' || match[1] === 'tablejson')) {
                return (
                    <DataGridViewer chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                );
            }

            if (!inline && match && (match[1] === 'map' || match[1] === 'mapjson')) {
                return (
                    <Suspense fallback={<div className="animate-pulse p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4">Memuat Interactive Maps...</div>}>
                        <LazyMapViewer chartCode={cleanCode} darkMode={darkMode} isStreaming={isStreaming} language={language} />
                    </Suspense>
                );
            }

            if (!inline && match && (match[1] === 'wizard' || match[1] === 'interactive_options')) {
                // 🎯 Jangan render di dalam markdown bubble, karena wizard di-dock mengambang di atas input bar
                return null;
            }

            return !inline && match ? (
                <div key={`code-block-${match[1]}`} style={{ borderRadius: '10px', overflow: 'hidden', margin: '12px 0', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                    <CodeBlockHeader lang={match[1]} code={cleanCode} language={language} />
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
    }), []);

    // Sync wizard to dock in ChatInputArea when active
    React.useEffect(() => {
        if (wizardBlock && messageIndex !== null && messageIndex !== undefined) {
            const hasAnswered = Boolean(wizardAnswers[messageIndex]);
            if (!hasAnswered && (isLastMessage || isStreaming)) {
                if (activeWizard?.messageIndex !== messageIndex || activeWizard?.data !== wizardBlock) {
                    setActiveWizard({ messageIndex, data: wizardBlock });
                }
            }
        }
    }, [wizardBlock, messageIndex, isLastMessage, isStreaming, wizardAnswers, activeWizard?.messageIndex, activeWizard?.data, setActiveWizard]);

    // 🛠️ FIX AMAN: guard render kosong dipindah ke bawah useMemo agar
    // hooks tidak dipanggil secara kondisional (Rules of Hooks)
    if (!thinkingBlock.trim() && !finalResponseBlock.trim() && !wizardBlock && !middleContent) {
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
            {(finalResponseBlock.trim() || wizardBlock) && (() => {
                // Hapus sintaks widget & meta-tag internal LLM agar tidak bocor ke teks UI
                const sanitizedResponseBlock = finalResponseBlock
                    .replace(/\[ACTION:(.*?)\]/g, '')
                    .replace(/\[GHOSTWRITER\]/ig, '')
                    .replace(/\[LINEAGE\]/ig, '')
                    .replace(/\[(?:TANYA(?:\s+LAGI)?|FOLLOW_UP|KLARIFIKASI|SUMMARY)\]/ig, '')
                let displayContent = sanitizedResponseBlock;
                if (isStreaming && displayContent) {
                    // Hindari flash horizontal rule saat teks berakhir sementara dengan trailing dashes/setext
                    displayContent = displayContent.replace(/\n[-_]{2,}\s*$/, '\n');
                }

                const answeredList = (messageIndex !== null && messageIndex !== undefined) ? wizardAnswers[messageIndex] : null;

                return (
                    <div style={{ width: '100%' }}>
                        {displayContent && (
                            <div className={isStreaming ? 'cakra-streaming-active' : ''}>
                                <ReactMarkdown
                                    children={displayContent}
                                    components={markdownComponents}
                                    remarkPlugins={remarkPluginsList}
                                    rehypePlugins={rehypePluginsList}
                                />
                            </div>
                        )}
                        
                        {/* 🎯 REKAM JEJAK PILIHAN USER (SUMMARY BADGES) SETELAH WIZARD DISUBMIT */}
                        {answeredList && Array.isArray(answeredList) && answeredList.length > 0 && (
                            <div className={`mt-3 pt-2.5 border-t flex flex-col gap-2 ${darkMode ? 'border-zinc-800/80' : 'border-gray-200'}`}>
                                <div className="text-[11.5px] font-semibold text-indigo-400 flex items-center gap-1.5">
                                    <Layers className="w-3.5 h-3.5" />
                                    <span>Konfirmasi Rujukan Terpilih:</span>
                                </div>
                                <div className="flex flex-col gap-1.5">
                                    {answeredList.map((item, idx) => (
                                        <div 
                                            key={idx} 
                                            className={`flex items-start sm:items-center gap-2 px-3 py-1.5 rounded-lg text-[12px] border ${
                                                darkMode 
                                                    ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-200' 
                                                    : 'bg-indigo-50 border-indigo-200 text-indigo-900'
                                            }`}
                                        >
                                            <CheckCircle className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0 mt-0.5 sm:mt-0" />
                                            <div className="flex flex-wrap items-center gap-1 min-w-0">
                                                {item.question && !item.question.toLowerCase().startsWith('pilih salah') && (
                                                    <span className={darkMode ? 'text-zinc-400 font-normal' : 'text-gray-600 font-normal'}>
                                                        {item.question.replace(/[:：\s]+$/, '')}:
                                                    </span>
                                                )}
                                                <span className="font-semibold text-indigo-300">
                                                    {item.answer}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <ChatActionWidgets rawContent={finalResponseBlock} />
                    </div>
                );
            })()}
        </div>
    );
};

export default React.memo(CakraResponseRenderer);