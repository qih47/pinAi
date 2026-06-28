import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const PulseLoader = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: '4px'
  }}>
    <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#818cf8', animation: 'cakraPulse 1.5s infinite ease-in-out' }} />
    <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#818cf8', animation: 'cakraPulse 1.5s infinite ease-in-out 0.2s' }} />
    <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#818cf8', animation: 'cakraPulse 1.5s infinite ease-in-out 0.4s' }} />
  </div>
);

const FileIcon = ({ color }) => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
  </svg>
);

const PencilIcon = ({ color }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9"></path>
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
  </svg>
);

const CheckIcon = ({ color }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>
);

const CheckCircleIcon = ({ color }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
    <polyline points="22 4 12 14.01 9 11.01"></polyline>
  </svg>
);

const ErrorIcon = ({ color }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
);

const ChevronRight = ({ expanded, color }) => (
  <svg 
    width="14" 
    height="14" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke={color} 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round"
    style={{ 
        transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.2s ease',
        cursor: 'pointer',
        display: 'inline-block',
        verticalAlign: 'middle'
    }}
  >
    <polyline points="9 18 15 12 9 6"></polyline>
  </svg>
);

export default function FileProcessLog({ fileGenerations, darkMode, batchIndex = 0, isFinalBatch = false }) {
  const [expanded, setExpanded] = useState(true);
  const [expandedSteps, setExpandedSteps] = useState({});

  if (!fileGenerations || fileGenerations.length === 0) return null;

  // Filter ONLY generations that belong to this batch
  const batchGens = fileGenerations.filter(fg => (fg.batchIndex || 0) === batchIndex);
  if (batchGens.length === 0) return null;

  const textColor = darkMode ? '#e4e4e7' : '#18181b';
  const mutedText = darkMode ? '#a1a1aa' : '#71717a';
  const borderColor = darkMode ? '#3f3f46' : '#d4d4d8';

  const doneCount = batchGens.filter(fg => fg.stage === 'done').length;
  const inProgressCount = batchGens.filter(fg => fg.stage === 'streaming' || fg.stage === 'creating').length;
  const errorCount = batchGens.filter(fg => fg.stage === 'error').length;
  const total = batchGens.length;

  let headerText = "";
  if (inProgressCount > 0) {
    headerText = `Mengerjakan ${inProgressCount} file...`;
  } else if (doneCount === total) {
    headerText = `Selesai ${total} file`;
  } else {
    headerText = `Selesai dengan ${errorCount} error`;
  }

  const toggleStep = (idx) => {
    setExpandedSteps(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  return (
    <div style={{
      marginBottom: '16px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <style>{`
        @keyframes cakraPulse {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.95); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes cakraFadeInSlide {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      
      {/* Header Log - Minimalist without border/card */}
      <div 
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          cursor: 'pointer',
          userSelect: 'none',
          color: mutedText,
          fontSize: '13px',
          fontWeight: 500,
          marginBottom: '8px'
        }}
      >
        <span>{headerText}</span>
        <ChevronRight expanded={expanded} color={mutedText} />
      </div>

      {/* Body Steps */}
      {expanded && (
        <div style={{ paddingLeft: '4px' }}>
          {batchGens.map((fg, idx) => {
            const isError = fg.stage === 'error';
            const isInProgress = fg.stage === 'streaming' || fg.stage === 'creating';
            const isStepExpanded = expandedSteps[idx] || false;
            
            let statusIcon;
            if (isError) statusIcon = <ErrorIcon color="#ef4444" />;
            else if (!isInProgress) statusIcon = <CheckIcon color="#10b981" />;
            else statusIcon = <div style={{ animation: 'cakraPulse 1.5s infinite ease-in-out', display: 'flex' }}><PencilIcon color="#818cf8" /></div>;

            const isAllDone = batchGens.every(g => g.stage === 'done' || g.stage === 'error');

            return (
              <div key={fg.filename + idx} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '6px 0',
                position: 'relative',
                animation: 'cakraFadeInSlide 0.3s ease-out forwards'
              }}>
                {/* Garis vertikal timeline */}
                {(idx !== batchGens.length - 1 || isAllDone) && (
                  <div style={{
                    position: 'absolute',
                    left: '6px',
                    top: '24px',
                    bottom: '-12px',
                    width: '1px',
                    background: borderColor
                  }} />
                )}

                <div style={{
                    width: '14px', 
                    height: '14px', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    marginTop: '2px',
                    zIndex: 1,
                    background: darkMode ? '#18181b' : '#ffffff' // Supaya garis tertutup icon
                }}>
                  {statusIcon}
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', width: '100%' }}>
                  <span 
                    style={{ 
                        fontSize: '13px', 
                        color: textColor, 
                        fontWeight: 500, 
                        display: 'inline-block' 
                    }}
                  >
                    {isInProgress ? (fg.tag_type === 'edit_file' ? `Mengedit ${fg.filename}...` : `Membuat ${fg.filename}...`) : (isError ? `Gagal menulis ${fg.filename}` : `Selesai ${fg.filename}`)}
                  </span>
                  
                  <div 
                    onClick={() => toggleStep(idx)}
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '4px', 
                      fontSize: '11px', 
                      color: mutedText,
                      cursor: 'pointer',
                      width: 'fit-content'
                    }}
                  >
                    <FileIcon color={mutedText} />
                    <span style={{ transition: 'color 0.2s' }} onMouseEnter={(e) => e.target.style.color = textColor} onMouseLeave={(e) => e.target.style.color = mutedText}>
                      File System
                    </span>
                  </div>

                  {/* Expanded Code Block (Terminal-like) */}
                  {isStepExpanded && (
                    <div style={{
                        marginTop: '8px',
                        background: '#1e1e1e', // Dark terminal background
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '6px',
                        padding: '12px',
                        overflowX: 'auto',
                        maxWidth: 'calc(100vw - 120px)'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#a1a1aa', fontSize: '12px', fontFamily: 'monospace' }}>
                            <span style={{ color: '#818cf8' }}>&gt;</span>
                            <span>{`cat > ${fg.filename} << 'EOF'`}</span>
                        </div>
                        {isInProgress ? (
                            <pre style={{
                                margin: 0,
                                padding: 0,
                                background: 'transparent',
                                fontSize: '12px',
                                fontFamily: 'monospace',
                                color: '#d4d4d8',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-all'
                            }}>
                                {fg.liveCode || '// Sedang menginisialisasi...'}
                            </pre>
                        ) : (
                            <SyntaxHighlighter
                                language={fg.filename.split('.').pop() || "javascript"}
                                style={vscDarkPlus}
                                customStyle={{
                                    margin: 0,
                                    padding: 0,
                                    background: 'transparent',
                                    fontSize: '12px'
                                }}
                            >
                                {fg.liveCode || '// Selesai.'}
                            </SyntaxHighlighter>
                        )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* FINAL DONE ROW */}
          {isFinalBatch && batchGens.length > 0 && fileGenerations.every(g => g.stage === 'done' || g.stage === 'error') && (
            <>
                {/* Presented Files Step */}
                <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    padding: '6px 0',
                    position: 'relative',
                    marginTop: '6px',
                    animation: 'cakraFadeInSlide 0.3s ease-out forwards'
                }}>
                    <div style={{
                        position: 'absolute',
                        left: '6px',
                        top: '24px',
                        bottom: '-12px',
                        width: '1px',
                        background: borderColor
                    }} />
                    <div style={{
                        width: '14px', 
                        height: '14px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        marginTop: '2px',
                        zIndex: 1,
                        background: darkMode ? '#18181b' : '#ffffff'
                    }}>
                      <FileIcon color={mutedText} />
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', width: '100%' }}>
                      <span style={{ fontSize: '13px', color: mutedText, fontWeight: 500 }}>
                        Presented {fileGenerations.length} files
                      </span>
                    </div>
                </div>

                {/* Final Done Step */}
                <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    padding: '6px 0',
                    position: 'relative',
                    marginTop: '6px',
                    animation: 'cakraFadeInSlide 0.4s ease-out forwards'
                }}>
                    <div style={{
                        width: '14px', 
                        height: '14px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        marginTop: '2px',
                        zIndex: 1,
                        background: darkMode ? '#18181b' : '#ffffff'
                    }}>
                      <CheckCircleIcon color={mutedText} />
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', width: '100%' }}>
                      <span style={{ fontSize: '13px', color: mutedText, fontWeight: 500 }}>
                        Done
                      </span>
                    </div>
                </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
