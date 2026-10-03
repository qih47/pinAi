import React, { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useSystemMetrics } from '../hooks/useSystemMetrics';
import apiClient from '../../../services/apiClient';

export const RequestLatencyChart = () => {
  const [filter, setFilter] = useState('Live Stream');
  const [dbData, setDbData] = useState({ series: [], avg: 0, peak: 0 });
  const [loading, setLoading] = useState(false);
  const { metrics } = useSystemMetrics();

  useEffect(() => {
    if (filter === 'Live Stream') return;

    const periodMap = {
      'Today': 'today',
      'Last 7 Days': '7d',
      'All Times': 'all'
    };

    const fetchLatencies = async () => {
      setLoading(true);
      try {
        const res = await apiClient.get(`/analytics/latencies?period=${periodMap[filter] || 'today'}`);
        if (res.data?.data) {
          setDbData(res.data.data);
        }
      } catch (e) {
        console.error('Failed to fetch aggregated latencies:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchLatencies();
    const interval = setInterval(fetchLatencies, 20000);
    return () => clearInterval(interval);
  }, [filter]);

  const { data, avg, peak } = useMemo(() => {
    if (filter === 'Live Stream') {
      const selectedData = metrics?.latencies?.length ? metrics.latencies : [{ time: '00:00', latency: 0 }];
      const max = Math.max(...selectedData.map(d => d.latency)) || 0;
      const average = selectedData.length ? Math.round(selectedData.reduce((acc, curr) => acc + curr.latency, 0) / selectedData.length) : 0;
      return { data: selectedData, avg: average, peak: max };
    }

    return {
      data: dbData.series?.length ? dbData.series : [{ time: '00:00', latency: 0 }],
      avg: Math.round(dbData.avg || 0),
      peak: Math.round(dbData.peak || 0)
    };
  }, [filter, metrics, dbData]);
  return (
    <div className="h-full w-full rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md p-6 flex flex-col">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="text-gray-200 font-semibold tracking-wide uppercase text-sm">REQUEST LATENCY [ms]</h3>
          <div className="flex items-center gap-4 mt-2">
            <span className="text-gray-400 text-xs">Avg. <span className="text-cyan-400 font-bold">{avg}ms</span></span>
            <span className="text-gray-400 text-xs">Peak <span className="text-amber-500 font-bold">{peak}ms</span></span>
          </div>
        </div>
        <select 
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-[#111827] border border-gray-700 text-gray-300 text-xs rounded px-2 py-1 outline-none cursor-pointer hover:border-gray-500 transition-colors"
        >
          <option value="Live Stream">Live Stream</option>
          <option value="Today">Today</option>
          <option value="Last 7 Days">Last 7 Days</option>
          <option value="All Times">All Times</option>
        </select>
      </div>
      
      <div className="flex-1 w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3.5" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={true} horizontal={true} />
            <XAxis dataKey="time" stroke="#4B5563" tick={{fill: '#6B7280', fontSize: 10}} tickMargin={10} axisLine={false} tickLine={false} />
            <YAxis stroke="#4B5563" tick={{fill: '#6B7280', fontSize: 10}} tickFormatter={(val) => `${val}ms`} axisLine={false} tickLine={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
              itemStyle={{ color: '#22D3EE' }}
            />
            <Line 
              type="monotone" 
              dataKey="latency" 
              stroke="#22D3EE" 
              strokeWidth={3}
              dot={{ fill: '#0B0F19', stroke: '#22D3EE', strokeWidth: 2, r: 4 }}
              activeDot={{ fill: '#22D3EE', stroke: '#fff', r: 6 }}
              filter="url(#glow)"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
