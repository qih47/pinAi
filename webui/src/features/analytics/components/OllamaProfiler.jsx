import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCw } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const OllamaProfiler = () => {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPS = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/analytics/ollama/ps');
      if (res.data.status === 'success') {
        setModels(res.data.running_models);
      }
    } catch (e) {
      console.error("Failed to fetch Ollama PS", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPS();
    const interval = setInterval(fetchPS, 10000); // 10s polling
    return () => clearInterval(interval);
  }, []);

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-bold tracking-widest text-gray-400 uppercase flex items-center gap-2">
          <Cpu size={16} className="text-fuchsia-500" /> VRAM Profiler (Ollama)
        </h3>
        <button onClick={fetchPS} className={`text-gray-500 hover:text-cyan-400 transition-colors ${loading ? 'animate-spin' : ''}`}>
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 space-y-4">
        {models.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-gray-500">
            No models currently loaded in VRAM.
          </div>
        ) : (
          models.map((m, i) => {
            const vramPercent = m.size_vram && m.size ? (m.size_vram / m.size) * 100 : 0;
            return (
              <div key={i} className="bg-[#111827] rounded-lg p-4 border border-gray-800/50">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-bold text-gray-200">{m.name}</span>
                  <span className="text-xs bg-fuchsia-500/20 text-fuchsia-400 px-2 py-1 rounded">
                    {formatBytes(m.size_vram)} VRAM
                  </span>
                </div>
                
                <div className="text-xs text-gray-500 flex justify-between mb-2">
                  <span>Total Size: {formatBytes(m.size)}</span>
                  <span>Until Unload: {m.expires_at ? new Date(m.expires_at).toLocaleTimeString() : 'Never'}</span>
                </div>
                
                <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                  <div 
                    className="bg-fuchsia-500 h-1.5 rounded-full" 
                    style={{ width: `${Math.max(vramPercent, 5)}%` }}
                  ></div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
