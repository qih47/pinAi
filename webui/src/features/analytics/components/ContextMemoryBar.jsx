import React, { useState, useEffect } from 'react';
import { Database, Server, Clock, Cpu } from 'lucide-react';
import apiClient from '../../../services/apiClient';

const dummyMemory = {
  system_tokens: 1500,
  history_tokens: 2000,
  rag_tokens: 4500,
  total_used: 8000,
  max_ctx: 16384
};

export const ContextMemoryBar = () => {
  const [memory, setMemory] = useState(dummyMemory);

  const fetchMemoryData = async () => {
    try {
      const res = await apiClient.get('/analytics/pipeline');
      if (res.data.status === 'success' && res.data.steps) {
        // Cari step CALL_2_SYNTHESIS atau CALL_2_FLASH terbaru
        const call2Step = res.data.steps.find(s => s.tool_called === 'CALL_2_SYNTHESIS' || s.tool_called === 'CALL_2_FLASH');
        if (call2Step && call2Step.observation) {
          try {
            const obsJson = JSON.parse(call2Step.observation);
            if (obsJson.memory) {
              setMemory(obsJson.memory);
            }
          } catch (err) {
            // Not a JSON or no memory
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch memory data", e);
    }
  };

  useEffect(() => {
    fetchMemoryData();
    const interval = setInterval(fetchMemoryData, 3000);
    return () => clearInterval(interval);
  }, []);

  const { system_tokens, history_tokens, rag_tokens, total_used, max_ctx } = memory;
  
  // Calculate percentages (avoid division by zero)
  const safeMax = max_ctx || 16384;
  const sysPct = Math.min(100, (system_tokens / safeMax) * 100);
  const histPct = Math.min(100, (history_tokens / safeMax) * 100);
  const ragPct = Math.min(100, (rag_tokens / safeMax) * 100);
  const totalPct = Math.min(100, (total_used / safeMax) * 100);
  const freePct = Math.max(0, 100 - totalPct);

  return (
    <div className="h-full w-full rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md p-6 flex flex-col relative overflow-hidden group">
      {/* Background glow effects */}
      <div className="absolute top-0 left-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl group-hover:bg-emerald-500/10 transition-colors"></div>
      
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div>
          <h3 className="flex items-center gap-2 text-emerald-400 font-bold tracking-widest uppercase text-xs">
            <Cpu size={14} /> ACTIVE CONTEXT MEMORY
          </h3>
          <div className="flex items-center gap-4 mt-2">
            <span className="text-gray-400 text-xs">Usage: <span className="text-amber-400 font-bold tracking-wider">{total_used.toLocaleString()} / {safeMax.toLocaleString()} Toks</span></span>
          </div>
        </div>
        <div className="text-right">
            <span className="text-emerald-400 font-mono font-bold text-[10px] bg-emerald-900/30 border border-emerald-800 px-2 py-1 rounded">LIVE SYNC</span>
            <div className="mt-2 text-[10px] font-mono text-gray-500">{totalPct.toFixed(1)}% FILLED</div>
        </div>
      </div>
      
      <div className="flex-1 w-full flex flex-col justify-center relative z-10">
        
        {/* The Hollow Graphic Memory Bar */}
        <div className="w-full h-8 bg-gray-900 border border-gray-700 rounded-lg flex overflow-hidden shadow-[inset_0_2px_10px_rgba(0,0,0,0.5)]">
            
            {/* System Area (Red) */}
            <div 
                className="h-full bg-rose-500/80 border-r border-rose-900 relative group/bar transition-all duration-1000" 
                style={{ width: `${sysPct}%` }}
                title={`System Prompt: ${system_tokens} tokens`}
            >
                <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.2)_50%,transparent_75%,transparent_100%)] bg-[length:20px_20px] opacity-20"></div>
            </div>
            
            {/* Context/RAG Area (Green) */}
            <div 
                className="h-full bg-emerald-500/80 border-r border-emerald-900 relative group/bar transition-all duration-1000" 
                style={{ width: `${ragPct}%` }}
                title={`RAG Documents: ${rag_tokens} tokens`}
            >
                <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.2)_50%,transparent_75%,transparent_100%)] bg-[length:20px_20px] opacity-20"></div>
            </div>

            {/* History Area (Blue) */}
            <div 
                className="h-full bg-blue-500/80 border-r border-blue-900 relative group/bar transition-all duration-1000" 
                style={{ width: `${histPct}%` }}
                title={`Chat History: ${history_tokens} tokens`}
            >
                <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.2)_50%,transparent_75%,transparent_100%)] bg-[length:20px_20px] opacity-20"></div>
            </div>
            
            {/* Free Area (Empty) */}
            <div 
                className="h-full bg-transparent relative group/bar transition-all duration-1000" 
                style={{ width: `${freePct}%` }}
                title={`Free Space: ${safeMax - total_used} tokens`}
            >
            </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between mt-6 text-xs font-mono">
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-rose-500"></div>
                <span className="text-gray-400">System <span className="text-gray-500">({system_tokens})</span></span>
            </div>
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                <span className="text-gray-400">RAG <span className="text-gray-500">({rag_tokens})</span></span>
            </div>
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                <span className="text-gray-400">History <span className="text-gray-500">({history_tokens})</span></span>
            </div>
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full border border-gray-600"></div>
                <span className="text-gray-400">Free <span className="text-gray-500">({safeMax - total_used})</span></span>
            </div>
        </div>
      </div>
    </div>
  );
};
