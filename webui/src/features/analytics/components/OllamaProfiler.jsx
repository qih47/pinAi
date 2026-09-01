import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCw, Layers } from 'lucide-react';
import apiClient from '../../../services/apiClient';

const CORE_SYSTEM_MODELS = [
  { id: 'gemma4:31b', name: 'gemma4:31b', displayName: 'gemma4:31b', role: 'Agentic Core Engine (Call 2 & Vision)', approxSize: '24.15 GB' },
  { id: 'gemma4:e4b', name: 'gemma4:e4b', displayName: 'gemma4:e4b', role: 'Router Engine (Call 1)', approxSize: '3.30 GB' },
  { id: 'mxbai-embed-large', name: 'mxbai-embed-large:latest', displayName: 'mxbai-embed-large', role: 'Vector Embedding (RAG)', approxSize: '589 MB' },
  { id: 'bge-reranker', name: 'bge-reranker-v2-m3', displayName: 'bge-reranker-v2-m3', role: 'Cross-Encoder Reranker (PyTorch)', approxSize: '570 MB' },
  { id: 'f5-tts', name: 'f5-tts-indo', displayName: 'f5-tts-indo', role: 'F5-TTS Voice Engine (PyTorch)', approxSize: '1.50 GB' },
];

export const OllamaProfiler = () => {
  const [runningModels, setRunningModels] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPS = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/analytics/ollama/ps');
      if (res.data && res.data.status === 'success') {
        setRunningModels(res.data.running_models || []);
      }
    } catch (e) {
      console.error("Failed to fetch Ollama PS", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPS();
    const interval = setInterval(fetchPS, 4000); // 4s polling
    return () => clearInterval(interval);
  }, []);

  const formatBytes = (bytes) => {
    if (!bytes || isNaN(bytes) || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatUntilUnload = (expiresAt) => {
    if (!expiresAt) return 'Never';
    const expDate = new Date(expiresAt);
    if (isNaN(expDate.getTime())) return 'Never';
    const currentYear = new Date().getFullYear();
    if (expDate.getFullYear() > currentYear + 10) {
      return 'Permanent (Forever)';
    }
    return expDate.toLocaleTimeString();
  };

  const cleanModelName = (str) => {
    if (!str) return '';
    return str.toLowerCase().replace(/^(baai\/|library\/)/, '').replace(/:latest$/, '').trim();
  };

  // Semua 5 core models selalu dirender permanen
  const displayedModels = (() => {
    const list = [...CORE_SYSTEM_MODELS];

    return list.map(item => {
      const targetClean = cleanModelName(item.name);
      const active = runningModels.find(rm => {
        const rmName = cleanModelName(rm.name || rm.model);
        return rmName === targetClean || rmName.includes(targetClean) || targetClean.includes(rmName);
      });

      if (active) {
        const isPinnedForever = active.expires_at && new Date(active.expires_at).getFullYear() > new Date().getFullYear() + 10;
        const vramPercent = active.size_vram && active.size ? (active.size_vram / active.size) * 100 : 100;
        return {
          ...item,
          isLoaded: true,
          size_vram: active.size_vram,
          size: active.size,
          vramPercent,
          isPinnedForever,
          untilUnload: isPinnedForever ? 'Permanent (Forever)' : formatUntilUnload(active.expires_at),
        };
      }

      return {
        ...item,
        isLoaded: false,
        size_vram: 0,
        size: 0,
        vramPercent: 0,
        isPinnedForever: false,
        untilUnload: 'Not Loaded (Standby)',
      };
    });
  })();

  return (
    <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-bold tracking-widest text-gray-400 uppercase flex items-center gap-2">
          <Cpu size={16} className="text-fuchsia-500" /> VRAM Profiler (Runtime AI)
        </h3>
        <button 
          onClick={fetchPS} 
          className={`text-gray-500 hover:text-cyan-400 transition-colors cursor-pointer ${loading ? 'animate-spin' : ''}`} 
          title="Refresh Status VRAM"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 space-y-3.5">
        {displayedModels.map((m, i) => {
          return (
            <div 
              key={i} 
              className={`rounded-lg p-3.5 border transition-all duration-200 ${
                m.isLoaded 
                  ? 'bg-[#111827] border-gray-800/80 hover:border-fuchsia-500/30' 
                  : 'bg-[#0d121f]/70 border-gray-800/40 opacity-70 hover:opacity-90'
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="font-bold text-gray-200 flex items-center gap-2 text-sm">
                    {m.displayName}
                    <span className="text-[10px] font-normal text-gray-500">({m.role})</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {m.isLoaded ? (
                    m.isPinnedForever ? (
                      <span className="text-[10px] uppercase font-bold tracking-wider bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/30">
                        Pinned 🔒
                      </span>
                    ) : (
                      <span className="text-[10px] uppercase font-bold tracking-wider bg-cyan-500/20 text-cyan-400 px-2 py-0.5 rounded border border-cyan-500/30">
                        Loaded ⚡
                      </span>
                    )
                  ) : (
                    <span className="text-[10px] uppercase font-semibold tracking-wider bg-gray-800/80 text-gray-400 px-2 py-0.5 rounded border border-gray-700/50">
                      Unpinned / Standby
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded font-mono font-medium ${
                    m.isLoaded 
                      ? 'bg-fuchsia-500/20 text-fuchsia-400' 
                      : 'bg-gray-800/60 text-gray-500'
                  }`}>
                    {m.isLoaded ? `${formatBytes(m.size_vram)} VRAM` : `0 B (${m.approxSize})`}
                  </span>
                </div>
              </div>
              
              <div className="text-xs text-gray-500 flex justify-between mb-1.5">
                <span>Total Size: {m.isLoaded && m.size ? formatBytes(m.size) : `${m.approxSize} (On Disk)`}</span>
                <span className={m.isLoaded && m.isPinnedForever ? "text-emerald-400 font-medium" : m.isLoaded ? "text-cyan-400" : "text-gray-500"}>
                  Until Unload: {m.untilUnload}
                </span>
              </div>
              
              <div className="w-full bg-gray-800/70 rounded-full h-1.5 overflow-hidden">
                <div 
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    m.isLoaded ? 'bg-fuchsia-500 shadow-[0_0_8px_rgba(217,70,239,0.5)]' : 'bg-transparent'
                  }`}
                  style={{ width: `${m.isLoaded ? Math.max(m.vramPercent, 5) : 0}%` }}
                ></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
