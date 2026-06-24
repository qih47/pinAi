import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThoughtAccordion from './ThoughtAccordion';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeBlockHeader from './CodeBlockHeader';

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
// 🔮 MAIN COMPONENT: CAKRA RESPONSE RENDERER
// =========================================================================
const CakraResponseRenderer = ({ rawContent, thinkingContent, isStreaming, darkMode, theme, searchQuery = '', statusMessage }) => {
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
            return <p style={{ marginTop: 0, marginBottom: '12px', lineHeight: '1.6', whiteSpace: 'normal' }} {...props}>{recursiveHighlight(children, searchQuery)}</p>;
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
        li({ children, ...props }) {
            // paddingLeft: '8px' ini kuncinya cuy! Dia ngasih jarak antara titik/angka dengan huruf pertama.
            // list-style-position bawaan browser otomatis akan bikin baris kedua sejajar sama huruf pertama (hanging indent)
            return <li style={{ marginBottom: '10px', lineHeight: '1.7', paddingLeft: '8px' }} {...props}>{recursiveHighlight(children, searchQuery)}</li>;
        },

        // 4. TEKS BOLD & KUTIPAN (BLOCKQUOTE)
        strong({ children, ...props }) {
            return <strong style={{ fontWeight: 700, color: darkMode ? '#f8fafc' : '#0f172a' }} {...props}>{recursiveHighlight(children, searchQuery)}</strong>;
        },
        blockquote({ children, ...props }) {
            return (
                <blockquote style={{ borderLeft: `4px solid ${darkMode ? '#6366f1' : '#3b82f6'}`, padding: '8px 16px', margin: '16px 0', background: darkMode ? 'rgba(99, 102, 241, 0.1)' : 'rgba(59, 130, 246, 0.05)', borderRadius: '0 8px 8px 0', fontStyle: 'italic', color: theme?.secondaryText || '#6b7280' }} {...props}>
                    {recursiveHighlight(children, searchQuery)}
                </blockquote>
            );
        },

        // 5. TABEL (Dengan Header Background)
        table({ children, ...props }) {
            return (
                <div style={{ overflowX: 'auto', margin: '16px 0' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', border: `1px solid ${theme?.borderColor || '#e5e7eb'}`, fontSize: '13.5px' }} {...props}>
                        {recursiveHighlight(children, searchQuery)}
                    </table>
                </div>
            );
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

        // 6. BLOK KODE (Tetap seperti milik lu aslinya, super aman)
        code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const cleanCode = String(children).replace(/\n$/, '');

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
                <code className={className} style={{ background: darkMode ? '#2d2d30' : '#f1f5f9', color: darkMode ? '#e2e8f0' : '#1e293b', padding: '2px 6px', borderRadius: '4px', fontFamily: "monospace", fontSize: '13px', border: `1px solid ${darkMode ? '#3f3f46' : '#e2e8f0'}` }} {...props}>
                    {children}
                </code>
            );
        }
    }), [darkMode, theme, searchQuery]);

    // 🛠️ FIX AMAN: guard render kosong dipindah ke bawah useMemo agar
    // hooks tidak dipanggil secara kondisional (Rules of Hooks)
    if (!thinkingBlock.trim() && !finalResponseBlock.trim()) {
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

            {/* 📝 2. RENDER UTAMA JAWABAN: Ditampilkan tepat di bawah proses berpikir */}
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

export default React.memo(CakraResponseRenderer);