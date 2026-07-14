import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import Gantt from 'frappe-gantt';
import { Maximize2, Minimize2, Calendar, ZoomIn, ZoomOut } from 'lucide-react';

// Requires importing frappe-gantt CSS in index.css or here if using a loader, but we will assume it's imported globally or we can import it here
import '../../../../node_modules/frappe-gantt/dist/frappe-gantt.css';

import { parsePartialJSON } from '../../../utils/jsonHelper';

const GanttViewer = ({ chartCode, darkMode, isStreaming }) => {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [viewMode, setViewMode] = useState('Week');
  const ganttInstance = useRef(null);

  useEffect(() => {
    if (!chartCode) return;
    
    // Gunakan parsePartialJSON agar aman saat streaming atau terpotong
    const parsed = parsePartialJSON(chartCode);
    
    if (!parsed) {
      if (isStreaming) {
        // Cukup biarkan saja, belum selesai
      } else {
        setError("Gagal merender Gantt Chart. Format JSON tidak valid atau terpotong.");
      }
      return;
    }
    
    if (!Array.isArray(parsed) || parsed.length === 0) {
      if (!isStreaming) {
        setError("Gantt data must be a non-empty JSON array of tasks.");
      }
      return;
    }
    
    setData(parsed);
    setError(null);
  }, [chartCode, isStreaming]);

  useEffect(() => {
    if (data.length > 0 && svgRef.current) {
      // Membersihkan instance sebelumnya jika ada
      if (ganttInstance.current) {
        svgRef.current.innerHTML = '';
      }

      try {
        ganttInstance.current = new Gantt(svgRef.current, data, {
          view_mode: viewMode,
          date_format: 'YYYY-MM-DD',
          custom_popup_html: function(task) {
            return `
              <div class="p-3 bg-white border border-gray-200 rounded-lg shadow-xl text-xs text-gray-800" style="min-width: 150px;">
                <div class="font-bold mb-1">${task.name}</div>
                <div class="text-gray-500 mb-2">Mulai: ${task.start} <br/> Selesai: ${task.end}</div>
                <div class="w-full bg-gray-200 rounded-full h-1.5 mb-1">
                  <div class="bg-blue-600 h-1.5 rounded-full" style="width: ${task.progress}%"></div>
                </div>
                <div class="text-right text-[10px] font-bold">${task.progress}%</div>
              </div>
            `;
          }
        });
      } catch (err) {
        console.error("Failed to initialize Frappe Gantt", err);
      }
    }
  }, [data, viewMode]);

  // CSS overrides for Dark Mode specifically for Frappe Gantt
  useEffect(() => {
    if (!svgRef.current) return;
    if (darkMode) {
      svgRef.current.classList.add('gantt-dark-mode');
    } else {
      svgRef.current.classList.remove('gantt-dark-mode');
    }
  }, [darkMode, data]);

  const toggleFullscreen = () => setIsFullscreen(!isFullscreen);

  if (error) {
    return (
      <div className="p-4 border border-red-500 bg-red-50 text-red-700 rounded-lg text-sm mt-4">
        <strong>Error:</strong> {error}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4 animate-pulse">
        Menyiapkan Gantt Chart...
      </div>
    );
  }

  const viewerContent = (
    <div ref={containerRef} className={`group rounded-xl border flex flex-col transition-all duration-300 ${
        darkMode ? 'bg-gray-800 border-gray-700 cakra-gantt-dark' : 'bg-white border-gray-200 cakra-gantt-light'
      } ${isFullscreen ? 'w-full h-full shadow-2xl overflow-hidden' : 'relative w-full my-4 overflow-hidden'}`}>
      
      {/* Custom Global CSS to fix dark mode visibility issues with Frappe Gantt */}
      <style>{`
        .cakra-gantt-dark {
          --g-arrow-color: #9ca3af;
          --g-bar-color: #101878; /* Pindad Blue */
          --g-bar-border: #1a237e;
          --g-tick-color-thick: #374151;
          --g-tick-color: #1f2937;
          --g-actions-background: #1f2937;
          --g-border-color: #374151;
          --g-text-muted: #9ca3af;
          --g-text-light: #ffffff;
          --g-text-dark: #f3f4f6;
          --g-progress-color: #E3B432; /* Pindad Yellow */
          --g-handle-color: #d1d5db;
          --g-weekend-label-color: #374151;
          --g-expected-progress: #4b5563;
          --g-header-background: #111827;
          --g-row-color: #1f2937;
          --g-row-border-color: #374151;
          --g-today-highlight: #4b5563;
          --g-popup-actions: #1f2937;
          --g-weekend-highlight-color: #111827;
        }

        .cakra-gantt-light {
          --g-bar-color: #101878; /* Pindad Blue */
          --g-progress-color: #E3B432; /* Pindad Yellow */
        }
        
        /* Fix text contrast in popup */
        .gantt-container .popup-wrapper {
          background: ${darkMode ? '#1f2937' : '#ffffff'} !important;
          color: ${darkMode ? '#f3f4f6' : '#1f2937'} !important;
          border: 1px solid ${darkMode ? '#374151' : '#e5e7eb'} !important;
        }
        
        .gantt-container .popup-wrapper * {
          color: inherit;
        }
        
        /* Ensure the container takes full height in fullscreen */
        ${isFullscreen ? `
          .gantt-container {
            height: calc(100vh - 120px) !important;
          }
        ` : ''}
      `}</style>

      {/* Toolbar */}
      <div className={`flex justify-end items-center gap-2 px-3 py-2 border-b ${
        darkMode ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'
      }`}>
        <span className={`text-xs font-semibold mr-auto ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          Cakra Project Planner (Gantt)
        </span>
        
        {/* View Mode Selectors */}
        <div className="flex bg-gray-100 dark:bg-gray-700 rounded-md p-0.5 text-xs mr-2">
          {['Day', 'Week', 'Month'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-2 py-1 rounded transition-colors ${
                viewMode === mode 
                  ? (darkMode ? 'bg-gray-600 text-white shadow-sm' : 'bg-white text-gray-800 shadow-sm')
                  : (darkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700')
              }`}
            >
              {mode}
            </button>
          ))}
        </div>

        <button onClick={toggleFullscreen} className={`p-1.5 rounded-md transition-colors ${
            darkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
        }`}>
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Main Gantt Content */}
      <div className="flex-1 overflow-auto bg-transparent relative">
        <svg ref={svgRef} className="w-full"></svg>
      </div>
    </div>
  );

  if (isFullscreen) {
    return (
      <>
        {/* Placeholder in the chat bubble so it doesn't collapse entirely */}
        <div className="w-full my-4 p-8 border border-dashed rounded-xl text-center text-sm font-medium text-gray-500">
          Mode Layar Penuh Aktif
        </div>
        {createPortal(
          <div className="fixed inset-0 z-[99999] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 md:p-8 animate-in fade-in duration-200">
            {viewerContent}
          </div>,
          document.body
        )}
      </>
    );
  }

  return viewerContent;
};

export default GanttViewer;
