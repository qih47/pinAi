import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { toPng, toSvg } from 'html-to-image';
import { Target, ClipboardList, Gift, Calendar, CheckCircle, Trophy, Maximize2, Minimize2, Download, ChevronRight, CheckCircle2 } from 'lucide-react';

import { parsePartialJSON } from '../../../utils/jsonHelper';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://192.168.11.80:5000';

const TimelineInfographic = ({ chartCode, darkMode, isStreaming }) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDownloadMenuOpen, setIsDownloadMenuOpen] = useState(false);
  const printRef = useRef(null);

  const activeDarkMode = isExporting ? false : darkMode;

  useEffect(() => {
    if (!chartCode) return;
    
    // Gunakan parsePartialJSON agar aman saat streaming atau terpotong
    const parsed = parsePartialJSON(chartCode);
    
    if (!parsed) {
      if (isStreaming) {
        // Cukup biarkan saja, belum selesai
      } else {
        setError("Gagal merender infografis. Format JSON tidak valid atau terpotong.");
      }
      return;
    }
    
    setData(parsed);
    setError(null);
  }, [chartCode, isStreaming]);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const executeDownload = async (format) => {
    try {
      const targetWidth = printRef.current.scrollWidth;
      const targetHeight = printRef.current.scrollHeight;

      // Create a wrapper style config for better rendering
      const config = {
        quality: 1,
        pixelRatio: 2,
        backgroundColor: '#ffffff', // Force white background for exports
        width: targetWidth,
        height: targetHeight,
        style: { 
          transform: 'scale(1)', 
          transformOrigin: 'top left',
          width: `${targetWidth}px`,
          height: `${targetHeight}px`
        },
        skipFonts: true,
        fontEmbedCSS: '',
      };
      
      let dataUrl;
      if (format === 'png') {
        dataUrl = await toPng(printRef.current, config);
      } else {
        dataUrl = await toSvg(printRef.current, config);
      }
      
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = `${API_BASE}/api/chat/artifacts/download_b64`;
      
      const b64Input = document.createElement('input');
      b64Input.type = 'hidden';
      b64Input.name = 'base64_data';
      b64Input.value = dataUrl;
      form.appendChild(b64Input);
      
      const filenameInput = document.createElement('input');
      filenameInput.type = 'hidden';
      filenameInput.name = 'filename';
      filenameInput.value = `cakra-timeline-${new Date().getTime()}.${format}`;
      form.appendChild(filenameInput);
      
      const mimeInput = document.createElement('input');
      mimeInput.type = 'hidden';
      mimeInput.name = 'mime_type';
      mimeInput.value = format === 'png' ? 'image/png' : 'image/svg+xml';
      form.appendChild(mimeInput);
      
      document.body.appendChild(form);
      form.submit();
      
      // Clean up the form after a short delay to ensure submission starts
      setTimeout(() => {
        document.body.removeChild(form);
      }, 1000);
      
    } catch (err) {
      console.error('Error downloading image:', err);
      alert('Gagal mengunduh infografis');
    }
  };

  const handleDownload = (format) => {
    if (!printRef.current) return;
    setIsDownloading(true);
    setIsDownloadMenuOpen(false);
    
    if (darkMode) {
      setIsExporting(true);
      // Wait for React to render the light mode DOM before capturing
      setTimeout(() => {
        executeDownload(format).finally(() => {
          setIsExporting(false);
          setIsDownloading(false);
        });
      }, 300);
    } else {
      executeDownload(format).finally(() => {
        setIsDownloading(false);
      });
    }
  };

  const getMonthColor = (index) => {
    const colors = [
      'from-[#101878] to-[#1a237e]', // Pindad Blue
      'from-blue-500 to-blue-600',
      'from-green-500 to-green-600',
      'from-[#E3B432] to-yellow-500', // Pindad Yellow
      'from-red-500 to-red-600',
      'from-purple-500 to-purple-600',
    ];
    return colors[index % colors.length];
  };

  if (error) {
    return (
      <div className="p-4 border border-red-500 bg-red-50 text-red-700 rounded-lg text-sm mt-4">
        <strong>Error:</strong> {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 border border-dashed rounded-xl text-sm text-center font-medium my-4 animate-pulse">
        Menyiapkan Infografis Timeline...
      </div>
    );
  }

  const viewerContent = (
    <div className={`group rounded-xl border flex flex-col transition-all duration-300 ${
        activeDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      } ${isFullscreen ? 'w-full h-full shadow-2xl overflow-auto' : 'relative w-full my-4 overflow-hidden'}`}>
      
      {/* Toolbar */}
      <div className={`flex justify-end items-center gap-2 px-3 py-2 border-b ${
        activeDarkMode ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'
      }`}>
        <span className={`text-xs font-semibold mr-auto ${activeDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          Cakra AI Infographic
        </span>
        
        {/* Download Dropdown */}
        <div className="relative">
          <button 
            onClick={() => setIsDownloadMenuOpen(!isDownloadMenuOpen)}
            disabled={isDownloading}
            className={`p-1.5 rounded-md transition-colors flex items-center gap-1 ${
              activeDarkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
            } disabled:opacity-50`}
            title="Download Infographic"
          >
            <Download size={14} />
          </button>
          
          {isDownloadMenuOpen && (
            <div className={`absolute right-0 top-full mt-1 w-32 rounded-lg shadow-xl overflow-hidden z-50 border ${
              activeDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <button 
                onClick={() => handleDownload('png')}
                className={`w-full text-left px-4 py-2 text-xs font-semibold transition-colors ${
                  activeDarkMode ? 'text-gray-200 hover:bg-gray-700' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                Unduh PNG
              </button>
              <button 
                onClick={() => handleDownload('svg')}
                className={`w-full text-left px-4 py-2 text-xs font-semibold transition-colors border-t ${
                  activeDarkMode ? 'text-gray-200 hover:bg-gray-700 border-gray-700' : 'text-gray-700 hover:bg-gray-100 border-gray-100'
                }`}
              >
                Unduh SVG
              </button>
            </div>
          )}
        </div>

        <button onClick={toggleFullscreen} className={`p-1.5 rounded-md transition-colors ${
            activeDarkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
        }`}>
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Scrollable Wrapper */}
      <div className="w-full overflow-x-auto rounded-b-xl custom-scrollbar">
        {/* Main Infographic Content */}
        <div ref={printRef} className={`p-6 md:p-8 ${activeDarkMode ? 'text-gray-100 bg-gray-800' : 'text-gray-800 bg-white'}`} style={{ width: 'max-content', minWidth: 'max(100%, 800px)' }}>
        
        {/* Header */}
        <div className="text-center mb-10">
          <h2 className="text-2xl md:text-3xl font-black uppercase tracking-tight" style={{ color: activeDarkMode ? '#E3B432' : '#101878' }}>
            {data.title || 'PROJECT TIMELINE'}
          </h2>
          <div className="h-1 w-32 bg-gradient-to-r from-[#101878] to-[#E3B432] mx-auto mt-4 rounded-full"></div>
        </div>

        {/* Timeline Grid */}
        <div className="flex flex-row gap-4 mb-8">
          
          {/* Legend Sidebar */}
          <div className="flex flex-col gap-4 w-48 shrink-0 pt-[86px]">
            <div className={`flex flex-col items-center justify-center p-4 rounded-xl shadow-sm ${activeDarkMode ? 'bg-gray-700/40' : 'bg-gray-50'} border ${activeDarkMode ? 'border-gray-600' : 'border-gray-200'} min-h-[80px]`}>
              <Target size={24} className="mb-2 text-[#101878] dark:text-[#E3B432]" />
              <span className="text-xs font-bold text-center uppercase tracking-wider">Tujuan Utama</span>
            </div>
            <div className={`flex flex-col items-center justify-center p-4 rounded-xl shadow-sm ${activeDarkMode ? 'bg-gray-700/40' : 'bg-gray-50'} border ${activeDarkMode ? 'border-gray-600' : 'border-gray-200'} h-48`}>
              <ClipboardList size={24} className="mb-2 text-[#101878] dark:text-[#E3B432]" />
              <span className="text-xs font-bold text-center uppercase tracking-wider">Kegiatan Utama</span>
            </div>
            <div className={`flex flex-col items-center justify-center p-4 rounded-xl shadow-sm ${activeDarkMode ? 'bg-gray-700/40' : 'bg-gray-50'} border ${activeDarkMode ? 'border-gray-600' : 'border-gray-200'} h-36`}>
              <Gift size={24} className="mb-2 text-[#101878] dark:text-[#E3B432]" />
              <span className="text-xs font-bold text-center uppercase tracking-wider">Output / Deliverable</span>
            </div>
          </div>

          {/* Month Columns */}
          <div className="flex flex-row flex-1 gap-4 overflow-x-visible">
            {data.months?.map((month, index) => (
              <div key={index} className="flex flex-col flex-1 min-w-[200px] group">
                
                {/* Month Badge */}
                <div className="flex flex-col items-center mb-5 relative">
                  <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${getMonthColor(index)} text-white flex items-center justify-center font-black text-xl mb-3 shadow-[0_0_15px_rgba(0,0,0,0.2)] z-10 transition-transform duration-300 group-hover:scale-110`}>
                    {month.month || (index + 1)}
                  </div>
                  {/* Connection Line */}
                  {index < (data.months.length - 1) && (
                    <div className="absolute top-6 left-1/2 w-[calc(100%+1rem)] h-[3px] bg-gradient-to-r from-gray-300 to-gray-200 dark:from-gray-600 dark:to-gray-700 -z-0"></div>
                  )}
                  <div className={`w-full text-center py-2.5 rounded-t-xl bg-gradient-to-r ${getMonthColor(index)} text-white font-bold text-xs uppercase tracking-wider shadow-md`}>
                    BULAN {month.month || (index + 1)}
                  </div>
                  <div className={`w-full text-center py-2 px-2 text-[10px] font-bold uppercase min-h-[48px] flex items-center justify-center ${activeDarkMode ? 'bg-gray-700/80 text-gray-200' : 'bg-gray-100 text-gray-700'}`}>
                    {month.title}
                  </div>
                </div>

                {/* Card Body Container */}
                <div className={`flex flex-col rounded-b-xl border border-t-0 shadow-sm transition-all duration-300 group-hover:shadow-lg group-hover:-translate-y-1 ${activeDarkMode ? 'border-gray-700 bg-gray-800/40' : 'border-gray-200 bg-white'}`}>
                  {/* Main Objective */}
                  <div className="p-4 text-xs text-center font-medium min-h-[80px] flex items-center justify-center border-b border-dashed border-gray-200 dark:border-gray-700">
                    {month.mainObjective}
                  </div>

                  {/* Activities List */}
                  <div className="p-4 text-[11px] h-48 overflow-y-auto border-b border-dashed border-gray-200 dark:border-gray-700">
                    <ul className="space-y-2.5">
                      {month.activities?.map((act, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <ChevronRight size={14} className="text-blue-500 mt-0.5 shrink-0" />
                          <span className="leading-snug">{act}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Outputs List */}
                  <div className={`p-4 text-[11px] h-36 overflow-y-auto ${activeDarkMode ? 'bg-gray-800/60' : 'bg-gray-50'} rounded-b-xl`}>
                    <ul className="space-y-2.5">
                      {month.outputs?.map((out, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <CheckCircle2 size={14} className="text-green-500 mt-0.5 shrink-0" />
                          <span className="leading-snug font-medium">{out}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  {/* Bottom Color Bar */}
                  <div className={`h-2 w-full rounded-b-xl bg-gradient-to-r ${getMonthColor(index)} opacity-90 group-hover:opacity-100 transition-opacity`}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer Summary */}
        <div className="flex flex-row flex-wrap gap-4 mt-8">
          <div className={`flex items-center gap-3 p-4 rounded-xl border flex-1 ${activeDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-blue-50/50 border-blue-100'}`}>
            <Calendar size={24} className="text-[#101878] dark:text-[#E3B432]" />
            <div>
              <div className="text-[10px] font-bold uppercase text-gray-500">Durasi Total</div>
              <div className="font-bold">{data.duration || `${data.months?.length || 0} BULAN`}</div>
            </div>
          </div>
          
          <div className={`flex items-center gap-3 p-4 rounded-xl border flex-[2] ${activeDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-purple-50/50 border-purple-100'}`}>
            <CheckCircle size={24} className="text-purple-600 dark:text-purple-400" />
            <div>
              <div className="text-[10px] font-bold uppercase text-gray-500">Catatan</div>
              <div className="text-xs">{data.note || 'Timeline dapat menyesuaikan dengan kondisi di lapangan.'}</div>
            </div>
          </div>

          <div className={`flex items-center gap-3 p-4 rounded-xl border flex-[2] ${activeDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-yellow-50/50 border-yellow-100'}`}>
            <Trophy size={24} className="text-[#E3B432]" />
            <div>
              <div className="text-[10px] font-bold uppercase text-gray-500">Hasil Akhir</div>
              <div className="text-xs">{data.result || 'Proyek selesai tepat waktu dan siap digunakan.'}</div>
            </div>
          </div>
        </div>

        </div>

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

export default TimelineInfographic;
