import React, { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Maximize2, Minimize2, Calendar, ZoomIn, ZoomOut, Info } from 'lucide-react';
import { toPng, toSvg } from 'html-to-image';

import { parsePartialJSON } from '../../../utils/jsonHelper';
import ViewerHeader from './ViewerHeader';

const GanttViewer = ({ chartCode, darkMode, isStreaming }) => {
  const containerRef = useRef(null);
  const printRef = useRef(null);
  
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hoveredTask, setHoveredTask] = useState(null);

  useEffect(() => {
    if (!chartCode) return;
    
    const parsed = parsePartialJSON(chartCode);
    
    if (!parsed) {
      if (isStreaming) {
        // Biarkan jika sedang streaming
      } else {
        setError("Gagal merender Gantt Chart. Format JSON tidak valid atau terpotong.");
      }
      return;
    }
    
    if (!Array.isArray(parsed) || parsed.length === 0) {
      if (!isStreaming) {
        setError("Data harus berupa array JSON berisi tugas-tugas.");
      }
      return;
    }
    
    setData(parsed);
    setError(null);
  }, [chartCode, isStreaming]);

  const toggleFullscreen = () => setIsFullscreen(!isFullscreen);

  // Proses data tanggal
  const { timelineInfo, processedTasks } = useMemo(() => {
    if (data.length === 0) return { timelineInfo: null, processedTasks: [] };

    const tasks = data.map(t => {
      const start = new Date(t.start || new Date());
      let end = new Date(t.end || t.start);
      if (end < start) end = new Date(start);
      return {
        ...t,
        startDate: start,
        endDate: end,
        duration: (end.getTime() - start.getTime()) / (1000 * 3600 * 24) + 1,
        progress: parseFloat(t.progress) || 0
      };
    });

    const minDate = new Date(Math.min(...tasks.map(t => t.startDate.getTime())));
    const maxDate = new Date(Math.max(...tasks.map(t => t.endDate.getTime())));
    
    // Beri buffer 2 hari di awal dan akhir
    minDate.setDate(minDate.getDate() - 2);
    maxDate.setDate(maxDate.getDate() + 2);
    
    const totalDays = Math.max(1, (maxDate.getTime() - minDate.getTime()) / (1000 * 3600 * 24) + 1);

    return {
      timelineInfo: { minDate, maxDate, totalDays },
      processedTasks: tasks
    };
  }, [data]);


  if (error) {
    return (
      <div className="p-4 border border-red-500 bg-red-50 text-red-700 rounded-lg text-sm mt-4">
        <strong>Error:</strong> {error}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4 animate-pulse text-gray-500">
        Menyiapkan Gantt Chart...
      </div>
    );
  }

  const { minDate, totalDays } = timelineInfo;
  
  // Minimal lebar tiap hari agar bisa di-scroll secara horizontal jika sangat panjang
  const dayWidth = isFullscreen ? Math.max(20, 1000 / totalDays) : Math.max(12, 600 / totalDays);
  const chartWidth = totalDays * dayWidth;

  const getLeftOffset = (date) => {
    return ((date.getTime() - minDate.getTime()) / (1000 * 3600 * 24)) * dayWidth;
  };

  // Generate ticks untuk axis (tiap minggu atau tiap hari tergantung lebar)
  const ticks = [];
  const currentDate = new Date(minDate);
  for (let i = 0; i < totalDays; i++) {
    ticks.push(new Date(currentDate));
    currentDate.setDate(currentDate.getDate() + 1);
  }

  const viewerContent = (
    <div ref={containerRef} className={`group rounded-xl border flex flex-col transition-all duration-300 ${
        darkMode ? 'bg-[#111827] border-gray-700 text-white' : 'bg-white border-gray-200 text-gray-900'
      } ${isFullscreen ? 'fixed inset-0 z-[9999] p-4 md:p-10 shadow-2xl overflow-hidden' : 'relative w-full my-4 min-h-[300px]'}`}>
      
      <ViewerHeader 
        title="Cakra Project Planner (Gantt)" 
        icon={<Calendar size={15} />} 
        onExpand={toggleFullscreen} 
        isExpanded={isFullscreen} 
        exportTargetRef={printRef} 
        darkMode={darkMode} 
      />

      <div className={`flex-1 overflow-auto bg-transparent relative custom-scrollbar ${isFullscreen ? 'rounded-b-xl' : ''}`}>
        <div ref={printRef} className={`relative min-w-full p-4 md:p-6 ${darkMode ? 'bg-[#111827]' : 'bg-white'}`} style={{ width: Math.max(800, chartWidth + 200) }}>
          
          {/* Header Axis Tanggal */}
          <div className="flex border-b border-gray-200 dark:border-gray-700 mb-4 pb-2 ml-[200px]" style={{ width: chartWidth }}>
            {ticks.map((date, idx) => {
              // Tampilkan label tanggal tiap beberapa hari agar tidak dempet
              const showLabel = totalDays < 30 ? true : (date.getDay() === 1 || idx === 0 || idx === totalDays - 1);
              return (
                <div key={idx} className="flex-none flex flex-col items-center justify-end relative" style={{ width: dayWidth }}>
                  {showLabel && (
                    <span className={`text-[9px] font-medium absolute -top-5 whitespace-nowrap ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                      {date.getDate()}/{date.getMonth() + 1}
                    </span>
                  )}
                  <div className={`w-[1px] h-2 ${showLabel ? (darkMode ? 'bg-gray-500' : 'bg-gray-400') : (darkMode ? 'bg-gray-700' : 'bg-gray-200')}`} />
                </div>
              );
            })}
          </div>

          {/* Grid Background */}
          <div className="absolute top-[70px] bottom-0 ml-[200px] flex pointer-events-none" style={{ width: chartWidth }}>
            {ticks.map((_, idx) => (
               <div key={idx} className={`flex-none border-l h-full ${darkMode ? 'border-gray-800' : 'border-gray-100'}`} style={{ width: dayWidth }} />
            ))}
          </div>

          {/* Task Rows */}
          <div className="relative z-10 flex flex-col gap-3">
            {processedTasks.map((task, idx) => {
              const left = getLeftOffset(task.startDate);
              const width = task.duration * dayWidth;
              
              return (
                <div key={task.id || idx} className="flex items-center relative group"
                     onMouseEnter={() => setHoveredTask(task)}
                     onMouseLeave={() => setHoveredTask(null)}>
                  
                  {/* Task Name Sidebar */}
                  <div className={`w-[190px] pr-4 shrink-0 text-xs font-semibold truncate ${darkMode ? 'text-gray-300' : 'text-gray-700'}`} title={task.name}>
                    {task.name}
                  </div>
                  
                  {/* Gantt Bar Area */}
                  <div className="relative flex items-center h-8" style={{ width: chartWidth }}>
                    <div 
                      className={`absolute h-6 rounded-md shadow-sm overflow-hidden flex items-center transition-all duration-300 ${
                        darkMode ? 'bg-gray-700 border-gray-600' : 'bg-blue-100 border-blue-200'
                      } border cursor-pointer hover:shadow-md hover:brightness-110`}
                      style={{ left, width: Math.max(width, 10) }}
                    >
                      {/* Progress Fill */}
                      <div 
                        className={`h-full ${darkMode ? 'bg-blue-500' : 'bg-blue-500'}`}
                        style={{ width: `${task.progress}%` }}
                      />
                      
                      {/* Text Inside Bar (if fits) */}
                      {width > 80 && (
                        <span className={`absolute inset-0 flex items-center px-2 text-[10px] font-bold ${
                          task.progress > 50 ? 'text-white' : (darkMode ? 'text-gray-200' : 'text-blue-900')
                        } truncate`}>
                          {task.progress}%
                        </span>
                      )}
                    </div>
                  </div>

                </div>
              );
            })}
          </div>

        </div>
      </div>
      
      {/* Floating Hover Tooltip */}
      {hoveredTask && (
        <div className={`absolute z-50 pointer-events-none p-3 rounded-xl shadow-2xl border backdrop-blur-md transition-all animate-in fade-in zoom-in duration-200 ${
            darkMode ? 'bg-gray-800/90 border-gray-700 text-gray-200' : 'bg-white/95 border-gray-200 text-gray-800'
          }`}
          style={{ bottom: 20, right: 20, minWidth: 200 }}
        >
          <div className="font-bold text-sm mb-2 pb-2 border-b border-gray-500/20 flex items-center gap-2">
             <Info size={14} className="text-blue-500" />
             {hoveredTask.name}
          </div>
          <div className="flex flex-col gap-1 text-xs">
            <div className="flex justify-between">
              <span className="opacity-70">Mulai:</span>
              <span className="font-semibold">{hoveredTask.startDate.toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-70">Selesai:</span>
              <span className="font-semibold">{hoveredTask.endDate.toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-70">Durasi:</span>
              <span className="font-semibold">{hoveredTask.duration} hari</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="opacity-70">Progress:</span>
              <div className="flex-1 h-1.5 rounded-full bg-gray-500/20 overflow-hidden">
                 <div className="h-full bg-blue-500" style={{ width: `${hoveredTask.progress}%` }} />
              </div>
              <span className="font-bold">{hoveredTask.progress}%</span>
            </div>
          </div>
        </div>
      )}
      
    </div>
  );

  if (isFullscreen) {
    return (
      <>
        <div className="w-full my-4 p-8 border border-dashed rounded-xl text-center text-sm font-medium text-gray-500">
          Tampilan layar penuh aktif. Tutup jendela popup untuk kembali.
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
