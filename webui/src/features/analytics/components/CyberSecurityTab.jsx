import React, { useState, useEffect } from 'react';
import { ShieldAlert, AlertTriangle, AlertCircle, Info, RefreshCw, Activity, Zap, Shield, Eye } from 'lucide-react';
import apiClient from '../../../services/apiClient';

const SEVERITY_CONFIG = {
  CRITICAL: { color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/50', icon: <AlertTriangle size={12}/>, bar: 'bg-red-500' },
  HIGH:     { color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/50', icon: <AlertCircle size={12}/>, bar: 'bg-orange-500' },
  MEDIUM:   { color: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/50', icon: <Info size={12}/>, bar: 'bg-yellow-500' },
  LOW:      { color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30', icon: <Info size={12}/>, bar: 'bg-blue-500' },
};

const ThreatArc = ({ score }) => {
  const clampedScore = Math.max(0, Math.min(100, score));
  const rotation = -90 + (clampedScore / 100) * 180;

  let arcColor = '#22c55e'; // green
  if (clampedScore > 70) arcColor = '#ef4444';
  else if (clampedScore > 40) arcColor = '#f97316';
  else if (clampedScore > 15) arcColor = '#eab308';

  const statusText = clampedScore > 70 ? 'CRITICAL' : clampedScore > 40 ? 'ELEVATED' : clampedScore > 15 ? 'MODERATE' : 'CLEAR';

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-48 h-28">
        <svg viewBox="0 0 200 120" className="w-full h-full drop-shadow-xl">
          <defs>
            <linearGradient id="threatArcBg" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.8"/>
              <stop offset="50%" stopColor="#eab308" stopOpacity="0.8"/>
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.8"/>
            </linearGradient>
          </defs>
          {/* Background arc */}
          <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#1f2937" strokeWidth="14" strokeLinecap="round"/>
          {/* Color arc */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="url(#threatArcBg)"
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray="251.2"
            strokeDashoffset={251.2 - (clampedScore / 100) * 251.2}
            className="transition-all duration-1000 ease-out"
          />
          {/* Needle */}
          <g className="transition-transform duration-1000 ease-out" style={{ transform: `rotate(${rotation}deg)`, transformOrigin: '100px 100px' }}>
            <line x1="100" y1="100" x2="100" y2="28" stroke="white" strokeWidth="5" strokeLinecap="round"/>
          </g>
          <circle cx="100" cy="100" r="9" fill="#111827" stroke="#374151" strokeWidth="2.5"/>
          <circle cx="100" cy="100" r="3" fill={arcColor}/>
          {/* Labels */}
          <text x="15" y="118" fill="#4b5563" fontSize="9" fontWeight="bold">0</text>
          <text x="185" y="118" fill="#4b5563" fontSize="9" fontWeight="bold" textAnchor="end">100</text>
        </svg>
      </div>
      <div className="text-center -mt-2">
        <div className="text-4xl font-black text-white tabular-nums">{clampedScore}</div>
        <div className="text-[10px] font-bold tracking-widest uppercase mt-1" style={{ color: arcColor }}>{statusText}</div>
        <div className="text-[10px] text-gray-500 mt-0.5">Threat Score (24h)</div>
      </div>
    </div>
  );
};

export const CyberSecurityTab = () => {
  const [threatData, setThreatData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const res = await apiClient.get('/analytics/security/threat-score');
      if (res.data.status === 'success') {
        setThreatData(res.data.data);
      }
    } catch (e) {
      console.error("Failed to fetch threat score", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const breakdown = threatData?.breakdown || {};
  const eventTypeCounts = threatData?.event_type_counts || {};
  const recentEvents = threatData?.recent_events || [];
  const totalEvents = threatData?.total_events || 0;
  const score = threatData?.score || 0;
  const maxEventCount = Math.max(...Object.values(eventTypeCounts), 1);

  return (
    <div className="flex-1 flex flex-col gap-5 h-full min-h-0">
      {/* Header */}
      <div className="bg-[#0B0F19]/90 border border-red-900/40 rounded-xl p-4 flex justify-between items-center flex-none">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-red-500/10 rounded-lg border border-red-500/20">
            <ShieldAlert className="text-red-500 w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-200 tracking-wide flex items-center gap-2">
              Security Operations Center
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
              </span>
            </h3>
            <p className="text-xs text-gray-500">Real-time CAKRA Firewall anomaly monitoring</p>
          </div>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 border border-gray-700 hover:border-gray-600 rounded-lg text-xs text-gray-300 transition-colors">
          <RefreshCw size={13} className={loading ? 'animate-spin text-cyan-500' : ''}/>
          Refresh
        </button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 flex-none">
        {/* Threat Score Meter */}
        <div className="bg-[#090C15] border border-gray-800 rounded-xl p-5 flex flex-col items-center justify-center gap-4">
          <h4 className="text-xs font-bold text-gray-500 uppercase tracking-widest self-start flex items-center gap-2">
            <Zap size={12} className="text-yellow-500"/> Threat Level
          </h4>
          {loading ? (
            <div className="h-32 flex items-center justify-center"><Activity className="animate-spin text-gray-600" size={24}/></div>
          ) : (
            <ThreatArc score={score}/>
          )}
        </div>

        {/* Severity Breakdown */}
        <div className="bg-[#090C15] border border-gray-800 rounded-xl p-5 flex flex-col gap-3">
          <h4 className="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
            <Shield size={12} className="text-blue-500"/> Severity Breakdown
          </h4>
          <div className="flex flex-col gap-2.5">
            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => {
              const count = breakdown[sev] || 0;
              const cfg = SEVERITY_CONFIG[sev];
              return (
                <div key={sev} className={`flex items-center gap-3 p-2.5 rounded-lg ${cfg.bg} border ${cfg.border}`}>
                  <span className={`flex items-center gap-1.5 text-[10px] font-bold ${cfg.color} uppercase w-16 shrink-0`}>
                    {cfg.icon} {sev}
                  </span>
                  <div className="flex-1 h-1.5 bg-black/40 rounded-full overflow-hidden">
                    <div className={`h-full ${cfg.bar} rounded-full transition-all duration-700`}
                         style={{ width: totalEvents > 0 ? `${(count / totalEvents) * 100}%` : '0%' }}/>
                  </div>
                  <span className={`text-sm font-black ${cfg.color} w-6 text-right`}>{count}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-auto pt-2 border-t border-gray-800 flex justify-between text-xs text-gray-500">
            <span>Total Events (24h)</span>
            <span className="font-bold text-gray-300">{totalEvents}</span>
          </div>
        </div>

        {/* Attack Type Breakdown */}
        <div className="bg-[#090C15] border border-gray-800 rounded-xl p-5 flex flex-col gap-3">
          <h4 className="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
            <Eye size={12} className="text-purple-500"/> Attack Vectors
          </h4>
          {Object.keys(eventTypeCounts).length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-gray-600">
              <Shield size={32} className="opacity-20"/>
              <p className="text-xs">No attack vectors detected</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {Object.entries(eventTypeCounts)
                .sort(([,a],[,b]) => b - a)
                .slice(0, 5)
                .map(([type, count]) => (
                <div key={type} className="flex flex-col gap-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-400 font-mono truncate max-w-[140px]">{type}</span>
                    <span className="text-purple-400 font-bold">{count}</span>
                  </div>
                  <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-purple-500/70 rounded-full transition-all duration-700"
                         style={{ width: `${(count / maxEventCount) * 100}%` }}/>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Live Event Ticker */}
      <div className="flex-1 bg-[#090C15] border border-gray-800 rounded-xl overflow-hidden flex flex-col min-h-0">
        <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/50 flex-none">
          <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
            <Activity size={12} className="text-red-500 animate-pulse"/> Live Event Feed
          </h4>
          <span className="text-[10px] text-gray-500">Latest {recentEvents.length} events</span>
        </div>
        <div className="overflow-auto flex-1">
          {recentEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-700">
              <ShieldAlert size={40} className="opacity-20"/>
              <p className="text-sm font-medium">No security events. System is secure.</p>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-[#090C15] z-10">
                <tr className="text-gray-500 text-[10px] uppercase tracking-wider">
                  <th className="px-4 py-3 font-semibold">Time</th>
                  <th className="px-4 py-3 font-semibold">Severity</th>
                  <th className="px-4 py-3 font-semibold">Event</th>
                  <th className="px-4 py-3 font-semibold">Actor</th>
                  <th className="px-4 py-3 font-semibold">IP</th>
                  <th className="px-4 py-3 font-semibold">Description</th>
                </tr>
              </thead>
              <tbody>
                {recentEvents.map((log, idx) => {
                  const cfg = SEVERITY_CONFIG[log.severity?.toUpperCase()] || SEVERITY_CONFIG.LOW;
                  return (
                    <tr key={log.id}
                        className={`border-t border-gray-800/50 hover:bg-gray-800/20 transition-colors ${idx === 0 ? 'animate-in slide-in-from-top-2 duration-500' : ''}`}>
                      <td className="px-4 py-3 font-mono text-gray-500 text-xs whitespace-nowrap">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`flex items-center gap-1 ${cfg.bg} ${cfg.color} border ${cfg.border} px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap`}>
                          {cfg.icon} {log.severity?.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs font-mono font-semibold text-gray-300">{log.event_type}</td>
                      <td className="px-4 py-3 font-mono text-xs text-cyan-400">{log.npp}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-400">{log.ip_address}</td>
                      <td className="px-4 py-3 text-xs text-gray-400 max-w-xs truncate" title={log.description}>{log.description}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
