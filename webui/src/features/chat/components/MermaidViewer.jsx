import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { Maximize2, Minimize2, Download } from 'lucide-react';

const MermaidViewer = ({ chartCode, darkMode }) => {
  const containerRef = useRef(null);
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: darkMode ? 'dark' : 'default',
      securityLevel: 'loose',
      fontFamily: 'inherit',
    });
  }, [darkMode]);

  useEffect(() => {

    const renderChart = async () => {
      try {
        // Cek dulu apakah sintaksnya udah valid (berguna pas LLM lagi streaming)
        try {
          await mermaid.parse(chartCode);
        } catch (parseError) {
          console.warn('Mermaid syntax is not complete yet (streaming)');
          return;
        }
        
        setError(null);
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, chartCode);
        setSvgContent(svg);
      } catch (err) {
        // Abaikan error saat sedang streaming (kode belum lengkap)
        console.warn('Mermaid partial render error (ignored during stream)');
      }
    };

    if (chartCode) {
      // Debounce 500ms agar tidak me-render setiap huruf saat AI streaming
      const timeoutId = setTimeout(() => {
        renderChart();
      }, 500);
      
      return () => clearTimeout(timeoutId);
    }
  }, [chartCode, darkMode]);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const handleDownload = () => {
    if (!svgContent) return;
    
    // Gunakan Data URI alih-alih Blob Object URL untuk menghindari
    // masalah pemblokiran keamanan di HTTP / IP Lokal (Insecure Connection).
    const encodedSvg = encodeURIComponent(svgContent);
    const url = `data:image/svg+xml;charset=utf-8,${encodedSvg}`;
    
    const link = document.createElement('a');
    link.href = url;
    link.download = 'diagram_cakra.svg';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const viewerContent = (
    <div
      ref={containerRef}
      className={`relative group rounded-xl border flex flex-col ${
        darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
      } ${isFullscreen ? 'w-full h-full p-6 flex-1' : 'w-full my-4 overflow-hidden'}`}
      style={isFullscreen ? { minHeight: 0 } : {}}
    >
      {/* Toolbar */}
      <div className={`flex justify-end items-center gap-2 px-3 py-2 border-b ${
        darkMode ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'
      }`}>
        <span className={`text-xs font-semibold mr-auto ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          Mermaid Diagram
        </span>
        <button
          onClick={handleDownload}
          title="Download SVG"
          className={`p-1.5 rounded-md transition-colors ${
            darkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
          }`}
        >
          <Download size={14} />
        </button>
        <button
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Keluar Layar Penuh' : 'Layar Penuh'}
          className={`p-1.5 rounded-md transition-colors ${
            darkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
          }`}
        >
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Render Area */}
      <div 
        className={`flex-1 flex items-center justify-center overflow-auto p-4 ${
          darkMode ? 'text-gray-200' : 'text-gray-800'
        }`}
        style={isFullscreen ? { minHeight: 0 } : { minHeight: '200px' }}
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
  );

  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-[100] flex flex-col bg-black/80 backdrop-blur-sm p-4 md:p-8">
        <div className="w-full h-full max-w-6xl mx-auto flex flex-col shadow-2xl rounded-2xl overflow-hidden">
          {viewerContent}
        </div>
      </div>
    );
  }

  return viewerContent;
};

export default MermaidViewer;
