import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Database, 
  Search, 
  FileText, 
  Cpu, 
  Waypoints, 
  Network, 
  Activity, 
  Atom, 
  Flame, 
  Sparkles, 
  ExternalLink, 
  X,
  Maximize2,
  Minimize2,
  Layers,
  RotateCcw
} from 'lucide-react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import apiClient from '../../../services/apiClient';

// ── Custom React Flow Node Components ────────────────────────────────────────

const EngineNode = ({ data }) => (
  <div className="bg-[#090D1A] border-2 border-emerald-500/80 rounded-2xl p-4 shadow-[0_0_30px_rgba(16,185,129,0.25)] min-w-[230px] text-center backdrop-blur-md">
    <Handle type="source" position={Position.Bottom} className="!bg-emerald-400 !w-3 !h-3 !border-2 !border-slate-900" />
    <div className="flex items-center justify-center gap-2 mb-1 text-emerald-400 font-bold text-xs uppercase tracking-wider">
      <Cpu className="w-4 h-4 animate-pulse text-emerald-400" /> CAKRA BRAIN ENGINE
    </div>
    <div className="text-xs text-gray-200 font-medium">{data.label || "Hybrid RAG & Semantic Core"}</div>
    <div className="mt-2 flex items-center justify-center gap-2">
      <span className="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 py-0.5 px-2.5 rounded-full font-semibold">
        ● Active · 16k Ctx
      </span>
      <span className="text-[9px] font-mono text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 py-0.5 px-2 rounded-full">
        Gemma4 Core
      </span>
    </div>
  </div>
);

const QueryNode = ({ data }) => (
  <div className={`bg-[#090D1A] border-2 ${data.borderColor || 'border-blue-500/70'} rounded-xl p-3.5 shadow-xl min-w-[230px] max-w-[260px] backdrop-blur-md transition-all hover:scale-105`}>
    <Handle type="target" position={Position.Top} className="!bg-blue-400 !w-2.5 !h-2.5 !border-2 !border-slate-900" />
    <div className="flex items-center justify-between mb-1.5">
      <span className="text-[9px] font-bold tracking-wider uppercase" style={{ color: data.textColor || '#60a5fa' }}>
        {data.badge || "SEMANTIC QUERY"}
      </span>
      <span className="text-[9px] font-mono text-gray-500">Tier 1</span>
    </div>
    <div className="text-xs text-gray-200 line-clamp-2 leading-relaxed font-medium">
      "{data.queryText}"
    </div>
    <Handle type="source" position={Position.Bottom} className="!bg-blue-400 !w-2.5 !h-2.5 !border-2 !border-slate-900" />
  </div>
);

const DocNode = ({ data }) => {
  const score = typeof data.score === 'string' ? parseFloat(data.score) : (data.score || 0);
  const pct = Math.min(100, Math.max(0, score * 100));
  const isTitle = data.isTitle;
  const strokeColor = isTitle ? 'border-amber-500/70' : 'border-purple-500/70';
  const textColor = isTitle ? '#fbbf24' : '#c084fc';
  const barColor = isTitle ? '#f59e0b' : '#a855f7';

  return (
    <div 
      onClick={() => data.onSelect && data.onSelect(data.raw)}
      className={`bg-[#090D1A] border-2 ${strokeColor} rounded-xl p-3.5 shadow-xl min-w-[220px] max-w-[260px] backdrop-blur-md cursor-pointer hover:scale-105 transition-all hover:shadow-[0_0_20px_rgba(168,85,247,0.2)]`}
    >
      <Handle type="target" position={Position.Top} className="!bg-purple-400 !w-2.5 !h-2.5 !border-2 !border-slate-900" />
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] font-bold tracking-wider uppercase" style={{ color: textColor }}>
          {isTitle ? 'FTS REGULATION' : 'VECTOR CHUNK'}
        </span>
        <span className="text-[10px] font-mono font-bold" style={{ color: textColor }}>
          {pct.toFixed(1)}%
        </span>
      </div>
      
      <div className="text-xs font-semibold text-gray-200 line-clamp-1">
        {data.title || "Dokumen Internal"}
      </div>

      <div className="mt-2.5 h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
        <div 
          className="h-full rounded-full transition-all duration-500" 
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between text-[9px] text-gray-500">
        <span className="font-mono">{data.docId ? `#${String(data.docId).slice(0,6)}` : 'Chunk'}</span>
        <span className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-0.5">
          Detail <ExternalLink size={9} />
        </span>
      </div>
    </div>
  );
};

const nodeTypes = {
  engine: EngineNode,
  query: QueryNode,
  document: DocNode,
};

// ── Main KnowledgeMonitor Component ──────────────────────────────────────────

export const KnowledgeMonitor = () => {
  const [activeTab, setActiveTab] = useState('graph'); // 'graph' | 'simulator' | 'clusters' | 'heatmap'
  
  // Graph State
  const [ragData, setRagData] = useState(null);
  const [selectedNodeDoc, setSelectedNodeDoc] = useState(null);

  // Simulator State
  const [totalChunks, setTotalChunks] = useState(0);
  const [simQuery, setSimQuery] = useState('');
  const [simResults, setSimResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  // Clusters State
  const [clusters, setClusters] = useState([]);
  const [clustersLoading, setClustersLoading] = useState(false);

  // React Flow State
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Fetch Live Graph Data from RAG pipeline
  const fetchLiveRAG = async () => {
    try {
      const res = await apiClient.get('/analytics/knowledge/latest-rag');
      if (res.data.status === 'success' && res.data.step && res.data.step.observation) {
        try {
          const obsJson = JSON.parse(res.data.step.observation);
          setRagData({
            queries: obsJson.queries || [],
            sources: obsJson.sources || []
          });
        } catch (e) {
          console.error("Parse error", e);
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
      fetchLiveRAG();
    }
  }, [activeTab]);

  // Construct React Flow graph from ragData
  useEffect(() => {
    // Default fallback sample data if no live query run yet
    const queries = ragData?.queries?.length > 0 ? ragData.queries : [
      { text: "Aturan cuti tahunan dan kompensasi", type: "SEMANTIC" },
      { text: "SKEP/14/P/BD/VIII/2026", type: "TITLE_SEARCH" },
      { text: "Tata kerja organisasi pindad", type: "SEMANTIC" }
    ];

    const sources = ragData?.sources?.length > 0 ? ragData.sources : [
      { title: "Organisasi dan Tata Kerja PT Pindad", doc_id: "142026", score: 0.94, type: "TITLE", snippet: "Surat Keputusan Direksi mengenai struktur dan tata kerja unit organisasi." },
      { title: "Pedoman Disiplin & Hubungan Industrial", doc_id: "082025", score: 0.86, type: "SEMANTIC", snippet: "Ketentuan pelaksanaan waktu kerja, istirahat, serta cuti tahunan karyawan." },
      { title: "Tata Kelola Manajemen Risiko & Kepatuhan", doc_id: "032024", score: 0.74, type: "SEMANTIC", snippet: "Pedoman mitigasi risiko operasional dan audit kepatuhan regulasi internal." }
    ];

    const qCount = queries.length;
    const dCount = sources.length;
    const centerX = 500;

    const newNodes = [];
    const newEdges = [];

    // 1. Engine Root Node
    newNodes.push({
      id: 'engine-root',
      type: 'engine',
      position: { x: centerX - 115, y: 30 },
      data: { label: "CAKRA Hybrid RAG Core" }
    });

    // 2. Query Nodes (Tier 1)
    queries.forEach((q, idx) => {
      const isObj = typeof q === 'object' && q !== null;
      const qText = isObj ? q.text : q;
      const qType = isObj ? q.type : "SEMANTIC";
      const qId = `query-${idx}`;

      let borderColor = 'border-blue-500/70';
      let textColor = '#60a5fa';
      let badge = `SEMANTIC QUERY #${idx + 1}`;

      if (qType === "TITLE_SEARCH") {
        borderColor = 'border-amber-500/70';
        textColor = '#fbbf24';
        badge = "TITLE EXACT MATCH";
      } else if (qType === "COMMUNITY_KNOWLEDGE") {
        borderColor = 'border-emerald-500/70';
        textColor = '#34d399';
        badge = "AI CORPUS";
      }

      const qX = centerX + (idx - (qCount - 1) / 2) * 280 - 115;
      newNodes.push({
        id: qId,
        type: 'query',
        position: { x: qX, y: 190 },
        data: { queryText: qText, badge, borderColor, textColor }
      });

      // Edge from Engine to Query
      newEdges.push({
        id: `edge-root-${qId}`,
        source: 'engine-root',
        target: qId,
        animated: true,
        style: { stroke: '#10b981', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' }
      });
    });

    // 3. Document Nodes (Tier 2)
    sources.forEach((s, idx) => {
      const dId = `doc-${idx}`;
      const isTitle = s.type === 'TITLE';
      const dX = centerX + (idx - (dCount - 1) / 2) * 260 - 115;

      newNodes.push({
        id: dId,
        type: 'document',
        position: { x: dX, y: 370 },
        data: {
          title: s.title,
          docId: s.doc_id,
          score: s.score,
          isTitle,
          raw: s,
          onSelect: (docRaw) => setSelectedNodeDoc(docRaw)
        }
      });

      // Connect Queries to Docs
      queries.forEach((_, qIdx) => {
        newEdges.push({
          id: `edge-q${qIdx}-${dId}`,
          source: `query-${qIdx}`,
          target: dId,
          animated: true,
          style: { stroke: isTitle ? '#f59e0b' : '#8b5cf6', strokeWidth: 1.5, opacity: 0.6 },
          markerEnd: { type: MarkerType.ArrowClosed, color: isTitle ? '#f59e0b' : '#8b5cf6' }
        });
      });
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [ragData]);

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
      <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-200 tracking-wide flex items-center gap-2">
              Knowledge Center & Vector Space
              <span className="bg-emerald-500/10 text-emerald-400 text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/20 font-mono">
                {totalChunks.toLocaleString()} chunks
              </span>
            </h2>
            <p className="text-xs text-gray-500">Visualisasi relasi retrieval interaktif, attention heatmap, dan query simulator.</p>
          </div>
        </div>

        {/* Internal Tabs */}
        <div className="flex p-1 bg-slate-950 rounded-xl border border-gray-800 flex-wrap gap-1">
          <button 
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${activeTab === 'graph' ? 'bg-gradient-to-r from-emerald-600 to-cyan-600 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'}`}
          >
            <Network size={14} /> Interactive Graph
          </button>
          <button 
            onClick={() => setActiveTab('heatmap')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${activeTab === 'heatmap' ? 'bg-gradient-to-r from-orange-600 to-red-600 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'}`}
          >
            <Flame size={14} /> Attention Heatmap
          </button>
          <button 
            onClick={() => setActiveTab('clusters')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${activeTab === 'clusters' ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'}`}
          >
            <Atom size={14} /> Query Clusters
          </button>
          <button 
            onClick={() => setActiveTab('simulator')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${activeTab === 'simulator' ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'}`}
          >
            <Search size={14} /> RAG Simulator
          </button>
        </div>
      </div>

      {/* Tab: React Flow Interactive Graph */}
      {activeTab === 'graph' && (
        <div className="flex-1 bg-[#05070D] border border-gray-800 rounded-2xl overflow-hidden relative flex min-h-[580px]">
          <div className="flex-1 h-full w-full relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.3}
              maxZoom={2.5}
            >
              <Background color="#1e293b" gap={24} size={1.5} />
              <Controls className="!bg-[#0f172a] !border-gray-800 !text-gray-300 !fill-gray-300 !rounded-xl !shadow-2xl" />
              <MiniMap 
                nodeColor={(n) => {
                  if (n.type === 'engine') return '#10b981';
                  if (n.type === 'query') return '#3b82f6';
                  return '#a855f7';
                }}
                className="!bg-[#090d1a] !border !border-gray-800 !rounded-xl"
              />
            </ReactFlow>

            {/* Instruction Tip Overlay */}
            <div className="absolute top-4 left-4 z-10 bg-slate-950/80 border border-gray-800 px-3 py-1.5 rounded-lg text-[11px] text-gray-400 backdrop-blur-md flex items-center gap-2 pointer-events-none">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>Canvas Interaktif: Geser / zoom node & klik dokumen untuk inspeksi</span>
            </div>
          </div>

          {/* Slide-out Document Detail Inspection Panel */}
          {selectedNodeDoc && (
            <div className="w-80 border-l border-gray-800 bg-[#0B0F19] p-5 flex flex-col justify-between animate-in slide-in-from-right-5 duration-300 z-20 overflow-y-auto">
              <div className="space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                      Doc Inspection
                    </span>
                    <h3 className="text-sm font-bold text-gray-100 mt-2 line-clamp-2">
                      {selectedNodeDoc.title || "Dokumen Internal"}
                    </h3>
                  </div>
                  <button onClick={() => setSelectedNodeDoc(null)} className="text-gray-500 hover:text-gray-300 p-1">
                    <X size={16} />
                  </button>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-gray-800 text-gray-400">
                    <span>Document ID:</span>
                    <span className="font-mono text-gray-200">{selectedNodeDoc.doc_id || "N/A"}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-800 text-gray-400">
                    <span>Relevance Score:</span>
                    <span className="font-mono font-bold text-emerald-400">
                      {((selectedNodeDoc.score || 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-800 text-gray-400">
                    <span>Search Mode:</span>
                    <span className="font-semibold text-purple-400">{selectedNodeDoc.type || "SEMANTIC"}</span>
                  </div>
                </div>

                <div>
                  <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Snippet / Excerpt:</h4>
                  <div className="bg-slate-950 border border-gray-800 p-3 rounded-xl text-xs text-gray-300 leading-relaxed max-h-48 overflow-y-auto">
                    {selectedNodeDoc.snippet || selectedNodeDoc.content || "Konten potongan paragraf yang diekstrak oleh model embedding."}
                  </div>
                </div>
              </div>

              {selectedNodeDoc.doc_id && (
                <a 
                  href={`https://peraturan.pindad.com/content/detail/${selectedNodeDoc.doc_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 w-full bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors"
                >
                  Buka di Portal Pindad <ExternalLink size={12} />
                </a>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab: Simulator */}
      {activeTab === 'simulator' && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-500">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl p-6 flex items-center gap-4">
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl">
                <Database className="text-emerald-400 w-8 h-8" />
              </div>
              <div>
                <p className="text-gray-500 text-xs tracking-widest font-bold uppercase mb-1">Total Vector Chunks</p>
                <h3 className="text-3xl font-black text-white">{totalChunks.toLocaleString()}</h3>
              </div>
            </div>
          </div>

          <div className="bg-[#0B0F19] border border-gray-800 rounded-2xl overflow-hidden flex-1">
            <div className="p-4 border-b border-gray-800 bg-slate-900/60">
              <form onSubmit={handleSimulate} className="flex gap-2">
                <input
                  type="text"
                  value={simQuery}
                  onChange={(e) => setSimQuery(e.target.value)}
                  placeholder="Ketik pertanyaan untuk simulasi RAG (misal: 'Apa aturan mutasi karyawan?')"
                  className="flex-1 bg-slate-950 border border-gray-700 text-white rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-cyan-500"
                />
                <button
                  type="submit"
                  disabled={isSearching}
                  className="bg-cyan-600 hover:bg-cyan-500 text-white px-6 py-2.5 rounded-xl font-semibold text-xs flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  {isSearching ? <Activity className="animate-spin" size={16} /> : <Search size={16} />}
                  SIMULASI
                </button>
              </form>
            </div>
            
            <div className="p-4 max-h-[420px] overflow-y-auto custom-scrollbar">
              {simResults.length === 0 && !isSearching ? (
                <div className="text-center text-gray-600 py-12">
                  <FileText className="w-12 h-12 mx-auto opacity-20 mb-3" />
                  <p className="text-sm">Belum ada hasil simulasi. Masukkan query di atas.</p>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {simResults.map((res, i) => (
                    <div key={i} className="bg-slate-950 border border-gray-800 rounded-xl p-4 hover:border-cyan-500/50 transition-colors">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <span className="bg-cyan-500/20 text-cyan-400 text-[10px] font-bold px-2 py-0.5 rounded border border-cyan-500/30">
                            Rank #{i+1}
                          </span>
                          <span className="text-xs text-gray-400 font-mono">Sim: {(res.similarity * 100).toFixed(1)}%</span>
                        </div>
                        <span className="text-[10px] text-gray-500 border border-gray-800 px-2 py-0.5 rounded">{res.document_title}</span>
                      </div>
                      <p className="text-gray-300 text-xs leading-relaxed">{res.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Query Clusters */}
      {activeTab === 'clusters' && (() => {
        const CLUSTER_COLORS = {
          dokumen:  { text: 'text-blue-400',   border: 'border-blue-500/40',   bg: 'bg-blue-500/10',   glow: 'shadow-[0_0_12px_rgba(59,130,246,0.5)]',  dot: '#3b82f6' },
          coding:   { text: 'text-emerald-400', border: 'border-emerald-500/40', bg: 'bg-emerald-500/10', glow: 'shadow-[0_0_12px_rgba(16,185,129,0.5)]', dot: '#10b981' },
          chitchat: { text: 'text-purple-400',  border: 'border-purple-500/40',  bg: 'bg-purple-500/10',  glow: 'shadow-[0_0_12px_rgba(168,85,247,0.5)]', dot: '#a855f7' },
          analitik: { text: 'text-orange-400',  border: 'border-orange-500/40',  bg: 'bg-orange-500/10',  glow: 'shadow-[0_0_12px_rgba(251,146,60,0.5)]', dot: '#fb923c' },
          ambigu:   { text: 'text-yellow-400',  border: 'border-yellow-500/40',  bg: 'bg-yellow-500/10',  glow: 'shadow-[0_0_12px_rgba(234,179,8,0.5)]',  dot: '#eab308' },
        };
        const totalCount = clusters.reduce((sum, c) => sum + c.count, 0) || 1;

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
              {clusters.map((c) => {
                const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                const pct = Math.round((c.count / totalCount) * 100);
                return (
                  <div key={c.mode} className={`${cfg.bg} border ${cfg.border} rounded-2xl p-4 flex flex-col gap-2`}>
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

            <div className="bg-[#090C15] border border-gray-800 rounded-2xl relative overflow-hidden min-h-[420px] flex items-center justify-center">
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

                  {clusters.map((c, idx) => {
                    const pos = positions[idx] || { x: 50, y: 50 };
                    const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                    return (
                      <line key={`line-${c.mode}`}
                        x1="50" y1="50" x2={pos.x} y2={pos.y}
                        stroke={cfg.dot} strokeWidth="0.3" strokeOpacity="0.3" strokeDasharray="1 1"/>
                    );
                  })}

                  {clusters.map((c, idx) => {
                    const pos = positions[idx] || { x: 50, y: 50 };
                    const cfg = CLUSTER_COLORS[c.mode] || CLUSTER_COLORS.ambigu;
                    const pct = c.count / totalCount;
                    const r = 4 + pct * 8;

                    return (
                      <g key={`node-${c.mode}`}>
                        <circle cx={pos.x} cy={pos.y} r={r + 4} fill={`url(#grad-${c.mode})`}/>
                        <circle cx={pos.x} cy={pos.y} r={r} fill={cfg.dot} fillOpacity="0.85" className="animate-pulse"/>
                        <circle cx={pos.x - r * 0.3} cy={pos.y - r * 0.3} r={r * 0.3} fill="white" fillOpacity="0.2"/>
                        <text x={pos.x} y={pos.y + r + 4} textAnchor="middle" fill={cfg.dot} fontSize="3" fontWeight="bold">
                          {c.mode.toUpperCase()}
                        </text>
                        <text x={pos.x} y={pos.y + r + 7} textAnchor="middle" fill="gray" fontSize="2.2">
                          {c.count} queries
                        </text>
                      </g>
                    );
                  })}

                  <circle cx="50" cy="50" r="3" fill="#1f2937" stroke="#4b5563" strokeWidth="0.8"/>
                  <circle cx="50" cy="50" r="1" fill="#9ca3af"/>
                </svg>
              )}
            </div>
          </div>
        );
      })()}

      {/* Tab: Attention Heatmap */}
      {activeTab === 'heatmap' && (() => {
        const sources = ragData?.sources || [];
        const queries = ragData?.queries || [];

        const scoreToColor = (score) => {
          const s = Math.min(1, Math.max(0, typeof score === 'string' ? parseFloat(score) : (score || 0)));
          if (s >= 0.8) return { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#fca5a5', bar: '#ef4444', label: '🔴 HIGH' };
          if (s >= 0.65) return { bg: 'rgba(249,115,22,0.12)', border: '#f97316', text: '#fdba74', bar: '#f97316', label: '🟠 GOOD' };
          if (s >= 0.5) return { bg: 'rgba(234,179,8,0.10)', border: '#eab308', text: '#fde047', bar: '#eab308', label: '🟡 FAIR' };
          return { bg: 'rgba(59,130,246,0.08)', border: '#3b82f6', text: '#93c5fd', bar: '#3b82f6', label: '🔵 LOW' };
        };

        return (
          <div className="flex flex-col gap-5 animate-in fade-in duration-500">
            <div className="bg-[#090C15] border border-orange-900/40 rounded-2xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-500/10 rounded-xl border border-orange-500/20">
                  <Flame className="text-orange-500 w-4 h-4"/>
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-200">Attention Heatmap</h3>
                  <p className="text-xs text-gray-500">Relevance score setiap sumber dokumen yang ditarik AI</p>
                </div>
              </div>
              <button onClick={fetchLiveRAG} className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1.5 border border-gray-700 px-3 py-1.5 rounded-lg hover:border-gray-600 transition-colors">
                <RotateCcw size={12}/> Refresh
              </button>
            </div>

            {sources.length === 0 ? (
              <div className="bg-[#090C15] border border-gray-800 rounded-2xl min-h-[300px] flex flex-col items-center justify-center gap-4 text-gray-600">
                <Flame size={40} className="opacity-20"/>
                <p className="text-sm">Belum ada data RAG. Chat dengan CAKRA menggunakan mode Dokumen.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <div className="bg-[#090C15] border border-gray-800 rounded-2xl p-5">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Flame size={12} className="text-orange-500"/> Relevance Score Map
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
                              <FileText size={12} style={{ color: cfg.text }}/>
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
                          <div className="h-3 bg-gray-800/60 rounded-full overflow-hidden relative">
                            <div
                              className="h-full rounded-full transition-all duration-1000 ease-out relative"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: cfg.bar,
                                boxShadow: `0 0 12px ${cfg.bar}80`,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { label: 'HIGH Relevance', range: '≥ 80%', color: '#ef4444' },
                    { label: 'GOOD Relevance', range: '65–79%', color: '#f97316' },
                    { label: 'FAIR Relevance', range: '50–64%', color: '#eab308' },
                    { label: 'LOW Relevance',  range: '< 50%',  color: '#3b82f6' },
                  ].map(item => (
                    <div key={item.label} className="bg-gray-900/50 border border-gray-800 rounded-xl p-3 flex items-center gap-3">
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
