import React, { useState, useEffect } from 'react';
import { Database, Search, FileText, Cpu, Waypoints, Network, Activity, Atom, Flame } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const KnowledgeMonitor = () => {
  const [activeTab, setActiveTab] = useState('graph'); // 'graph' | 'simulator' | 'clusters'
  
  // Graph State
  const [ragData, setRagData] = useState(null);
  const [isLive, setIsLive] = useState(true);

  // Simulator State
  const [totalChunks, setTotalChunks] = useState(0);
  const [simQuery, setSimQuery] = useState('');
  const [simResults, setSimResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  // Clusters State
  const [clusters, setClusters] = useState([]);
  const [clustersLoading, setClustersLoading] = useState(false);

  // Heatmap State
  const [heatSources, setHeatSources] = useState([]);

  // Fetch Live Graph
  const fetchLiveRAG = async () => {
    try {
      const res = await apiClient.get('/analytics/pipeline');
      if (res.data.status === 'success' && res.data.steps) {
        const ragStep = [...res.data.steps].reverse().find(s => s.tool_called === 'RAG_SEARCH');
        if (ragStep && ragStep.observation) {
          try {
            const obsJson = JSON.parse(ragStep.observation);
            setRagData({
              queries: obsJson.queries || [],
              sources: obsJson.sources || []
            });
          } catch (e) {
            console.error("Parse error", e);
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch pipeline", e);
    }
  };

  // Fetch Simulator Stats
  const fetchStats = async () => {
    try {
      const res = await apiClient.get('/analytics/knowledge/stats');
      if (res.data.status === 'success') {
        setTotalChunks(res.data.total_chunks);
      }
    } catch (e) {
      console.error("Failed to fetch stats", e);
    }
  };

  // Fetch Clusters
  const fetchClusters = async () => {
    setClustersLoading(true);
    try {
      const res = await apiClient.get('/analytics/knowledge/clusters');
      if (res.data.status === 'success') {
        setClusters(res.data.clusters);
      }
    } catch (e) {
      console.error("Failed to fetch clusters", e);
    } finally {
      setClustersLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    if (activeTab === 'graph') {
        fetchLiveRAG();
        const interval = setInterval(fetchLiveRAG, 3000);
        return () => clearInterval(interval);
    } else if (activeTab === 'clusters') {
        fetchClusters();
    } else if (activeTab === 'heatmap') {
        // Reuse ragData from pipeline - refresh once
        fetchLiveRAG();
    }
  }, [activeTab]);

  // Handle Simulation
  const handleSimulate = async (e) => {
    e.preventDefault();
    if (!simQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await apiClient.post('/analytics/knowledge/simulate', { query: simQuery });
      if (res.data.status === 'success') {
        setSimResults(res.data.results);
      }
    } catch (e) {
      console.error("Simulation failed", e);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6 h-full">
      {/* Header & Tabs */}
      <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/10 rounded-lg">
            <Database className="text-emerald-500 w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-200 tracking-wide">Knowledge Center</h2>
            <p className="text-xs text-gray-500">VectorDB stats & RAG visualization</p>
          </div>
        </div>

        {/* Internal Tabs */}
        <div className="flex p-1 bg-gray-900 rounded-lg border border-gray-800 flex-wrap gap-1">
            <button 
                onClick={() => setActiveTab('graph')}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${activeTab === 'graph' ? 'bg-gray-800 text-white shadow' : 'text-gray-500 hover:text-gray-300'}`}
            >
                <Network size={13} /> Live Context Graph
            </button>
            <button 
                onClick={() => setActiveTab('heatmap')}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${activeTab === 'heatmap' ? 'bg-orange-900/50 text-orange-300 shadow' : 'text-gray-500 hover:text-gray-300'}`}
            >
                <Flame size={13} /> Attention Heatmap
            </button>
            <button 
                onClick={() => setActiveTab('clusters')}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${activeTab === 'clusters' ? 'bg-gray-800 text-white shadow' : 'text-gray-500 hover:text-gray-300'}`}
            >
                <Atom size={13} /> Query Clusters
            </button>
            <button 
                onClick={() => setActiveTab('simulator')}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${activeTab === 'simulator' ? 'bg-gray-800 text-white shadow' : 'text-gray-500 hover:text-gray-300'}`}
            >
                <Search size={13} /> RAG Simulator
            </button>
        </div>
      </div>

      {activeTab === 'graph' && (() => {
        // ── Layout constants (SVG viewBox = 1000 x 500) ───────────────────────
        const VW = 1000, VH = 500;
        const ENGINE_X = 130, ENGINE_Y = VH / 2;
        const QUERY_X  = 420;
        const DOC_X    = 750;

        const qCount = ragData?.queries?.length || 0;
        const dCount = ragData?.sources?.length || 0;

        const queryY = (i) => VH / 2 + (i - (qCount - 1) / 2) * 110;
        const docY   = (i) => VH / 2 + (i - (dCount - 1) / 2) * 90;

        return (
        <div className="flex-1 bg-[#090C15] border border-gray-800 rounded-xl relative overflow-hidden min-h-[480px]">
          {/* Background Grid */}
          <div className="absolute inset-0 opacity-10 pointer-events-none"
               style={{ backgroundImage: 'linear-gradient(#374151 1px, transparent 1px), linear-gradient(90deg, #374151 1px, transparent 1px)', backgroundSize: '40px 40px' }}/>

          {!ragData ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-gray-600">
              <Waypoints className="w-12 h-12 opacity-50" />
              <p className="text-sm font-medium tracking-widest uppercase">Waiting for RAG Execution...</p>
            </div>
          ) : (
            <svg viewBox={`0 0 ${VW} ${VH}`} className="absolute inset-0 w-full h-full" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="lineEQ" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.9"/>
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.5"/>
                </linearGradient>
                <linearGradient id="lineQD" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6"/>
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.4"/>
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="3" result="blur"/>
                  <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
              </defs>

              {/* ── Lines: Engine → Queries ── */}
              {ragData.queries.map((_, i) => (
                <path key={`eq-${i}`}
                  d={`M ${ENGINE_X + 36} ${ENGINE_Y} C ${(ENGINE_X + QUERY_X) / 2} ${ENGINE_Y}, ${(ENGINE_X + QUERY_X) / 2} ${queryY(i)}, ${QUERY_X - 110} ${queryY(i)}`}
                  fill="none" stroke="url(#lineEQ)" strokeWidth="2.5" strokeLinecap="round"
                  filter="url(#glow)"
                />
              ))}

              {/* ── Lines: Queries → Docs ── */}
              {ragData.queries.map((_, qi) =>
                ragData.sources.map((_, di) => (
                  <path key={`qd-${qi}-${di}`}
                    d={`M ${QUERY_X + 110} ${queryY(qi)} C ${(QUERY_X + DOC_X) / 2} ${queryY(qi)}, ${(QUERY_X + DOC_X) / 2} ${docY(di)}, ${DOC_X - 95} ${docY(di)}`}
                    fill="none" stroke="url(#lineQD)" strokeWidth="1.5" strokeLinecap="round"
                    strokeDasharray="6 4" opacity="0.6"
                  />
                ))
              )}

              {/* ── Node: Engine ── */}
              <g filter="url(#glow)">
                <circle cx={ENGINE_X} cy={ENGINE_Y} r="44" fill="#10b981" fillOpacity="0.12" stroke="#10b981" strokeWidth="1.5"/>
                <rect x={ENGINE_X - 28} y={ENGINE_Y - 28} width="56" height="56" rx="14"
                      fill="#0f172a" stroke="#10b981" strokeWidth="2"/>
                {/* CPU icon approx */}
                <rect x={ENGINE_X - 16} y={ENGINE_Y - 16} width="32" height="32" rx="4" fill="none" stroke="#10b981" strokeWidth="1.5"/>
                <rect x={ENGINE_X - 8} y={ENGINE_Y - 8} width="16" height="16" rx="2" fill="#10b981" fillOpacity="0.4"/>
              </g>
              <text x={ENGINE_X} y={ENGINE_Y + 52} textAnchor="middle" fill="#10b981" fontSize="11" fontWeight="bold" letterSpacing="1">CORE ENGINE</text>

              {/* ── Nodes: Queries ── */}
              {ragData.queries.map((q, i) => (
                <g key={`q-node-${i}`}>
                  <rect x={QUERY_X - 110} y={queryY(i) - 32} width="220" height="64" rx="10"
                        fill="#0f172a" stroke="#3b82f6" strokeWidth="1.5" filter="url(#glow)"/>
                  <rect x={QUERY_X - 110} y={queryY(i) - 32} width="220" height="64" rx="10"
                        fill="#3b82f6" fillOpacity="0.07"/>
                  <text x={QUERY_X - 100} y={queryY(i) - 12} fill="#60a5fa" fontSize="8" fontWeight="bold" letterSpacing="1">SUB-QUERY {i + 1}</text>
                  <foreignObject x={QUERY_X - 105} y={queryY(i) - 6} width="210" height="34">
                    <div xmlns="http://www.w3.org/1999/xhtml"
                         style={{ fontSize: '11px', color: '#d1d5db', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      {q}
                    </div>
                  </foreignObject>
                </g>
              ))}

              {/* ── Nodes: Documents ── */}
              {ragData.sources.map((s, i) => {
                const score = typeof s.score === 'string' ? parseFloat(s.score) : (s.score || 0);
                const pct = Math.min(1, score);
                return (
                  <g key={`d-node-${i}`}>
                    <rect x={DOC_X - 95} y={docY(i) - 38} width="190" height="76" rx="10"
                          fill="#0f172a" stroke="#7c3aed" strokeWidth="1.5" filter="url(#glow)"/>
                    <rect x={DOC_X - 95} y={docY(i) - 38} width="190" height="76" rx="10"
                          fill="#7c3aed" fillOpacity="0.07"/>
                    <text x={DOC_X - 85} y={docY(i) - 18} fill="#a78bfa" fontSize="7.5" fontWeight="bold" letterSpacing="0.8">
                      {s.doc_id ? `DOC #${String(s.doc_id).slice(0, 6)}` : `DOKUMEN ${i + 1}`}
                    </text>
                    <foreignObject x={DOC_X - 90} y={docY(i) - 10} width="180" height="24">
                      <div xmlns="http://www.w3.org/1999/xhtml"
                           style={{ fontSize: '11px', color: '#e5e7eb', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', fontWeight: '500' }}>
                        {s.title || 'Dokumen Internal'}
                      </div>
                    </foreignObject>
                    {/* Score bar */}
                    <rect x={DOC_X - 85} y={docY(i) + 20} width="140" height="5" rx="3" fill="#1f2937"/>
                    <rect x={DOC_X - 85} y={docY(i) + 20} width={140 * pct} height="5" rx="3" fill="#8b5cf6"/>
                    <text x={DOC_X + 60} y={docY(i) + 26} fill="#9ca3af" fontSize="8" textAnchor="end">
                      {(pct * 100).toFixed(1)}%
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>
        );
      })()}


      {activeTab === 'simulator' && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-500">
            {/* Stats Header */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 flex items-center gap-4">
                    <div className="p-4 bg-emerald-500/10 rounded-full">
                        <Database className="text-emerald-500 w-8 h-8" />
                    </div>
                    <div>
                        <p className="text-gray-500 text-xs tracking-widest font-bold uppercase mb-1">Total Vector Chunks</p>
                        <h3 className="text-3xl font-black text-white">{totalChunks.toLocaleString()}</h3>
                    </div>
                </div>
            </div>

            <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl overflow-hidden flex-1">
                <div className="p-4 border-b border-gray-800 bg-gray-900/50">
                    <form onSubmit={handleSimulate} className="flex gap-2">
                        <input
                            type="text"
                            value={simQuery}
                            onChange={(e) => setSimQuery(e.target.value)}
                            placeholder="Ketik pertanyaan untuk simulasi RAG (misal: 'Apa aturan pinjaman?')"
                            className="flex-1 bg-gray-900 border border-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:border-cyan-500"
                        />
                        <button
                            type="submit"
                            disabled={isSearching}
                            className="bg-cyan-600 hover:bg-cyan-500 text-white px-6 py-2 rounded-lg font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
                        >
                            {isSearching ? <Activity className="animate-spin" size={18} /> : <Search size={18} />}
                            SIMULASI
                        </button>
                    </form>
                </div>
                
                <div className="p-4 max-h-[400px] overflow-y-auto">
                    {simResults.length === 0 && !isSearching ? (
                        <div className="text-center text-gray-600 py-12">
                            <FileText className="w-12 h-12 mx-auto opacity-20 mb-3" />
                            <p>Belum ada hasil simulasi.</p>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-3">
                            {simResults.map((res, i) => (
                                <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-cyan-500/50 transition-colors">
                                    <div className="flex justify-between items-start mb-2">
                                        <div className="flex items-center gap-2">
                                            <span className="bg-cyan-500/20 text-cyan-400 text-[10px] font-bold px-2 py-0.5 rounded border border-cyan-500/30">
                                                Rank #{i+1}
                                            </span>
                                            <span className="text-xs text-gray-400 font-mono">Sim: {(res.similarity * 100).toFixed(1)}%</span>
                                        </div>
                                        <span className="text-[10px] text-gray-500 border border-gray-800 px-2 py-0.5 rounded">{res.document_title}</span>
                                    </div>
                                    <p className="text-gray-300 text-sm leading-relaxed">{res.content}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
      )}
      {activeTab === 'clusters' && (() => {
        const CLUSTER_COLORS = {
          dokumen:  { text: 'text-blue-400',   border: 'border-blue-500/40',   bg: 'bg-blue-500/10',   glow: 'shadow-[0_0_12px_rgba(59,130,246,0.5)]',  dot: '#3b82f6' },
          coding:   { text: 'text-emerald-400', border: 'border-emerald-500/40', bg: 'bg-emerald-500/10', glow: 'shadow-[0_0_12px_rgba(16,185,129,0.5)]', dot: '#10b981' },
          chitchat: { text: 'text-purple-400',  border: 'border-purple-500/40',  bg: 'bg-purple-500/10',  glow: 'shadow-[0_0_12px_rgba(168,85,247,0.5)]', dot: '#a855f7' },
          analitik: { text: 'text-orange-400',  border: 'border-orange-500/40',  bg: 'bg-orange-500/10',  glow: 'shadow-[0_0_12px_rgba(251,146,60,0.5)]', dot: '#fb923c' },
          ambigu:   { text: 'text-yellow-400',  border: 'border-yellow-500/40',  bg: 'bg-yellow-500/10',  glow: 'shadow-[0_0_12px_rgba(234,179,8,0.5)]',  dot: '#eab308' },
        };
        const totalCount = clusters.reduce((sum, c) => sum + c.count, 0) || 1;

        // Deterministic scatter positions per mode
        const positions = [
          { x: 50, y: 45 },
          { x: 22, y: 30 },
          { x: 75, y: 25 },
          { x: 20, y: 65 },
          { x: 75, y: 68 },
        ];

        return (
          <div className="flex flex-col gap-5 animate-in fade-in duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
              {clusters.map((c, idx) => {
                const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                const pct = Math.round((c.count / totalCount) * 100);
                return (
                  <div key={c.mode} className={`${cfg.bg} border ${cfg.border} rounded-xl p-4 flex flex-col gap-2`}>
                    <div className="flex justify-between items-center">
                      <span className={`text-[10px] font-bold uppercase tracking-widest ${cfg.text}`}>{c.mode}</span>
                      <span className={`text-lg font-black ${cfg.text}`}>{pct}%</span>
                    </div>
                    <div className="h-1 bg-black/30 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${pct}%`, backgroundColor: cfg.dot }}/>
                    </div>
                    <div className="text-[10px] text-gray-500">{c.count} queries · {c.unique_users} users</div>
                  </div>
                );
              })}
            </div>

            {/* Scatter Plot Galaxy */}
            <div className="bg-[#090C15] border border-gray-800 rounded-xl relative overflow-hidden min-h-[400px] flex items-center justify-center">
              <div className="absolute inset-0 opacity-[0.07] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle, #374151 1px, transparent 1px)', backgroundSize: '30px 30px' }}/>

              {clustersLoading ? (
                <div className="flex items-center gap-3 text-gray-600">
                  <Activity className="animate-spin" size={20}/> <span className="text-sm">Loading clusters...</span>
                </div>
              ) : clusters.length === 0 ? (
                <div className="flex flex-col items-center gap-3 text-gray-600">
                  <Atom size={40} className="opacity-20"/>
                  <p className="text-sm">No routing data yet. Chat dengan CAKRA untuk mengisi data.</p>
                </div>
              ) : (
                <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full" preserveAspectRatio="xMidYMid meet">
                  <defs>
                    {clusters.map((c) => {
                      const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                      return (
                        <radialGradient key={`grad-${c.mode}`} id={`grad-${c.mode}`} cx="50%" cy="50%" r="50%">
                          <stop offset="0%" stopColor={cfg.dot} stopOpacity="0.8"/>
                          <stop offset="100%" stopColor={cfg.dot} stopOpacity="0"/>
                        </radialGradient>
                      );
                    })}
                  </defs>

                  {/* Connection lines from center to each node */}
                  {clusters.map((c, idx) => {
                    const pos = positions[idx] || { x: 50, y: 50 };
                    const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                    return (
                      <line key={`line-${c.mode}`}
                            x1="50" y1="50" x2={pos.x} y2={pos.y}
                            stroke={cfg.dot} strokeWidth="0.3" strokeOpacity="0.3" strokeDasharray="1 1"/>
                    );
                  })}

                  {/* Cluster Nodes */}
                  {clusters.map((c, idx) => {
                    const pos = positions[idx] || { x: 50, y: 50 };
                    const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                    const pct = c.count / totalCount;
                    const r = 4 + pct * 8; // radius scales with count

                    // Mini dots around each node (sample queries)
                    const miniDots = c.queries_sample?.slice(0, 3).map((_, qi) => ({
                      x: pos.x + Math.cos((qi / 3) * Math.PI * 2) * (r + 3),
                      y: pos.y + Math.sin((qi / 3) * Math.PI * 2) * (r + 3),
                    })) || [];

                    return (
                      <g key={`node-${c.mode}`}>
                        {/* Glow halo */}
                        <circle cx={pos.x} cy={pos.y} r={r + 4} fill={`url(#grad-${c.mode})`}/>
                        {/* Main node */}
                        <circle cx={pos.x} cy={pos.y} r={r} fill={cfg.dot} fillOpacity="0.85" className="animate-pulse"/>
                        {/* Inner highlight */}
                        <circle cx={pos.x - r * 0.3} cy={pos.y - r * 0.3} r={r * 0.3} fill="white" fillOpacity="0.2"/>
                        {/* Mini orbit dots */}
                        {miniDots.map((d, di) => (
                          <circle key={di} cx={d.x} cy={d.y} r="0.8" fill={cfg.dot} fillOpacity="0.6"/>
                        ))}
                        {/* Label */}
                        <text x={pos.x} y={pos.y + r + 4} textAnchor="middle" fill={cfg.dot} fontSize="3" fontWeight="bold">
                          {c.mode.toUpperCase()}
                        </text>
                        <text x={pos.x} y={pos.y + r + 7} textAnchor="middle" fill="gray" fontSize="2.2">
                          {c.count} queries
                        </text>
                      </g>
                    );
                  })}

                  {/* Center hub */}
                  <circle cx="50" cy="50" r="3" fill="#1f2937" stroke="#4b5563" strokeWidth="0.8"/>
                  <circle cx="50" cy="50" r="1" fill="#9ca3af"/>
                </svg>
              )}
            </div>
          </div>
        );
      })()}

      {activeTab === 'heatmap' && (() => {
        const sources = ragData?.sources || [];
        const queries = ragData?.queries || [];

        // Score to heat color
        const scoreToColor = (score) => {
          const s = Math.min(1, Math.max(0, typeof score === 'string' ? parseFloat(score) : (score || 0)));
          if (s >= 0.8) return { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#fca5a5', bar: '#ef4444', label: '🔴 HIGH' };
          if (s >= 0.65) return { bg: 'rgba(249,115,22,0.12)', border: '#f97316', text: '#fdba74', bar: '#f97316', label: '🟠 GOOD' };
          if (s >= 0.5) return { bg: 'rgba(234,179,8,0.10)', border: '#eab308', text: '#fde047', bar: '#eab308', label: '🟡 FAIR' };
          return { bg: 'rgba(59,130,246,0.08)', border: '#3b82f6', text: '#93c5fd', bar: '#3b82f6', label: '🔵 LOW' };
        };

        return (
          <div className="flex flex-col gap-5 animate-in fade-in duration-500">
            {/* Header info */}
            <div className="bg-[#090C15] border border-orange-900/40 rounded-xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-500/10 rounded-lg border border-orange-500/20">
                  <Flame className="text-orange-500 w-4 h-4"/>
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-200">Attention Heatmap</h3>
                  <p className="text-xs text-gray-500">Relevance score setiap sumber dokumen yang ditarik AI</p>
                </div>
              </div>
              <button onClick={fetchLiveRAG} className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1.5 border border-gray-700 px-3 py-1.5 rounded-lg hover:border-gray-600 transition-colors">
                <Activity size={12}/> Refresh
              </button>
            </div>

            {/* Queries used */}
            {queries.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {queries.map((q, i) => (
                  <span key={i} className="text-xs bg-blue-500/10 border border-blue-500/30 text-blue-300 px-3 py-1 rounded-full font-mono">
                    🔍 {q}
                  </span>
                ))}
              </div>
            )}

            {/* No data */}
            {sources.length === 0 ? (
              <div className="bg-[#090C15] border border-gray-800 rounded-xl min-h-[300px] flex flex-col items-center justify-center gap-4 text-gray-600">
                <Flame size={40} className="opacity-20"/>
                <p className="text-sm">Belum ada data RAG. Chat dengan CAKRA menggunakan mode Dokumen.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {/* Heatmap bar visualization */}
                <div className="bg-[#090C15] border border-gray-800 rounded-xl p-5">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Flame size={11} className="text-orange-500"/> Relevance Score Map
                  </h4>
                  <div className="flex flex-col gap-3">
                    {sources.map((s, i) => {
                      const rawScore = typeof s.score === 'string' ? parseFloat(s.score) : (s.score || 0);
                      const pct = Math.min(100, rawScore * 100);
                      const cfg = scoreToColor(rawScore);
                      return (
                        <div key={i} className="flex flex-col gap-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <FileText size={11} style={{ color: cfg.text }}/>
                              <span className="text-gray-300 font-medium truncate max-w-[400px]">
                                {s.title || `Dokumen ${i + 1}`}
                              </span>
                              {s.doc_id && (
                                <span className="text-[10px] text-gray-600 font-mono">
                                  #{String(s.doc_id).slice(0, 8)}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-[10px] font-bold" style={{ color: cfg.text }}>{cfg.label}</span>
                              <span className="font-mono font-black text-sm" style={{ color: cfg.text }}>
                                {pct.toFixed(1)}%
                              </span>
                            </div>
                          </div>
                          {/* Heat bar */}
                          <div className="h-3 bg-gray-800/60 rounded-full overflow-hidden relative">
                            <div
                              className="h-full rounded-full transition-all duration-1000 ease-out relative"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: cfg.bar,
                                boxShadow: `0 0 12px ${cfg.bar}80`,
                              }}
                            >
                              {/* Heat gradient shimmer */}
                              <div className="absolute inset-0 rounded-full opacity-50"
                                   style={{ background: `linear-gradient(90deg, transparent, ${cfg.bar}, transparent)`,
                                            animation: 'shimmer 2s ease-in-out infinite' }}/>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Heat Legend + Summary */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { label: 'HIGH Relevance', range: '≥ 80%', color: '#ef4444', emoji: '🔴' },
                    { label: 'GOOD Relevance', range: '65–79%', color: '#f97316', emoji: '🟠' },
                    { label: 'FAIR Relevance', range: '50–64%', color: '#eab308', emoji: '🟡' },
                    { label: 'LOW Relevance',  range: '< 50%',  color: '#3b82f6', emoji: '🔵' },
                  ].map(item => (
                    <div key={item.label} className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 flex items-center gap-3">
                      <div className="w-3 h-8 rounded-full" style={{ backgroundColor: item.color, boxShadow: `0 0 8px ${item.color}60` }}/>
                      <div>
                        <div className="text-[10px] font-bold text-gray-300">{item.label}</div>
                        <div className="text-[10px] text-gray-500 font-mono">{item.range}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
};
