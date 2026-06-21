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
const CakraResponseRenderer = ({ rawContent, thinkingContent, isStreaming, darkMode, theme, searchQuery = '' }) => {
    const thinkStartTag = "<think>";
    const thinkEndTag = "</think>";

    // 🔧 FIX: bungkus parsing index/substring dengan useMemo agar hanya
    // dihitung ulang saat rawContent benar-benar berubah, bukan setiap render
    const { thinkingBlock, finalResponseBlock } = useMemo(() => {
        let thinking = thinkingContent || "";
        let final = rawContent || "";

        // Selalu bersihkan tag <think> dari final response agar tidak double render
        if (final.includes(thinkStartTag)) {
            const startIdx = final.indexOf(thinkStartTag);
            const endIdx = final.indexOf(thinkEndTag);

            if (endIdx !== -1 && endIdx > startIdx) {
                // Ekstrak thought ke variabel thinking JIKA thinking belum ada (fallback histori lama)
                if (!thinking) {
                    thinking = final.substring(startIdx + thinkStartTag.length, endIdx);
                }
                const beforeThink = final.substring(0, startIdx);
                const afterThink = final.substring(endIdx + thinkEndTag.length);
                final = `${beforeThink}${afterThink}`;
            } else {
                if (!thinking) {
                    thinking = final.substring(startIdx + thinkStartTag.length);
                }
                final = final.substring(0, startIdx);
            }
        }

        return { thinkingBlock: thinking, finalResponseBlock: final };
    }, [rawContent, thinkingContent]);

    const markdownComponents = useMemo(() => ({
        p({ children, ...props }) {
            return <p style={{ marginTop: 0, marginBottom: '16px', lineHeight: '1.7', whiteSpace: 'normal' }} {...props}>{recursiveHighlight(children, searchQuery)}</p>;
        },
        li({ children, ...props }) {
            return <li style={{ marginBottom: '4px' }} {...props}>{recursiveHighlight(children, searchQuery)}</li>;
        },
        span({ children, ...props }) {
            return <span {...props}>{recursiveHighlight(children, searchQuery)}</span>;
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
    }), [darkMode, searchQuery]);

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