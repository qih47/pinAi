import React, { useMemo, useCallback, useState, useRef, Component } from 'react';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, addEdge, BaseEdge, EdgeLabelRenderer, getSmoothStepPath, useStore, ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { translations } from '../../../utils/translations';
import ViewerHeader from './ViewerHeader';
import { Share2 } from 'lucide-react';

class FlowErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ReactFlow Error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center text-red-500 bg-red-50/10 p-4 border border-red-200/20 rounded-xl">
          <svg className="w-8 h-8 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div className="font-semibold text-sm">Gagal me-render Diagram</div>
          <div className="text-xs mt-1 opacity-80 text-center max-w-md">{this.state.error?.message || 'Data diagram tidak valid'}</div>
        </div>
      );
    }
    return this.props.children;
  }
}


// --- CUSTOM EDGE ---
// SmartEdge mendeteksi jika ada garis bolak-balik antara 2 node yang sama,
// dan akan menggeser posisi labelnya (satu ke atas, satu ke bawah) agar tidak tumpeng tindih.
function SmartEdge({ id, source, target, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, label, animated }) {
  // Cek apakah ada edge dari arah sebaliknya di store (bi-directional)
  const isBiDirect = useStore((s) => s.edges.some((e) => e.source === target && e.target === source));
  
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition,
  });

  // Geser label secara vertikal jika rutenya bolak-balik bertabrakan
  let yOffset = 0;
  if (isBiDirect) {
    yOffset = source > target ? 18 : -18;
  }

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={{ ...style, strokeWidth: 2 }} markerEnd={markerEnd} />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY + yOffset}px)`,
              background: '#1e293b',
              color: '#ffffff',
              padding: '4px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              pointerEvents: 'all',
              border: '1px solid #334155',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            }}
            className="nodrag nopan"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const edgeTypes = {
  smart: SmartEdge,
};

export default function ReactFlowViewer({ chartCode, darkMode, isStreaming, language = 'id' }) {
  const tGlobal = translations[language] || translations.id;
  const [isExpanded, setIsExpanded] = useState(false);
  const exportRef = useRef(null);

  // 1. Coba parse JSON terlebih dahulu
  const parsedData = useMemo(() => {
    try {
      if (!chartCode || chartCode.trim() === '') return null;
      // Normalisasi edges agar menggunakan type 'smart'
      const data = JSON.parse(chartCode);
      if (data && !Array.isArray(data.nodes)) data.nodes = [];
      if (data && !Array.isArray(data.edges)) data.edges = [];
      if (data && data.edges) {
        data.edges = data.edges.map(e => ({ ...e, type: 'smart', animated: true }));
      }
      return data;
    } catch (e) {
      return { error: 'Invalid JSON format for flow data.' };
    }
  }, [chartCode]);

  // 2. Jika masih streaming dan JSON belum valid/lengkap, tampilkan loading
  // Ini memungkinkan diagram dirender segera setelah blok JSON valid selesai,
  // meskipun teks di bawah diagram masih terus di-stream oleh AI.
  if (isStreaming && (!parsedData || parsedData.error)) {
    return (
      <div className={`w-full h-[400px] flex items-center justify-center rounded-xl border border-dashed ${darkMode ? 'border-gray-700 bg-gray-800/30 text-gray-400' : 'border-gray-300 bg-gray-50 text-gray-500'}`}>
        <div className="flex flex-col items-center gap-2">
          <svg className="animate-spin h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-sm font-medium">Membuat Diagram...</span>
        </div>
      </div>
    );
  }

  // 3. Error sesudah streaming selesai
  if (parsedData?.error || !parsedData?.nodes || !parsedData?.edges) {
    return (
      <div className={`w-full p-4 text-sm rounded-lg border ${darkMode ? 'bg-red-900/10 border-red-900/50 text-red-400' : 'bg-red-50 border-red-200 text-red-600'}`}>
        <div className="flex items-center gap-2 font-semibold mb-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Gagal Membaca Data Diagram (Flowchart)
        </div>
        <pre className="text-xs mt-2 overflow-x-auto p-2 bg-black/10 rounded">{chartCode}</pre>
      </div>
    );
  }


  return (
    <div className={
      isExpanded 
        ? `fixed inset-0 z-[9999] p-4 md:p-10 flex flex-col ${darkMode ? 'bg-[#121212]/95 backdrop-blur-sm' : 'bg-gray-100/95 backdrop-blur-sm'}`
        : `my-4 w-full rounded-xl border shadow-sm flex flex-col ${darkMode ? 'bg-[#222225] border-gray-700/60' : 'bg-white border-gray-200'}`
    }>
      <ViewerHeader 
        title={parsedData.title || "Flow Diagram"} 
        icon={<Share2 size={15} />} 
        onExpand={() => setIsExpanded(!isExpanded)} 
        isExpanded={isExpanded} 
        exportTargetRef={exportRef} 
        darkMode={darkMode} 
      />

      <div 
        ref={exportRef} 
        className={`flex-1 w-full flex flex-col ${darkMode ? 'bg-[#222225]' : 'bg-white'} ${isExpanded ? 'rounded-b-xl shadow-2xl border-x border-b ' + (darkMode ? 'border-gray-800' : 'border-gray-200') : 'rounded-b-xl p-2'}`}
      >
        {isExpanded && parsedData.title && (
          <h3 className={`text-lg font-bold my-4 text-center ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>
            {parsedData.title}
          </h3>
        )}
        <div style={{ width: '100%', height: isExpanded ? '100%' : '400px', flex: isExpanded ? 1 : 'none', borderRadius: '12px', overflow: 'hidden' }}>
          <FlowErrorBoundary>
            <ReactFlowProvider>
              <FlowComponent initialNodes={parsedData.nodes} initialEdges={parsedData.edges} darkMode={darkMode} />
            </ReactFlowProvider>
          </FlowErrorBoundary>
        </div>
      </div>
    </div>
  );
}

// Pisahkan komponen Flow agar hooks useNodesState berfungsi baik
function FlowComponent({ initialNodes = [], initialEdges = [], darkMode }) {
  // Validate that nodes have valid IDs to prevent crashes
  const safeNodes = (Array.isArray(initialNodes) ? initialNodes : []).filter(n => n && n.id);
  const safeEdges = (Array.isArray(initialEdges) ? initialEdges : []).filter(e => e && e.id && e.source && e.target);

  const [nodes, setNodes, onNodesChange] = useNodesState(safeNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(safeEdges);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge({ ...params, animated: true, type: 'smart' }, eds)),
    [setEdges]
  );

  const bgColor = darkMode ? '#0f172a' : '#f8fafc';
  const dotColor = darkMode ? '#334155' : '#cbd5e1';

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      colorMode={darkMode ? 'dark' : 'light'}
      style={{ background: bgColor }}
      proOptions={{ hideAttribution: true }}
      preventScrolling={false}
      zoomOnScroll={false}
      panOnScroll={false}
    >
      <Controls />
      <MiniMap 
        nodeStrokeColor={() => (darkMode ? '#475569' : '#94a3b8')} 
        nodeColor={() => (darkMode ? '#1e293b' : '#ffffff')}
        maskColor={darkMode ? 'rgba(0, 0, 0, 0.6)' : 'rgba(255, 255, 255, 0.6)'} 
      />
      <Background variant="dots" gap={16} size={1.5} color={dotColor} />
    </ReactFlow>
  );
}
