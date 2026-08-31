import React, { useState, useEffect, useRef } from 'react';
import { X, MessageSquare, Clock, User, Bot, AlertTriangle, Play, File, Paperclip, CheckSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import apiClient from '../../../services/apiClient';

export const ChatReplayModal = ({ npp, onClose }) => {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [history, setHistory] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const isUserScrolledUp = useRef(false);
  const [forceRender, setForceRender] = useState(0);
  const scrollRef = useRef(null);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const res = await apiClient.get(`/analytics/users/${npp}/sessions`);
        if (res.data.status === 'success') {
          setSessions(res.data.sessions);
        }
      } catch (e) {
        console.error("Failed to fetch sessions", e);
      } finally {
        setLoadingSessions(false);
      }
    };
    fetchSessions();
  }, [npp]);

  useEffect(() => {
    if (!selectedSession) return;
    
    const fetchHistory = async () => {
      setLoadingHistory(true);
      try {
        const res = await apiClient.get(`/analytics/sessions/${selectedSession}`);
        if (res.data.status === 'success') {
          setHistory(res.data.history);
          setAttachments(res.data.attachments || []);
        }
      } catch (e) {
        console.error("Failed to fetch history", e);
      } finally {
        setLoadingHistory(false);
      }
    };
    
    fetchHistory();
    // Optional: auto-refresh active session every 5s for live viewing
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, [selectedSession]);

  // Auto scroll to bottom when history changes
  useEffect(() => {
    if (scrollRef.current && !isUserScrolledUp.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    const isUp = scrollHeight - scrollTop - clientHeight > 50;
    if (isUserScrolledUp.current !== isUp) {
      isUserScrolledUp.current = isUp;
      setForceRender(prev => prev + 1);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 md:p-8">
      <div className="bg-[#0B0F19] border border-cyan-900/50 rounded-2xl w-full max-w-6xl h-full flex flex-col overflow-hidden shadow-2xl shadow-cyan-900/20">
        
        {/* Header */}
        <div className="bg-[#111827] border-b border-gray-800 p-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="bg-cyan-500/20 p-2 rounded-lg">
              <Play className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-200">Live Chat Audit (God Mode)</h2>
              <p className="text-sm text-gray-500">Monitoring activities for NPP: <span className="text-cyan-400 font-mono">{npp}</span></p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-800 rounded-full text-gray-400 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 flex min-h-0">
          
          {/* Sidebar - Sessions */}
          <div className="w-80 border-r border-gray-800 bg-[#05070A] flex flex-col">
            <div className="p-4 border-b border-gray-800">
              <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                <Clock size={16} /> Recent Sessions
              </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {loadingSessions ? (
                <div className="p-4 text-center text-sm text-gray-500 animate-pulse">Loading sessions...</div>
              ) : sessions.length === 0 ? (
                <div className="p-4 text-center text-sm text-gray-500">No sessions found.</div>
              ) : (
                sessions.map((s) => (
                  <button 
                    key={s.session_uuid}
                    onClick={() => setSelectedSession(s.session_uuid)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      selectedSession === s.session_uuid 
                        ? 'bg-cyan-900/30 border border-cyan-800/50' 
                        : 'hover:bg-gray-800/50 border border-transparent'
                    }`}
                  >
                    <div className="font-semibold text-gray-200 truncate">{s.title}</div>
                    <div className="text-xs text-gray-500 mt-1 flex justify-between">
                      <span>{new Date(s.updated_at).toLocaleTimeString()}</span>
                      {s.is_deleted && <span className="text-red-400/80">Deleted</span>}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Main - Chat History */}
          <div className="flex-1 flex flex-col bg-[#0B0F19]">
            {!selectedSession ? (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-600">
                <MessageSquare className="w-16 h-16 mb-4 opacity-20" />
                <p>Select a session from the left to view chat history.</p>
              </div>
            ) : (
              <>
                <div className="p-3 bg-[#111827]/50 border-b border-gray-800 text-xs text-center text-gray-500 flex items-center justify-center gap-2">
                  <AlertTriangle size={14} className="text-yellow-600" />
                  READ-ONLY AUDIT MODE. DO NOT SHARE SENSITIVE INFORMATION.
                </div>
                
                <div 
                  ref={scrollRef} 
                  className="flex-1 overflow-y-auto p-6 space-y-6"
                  onScroll={handleScroll}
                >
                  {attachments.length > 0 && (
                    <div className="bg-cyan-900/10 border border-cyan-800/30 rounded-xl p-4 mb-6">
                      <div className="text-xs font-bold text-cyan-400 uppercase flex items-center gap-2 mb-3">
                        <Paperclip size={14} /> Session Attachments ({attachments.length})
                      </div>
                      <div className="flex flex-wrap gap-3">
                        {attachments.map(att => (
                          <div key={att.id} className="flex items-center gap-3 bg-black/40 border border-gray-700/50 rounded-lg p-3 w-64">
                            <File size={20} className="text-gray-400 flex-shrink-0" />
                            <div className="overflow-hidden">
                              <div className="text-sm font-semibold text-gray-200 truncate" title={att.filename}>{att.filename}</div>
                              <div className="text-xs text-gray-500 uppercase">{att.mime_type?.split('/')[1] || 'FILE'} • {(att.size / 1024).toFixed(1)} KB</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {loadingHistory && history.length === 0 ? (
                    <div className="text-center text-gray-500 animate-pulse">Loading messages...</div>
                  ) : history.length === 0 ? (
                    <div className="text-center text-gray-500">No messages in this session.</div>
                  ) : (
                    history.map((msg, i) => {
                      const isUser = msg.role === 'user';
                      return (
                        <div key={i} className={`flex gap-4 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                            isUser ? 'bg-blue-600/20 text-blue-400' : 'bg-cyan-600/20 text-cyan-400'
                          }`}>
                            {isUser ? <User size={16} /> : <Bot size={16} />}
                          </div>
                          
                          <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
                            <div className="flex items-center gap-2 text-xs text-gray-500">
                              <span className="font-semibold text-gray-400">{isUser ? npp : 'CAKRA AI'}</span>
                              <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                            </div>
                            
                            <div className={`p-4 rounded-2xl ${
                              isUser 
                                ? 'bg-blue-900/20 border border-blue-800/30 text-gray-200' 
                                : 'bg-[#111827] border border-gray-800 text-gray-300'
                            } prose prose-invert prose-sm max-w-none`}>
                              
                              {msg.metadata?.attachments && msg.metadata.attachments.length > 0 && (
                                <div className="mb-3 flex flex-wrap gap-2">
                                  {msg.metadata.attachments.map((att, idx) => (
                                    <div key={idx} className="flex items-center gap-2 bg-black/30 border border-gray-700 rounded-lg p-2 text-xs text-gray-400">
                                      <Paperclip size={14} />
                                      <span className="truncate max-w-[150px]">{att.filename || 'Attachment'}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              
                              <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                                {msg.message_text}
                              </ReactMarkdown>

                              {msg.metadata?.artifacts && msg.metadata.artifacts.length > 0 && (
                                <div className="mt-4 flex flex-col gap-2 border-t border-gray-800 pt-3">
                                  <div className="text-xs font-bold text-gray-500 uppercase flex items-center gap-2"><CheckSquare size={12}/> Artifacts Generated</div>
                                  {msg.metadata.artifacts.map((art, idx) => (
                                    <div key={idx} className="flex flex-col bg-cyan-900/10 border border-cyan-800/30 rounded-lg p-3 text-sm">
                                      <div className="flex items-center gap-2 text-cyan-400 font-mono mb-1">
                                        <File size={14} />
                                        <span>{art.filename}</span>
                                      </div>
                                      <div className="text-gray-500 text-xs">{art.summary}</div>
                                    </div>
                                  ))}
                                </div>
                              )}
                              
                              {!isUser && msg.thought && (
                                <div className="mt-4 p-3 bg-black/40 rounded-lg text-xs font-mono text-gray-500 border border-gray-800/50">
                                  <div className="font-bold mb-1 text-gray-600">THOUGHT PROCESS:</div>
                                  {msg.thought}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};
