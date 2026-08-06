import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import mermaid from 'mermaid';
import { toPng } from 'html-to-image';
import { Maximize2, Minimize2, Download } from 'lucide-react';
import { translations } from '../../../utils/translations';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://192.168.11.80:5000';

import ViewerHeader from './ViewerHeader';
import { GitMerge } from 'lucide-react';

const MermaidViewer = ({ chartCode, darkMode, isStreaming, language = 'id' }) => {
  const tGlobal = translations[language] || translations.id;
  const containerRef = useRef(null);
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const printRef = useRef(null);

  const activeDarkMode = darkMode;

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
        let cleanCode = chartCode;
        if (cleanCode) {
          cleanCode = cleanCode
            .replace(/\brect_[a-zA-Z0-9_-]+\b/g, 'rect rgb(70, 130, 180)')
            .replace(/^\s*rect\s+([a-zA-Z]+)\s*$/gm, 'rect rgb(70, 130, 180)')
            .replace(/^\s*rect\s*$/gm, 'rect rgb(70, 130, 180)');
        }

        try {
          await mermaid.parse(cleanCode);
        } catch (parseError) {
          if (isStreaming) {
            console.warn('Mermaid syntax is not complete yet (streaming)');
            return;
          }
          throw parseError;
        }

        setError(null);
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, cleanCode);
        setSvgContent(svg);
      } catch (err) {
        if (isStreaming) {
          console.warn('Mermaid partial render error (ignored during stream)');
        } else {
          setError(err.message || tGlobal.render.mermaidRenderFail);
        }
      }
    };

    if (chartCode) {
      const timeoutId = setTimeout(() => {
        renderChart();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [chartCode, activeDarkMode]);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const viewerContent = (
    <div
      ref={containerRef}
      className={
        isFullscreen 
          ? `fixed inset-0 z-[9999] p-4 md:p-10 flex flex-col ${activeDarkMode ? 'bg-[#121212]/95 backdrop-blur-sm' : 'bg-gray-100/95 backdrop-blur-sm'}`
          : `my-4 w-full rounded-xl border flex flex-col shadow-sm transition-all duration-300 ${activeDarkMode ? 'bg-[#222225] border-gray-700/60' : 'bg-white border-gray-200'}`
      }
    >
      <ViewerHeader 
        title="Cakra Diagram" 
        icon={<GitMerge size={15} />} 
        onExpand={toggleFullscreen} 
        isExpanded={isFullscreen} 
        exportTargetRef={printRef} 
        darkMode={activeDarkMode} 
      />

      {/* Scrollable Wrapper */}
      <div
        className={`flex-1 flex overflow-auto ${activeDarkMode ? 'text-gray-200' : 'text-gray-800'
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
            <div className="animate-pulse text-sm">{tGlobal.render.renderingDiagram}</div>
          )}
        </div>
      </div>
    </div>
  );

  if (isFullscreen) {
    return (
      <>
        <div className="w-full my-4 p-8 border border-dashed rounded-xl text-center text-sm font-medium text-gray-500">
          {tGlobal.render.fullscreenModeActive}
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
