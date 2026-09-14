import React, { useState, useEffect, useMemo } from 'react';
import { 
  Coins, 
  TrendingUp, 
  TrendingDown, 
  Cpu, 
  Layers, 
  Clock, 
  Search, 
  RefreshCw, 
  Filter, 
  ChevronLeft, 
  ChevronRight,
  Sparkles,
  BarChart3,
  Calendar,
  Zap,
  CheckCircle2,
  Copy
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid, 
  Legend 
} from 'recharts';
import apiClient from '../../../services/apiClient';

const MODE_COLORS = {
  general: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  guest: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  documents: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  coding: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  flash: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  docwriter: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
  web_search: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  collab: 'bg-pink-500/10 text-pink-400 border-pink-500/30',
};

export const TokenMonitorTab = () => {
  const [days, setDays] = useState(0);
  const [dailyData, setDailyData] = useState(null);
  const [loadingDaily, setLoadingDaily] = useState(true);

  // Request logs pagination & filter state
  const [logs, setLogs] = useState([]);
  const [totalLogs, setTotalLogs] = useState(0);
  const [loadingLogs, setLoadingLogs] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMode, setSelectedMode] = useState('all');
  const [copiedId, setCopiedId] = useState(null);

  // Fetch Daily Aggregations
  const fetchDailyData = async () => {
    setLoadingDaily(true);
    try {
      const res = await apiClient.get(`/analytics/tokens/daily?days=${days}`);
      if (res.data?.status === 'success') {
        setDailyData(res.data);
      }
    } catch (err) {
      console.error('Failed to fetch daily token data', err);
    } finally {
      setLoadingDaily(false);
    }
  };

  // Fetch Request Logs
  const fetchLogs = async () => {
    setLoadingLogs(true);
    try {
      const offset = (page - 1) * pageSize;
      let url = `/analytics/tokens/requests?limit=${pageSize}&offset=${offset}`;
      if (searchQuery.trim()) url += `&search=${encodeURIComponent(searchQuery.trim())}`;
      if (selectedMode && selectedMode !== 'all') url += `&mode=${encodeURIComponent(selectedMode)}`;

      const res = await apiClient.get(url);
      if (res.data?.status === 'success') {
        setLogs(res.data.logs || []);
        setTotalLogs(res.data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch token request logs', err);
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    fetchDailyData();
  }, [days]);

  useEffect(() => {
    fetchLogs();
  }, [page, searchQuery, selectedMode]);

  const handleCopyId = (id) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const totalPages = Math.ceil(totalLogs / pageSize) || 1;
  const kpi = dailyData?.kpi || {};

  // Custom Recharts Tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const total = (payload[0]?.value || 0) + (payload[1]?.value || 0);
      return (
        <div className="bg-[#0B0F19] border border-gray-700 p-3 rounded-lg shadow-xl text-xs space-y-1">
          <p className="font-semibold text-gray-200">{label}</p>
          <p className="text-cyan-400">
            Prompt: <span className="font-bold">{payload[0]?.value?.toLocaleString()}</span> tokens
          </p>
          <p className="text-purple-400">
            Completion: <span className="font-bold">{payload[1]?.value?.toLocaleString()}</span> tokens
          </p>
          <div className="border-t border-gray-800 pt-1 text-gray-300 font-bold">
            Total: {total.toLocaleString()} tokens
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-300 pb-12">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#0B0F19]/90 border border-gray-800 p-4 rounded-xl backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2">
            <Coins className="text-cyan-400 w-5 h-5" />
            <h2 className="text-base font-bold text-gray-100 tracking-wide">
              TOKEN CONSUMPTION & AUDIT RADAR
            </h2>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            Pelacakan akurat konsumsi token riil (Call 1 Router + Call 2 Generator) per-request dan historis
          </p>
        </div>

        {/* Days Filter Pills */}
        <div className="flex items-center gap-2">
          <div className="flex bg-[#05070A] p-1 rounded-lg border border-gray-800 text-xs">
            {[
              { label: 'Semua Waktu', value: 0 },
              { label: '7 Hari', value: 7 },
              { label: '14 Hari', value: 14 },
              { label: '30 Hari', value: 30 },
            ].map((item) => (
              <button
                key={item.value}
                onClick={() => setDays(item.value)}
                className={`px-3 py-1 rounded-md transition-all font-medium ${
                  days === item.value
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              fetchDailyData();
              fetchLogs();
            }}
            disabled={loadingDaily || loadingLogs}
            className="p-2 bg-gray-800/60 hover:bg-gray-700/60 text-gray-300 rounded-lg border border-gray-700 transition-colors disabled:opacity-50"
            title="Refresh Data"
          >
            <RefreshCw size={14} className={loadingDaily || loadingLogs ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Today's Consumption */}
        <div className="bg-[#0B0F19]/90 border border-gray-800 p-4 rounded-xl relative overflow-hidden group hover:border-cyan-500/40 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
              Konsumsi Hari Ini
            </span>
            <div className="p-2 bg-cyan-500/10 rounded-lg text-cyan-400">
              <Zap size={16} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-gray-100 font-mono">
              {(kpi.today_tokens || 0).toLocaleString()}
            </span>
            <span className="text-xs text-gray-400">tokens</span>
          </div>
          <div className="mt-2 flex items-center text-xs">
            {kpi.pct_change > 0 ? (
              <span className="flex items-center text-rose-400 font-medium">
                <TrendingUp size={12} className="mr-1" /> +{kpi.pct_change}%
              </span>
            ) : kpi.pct_change < 0 ? (
              <span className="flex items-center text-emerald-400 font-medium">
                <TrendingDown size={12} className="mr-1" /> {kpi.pct_change}%
              </span>
            ) : (
              <span className="text-gray-500 font-medium">— stabil vs kemarin</span>
            )}
            <span className="text-gray-500 ml-1.5 text-[10px]">vs hari kemarin</span>
          </div>
        </div>

        {/* Card 2: Period Total */}
        <div className="bg-[#0B0F19]/90 border border-gray-800 p-4 rounded-xl relative overflow-hidden group hover:border-purple-500/40 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
              {days === 0 ? 'Total Periode (Semua)' : `Total ${days} Hari Terakhir`}
            </span>
            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
              <Layers size={16} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-gray-100 font-mono">
              {(kpi.period_total_tokens || 0).toLocaleString()}
            </span>
            <span className="text-xs text-gray-400">tokens</span>
          </div>
          <div className="mt-2 text-xs text-gray-400">
            Dari <span className="text-purple-400 font-semibold">{(kpi.period_requests || 0).toLocaleString()}</span> permintaan di rentang ini
          </div>
        </div>

        {/* Card 3: All-Time Cumulative Total */}
        <div className="bg-[#0B0F19]/90 border border-gray-800 p-4 rounded-xl relative overflow-hidden group hover:border-amber-500/40 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-medium text-amber-400/90 uppercase tracking-wider font-semibold">
              Total Akumulatif (All-Time)
            </span>
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
              <Coins size={16} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-amber-300 font-mono">
              {((kpi.all_time_tokens || kpi.period_total_tokens || 0) >= 1000000 
                ? `${((kpi.all_time_tokens || kpi.period_total_tokens || 0) / 1000000).toFixed(2)}M` 
                : (kpi.all_time_tokens || 0).toLocaleString())}
            </span>
            <span className="text-xs text-gray-400">
              ({(kpi.all_time_tokens || 0).toLocaleString()} tok)
            </span>
          </div>
          <div className="mt-2 text-xs text-gray-400">
            Dari <span className="text-amber-400 font-semibold">{(kpi.all_time_requests || 0).toLocaleString()}</span> total chat sepanjang masa
          </div>
        </div>

        {/* Card 4: Avg per Request */}
        <div className="bg-[#0B0F19]/90 border border-gray-800 p-4 rounded-xl relative overflow-hidden group hover:border-emerald-500/40 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
              Rata-rata / Request
            </span>
            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
              <Cpu size={16} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-gray-100 font-mono">
              {(kpi.avg_tokens_per_req || 0).toLocaleString()}
            </span>
            <span className="text-xs text-gray-400">tokens</span>
          </div>
          <div className="mt-2 text-xs text-gray-400">
            Peak: <span className="text-emerald-400 font-semibold">{kpi.peak_day || '—'}</span>
          </div>
        </div>
      </div>

      {/* Visual Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Daily Trend Bar Chart */}
        <div className="lg:col-span-2 bg-[#0B0F19]/90 border border-gray-800 p-5 rounded-xl flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="text-cyan-400 w-4 h-4" />
              <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                TREN PENGGUNAAN TOKEN PER HARI
              </h3>
            </div>
            <div className="flex items-center gap-3 text-[11px]">
              <span className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-2 h-2 rounded-sm bg-cyan-400 inline-block" /> Prompt (Input)
              </span>
              <span className="flex items-center gap-1.5 text-purple-400">
                <span className="w-2 h-2 rounded-sm bg-purple-500 inline-block" /> Completion (Output)
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            {dailyData?.series && dailyData.series.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyData.series} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="#4b5563" 
                    fontSize={10} 
                    minTickGap={20}
                    tickFormatter={(val) => val.slice(5)}
                  />
                  <YAxis 
                    stroke="#4b5563" 
                    fontSize={10} 
                    tickFormatter={(val) => val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="prompt_tokens" stackId="a" fill="#22d3ee" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="completion_tokens" stackId="a" fill="#a855f7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full w-full flex flex-col items-center justify-center text-gray-500 text-xs gap-2">
                <Coins size={28} className="opacity-30" />
                <span>Belum ada riwayat penggunaan token untuk periode ini.</span>
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Col: Model Breakdown */}
        <div className="bg-[#0B0F19]/90 border border-gray-800 p-5 rounded-xl flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="text-purple-400 w-4 h-4" />
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              DISTRIBUSI MODEL
            </h3>
          </div>

          <div className="flex-1 flex flex-col justify-center space-y-4">
            {dailyData?.models && dailyData.models.length > 0 ? (
              dailyData.models.map((m, idx) => {
                const totalPeriod = kpi.period_total_tokens || 1;
                const pct = Math.min(100, Math.round((m.tokens / totalPeriod) * 100));
                return (
                  <div key={idx} className="space-y-1.5 bg-[#05070A]/60 p-3 rounded-lg border border-gray-800/80">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-mono text-gray-200 font-semibold">{m.model}</span>
                      <span className="text-cyan-400 font-bold font-mono">{m.tokens.toLocaleString()} tok</span>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                      <div 
                        className="bg-gradient-to-r from-cyan-400 to-purple-500 h-full rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="flex justify-between items-center text-[10px] text-gray-400">
                      <span>{m.requests} requests</span>
                      <span>{pct}% total volume</span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-center text-xs text-gray-500 py-8">
                Data model belum tersedia.
              </div>
            )}

            {/* Note info box */}
            <div className="p-3 bg-cyan-950/20 border border-cyan-800/30 rounded-lg text-[11px] text-cyan-300 flex items-start gap-2">
              <Sparkles size={14} className="shrink-0 mt-0.5 text-cyan-400" />
              <span>
                <strong>Gemma 4 e4b</strong> bertindak sebagai Call 1 Router instan (~850 token/req), sedangkan <strong>Gemma 4 31b</strong> bertindak sebagai generator respons persona utama.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Real-Time Request Audit Table */}
      <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
        {/* Table Header & Search Filters */}
        <div className="p-4 border-b border-gray-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              LOG AUDIT PER-REQUEST TOKEN
            </h3>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Menampilkan {logs.length} dari {totalLogs} riwayat permintaan
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            {/* Search Input */}
            <div className="relative flex-1 sm:w-60">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                placeholder="Cari Req ID / NPP / Session..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#05070A] border border-gray-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500/50"
              />
            </div>

            {/* Mode Dropdown */}
            <select
              value={selectedMode}
              onChange={(e) => {
                setSelectedMode(e.target.value);
                setPage(1);
              }}
              className="bg-[#05070A] border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-cyan-500/50 cursor-pointer"
            >
              <option value="all">Semua Mode</option>
              <option value="general">General</option>
              <option value="guest">Guest</option>
              <option value="documents">Documents (RAG)</option>
              <option value="coding">Coding</option>
              <option value="flash">Flash</option>
              <option value="docwriter">DocWriter</option>
              <option value="web_search">Web Search</option>
            </select>
          </div>
        </div>

        {/* Table Body */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-gray-800 bg-[#05070A]/50 text-gray-400 font-semibold uppercase text-[10px] tracking-wider">
                <th className="py-3 px-4">Waktu</th>
                <th className="py-3 px-4">Request ID</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Mode</th>
                <th className="py-3 px-4 text-right">Router (Prompt/Out)</th>
                <th className="py-3 px-4 text-right">Generator (Prompt/Out)</th>
                <th className="py-3 px-4 text-right">Total Tokens</th>
                <th className="py-3 px-4 text-right">Durasi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50 text-gray-300 font-mono">
              {loadingLogs ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-gray-500">
                    <RefreshCw size={18} className="animate-spin inline mr-2 text-cyan-400" />
                    Memuat data audit token...
                  </td>
                </tr>
              ) : logs.length > 0 ? (
                logs.map((row) => {
                  const modeClass = MODE_COLORS[row.mode?.toLowerCase()] || 'bg-gray-500/10 text-gray-400 border-gray-500/30';
                  const isCopied = copiedId === row.request_id;
                  const formattedTime = row.timestamp ? new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
                  const formattedDate = row.timestamp ? new Date(row.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '';

                  return (
                    <tr key={row.id} className="hover:bg-gray-800/30 transition-colors font-sans">
                      {/* Timestamp */}
                      <td className="py-2.5 px-4 text-gray-400 text-xs whitespace-nowrap">
                        <span className="font-mono text-gray-200">{formattedTime}</span>
                        <span className="text-[10px] text-gray-500 block">{formattedDate}</span>
                      </td>

                      {/* Request ID */}
                      <td className="py-2.5 px-4 font-mono text-xs">
                        <button
                          onClick={() => handleCopyId(row.request_id)}
                          className="flex items-center gap-1.5 text-cyan-400 hover:text-cyan-300 transition-colors"
                          title="Klik untuk salin Request ID"
                        >
                          <span>{row.request_id?.slice(0, 8) || '—'}</span>
                          {isCopied ? <CheckCircle2 size={11} className="text-emerald-400" /> : <Copy size={11} className="opacity-40" />}
                        </button>
                      </td>

                      {/* User */}
                      <td className="py-2.5 px-4">
                        <span className={`text-[11px] px-2 py-0.5 rounded font-mono font-medium ${row.user_npp === 'GUEST' ? 'bg-gray-800 text-gray-400' : 'bg-cyan-950/40 text-cyan-300 border border-cyan-800/40'}`}>
                          {row.user_npp || 'GUEST'}
                        </span>
                      </td>

                      {/* Mode */}
                      <td className="py-2.5 px-4">
                        <span className={`text-[10px] px-2 py-0.5 rounded border uppercase tracking-wider font-semibold ${modeClass}`}>
                          {row.mode || 'general'}
                        </span>
                      </td>

                      {/* Router Tokens */}
                      <td className="py-2.5 px-4 text-right font-mono text-xs text-gray-400">
                        <span className="text-gray-300">{row.router_prompt_tokens}</span>
                        <span className="text-gray-500 mx-1">/</span>
                        <span className="text-cyan-400">{row.router_completion_tokens}</span>
                      </td>

                      {/* Generator Tokens */}
                      <td className="py-2.5 px-4 text-right font-mono text-xs text-gray-400">
                        <span className="text-gray-300">{row.gen_prompt_tokens}</span>
                        <span className="text-gray-500 mx-1">/</span>
                        <span className="text-purple-400">{row.gen_completion_tokens}</span>
                      </td>

                      {/* Total Tokens */}
                      <td className="py-2.5 px-4 text-right font-mono text-xs">
                        <span className="font-bold text-gray-100 bg-gray-800/80 px-2 py-0.5 rounded border border-gray-700">
                          {row.total_tokens?.toLocaleString()}
                        </span>
                      </td>

                      {/* Duration */}
                      <td className="py-2.5 px-4 text-right font-mono text-xs text-gray-400">
                        {row.duration_ms > 0 ? `${(row.duration_ms / 1000).toFixed(1)}s` : '<1s'}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-gray-500 text-xs">
                    Tidak ada log request yang cocok dengan filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalLogs > pageSize && (
          <div className="p-3 border-t border-gray-800 flex justify-between items-center bg-[#05070A]/40 text-xs">
            <span className="text-gray-400">
              Halaman <span className="font-semibold text-gray-200">{page}</span> dari <span className="font-semibold text-gray-200">{totalPages}</span>
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-40 disabled:hover:bg-gray-800 transition-colors"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-40 disabled:hover:bg-gray-800 transition-colors"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
