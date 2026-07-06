import React, { useState, useEffect } from 'react';
import { Gauge, Zap } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const TokenVelocityMeter = () => {
  const [tps, setTps] = useState(0);
  const [model, setModel] = useState("gemma4:12b");

  const fetchTpsData = async () => {
    try {
      const res = await apiClient.get('/analytics/pipeline');
      if (res.data.status === 'success' && res.data.steps) {
        // Cari step INFERENCE_STATS terbaru
        const statsStep = res.data.steps.find(s => s.tool_called === 'INFERENCE_STATS');
        if (statsStep && statsStep.observation) {
          try {
            const obsJson = JSON.parse(statsStep.observation);
            if (obsJson.stats && obsJson.stats.tps) {
              setTps(obsJson.stats.tps);
            }
            if (statsStep.tool_input) {
                setModel(statsStep.tool_input.replace('Model: ', ''));
            }
          } catch (err) {
            console.error("Parse error for stats", err);
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch TPS data", e);
    }
  };

  useEffect(() => {
    fetchTpsData();
    const interval = setInterval(fetchTpsData, 2000);
    return () => clearInterval(interval);
  }, []);

  // Konfigurasi Speedometer
  const maxTps = 100; // Maksimal skala jarum (sesuaikan performa A40)
  const clampedTps = Math.min(Math.max(tps, 0), maxTps);
  // Rotasi dari -90 derajat (kiri) ke +90 derajat (kanan)
  const rotation = -90 + (clampedTps / maxTps) * 180;

  // Warna indikator
  let statusColor = "text-red-500";
  let statusText = "SLOW";
  let glowColor = "rgba(239, 68, 68, 0.4)"; // red
  if (tps > 20) {
      statusColor = "text-amber-500";
      statusText = "NORMAL";
      glowColor = "rgba(245, 158, 11, 0.4)"; // amber
  }
  if (tps > 40) {
      statusColor = "text-emerald-500";
      statusText = "FAST";
      glowColor = "rgba(16, 185, 129, 0.4)"; // emerald
  }
  if (tps > 65) {
      statusColor = "text-blue-500";
      statusText = "BLAZING";
      glowColor = "rgba(59, 130, 246, 0.4)"; // blue
  }

  return (
    <div className="h-full w-full rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md p-6 flex flex-col items-center justify-between relative overflow-hidden group">
      {/* Glow background sesuai kecepatan */}
      <div 
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-40 h-40 rounded-full blur-[50px] transition-all duration-1000 opacity-30 group-hover:opacity-60"
        style={{ backgroundColor: glowColor }}
      ></div>

      <div className="flex justify-between w-full relative z-10">
        <h3 className="text-xs font-bold tracking-widest uppercase flex items-center gap-2 text-gray-400">
          <Gauge size={16} className={statusColor} /> 
          Token Velocity
        </h3>
        <span className="text-[10px] font-mono text-gray-500 border border-gray-800 px-2 py-0.5 rounded bg-black/50">
          {model}
        </span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-end relative w-full pb-2 z-10">
        {/* SVG Speedometer Arc */}
        <div className="relative w-full max-w-[280px] aspect-[5/3] flex items-center justify-center">
            <svg viewBox="0 0 200 120" className="w-full h-full drop-shadow-2xl">
                <defs>
                    <linearGradient id="needleGrad" x1="0" y1="1" x2="0" y2="0">
                        <stop offset="0%" stopColor="#4b5563" />
                        <stop offset="100%" stopColor="#ffffff" />
                    </linearGradient>
                </defs>

                {/* Background Arc */}
                <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#1f2937" strokeWidth="15" strokeLinecap="round" />
                
                {/* Foreground Arc (Active) */}
                <path 
                    d="M 20 100 A 80 80 0 0 1 180 100" 
                    fill="none" 
                    stroke="currentColor" 
                    className={`${statusColor} transition-all duration-1000 ease-out`}
                    strokeWidth="15" 
                    strokeLinecap="round" 
                    strokeDasharray="251.2" 
                    strokeDashoffset={251.2 - (clampedTps / maxTps) * 251.2}
                />
                
                {/* Needle Group */}
                <g 
                    className="transition-transform duration-1000 ease-out"
                    style={{ transform: `rotate(${rotation}deg)`, transformOrigin: '100px 100px' }}
                >
                    <line x1="100" y1="100" x2="100" y2="25" stroke="url(#needleGrad)" strokeWidth="6" strokeLinecap="round" />
                </g>
                
                {/* Needle Pivot Center */}
                <circle cx="100" cy="100" r="10" fill="#111827" stroke="#374151" strokeWidth="3" />
                <circle cx="100" cy="100" r="3" fill="#9ca3af" />
            </svg>
        </div>

        {/* Numeric Value — t/s absolute so "0.0" is the true center anchor */}
        <div className="flex flex-col items-center -mt-4">
            <div className="relative inline-block">
                <span className="text-5xl font-black tracking-tighter text-white drop-shadow-md">
                    {tps.toFixed(1)}
                </span>
                <span className="absolute -right-7 bottom-1 text-sm font-bold text-gray-500">t/s</span>
            </div>
            <div className={`text-[11px] font-bold tracking-widest uppercase mt-1 ${statusColor} drop-shadow-sm`}>
                {statusText}
            </div>
        </div>
      </div>
    </div>
  );
};
