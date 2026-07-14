import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import mermaid from 'mermaid';
import { toPng } from 'html-to-image';
import { Maximize2, Minimize2, Download } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://192.168.11.80:5000';

const MermaidViewer = ({ chartCode, darkMode, isStreaming }) => {
  const containerRef = useRef(null);
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDownloadMenuOpen, setIsDownloadMenuOpen] = useState(false);
  const printRef = useRef(null);

  const activeDarkMode = isExporting ? false : darkMode;

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: activeDarkMode ? 'dark' : 'default',
      securityLevel: 'loose',
      fontFamily: 'inherit',
    });
  }, [activeDarkMode]);

  useEffect(() => {

    const renderChart = async () => {
      try {
        // Cek dulu apakah sintaksnya udah valid (berguna pas LLM lagi streaming)
        try {
          await mermaid.parse(chartCode);
        } catch (parseError) {
          if (isStreaming) {
            console.warn('Mermaid syntax is not complete yet (streaming)');
            return;
          }
          throw parseError;
        }
        
        setError(null);
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, chartCode);
        setSvgContent(svg);
      } catch (err) {
        if (isStreaming) {
          // Abaikan error saat sedang streaming (kode belum lengkap)
          console.warn('Mermaid partial render error (ignored during stream)');
        } else {
          console.error('Mermaid render error:', err);
          setError(err.message || 'Gagal me-render diagram. Pastikan sintaks Mermaid valid.');
        }
      }
    };

    if (chartCode) {
      // Debounce 500ms agar tidak me-render setiap huruf saat AI streaming
      // Tapi kalau lagi nge-export (isExporting), kita langsung cepet aja render-nya
      const timeoutId = setTimeout(() => {
        renderChart();
      }, isExporting ? 50 : 500);
      
      return () => clearTimeout(timeoutId);
    }
  }, [chartCode, activeDarkMode, isExporting]);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const executeDownload = async (format) => {
    if (format === 'svg' && svgContent) {
      const encodedSvg = encodeURIComponent(svgContent);
      const dataUrl = `data:image/svg+xml;charset=utf-8,${encodedSvg}`;
      
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
      filenameInput.value = `cakra-diagram-${new Date().getTime()}.svg`;
      form.appendChild(filenameInput);
      
      const mimeInput = document.createElement('input');
      mimeInput.type = 'hidden';
      mimeInput.name = 'mime_type';
      mimeInput.value = 'image/svg+xml';
      form.appendChild(mimeInput);
      
      document.body.appendChild(form);
      form.submit();
      setTimeout(() => document.body.removeChild(form), 1000);
      
    } else if (format === 'png' && printRef.current) {
      try {
        const targetWidth = printRef.current.scrollWidth;
        const targetHeight = printRef.current.scrollHeight;

        const config = {
          quality: 1,
          pixelRatio: 2,
          backgroundColor: '#ffffff', // Force white background
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
        const dataUrl = await toPng(printRef.current, config);
        
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
        filenameInput.value = `cakra-diagram-${new Date().getTime()}.png`;
        form.appendChild(filenameInput);
        
        const mimeInput = document.createElement('input');
        mimeInput.type = 'hidden';
        mimeInput.name = 'mime_type';
        mimeInput.value = 'image/png';
        form.appendChild(mimeInput);
        
        document.body.appendChild(form);
        form.submit();
        setTimeout(() => document.body.removeChild(form), 1000);
        
      } catch (err) {
        console.error('Error downloading image:', err);
        alert('Gagal mengunduh diagram');
      }
    }
  };

  const handleDownload = (format) => {
    if (!svgContent) return;
    setIsDownloading(true);
    setIsDownloadMenuOpen(false);
    
    if (darkMode) {
      setIsExporting(true);
      // Tunggu mermaid re-render ke light mode
      setTimeout(() => {
        executeDownload(format).finally(() => {
          setIsExporting(false);
          setIsDownloading(false);
        });
      }, 500); // 500ms cukup karena isExporting debounce-nya 50ms
    } else {
      executeDownload(format).finally(() => {
        setIsDownloading(false);
      });
    }
  };

  const viewerContent = (
    <div
      ref={containerRef}
      className={`group rounded-xl border flex flex-col transition-all duration-300 ${
        activeDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      } ${isFullscreen ? 'w-full h-full shadow-2xl overflow-auto' : 'relative w-full my-4 overflow-hidden'}`}
      style={isFullscreen ? { minHeight: 0 } : {}}
    >
      {/* Toolbar */}
      <div className={`flex justify-end items-center gap-2 px-3 py-2 border-b ${
        activeDarkMode ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'
      }`}>
        <span className={`text-xs font-semibold mr-auto ${activeDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          Cakra AI Diagram
        </span>
        {/* Download Dropdown */}
        <div className="relative">
          <button 
            onClick={() => setIsDownloadMenuOpen(!isDownloadMenuOpen)}
            disabled={isDownloading}
            className={`p-1.5 rounded-md transition-colors flex items-center gap-1 ${
              activeDarkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
            } disabled:opacity-50`}
            title="Download Diagram"
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
        <button
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Keluar Layar Penuh' : 'Layar Penuh'}
          className={`p-1.5 rounded-md transition-colors ${
            activeDarkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
          }`}
        >
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Scrollable Wrapper */}
      <div 
        className={`flex-1 flex overflow-auto ${
          activeDarkMode ? 'text-gray-200' : 'text-gray-800'
        }`}
        style={isFullscreen ? { minHeight: 0 } : { minHeight: '200px' }}
      >
        {/* Render Area (No overflow hidden/auto on the print container) */}
        <div 
          ref={printRef}
          className="flex-1 flex items-center justify-center p-4 min-w-max min-h-max"
        >
        {error ? (
          <div className="text-red-500 text-sm font-medium text-center bg-red-500/10 p-4 rounded-lg">
            {error}
          </div>
        ) : svgContent ? (
          <div 
            dangerouslySetInnerHTML={{ __html: svgContent }} 
            className="w-full h-full flex justify-center [&>svg]:max-w-full [&>svg]:h-auto"
          />
        ) : (
          <div className="animate-pulse text-sm">Me-render diagram...</div>
        )}
        </div>
      </div>
    </div>
  );

  if (isFullscreen) {
    return (
      <>
        {/* Placeholder in the chat bubble */}
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

export default MermaidViewer;
