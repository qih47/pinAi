import React, { useState, useEffect } from 'react';
import { BrainCircuit, Zap } from 'lucide-react';
import apiClient from '../../../services/apiClient';

const AXES = [
  { key: 'dokumen',       label: 'DOKUMEN',    color: '#3b82f6', angle: -90 },
  { key: 'coding',        label: 'CODING',     color: '#10b981', angle: -18 },
  { key: 'flash',         label: 'FLASH',      color: '#a855f7', angle:  54 },
  { key: 'generate_file', label: 'GEN-FILE',   color: '#f97316', angle: 126 },
  { key: 'compliance',    label: 'COMPLIANCE', color: '#eab308', angle: 198 },
];

const toRad = (deg) => (deg * Math.PI) / 180;
const polarToXY = (angle, r, cx, cy) => ({
  x: cx + r * Math.cos(toRad(angle)),
  y: cy + r * Math.sin(toRad(angle)),
});

const RadarSVG = ({ scores, cx = 120, cy = 120, maxR = 90 }) => {
  const levels = [0.2, 0.4, 0.6, 0.8, 1.0];

  // Build polygon points for each level (grid)
  const gridPolygons = levels.map(lvl =>
    AXES.map(ax => polarToXY(ax.angle, maxR * lvl, cx, cy))
      .map(p => `${p.x},${p.y}`)
      .join(' ')
  );

  // Build data polygon
  const dataPoints = AXES.map(ax => {
    const val = (scores[ax.key] || 5) / 100;
    return polarToXY(ax.angle, maxR * val, cx, cy);
  });
  const dataPolygon = dataPoints.map(p => `${p.x},${p.y}`).join(' ');

  // Dominant axis
  const dominant = AXES.reduce((best, ax) =>
    (scores[ax.key] || 0) > (scores[best.key] || 0) ? ax : best
  , AXES[0]);

  return (
    <svg viewBox="0 0 240 240" className="w-full h-full">
      <defs>
        <filter id="radarGlow">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <radialGradient id="radarFill" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={dominant.color} stopOpacity="0.5"/>
          <stop offset="100%" stopColor={dominant.color} stopOpacity="0.05"/>
        </radialGradient>
      </defs>

      {/* Grid lines from center to axes */}
      {AXES.map(ax => {
        const end = polarToXY(ax.angle, maxR, cx, cy);
        return <line key={ax.key} x1={cx} y1={cy} x2={end.x} y2={end.y}
                     stroke="#1e293b" strokeWidth="1"/>;
      })}

      {/* Grid level polygons */}
      {gridPolygons.map((pts, i) => (
        <polygon key={i} points={pts} fill="none" stroke="#1e293b" strokeWidth={i === 4 ? 1.5 : 0.8}
                 strokeDasharray={i === 4 ? '' : '3 3'}/>
      ))}

      {/* Data filled polygon */}
      <polygon points={dataPolygon} fill="url(#radarFill)" stroke={dominant.color}
               strokeWidth="2" filter="url(#radarGlow)"
               className="transition-all duration-1000 ease-out"/>

      {/* Data points */}
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="4" fill={AXES[i].color}
                filter="url(#radarGlow)" className="transition-all duration-1000"/>
      ))}

      {/* Axis labels */}
      {AXES.map(ax => {
        const labelPos = polarToXY(ax.angle, maxR + 18, cx, cy);
        const val = scores[ax.key] || 5;
        return (
          <g key={ax.key}>
            <text x={labelPos.x} y={labelPos.y - 3} textAnchor="middle"
                  fill={ax.color} fontSize="7.5" fontWeight="bold" letterSpacing="0.5">
              {ax.label}
            </text>
            <text x={labelPos.x} y={labelPos.y + 8} textAnchor="middle"
                  fill={ax.color} fontSize="8" fontWeight="black" fillOpacity="0.9">
              {val}%
            </text>
          </g>
        );
      })}

      {/* Center dot */}
      <circle cx={cx} cy={cy} r="3" fill="#374151"/>
    </svg>
  );
};

export const AgenticRadar = () => {
  const [scores, setScores] = useState({ dokumen: 35, coding: 20, flash: 25, generate_file: 10, compliance: 10 });
  const [dominantMode, setDominantMode] = useState('DOKUMEN');
  const [dominantColor, setDominantColor] = useState('#3b82f6');
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchRadarData = async () => {
    try {
      const res = await apiClient.get('/analytics/knowledge/clusters');
      if (res.data?.status === 'success' && Array.isArray(res.data.clusters)) {
        const clusters = res.data.clusters;
        const totalCount = clusters.reduce((acc, c) => acc + (c.count || 0), 0) || 1;

        const rawDoc = clusters.find(c => c.mode === 'dokumen')?.count || 0;
        const rawCode = clusters.find(c => c.mode === 'coding')?.count || 0;
        const rawFlash = clusters.find(c => c.mode === 'flash' || c.mode === 'chitchat')?.count || 0;
        const rawGen = clusters.find(c => c.mode === 'generate_file' || c.mode === 'analitik')?.count || 0;
        const rawComp = clusters.find(c => c.mode === 'compliance' || c.mode === 'deck' || c.mode === 'email')?.count || 0;

        const newScores = {
          dokumen: Math.max(5, Math.min(100, Math.round((rawDoc / totalCount) * 100))),
          coding: Math.max(5, Math.min(100, Math.round((rawCode / totalCount) * 100))),
          flash: Math.max(5, Math.min(100, Math.round((rawFlash / totalCount) * 100))),
          generate_file: Math.max(5, Math.min(100, Math.round((rawGen / totalCount) * 100))),
          compliance: Math.max(5, Math.min(100, Math.round((rawComp / totalCount) * 100))),
        };

        setScores(newScores);
        const dom = AXES.reduce((best, ax) =>
          newScores[ax.key] > newScores[best.key] ? ax : best, AXES[0]);
        setDominantMode(dom.label);
        setDominantColor(dom.color);
        setLastUpdate(new Date());
      }
    } catch (e) {
      console.error('Failed to fetch radar data', e);
    }
  };

  useEffect(() => {
    fetchRadarData();
    const interval = setInterval(fetchRadarData, 10000); // 10s optimized interval
    return () => clearInterval(interval);
  }, []);

  const totalSignal = Object.values(scores).reduce((s, v) => s + v, 0);

  return (
    <div className="h-full w-full rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md p-4 flex flex-col relative overflow-hidden">
      {/* Glow bg */}
      <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl transition-colors duration-1000"
           style={{ backgroundColor: `${dominantColor}10` }}/>

      {/* Header */}
      <div className="flex justify-between items-start mb-3 relative z-10">
        <div>
          <h3 className="flex items-center gap-2 font-bold tracking-widest uppercase text-xs" style={{ color: dominantColor }}>
            <BrainCircuit size={13}/> Agentic Decision Radar
          </h3>
          <div className="flex items-center gap-2 mt-1.5">
            <Zap size={10} style={{ color: dominantColor }}/>
            <span className="text-gray-400 text-[10px]">
              Intent: <span className="font-black text-xs" style={{ color: dominantColor }}>{dominantMode}</span>
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded border animate-pulse"
                style={{ color: dominantColor, borderColor: `${dominantColor}50`, backgroundColor: `${dominantColor}10` }}>
            LIVE
          </span>
          {lastUpdate && (
            <span className="text-[9px] text-gray-600 font-mono">
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Radar SVG */}
      <div className="flex-1 relative z-10 min-h-0">
        <RadarSVG scores={scores}/>
      </div>

      {/* Confidence bars */}
      <div className="mt-3 space-y-1.5 relative z-10">
        {AXES.map(ax => {
          const val = scores[ax.key] || 5;
          const pct = (val / totalSignal) * 100;
          return (
            <div key={ax.key} className="flex items-center gap-2">
              <span className="text-[9px] font-bold w-14 text-right shrink-0" style={{ color: ax.color }}>
                {ax.label}
              </span>
              <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-1000 ease-out"
                     style={{ width: `${pct}%`, backgroundColor: ax.color, boxShadow: `0 0 6px ${ax.color}80` }}/>
              </div>
              <span className="text-[9px] font-mono w-6 text-right shrink-0" style={{ color: ax.color }}>
                {val}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
