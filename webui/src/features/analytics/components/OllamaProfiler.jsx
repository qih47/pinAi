import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCw, Layers, Zap } from 'lucide-react';
import apiClient from '../../../services/apiClient';

const CORE_SYSTEM_MODELS = [
  { id: 'gemma4:31b', name: 'gemma-4-31B-it-AWQ', displayName: 'Gemma 4 31B AWQ', role: 'Base Engine (vLLM Marlin AWQ)', approxSize: '19.05 GB' },
  { id: 'cakra-router-lora', name: 'cakra-router-lora', displayName: 'cakra-router (LoRA)', role: 'Call 1 Fast Router Adapter', approxSize: '120 MB' },
  { id: 'cakra-core-lora', name: 'cakra-core-lora', displayName: 'cakra-core (LoRA)', role: 'Call 2 Reasoning & Synthesis Adapter', approxSize: '250 MB' },
  { id: 'mxbai-embed-large', name: 'mxbai-embed-large:latest', displayName: 'mxbai-embed-large', role: 'Vector Embedding (Ollama)', approxSize: '589 MB' },
  { id: 'bge-reranker', name: 'bge-reranker-v2-m3', displayName: 'bge-reranker-v2-m3', role: 'Cross-Encoder Reranker (PyTorch)', approxSize: '570 MB' },
  { id: 'f5-tts', name: 'f5-tts-indo', displayName: 'f5-tts-indo', role: 'Voice TTS Engine (PyTorch CUDA)', approxSize: '1.50 GB' },
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
      console.error("Failed to fetch Engine PS", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPS();
    const interval = setInterval(fetchPS, 5000); // 5s polling
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

  const displayedModels = (() => {
    const list = [...CORE_SYSTEM_MODELS];

    return list.map(item => {
      const targetClean = cleanModelName(item.name);
      const targetId = (item.id || '').toLowerCase();

      const active = runningModels.find(rm => {
        const rmId = (rm.id || '').toLowerCase();
        const rmName = cleanModelName(rm.name || rm.model || '');

        // Exact match
        if (rmId && (rmId === targetId || rmId.includes(targetId))) return true;
        if (rmName === targetClean) return true;

        // Base Engine Gemma
        if (targetId === 'gemma4:31b' && (rmName.includes('gemma') || rmId.includes('gemma'))) return true;

        // Router LoRA
        if (targetId.includes('router') && (rmName.includes('router') || rmId.includes('router'))) return true;

        // Core LoRA
        if (targetId.includes('core') && (rmName.includes('core') || rmId.includes('core'))) return true;

        return rmName.includes(targetClean) || targetClean.includes(rmName);
      });

      if (active) {
        const isPinnedForever = (active.expires_at && new Date(active.expires_at).getFullYear() > new Date().getFullYear() + 10) || active.is_vllm || active.is_training;
        const vramPercent = active.size_vram && active.size ? Math.min(100, (active.size_vram / active.size) * 100) : 100;
        const role = active.role || (active.is_vllm ? 'Agentic Base Engine (vLLM Marlin AWQ)' : item.role);
        return {
          ...item,
          role,
          isLoaded: true,
          isTraining: !!active.is_training,
          size_vram: active.size_vram,
          size: active.size,
          vramPercent,
          isPinnedForever,
          untilUnload: active.is_training ? 'Training Lock' : (isPinnedForever ? 'Permanent (Forever)' : formatUntilUnload(active.expires_at)),
        };
      }

      return {
        ...item,
        isLoaded: false,
        isTraining: false,
        size_vram: 0,
        size: 0,
        vramPercent: 0,
        isPinnedForever: false,
        untilUnload: 'Standby / On-Demand',
      };
    });
  })();

  return (
    <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-bold tracking-widest text-gray-400 uppercase flex items-center gap-2">
          <Cpu size={16} className="text-fuchsia-500" /> AI Engine & VRAM Profiler
        </h3>
        <button 
          onClick={fetchPS} 
          className={`text-gray-500 hover:text-cyan-400 transition-colors cursor-pointer ${loading ? 'animate-spin' : ''}`} 
          title="Refresh Status VRAM"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 space-y-3.5 custom-scrollbar">
        {displayedModels.map((m, i) => {
          return (
            <div 
              key={i} 
              className={`rounded-lg p-3.5 border transition-all duration-200 ${
                m.isTraining
                  ? 'bg-amber-950/20 border-amber-500/40 shadow-sm'
                  : m.isLoaded 
                    ? 'bg-[#111827] border-gray-800/80 hover:border-fuchsia-500/30' 
                    : 'bg-[#0d121f]/70 border-gray-800/40 opacity-70 hover:opacity-90'
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="font-bold text-gray-200 flex items-center gap-2 text-sm">
                    {m.displayName}
                    <span className="text-[10px] font-normal text-gray-400">({m.role})</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {m.isTraining ? (
                    <span className="text-[10px] uppercase font-bold tracking-wider bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-500/40 flex items-center gap-1 animate-pulse">
                      <Zap size={10} /> Training
                    </span>
                  ) : m.isLoaded ? (
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
                      Standby
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded font-mono font-medium ${
                    m.isTraining
                      ? 'bg-amber-500/20 text-amber-300'
                      : m.isLoaded 
                        ? 'bg-fuchsia-500/20 text-fuchsia-400' 
                        : 'bg-gray-800/60 text-gray-500'
                  }`}>
                    {m.isLoaded ? `${formatBytes(m.size_vram)} VRAM` : `0 B (${m.approxSize})`}
                  </span>
                </div>
              </div>
              
              <div className="text-xs text-gray-500 flex justify-between mb-1.5">
                <span>Total Size: {m.isLoaded && m.size ? formatBytes(m.size) : `${m.approxSize} (On Disk)`}</span>
                <span className={m.isTraining ? "text-amber-400 font-medium" : (m.isLoaded && m.isPinnedForever ? "text-emerald-400 font-medium" : m.isLoaded ? "text-cyan-400" : "text-gray-500")}>
                  Status: {m.untilUnload}
                </span>
              </div>
              
              <div className="w-full bg-gray-800/70 rounded-full h-1.5 overflow-hidden">
                <div 
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    m.isTraining 
                      ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]'
                      : m.isLoaded 
                        ? 'bg-fuchsia-500 shadow-[0_0_8px_rgba(217,70,239,0.5)]' 
                        : 'bg-transparent'
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
