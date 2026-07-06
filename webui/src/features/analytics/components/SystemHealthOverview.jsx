import React from 'react';
import { Cpu, Database, Network, Zap } from 'lucide-react';
import { useSystemMetrics } from '../hooks/useSystemMetrics';

export const SystemHealthOverview = () => {
  const { metrics, isConnected } = useSystemMetrics();

  // Fallback defaults
  const kpi = metrics?.kpi || {
    tokens: "0",
    sessions: "0",
    vram: "0%",
    db_storage: "N/A"
  };
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard 
        title="Token Consumption"
        value={kpi.tokens}
        subtitle="Total Accumulated"
        icon={<Zap className="w-5 h-5 text-cyan-400" />}
        trend="+14% vs yesterday"
        trendUp={true}
      />
      <KpiCard 
        title="Active Sessions"
        value={kpi.sessions}
        subtitle="Last 24 Hours"
        icon={<Network className="w-5 h-5 text-indigo-400" />}
        trend="Peak load reached"
        trendUp={false}
      />
      <KpiCard 
        title="Gemma4 Engine"
        value={kpi.vram}
        subtitle="VRAM Utilization"
        icon={<Cpu className="w-5 h-5 text-amber-500" />}
        trend="Optimal temperature"
        trendUp={true}
      />
      <KpiCard 
        title="Vector DB (PGVector)"
        value={kpi.db_storage}
        subtitle="Storage Capacity"
        icon={<Database className="w-5 h-5 text-red-400" />}
        trend="Nearing limit"
        trendUp={false}
      />
    </div>
  );
};

const KpiCard = ({ title, value, subtitle, icon, trend, trendUp }) => (
  <div className="rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md p-5 flex flex-col justify-between">
    <div className="flex justify-between items-start mb-2">
      <h3 className="text-gray-400 text-xs font-semibold tracking-wider uppercase">{title}</h3>
      <div className="p-2 rounded-lg bg-gray-800/50">{icon}</div>
    </div>
    <div>
      <div className="text-3xl font-bold text-gray-100">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
    </div>
    <div className="mt-4 pt-3 border-t border-gray-800/50 flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${trendUp ? 'bg-green-400' : 'bg-amber-500 animate-pulse'}`} />
      <span className="text-xs text-gray-400">{trend}</span>
    </div>
  </div>
);
