import React, { useState, useEffect } from 'react';
import { Activity, Network, ArrowRight, BrainCircuit, Database, Server, ChevronRight, Zap, Search, Paperclip, Code, User } from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const PipelineVisualizer = () => {
  const [steps, setSteps] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPipeline = async () => {
    try {
      const res = await apiClient.get('/analytics/pipeline');
      if (res.data.status === 'success') {
        setSteps(res.data.steps || []);
      }
    } catch (e) {
      console.error("Failed to fetch pipeline data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPipeline();
    const interval = setInterval(fetchPipeline, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  const getToolIcon = (toolName) => {
    const t = (toolName || '').toUpperCase();
    if (t.includes('ROUTER')) return <BrainCircuit size={16} />;
    if (t.includes('FLASH')) return <Zap size={16} />;
    if (t.includes('FOCUS')) return <Search size={16} />;
    if (t.includes('ATTACHMENT')) return <Paperclip size={16} />;
    if (t.includes('ANALYST') || t.includes('CODE')) return <Code size={16} />;
    if (t.includes('GUEST')) return <User size={16} />;
    if (t.includes('SYNTHESIS') || t.includes('RAG')) return <Network size={16} />;
    if (t.includes('SQL') || t.includes('DB')) return <Database size={16} />;
    return <Server size={16} />;
  };

  const getToolColor = (toolName) => {
    const t = (toolName || '').toUpperCase();
    if (t.includes('ROUTER')) return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50';
    if (t.includes('FLASH')) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
    if (t.includes('FOCUS')) return 'bg-fuchsia-500/20 text-fuchsia-400 border-fuchsia-500/50';
    if (t.includes('ATTACHMENT')) return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
    if (t.includes('ANALYST')) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
    if (t.includes('GUEST')) return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
    if (t.includes('SYNTHESIS')) return 'bg-blue-500/20 text-blue-400 border-blue-500/50';
    if (t.includes('SQL')) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
    if (t.includes('SEARCH')) return 'bg-purple-500/20 text-purple-400 border-purple-500/50';
    return 'bg-blue-500/20 text-blue-400 border-blue-500/50';
  };

  return (
    <div className="bg-[#0B0F19]/90 border border-gray-800 rounded-xl p-6 flex flex-col h-full">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-bold tracking-widest uppercase flex items-center gap-2 text-gray-400">
          <Activity size={16} className="text-blue-500" /> 
          Agentic Pipeline Visualizer
        </h3>
        <div className="flex items-center gap-2 text-xs font-mono text-gray-500">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
          </span>
          LIVE TRACING
        </div>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
        {loading && steps.length === 0 ? (
          <div className="flex h-full items-center justify-center animate-pulse text-gray-600">
            Scanning Agent Pathways...
          </div>
        ) : steps.length === 0 ? (
          <div className="flex h-full items-center justify-center text-gray-600">
            No pipeline activity detected yet.
          </div>
        ) : (
          <div className="flex items-center space-x-2 h-full min-w-max px-4">
            {/* Show top 5 recent steps to form a pipeline */}
            {steps.slice(0, 5).map((step, index) => {
              const toolLabel = step.tool_called || 'ROUTER';
              const colors = getToolColor(step.tool_called);
              
              return (
                <React.Fragment key={step.id}>
                  {/* Node */}
                  <div className={`flex flex-col min-w-[200px] max-w-[250px] border rounded-lg p-3 ${colors} shadow-lg shadow-black/50 relative group`}>
                    <div className="flex justify-between items-center mb-2 border-b border-inherit/30 pb-2">
                      <div className="flex items-center gap-2 font-bold text-xs tracking-wider">
                        {getToolIcon(step.tool_called)}
                        {toolLabel.toUpperCase()}
                      </div>
                      <div className="text-[10px] opacity-70">
                        {new Date(step.created_at).toLocaleTimeString()}
                      </div>
                    </div>
                    
                    <div className="text-xs opacity-90 truncate font-mono">
                      {step.tool_input || 'Synthesizing Response...'}
                    </div>
                    
                    {/* Tooltip / Details on hover */}
                    <div className="absolute top-full left-0 mt-2 w-64 bg-black/90 border border-gray-700 rounded p-3 text-xs text-gray-300 z-10 hidden group-hover:block shadow-xl break-words">
                      <div className="font-bold text-gray-400 mb-1 border-b border-gray-700 pb-1">Input Context</div>
                      <div className="mb-2 max-h-20 overflow-y-auto">{step.tool_input || '-'}</div>
                      <div className="font-bold text-gray-400 mb-1 border-b border-gray-700 pb-1">Observation Result</div>
                      <div className="max-h-20 overflow-y-auto font-mono text-[10px] text-green-400">{step.observation || '-'}</div>
                      <div className="mt-2 text-[10px] text-gray-500 pt-1 border-t border-gray-800">
                        Session: {step.session_uuid.split('-')[0]}... | User: {step.npp}
                      </div>
                    </div>
                  </div>
                  
                  {/* Connector Arrow */}
                  {index < Math.min(steps.length, 5) - 1 && (
                    <div className="flex flex-col items-center px-1">
                      <div className="h-0.5 w-8 bg-gray-700 relative">
                        <ArrowRight size={14} className="absolute -right-2 -top-1.5 text-gray-500" />
                      </div>
                    </div>
                  )}
                </React.Fragment>
              );
            })}
            
            {/* End Node: Output */}
            <div className="flex flex-col items-center px-1">
              <div className="h-0.5 w-8 bg-gray-700 relative">
                <ChevronRight size={14} className="absolute -right-2 -top-1.5 text-gray-500" />
              </div>
            </div>
            <div className="flex flex-col justify-center items-center h-12 w-12 rounded-full border-2 border-green-500/50 bg-green-500/10 text-green-400 shadow-[0_0_15px_rgba(34,197,94,0.2)]">
              <span className="text-[10px] font-bold">OUTPUT</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
