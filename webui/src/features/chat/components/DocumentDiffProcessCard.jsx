import React, { useState } from 'react';
import { 
  Check, 
  ChevronRight, 
  FileText, 
  Terminal, 
  Copy, 
  CheckCheck 
} from 'lucide-react';
import { translations } from '../../../utils/translations';

/**
 * DocumentDiffProcessCard
 * =======================
 * Komponen inspeksi perbandingan naskah dokumen dengan estetika elegan
 * yang 100% selaras dengan alur FileProcessLog (Finished X -> File System -> Diff Inspector).
 */
export default function DocumentDiffProcessCard({
  diffData,
  darkMode = true,
  language = 'id',
  isStreaming = false,
  hasStartedResponding = false
}) {
  const t = translations[language]?.documentDiff || translations.id.documentDiff || {
    finishedComparison: "Selesai 1 komparasi dokumen",
    fileSystem: "File System",
    diffInspector: "Inspeksi Perbedaan Dokumen",
    presented: "Menyajikan 1 komparasi",
    done: "Selesai",
    copied: "Tersalin!",
    copyDiff: "Salin Diff",
    noChanges: "Tidak ada perbedaan teks yang ditemukan."
  };

  const userToggledMainRef = React.useRef(false);
  const userToggledStepRef = React.useRef(false);

  // Auto-collapse: jika sudah mulai streaming teks jawaban atau jika streaming selesai, tutup accordion
  const [isMainExpanded, setIsMainExpanded] = useState(() => {
    return Boolean(isStreaming && !hasStartedResponding);
  });
  const [isStepExpanded, setIsStepExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  // Efek auto-collapse saat respon teks AI mulai mengalir atau setelah streaming usai
  React.useEffect(() => {
    if (userToggledMainRef.current) return;
    if (hasStartedResponding || !isStreaming) {
      const timer = setTimeout(() => {
        setIsMainExpanded(false);
      }, 350);
      return () => clearTimeout(timer);
    } else {
      setIsMainExpanded(true);
    }
  }, [hasStartedResponding, isStreaming]);

  const handleMainToggle = () => {
    userToggledMainRef.current = true;
    setIsMainExpanded(prev => !prev);
  };

  const handleStepToggle = (e) => {
    e.stopPropagation();
    userToggledStepRef.current = true;
    setIsStepExpanded(prev => !prev);
  };

  // Parsing payload tahan banting
  const data = React.useMemo(() => {
    if (!diffData) return {};
    if (typeof diffData === 'string') {
      try {
        return JSON.parse(diffData);
      } catch (e) {
        try {
          const firstBrace = diffData.indexOf('{');
          const lastBrace = diffData.lastIndexOf('}');
          if (firstBrace !== -1 && lastBrace !== -1) {
            return JSON.parse(diffData.substring(firstBrace, lastBrace + 1));
          }
        } catch (e2) {
          return { diff_text: diffData };
        }
        return { diff_text: diffData };
      }
    }
    return diffData;
  }, [diffData]);

  const filename = data.filename || "Komparasi_Klausul_Dokumen.diff";
  const diffContent = data.diff_text || data.diff || "";

  const handleCopy = (e) => {
    e.stopPropagation();
    if (!diffContent) return;
    navigator.clipboard.writeText(diffContent).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const textColor = darkMode ? '#e4e4e7' : '#18181b';
  const mutedText = darkMode ? '#a1a1aa' : '#71717a';

  // Render baris diff dengan penanda warna halus (GitHub-style)
  const renderDiffLines = () => {
    if (!diffContent.trim()) {
      return (
        <div className="p-3 text-xs text-gray-500 italic font-mono">
          {t.noChanges}
        </div>
      );
    }

    const lines = diffContent.split('\n');
    return lines.map((line, idx) => {
      let lineStyle = 'text-zinc-300';
      let bgStyle = 'transparent';

      if (line.startsWith('+++') || line.startsWith('---')) {
        lineStyle = darkMode ? 'text-amber-400 font-semibold' : 'text-amber-700 font-semibold';
        bgStyle = darkMode ? 'rgba(245, 158, 11, 0.08)' : 'rgba(245, 158, 11, 0.12)';
      } else if (line.startsWith('+')) {
        lineStyle = darkMode ? 'text-emerald-400' : 'text-emerald-700';
        bgStyle = darkMode ? 'rgba(16, 185, 129, 0.12)' : 'rgba(16, 185, 129, 0.15)';
      } else if (line.startsWith('-')) {
        lineStyle = darkMode ? 'text-rose-400' : 'text-rose-700';
        bgStyle = darkMode ? 'rgba(244, 63, 94, 0.12)' : 'rgba(244, 63, 94, 0.15)';
      } else if (line.startsWith('@@')) {
        lineStyle = darkMode ? 'text-indigo-400 font-medium' : 'text-indigo-600 font-medium';
        bgStyle = darkMode ? 'rgba(99, 102, 241, 0.08)' : 'rgba(99, 102, 241, 0.1)';
      }

      return (
        <div
          key={idx}
          style={{ background: bgStyle }}
          className={`px-3 py-0.5 font-mono text-[11.5px] leading-relaxed whitespace-pre font-normal select-text ${lineStyle}`}
        >
          {line || ' '}
        </div>
      );
    });
  };

  return (
    <div style={{
      display: 'block',
      width: '100%',
      marginBottom: '16px',
      marginTop: '8px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* 1. Header Accordion Minimalist (Persis FileProcessLog) */}
      <div
        onClick={handleMainToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          width: 'fit-content',
          gap: '6px',
          cursor: 'pointer',
          userSelect: 'none',
          color: mutedText,
          fontSize: '13px',
          fontWeight: 500,
          marginBottom: '8px'
        }}
      >
        <span>{t.finishedComparison || "Finished 1 comparison(s)"}</span>
        <div style={{
          transform: isMainExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease',
          display: 'flex',
          alignItems: 'center'
        }}>
          <ChevronRight size={14} color={mutedText} />
        </div>
      </div>

      {/* 2. Body Steps Container */}
      {isMainExpanded && (
        <div style={{ paddingLeft: '4px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Step File Item */}
            <div>
              {/* Finished filename line */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '13px',
                fontWeight: 600,
                color: textColor
              }}>
                <div style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Check size={11} strokeWidth={3} />
                </div>
                <span>Finished {filename}</span>
              </div>

              {/* Sub dropdown: File System / Diff Inspector */}
              <div
                onClick={handleStepToggle}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '11px',
                  color: isStepExpanded ? '#818cf8' : mutedText,
                  cursor: 'pointer',
                  width: 'fit-content',
                  marginLeft: '26px',
                  marginTop: '4px',
                  transition: 'color 0.2s'
                }}
              >
                <Terminal size={12} color={isStepExpanded ? '#818cf8' : mutedText} />
                <span style={{ fontWeight: 500 }}>
                  {t.fileSystem || "File System"}
                </span>
                <div style={{
                  transform: isStepExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s ease'
                }}>
                  <ChevronRight size={12} color={isStepExpanded ? '#818cf8' : mutedText} />
                </div>
              </div>

              {/* Expanded Diff Window Box (Clean Dark Window persis FileProcessLog) */}
              {isStepExpanded && (
                <div style={{
                  marginLeft: '26px',
                  marginTop: '8px',
                  background: '#0e1015',
                  border: '1px solid rgba(255, 255, 255, 0.09)',
                  borderRadius: '7px',
                  overflow: 'hidden',
                  maxWidth: 'calc(100vw - 120px)'
                }}>
                  {/* Top Bar Header */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '7px 12px',
                    background: '#16181f',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.07)',
                    userSelect: 'none'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      color: '#a1a1aa',
                      fontSize: '11px',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
                    }}>
                      <Terminal size={13} color="#818cf8" />
                      <span style={{ color: '#e4e4e7', fontWeight: 500 }}>
                        {t.diffInspector || "Inspeksi Perbedaan Dokumen"}
                      </span>
                    </div>

                    <button
                      onClick={handleCopy}
                      className="flex items-center gap-1 text-[10.5px] text-gray-400 hover:text-white transition-colors px-1.5 py-0.5 rounded hover:bg-white/5"
                      title={t.copyDiff || "Salin Diff"}
                    >
                      {copied ? (
                        <>
                          <CheckCheck size={12} className="text-emerald-400" />
                          <span className="text-emerald-400 font-sans">{t.copied || "Tersalin"}</span>
                        </>
                      ) : (
                        <>
                          <Copy size={12} />
                          <span className="font-sans">{t.copyDiff || "Salin"}</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Scrollable Content Body */}
                  <div style={{
                    maxHeight: '340px',
                    overflowY: 'auto',
                    overflowX: 'auto',
                    background: '#0a0b0d',
                    padding: '4px 0'
                  }}>
                    {renderDiffLines()}
                  </div>
                </div>
              )}
            </div>

            {/* Presented Line */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: mutedText,
              marginTop: '4px'
            }}>
              <FileText size={13} color={mutedText} />
              <span>{t.presented || "Presented 1 comparison"}</span>
            </div>

            {/* Done Line */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: mutedText
            }}>
              <Check size={13} strokeWidth={2.5} color={mutedText} />
              <span>{t.done || "Done"}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
