import React from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { useSystemMetrics } from '../hooks/useSystemMetrics';

const dummyData = [
  { subject: 'CPU', A: 45, fullMark: 100 },
  { subject: 'MEMORY', A: 85, fullMark: 100 },
  { subject: 'DB IO', A: 30, fullMark: 100 },
  { subject: 'NETWORK', A: 20, fullMark: 100 },
  { subject: 'VRAM', A: 78, fullMark: 100 },
  { subject: 'API', A: 65, fullMark: 100 },
];

export const BottleneckRadar = () => {
  const { metrics } = useSystemMetrics();
  
  const data = metrics?.radar || dummyData;

  // Temukan bottleneck terbesar
  const highest = [...data].sort((a, b) => b.A - a.A)[0];

  return (
    <div className="h-full w-full rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md p-6 flex flex-col">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="text-gray-200 font-semibold tracking-wide uppercase text-sm">BOTTLENECK ANALYSIS</h3>
          <div className="flex items-center gap-4 mt-2">
            <span className="text-gray-400 text-xs">Current: <span className="text-amber-500 font-bold">{highest.subject} {highest.A}%</span></span>
            <span className="text-gray-400 text-xs">Highest: <span className="text-red-400 font-bold">{highest.subject}</span></span>
          </div>
        </div>
        <span className="text-amber-500 font-bold text-xs bg-amber-500/10 px-2 py-1 rounded">Radar Mode</span>
      </div>
      
      <div className="flex-1 w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
            <defs>
              <filter id="glowAmber">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="subject" tick={{ fill: '#9CA3AF', fontSize: 10 }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
              itemStyle={{ color: '#F59E0B' }}
            />
            <Radar 
              name="Load" 
              dataKey="A" 
              stroke="#F59E0B" 
              strokeWidth={2}
              fill="#F59E0B" 
              fillOpacity={0.3} 
              filter="url(#glowAmber)"
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
