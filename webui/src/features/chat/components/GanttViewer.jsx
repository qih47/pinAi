import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import Gantt from 'frappe-gantt';
import { Maximize2, Minimize2, Calendar, ZoomIn, ZoomOut } from 'lucide-react';

// Requires importing frappe-gantt CSS in index.css or here if using a loader, but we will assume it's imported globally or we can import it here
import '../../../../node_modules/frappe-gantt/dist/frappe-gantt.css';

import { parsePartialJSON } from '../../../utils/jsonHelper';
import ViewerHeader from './ViewerHeader';

const GanttViewer = ({ chartCode, darkMode, isStreaming }) => {
  const containerRef = useRef(null);
  const scrollRef = useRef(null);
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

        // Cegah frappe-gantt melakukan mouse wheel hijacking yang bisa menggeser tanggal ke area kosong
        const handleWheel = (e) => {
          e.stopPropagation();
        };
        svgRef.current.addEventListener('wheel', handleWheel, { capture: true });

        // Auto-scroll ke posisi tugas pertama agar user langsung melihat batang tugas
        setTimeout(() => {
          if (scrollRef.current && svgRef.current) {
            const firstBar = svgRef.current.querySelector('.bar-wrapper, .bar-group, .bar');
            if (firstBar && typeof firstBar.getBBox === 'function') {
              try {
                const bbox = firstBar.getBBox();
                if (bbox && bbox.x > 80) {
                  scrollRef.current.scrollLeft = bbox.x - 60;
                }
              } catch (e) {}
            }
          }
        }, 150);
      } catch (err) {
        console.error("Failed to initialize Frappe Gantt", err);
      }
    }
  }, [data, viewMode, isFullscreen]);

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
        darkMode ? 'bg-[#111827] border-gray-700 cakra-gantt-dark text-white' : 'bg-white border-gray-200 cakra-gantt-light text-gray-900'
      } ${isFullscreen ? 'fixed inset-0 z-[9999] p-4 md:p-10 shadow-2xl' : 'relative w-full my-4 min-h-[280px] md:min-h-[340px]'}`}>
      
      {/* Custom Global CSS to fix dark mode visibility issues with Frappe Gantt */}
      <style>{`
        .cakra-gantt-dark {
          --g-arrow-color: #9ca3af;
          --g-bar-color: #3b82f6; /* Blue Cerah untuk Dark Mode */
          --g-bar-border: #60a5fa;
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
          --g-bar-color: #101878; /* Pindad Blue untuk Light Mode */
          --g-progress-color: #E3B432; /* Pindad Yellow */
          --g-text-dark: #1f2937;
          --g-text-light: #ffffff;
          --g-row-color: #ffffff;
        }

        /* Perkencang kejelasan teks tanggal & task di kedua mode */
        .gantt .grid-header {
          fill: ${darkMode ? '#111827' : '#f9fafb'} !important;
        }
        .gantt .grid-row {
          fill: ${darkMode ? '#1f2937' : '#ffffff'} !important;
        }
        .gantt .row-line {
          stroke: ${darkMode ? '#374151' : '#e5e7eb'} !important;
        }
        .gantt .tick {
          stroke: ${darkMode ? '#374151' : '#e5e7eb'} !important;
        }
        .gantt text {
          fill: ${darkMode ? '#f3f4f6' : '#1f2937'} !important;
          font-weight: 600 !important;
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
            height: calc(90vh - 80px) !important;
          }
        ` : `
          .gantt-container {
            min-height: 250px !important;
          }
        `}
        
        /* Cegah pemotongan SVG dari batas viewport */
        .gantt-container, svg.gantt {
          overflow: visible !important;
        }
      `}</style>

      {/* Viewer Header Universal */}
      <ViewerHeader 
        title="Cakra Project Planner (Gantt)" 
        icon={<Calendar size={15} />} 
        onExpand={toggleFullscreen} 
        isExpanded={isFullscreen} 
        exportTargetRef={containerRef} 
        darkMode={darkMode} 
      />

      {/* Sub-Toolbar Kustom Gantt */}
      <div className={`flex justify-end items-center gap-2 px-3 py-2 border-b ${
        darkMode ? 'border-gray-700 bg-gray-900/80 text-gray-200' : 'border-gray-200 bg-gray-50 text-gray-700'
      }`}>
        {/* View Mode Selectors */}
        <div className="flex bg-gray-100 dark:bg-gray-700 rounded-md p-0.5 text-xs mr-auto">
          {['Day', 'Week', 'Month'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-2 py-1 rounded transition-colors ${
                viewMode === mode 
                  ? (darkMode ? 'bg-gray-600 text-white shadow-sm' : 'bg-white text-gray-800 shadow-sm font-semibold')
                  : (darkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700')
              }`}
            >
              {mode}
            </button>
          ))}
        </div>

        <button
          onClick={() => {
            if (scrollRef.current && svgRef.current) {
              const firstBar = svgRef.current.querySelector('.bar-wrapper, .bar-group, .bar');
              if (firstBar && typeof firstBar.getBBox === 'function') {
                try {
                  const bbox = firstBar.getBBox();
                  if (bbox && bbox.x > 80) {
                    scrollRef.current.scrollLeft = bbox.x - 60;
                  }
                } catch (e) {}
              }
            }
          }}
          className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors mr-1 border ${
            darkMode ? 'border-gray-600 hover:bg-gray-700 text-gray-200' : 'border-gray-300 hover:bg-gray-200 text-gray-700'
          }`}
          title="Scroll ke awal tugas"
        >
          Today
        </button>
      </div>

      {/* Main Gantt Content */}
      <div ref={scrollRef} className={`flex-1 overflow-auto bg-transparent relative min-w-0 ${isFullscreen ? 'rounded-b-xl' : ''}`}>
        <div className="inline-block min-w-full">
          <svg ref={svgRef} className="block min-w-full"></svg>
        </div>
      </div>
    </div>
  );
};

export default GanttViewer;
