import React, { useState, useEffect, useRef } from 'react';
import { Terminal, ArrowDownToLine, MousePointer2, Trash2, Eye, EyeOff } from 'lucide-react';
import { getApiBase } from '../../../services/endpoints';

export const LiveTerminal = () => {
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const isUserScrolledUp = useRef(false);
  const [forceRender, setForceRender] = useState(0); // For UI toggle button
  const endRef = useRef(null);

  useEffect(() => {
    const apiBase = getApiBase();
    const eventSource = new EventSource(`${apiBase}/api/analytics/logs/stream`);
    
    eventSource.onopen = () => setIsConnected(true);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status) return; // Ignore initial status messages
        
        setLogs(prev => {
          const newLogs = [...prev, data];
          return newLogs.length > 100 ? newLogs.slice(newLogs.length - 100) : newLogs;
        });
      } catch (e) {
        // Fallback for non-json
        setLogs(prev => [...prev, { message: event.data, level: "INFO" }]);
      }
    };

    eventSource.onerror = (e) => {
      setIsConnected(false);
      eventSource.close();
    };

    return () => eventSource.close();
  }, []);

  useEffect(() => {
    if (!isUserScrolledUp.current && !isMinimized) {
      endRef.current?.scrollIntoView({ behavior: 'auto' });
    }
  }, [logs, isMinimized]);

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    const isUp = scrollHeight - scrollTop - clientHeight > 50;
    if (isUserScrolledUp.current !== isUp) {
      isUserScrolledUp.current = isUp;
      setForceRender(prev => prev + 1); // just to update the icon
    }
  };

  const toggleAutoScroll = () => {
    isUserScrolledUp.current = !isUserScrolledUp.current;
    if (!isUserScrolledUp.current) {
      endRef.current?.scrollIntoView({ behavior: 'auto' });
    }
    setForceRender(prev => prev + 1);
  };

  const getColorByLevel = (level) => {
    switch(level) {
      case 'ERROR': return 'text-red-500 font-bold';
      case 'WARNING': return 'text-amber-500';
      case 'INFO': return 'text-cyan-400';
      case 'DEBUG': return 'text-gray-500';
      default: return 'text-gray-300';
    }
  };

  return (
    <div className="flex flex-col h-full w-full rounded-xl border border-gray-800 bg-[#0B0F19]/90 backdrop-blur-md overflow-hidden">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-[#111827]">
        <div className="flex items-center gap-2">
          <Terminal size={16} className="text-cyan-400" />
          <span className="text-xs font-mono text-gray-400 uppercase tracking-widest">
            LIVE SERVER LOGS // OPERATIONAL STREAM
          </span>
          <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-cyan-500 animate-pulse' : 'bg-red-500'}`} />
        </div>
        <div className="flex gap-3 text-gray-500">
          {!isUserScrolledUp.current ? (
            <ArrowDownToLine 
              size={14} 
              onClick={toggleAutoScroll}
              className="text-cyan-400 cursor-pointer transition-colors" 
              title="Auto-scroll: ON"
            />
          ) : (
            <MousePointer2 
              size={14} 
              onClick={toggleAutoScroll}
              className="hover:text-cyan-400 cursor-pointer transition-colors" 
              title="Auto-scroll: OFF"
            />
          )}
          
          {isMinimized ? (
            <EyeOff 
              size={14} 
              onClick={() => setIsMinimized(false)}
              className="text-amber-500 hover:text-amber-400 cursor-pointer transition-colors" 
              title="Show Logs"
            />
          ) : (
            <Eye 
              size={14} 
              onClick={() => setIsMinimized(true)}
              className="hover:text-cyan-400 cursor-pointer transition-colors" 
              title="Hide Logs"
            />
          )}

          <Trash2 
            size={14} 
            onClick={() => setLogs([])}
            className="hover:text-red-400 cursor-pointer transition-colors" 
            title="Clear Logs"
          />
        </div>
      </div>
      
      {/* Terminal Body */}
      {!isMinimized && (
        <div 
          className="flex-1 overflow-y-auto p-4 font-mono text-xs whitespace-pre-wrap"
          onScroll={handleScroll}
        >
        {logs.length === 0 ? (
          <div className="text-gray-600 flex items-center h-full justify-center animate-pulse">
            Waiting for logs...
          </div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="mb-1 leading-relaxed break-all hover:bg-gray-800/30 px-1 rounded transition-colors">
              <span className="text-gray-500 mr-2">[{log.timestamp ? log.timestamp.split('T')[1]?.split('Z')[0] : new Date().toLocaleTimeString()}]</span>
              <span className={`mr-2 ${getColorByLevel(log.level)}`}>[{log.level}]</span>
              {log.request_id && log.request_id !== "SYSTEM" && (
                <span className="text-purple-400 mr-2">[{log.request_id}]</span>
              )}
              <span className="text-gray-400 mr-2">({log.logger})</span>
              <span className="text-gray-300">{log.message}</span>
              {log.exc_info && (
                <div className="mt-1 ml-4 text-red-400 opacity-80 border-l-2 border-red-500/50 pl-2">
                  {log.exc_info}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
      )}
    </div>
  );
};
