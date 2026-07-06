import React, { useState, useEffect } from 'react';
import { Cpu, HardDrive, Thermometer, Database } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const HardwareMonitor = () => {
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchTelemetry = async () => {
    try {
      const res = await apiClient.get('/analytics/hardware');
      if (res.data.status === 'success') {
        setTelemetry(res.data.telemetry);
      }
    } catch (e) {
      console.error("Failed to fetch hardware telemetry", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3000); // 3s polling for real-time feel
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (percent) => {
    if (percent > 90) return 'text-red-500 bg-red-500/10 border-red-500/30';
    if (percent > 75) return 'text-amber-500 bg-amber-500/10 border-amber-500/30';
    return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  };
  
  const getProgressColor = (percent) => {
    if (percent > 90) return 'bg-red-500';
    if (percent > 75) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  if (loading && !telemetry) {
    return (
      <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-4 flex items-center justify-center h-[200px] animate-pulse">
        <span className="text-gray-500">Scanning Hardware...</span>
      </div>
    );
  }

  const { cpu_percent, ram_percent, ram_used_gb, ram_total_gb, gpu_percent, vram_used_gb, vram_total_gb, vram_percent, gpu_temp, gpu_name, has_gpu } = telemetry || {};

  return (
    <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 h-full flex flex-col justify-between relative overflow-hidden group">
      
      {/* Background glow based on GPU heat */}
      {has_gpu && gpu_temp > 80 && (
        <div className="absolute inset-0 bg-red-500/5 animate-pulse rounded-xl pointer-events-none" />
      )}

      <div className="flex justify-between items-center mb-4 z-10 relative">
        <h3 className="text-sm font-bold tracking-widest uppercase flex items-center gap-2 text-gray-400">
          <HardDrive size={16} className="text-purple-500" /> 
          Hardware Telemetry
        </h3>
        <div className="flex items-center gap-2 text-xs font-mono text-gray-500">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
          </span>
          SENSOR LINK ACTIVE
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 z-10 relative">
        {/* GPU Block */}
        <div className={`p-4 rounded-lg border ${getStatusColor(gpu_percent)} transition-colors duration-500`}>
          <div className="flex justify-between items-start mb-2">
            <div className="text-xs opacity-70 uppercase tracking-widest font-bold">GPU Compute</div>
            <Cpu size={14} className="opacity-70" />
          </div>
          <div className="text-2xl font-mono font-bold mb-1">
            {has_gpu ? `${gpu_percent}%` : 'N/A'}
          </div>
          <div className="w-full bg-black/40 rounded-full h-1.5 mb-2">
            <div className={`h-1.5 rounded-full ${getProgressColor(gpu_percent)} transition-all duration-500`} style={{ width: `${has_gpu ? gpu_percent : 0}%` }} />
          </div>
          <div className="text-[10px] font-mono opacity-60 truncate" title={gpu_name}>{gpu_name}</div>
        </div>

        {/* VRAM Block */}
        <div className={`p-4 rounded-lg border ${getStatusColor(vram_percent)} transition-colors duration-500`}>
          <div className="flex justify-between items-start mb-2">
            <div className="text-xs opacity-70 uppercase tracking-widest font-bold">GPU VRAM</div>
            <Database size={14} className="opacity-70" />
          </div>
          <div className="text-2xl font-mono font-bold mb-1">
            {has_gpu ? `${vram_percent}%` : 'N/A'}
          </div>
          <div className="w-full bg-black/40 rounded-full h-1.5 mb-2">
            <div className={`h-1.5 rounded-full ${getProgressColor(vram_percent)} transition-all duration-500`} style={{ width: `${has_gpu ? vram_percent : 0}%` }} />
          </div>
          <div className="text-[10px] font-mono opacity-60">
            {has_gpu ? `${vram_used_gb} / ${vram_total_gb} GB` : '0.0 / 0.0 GB'}
          </div>
        </div>

        {/* GPU Temp */}
        <div className={`p-4 rounded-lg border ${gpu_temp > 80 ? 'text-red-500 bg-red-500/10 border-red-500/30' : 'text-orange-400 bg-orange-500/10 border-orange-500/30'} transition-colors duration-500`}>
          <div className="flex justify-between items-start mb-2">
            <div className="text-xs opacity-70 uppercase tracking-widest font-bold">GPU Temp</div>
            <Thermometer size={14} className="opacity-70" />
          </div>
          <div className="text-2xl font-mono font-bold mb-1">
            {has_gpu ? `${gpu_temp}°C` : 'N/A'}
          </div>
          <div className="text-[10px] font-mono opacity-60 mt-4">
            {gpu_temp > 85 ? 'CRITICAL HEAT' : gpu_temp > 75 ? 'WARM' : 'OPTIMAL'}
          </div>
        </div>

        {/* System RAM */}
        <div className={`p-4 rounded-lg border ${getStatusColor(ram_percent)} transition-colors duration-500`}>
          <div className="flex justify-between items-start mb-2">
            <div className="text-xs opacity-70 uppercase tracking-widest font-bold">System RAM</div>
            <Database size={14} className="opacity-70" />
          </div>
          <div className="text-2xl font-mono font-bold mb-1">
            {ram_percent}%
          </div>
          <div className="w-full bg-black/40 rounded-full h-1.5 mb-2">
            <div className={`h-1.5 rounded-full ${getProgressColor(ram_percent)} transition-all duration-500`} style={{ width: `${ram_percent}%` }} />
          </div>
          <div className="text-[10px] font-mono opacity-60">
            {ram_used_gb} / {ram_total_gb} GB
          </div>
        </div>

      </div>
    </div>
  );
};
