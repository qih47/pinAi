import React, { useState, useEffect } from 'react';
import { X, Activity, Database, BrainCircuit, Terminal, ArrowRight, ShieldAlert, Zap, FileText } from 'lucide-react';
import DOMPurify from 'dompurify';
import apiClient from '../../../services/apiClient';

export default function GodModeTelepathyPanel({ sessionUuid, npp, onClose }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [selectedMsgIndex, setSelectedMsgIndex] = useState(null);
  const [expandedSource, setExpandedSource] = useState(null);
  const [userSessions, setUserSessions] = useState([]);
  const [activeSessionUuid, setActiveSessionUuid] = useState(sessionUuid);

  // Fetch list of sessions if NPP is provided
  useEffect(() => {
    if (!npp) return;
    const fetchUserSessions = async () => {
      try {
        const res = await apiClient.get(`/analytics/users/${npp}/sessions`);
        if (res.data?.status === 'success' && res.data.sessions) {
          setUserSessions(res.data.sessions);
          if (res.data.sessions.length > 0 && !activeSessionUuid) {
            setActiveSessionUuid(res.data.sessions[0].session_uuid);
          }
        }
      } catch (err) {
        console.error("Failed to fetch user sessions", err);
      }
    };
    fetchUserSessions();
  }, [npp]);

  // Fetch session history
  useEffect(() => {
    if (!activeSessionUuid) {
      if (!npp) setLoading(false);
      return;
    }
    const fetchSession = async () => {
      setLoading(true);
      setError(null);
      setChatHistory([]);
      setSelectedMsgIndex(null);
      try {
        const res = await apiClient.get(`/analytics/sessions/${activeSessionUuid}`);
        if (res.data?.status === 'success' && res.data.history) {
          setChatHistory(res.data.history);
          const firstAiIndex = res.data.history.findIndex(m => m.role === 'assistant');
          if (firstAiIndex !== -1) {
            setSelectedMsgIndex(firstAiIndex);
          }
        } else {
          setError("Data sesi tidak valid.");
        }
      } catch (err) {
        console.error("Failed to fetch session telepathy:", err);
        setError("Gagal mengambil jejak pikiran AI.");
      } finally {
        setLoading(false);
      }
    };
    fetchSession();
  }, [activeSessionUuid]);

  const selectedMsg = selectedMsgIndex !== null ? chatHistory[selectedMsgIndex] : null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-[#0b0e14] border border-[#2d3748] shadow-2xl shadow-indigo-900/20 w-full max-w-7xl h-[90vh] rounded-2xl flex flex-col overflow-hidden">
        
        {/* HEADER */}
        <div className="h-14 bg-[#11151f] border-b border-[#2d3748] flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-indigo-500/20 rounded-md">
              <BrainCircuit className="text-indigo-400 w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                God Mode: Session Telepathy
                <span className="px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-red-500/20 text-red-400 border border-red-500/30">
                  Level 5 Clearance
                </span>
              </h2>
              {npp ? (
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-gray-400 font-mono">NPP: {npp}</span>
                  {userSessions.length > 0 && (
                    <select 
                      className="bg-black/50 border border-[#2d3748] text-gray-300 text-[10px] rounded px-2 py-0.5 outline-none font-mono"
                      value={activeSessionUuid || ''}
                      onChange={(e) => setActiveSessionUuid(e.target.value)}
                    >
                      {userSessions.map(s => (
                        <option key={s.session_uuid} value={s.session_uuid}>
                          {s.title} ({new Date(s.created_at).toLocaleDateString()})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              ) : (
                <p className="text-[10px] text-gray-500 font-mono mt-1">{activeSessionUuid}</p>
              )}
            </div>
          </div>
          <button 
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center shrink-0 bg-transparent hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-all border-none outline-none"
          >
            <X size={18} />
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center text-indigo-400 gap-4">
            <Activity className="w-10 h-10 animate-spin" />
            <p className="text-sm font-mono animate-pulse">Menghubungkan ke korteks memori AI...</p>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center text-red-400 gap-4">
            <ShieldAlert className="w-12 h-12" />
            <p className="text-sm">{error}</p>
          </div>
        ) : (
          <div className="flex-1 flex min-h-0">
            {/* LEFT PANE: Chat Transcript */}
            <div className="w-1/3 border-r border-[#2d3748] bg-[#0d1117] flex flex-col min-h-0">
              <div className="p-3 border-b border-[#2d3748] bg-[#11151f]">
                <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                  <Terminal size={12}/> Transcript
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {chatHistory.map((msg, idx) => {
                  const isAssistant = msg.role === 'assistant';
                  const isSelected = selectedMsgIndex === idx;
                  return (
                    <div 
                      key={idx}
                      onClick={() => setSelectedMsgIndex(idx)}
                      className={`
                        p-3 rounded-xl border text-sm cursor-pointer transition-all
                        ${isAssistant ? 'ml-6' : 'mr-6'}
                        ${isSelected 
                          ? (isAssistant ? 'bg-indigo-500/10 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.15)]' : 'bg-emerald-500/10 border-emerald-500/50') 
                          : 'bg-[#161b22] border-transparent hover:border-[#2d3748]'
                        }
                      `}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${isAssistant ? 'text-indigo-400' : 'text-emerald-400'}`}>
                          {msg.role}
                        </span>
                        <span className="text-[9px] text-gray-500 font-mono">
                          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                        </span>
                      </div>
                      <div className="text-gray-300 text-xs line-clamp-4 overflow-hidden" 
                           dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(msg.message_text.replace(/\\n/g, '<br/>'))}} 
                      />
                      {isAssistant && msg.thought && (
                        <div className="mt-3 pt-2 border-t border-gray-800 flex items-center justify-between">
                          <span className="text-[9px] text-yellow-500/70 flex items-center gap-1 font-mono">
                            <Zap size={10}/> Thought Process Detected
                          </span>
                          {isSelected && <ArrowRight size={12} className="text-indigo-400 animate-pulse"/>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* RIGHT PANE: X-Ray Inspector */}
            <div className="flex-1 bg-[#090b10] flex flex-col min-h-0">
              <div className="p-3 border-b border-[#2d3748] bg-[#11151f] flex justify-between items-center">
                <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                  <Activity size={12}/> X-Ray Inspector
                </h3>
                {selectedMsg && (
                  <span className="text-[10px] text-gray-500 font-mono bg-black/40 px-2 py-1 rounded border border-gray-800">
                    Inspecting Log #{selectedMsgIndex + 1}
                  </span>
                )}
              </div>
              
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {!selectedMsg ? (
                  <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-3">
                    <BrainCircuit size={40} className="opacity-20"/>
                    <p className="text-xs font-mono">Pilih pesan di sebelah kiri untuk melihat Nalar AI</p>
                  </div>
                ) : (
                  <>
                    {/* THOUGHT PROCESS */}
                    {selectedMsg.role === 'assistant' && selectedMsg.thought ? (
                      <div className="bg-[#111520] border border-indigo-900/40 rounded-xl overflow-hidden">
                        <div className="px-4 py-2 bg-indigo-950/30 border-b border-indigo-900/40 flex items-center gap-2">
                          <BrainCircuit className="text-indigo-400 w-4 h-4"/>
                          <h4 className="text-[11px] font-bold text-indigo-300 uppercase tracking-widest">Internal Monologue</h4>
                        </div>
                        <div className="p-4 bg-[#0d1017]">
                          <pre className="text-[11px] text-indigo-200/80 font-mono whitespace-pre-wrap overflow-x-auto">
                            {selectedMsg.thought}
                          </pre>
                        </div>
                      </div>
                    ) : (
                      selectedMsg.role === 'assistant' && (
                        <div className="p-4 border border-dashed border-gray-800 rounded-xl flex items-center justify-center text-gray-600 text-xs font-mono">
                          Tidak ada rekaman monolog untuk pesan ini
                        </div>
                      )
                    )}

                    {/* RAG SOURCES */}
                    {selectedMsg.role === 'assistant' && selectedMsg.sources && selectedMsg.sources.length > 0 && (
                      <div className="bg-[#15130d] border border-yellow-900/40 rounded-xl overflow-hidden">
                        <div className="px-4 py-2 bg-yellow-950/30 border-b border-yellow-900/40 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Database className="text-yellow-500 w-4 h-4"/>
                            <h4 className="text-[11px] font-bold text-yellow-500 uppercase tracking-widest">Vector Context Retrieved</h4>
                          </div>
                          <span className="text-[10px] text-yellow-600 font-mono">{selectedMsg.sources.length} Chunks</span>
                        </div>
                        <div className="p-4 bg-[#0d0b09] space-y-3">
                          {selectedMsg.sources.map((src, i) => (
                            <div key={i} className="border border-yellow-900/30 rounded-lg bg-[#110e0b]">
                              <div 
                                className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-yellow-900/20"
                                onClick={() => setExpandedSource(expandedSource === i ? null : i)}
                              >
                                <div className="flex items-center gap-2 max-w-[80%]">
                                  <FileText size={12} className="text-yellow-600 shrink-0"/>
                                  <span className="text-xs text-yellow-200/80 font-mono truncate">
                                    {src.metadata?.filename || src.metadata?.source || 'Unknown Source'}
                                  </span>
                                </div>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-500 border border-yellow-500/20">
                                  Score: {src.score !== undefined ? (src.score * 100).toFixed(1) : 'N/A'}
                                </span>
                              </div>
                              {expandedSource === i && (
                                <div className="p-3 border-t border-yellow-900/30 text-[11px] text-yellow-100/60 leading-relaxed font-mono whitespace-pre-wrap">
                                  {src.content}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* METADATA */}
                    {Object.keys(selectedMsg.metadata || {}).length > 0 && (
                      <div className="bg-[#0b1215] border border-cyan-900/40 rounded-xl overflow-hidden">
                        <div className="px-4 py-2 bg-cyan-950/30 border-b border-cyan-900/40 flex items-center gap-2">
                          <Terminal className="text-cyan-500 w-4 h-4"/>
                          <h4 className="text-[11px] font-bold text-cyan-500 uppercase tracking-widest">Metadata Artifacts</h4>
                        </div>
                        <div className="p-4 bg-[#080d10]">
                          <pre className="text-[11px] text-cyan-200/80 font-mono whitespace-pre-wrap overflow-x-auto">
                            {JSON.stringify(selectedMsg.metadata, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}

                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
