import React, { useState, useRef, useEffect } from 'react';
import { toPng, toSvg } from 'html-to-image';
import { ChevronDown, Download, Maximize2, Minimize2, Image, FileCode2, FileSpreadsheet, CloudUpload } from 'lucide-react';
import useToast from "../../../hooks/useToast";
import { useChatStore } from "../../../stores/chatStore";
import { translations } from "../../../utils/translations";

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://192.168.11.80:5000';

export default function ViewerHeader({
  title,
  icon,
  onExpand,
  isExpanded,
  exportTargetRef,
  darkMode,
  isTable = false,
  tableData = null
}) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const dropdownRef = useRef(null);
  const toast = useToast();
  const language = useChatStore((state) => state.language || 'id');
  const tToast = translations[language]?.toast || translations.id.toast;

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const generateCSVDataUrl = () => {
    if (!tableData || !tableData.columns || !tableData.rows) return null;
    const header = tableData.columns.map(c => `"${c.label}"`).join(',');
    const rows = tableData.rows.map(row =>
      tableData.columns.map(c => `"${String(row[c.key] || '').replace(/"/g, '""')}"`).join(',')
    );
    const csvContent = [header, ...rows].join('\n');
    return `data:text/csv;charset=utf-8,${encodeURIComponent(csvContent)}`;
  };

  const getMediaDataUrl = async (format) => {
    if (format === 'csv') {
      return generateCSVDataUrl();
    }
    if (!exportTargetRef || !exportTargetRef.current) return null;

    const bgColor = darkMode ? '#1e1e1e' : '#ffffff';
    if (format === 'png') {
      return await toPng(exportTargetRef.current, { backgroundColor: bgColor });
    } else if (format === 'svg') {
      return await toSvg(exportTargetRef.current, { backgroundColor: bgColor });
    }
    return null;
  };

  const handleExport = async (format) => {
    setIsExporting(true);
    setShowDropdown(false);

    try {
      const dataUrl = await getMediaDataUrl(format);
      if (!dataUrl) throw new Error("Data kosong atau target tidak ditemukan");

      const link = document.createElement('a');
      link.download = `${title.replace(/\s+/g, '_').toLowerCase()}_${new Date().getTime()}.${format}`;
      link.href = dataUrl;
      link.click();

      toast.success(tToast.saveChartSuccess || `Berhasil menyimpan grafik sebagai ${format.toUpperCase()}`);
    } catch (err) {
      console.error("Gagal export", err);
      toast.error(tToast.saveChartFail || `Gagal menyimpan ${format.toUpperCase()}`);
    } finally {
      setIsExporting(false);
    }
  };

  const handleUploadPincloud = async (format) => {
    setIsExporting(true);
    setShowDropdown(false);

    try {
      const dataUrl = await getMediaDataUrl(format);
      if (!dataUrl) throw new Error("Data kosong atau target tidak ditemukan");

      const filename = `${title.replace(/\s+/g, '_').toLowerCase()}_${new Date().getTime()}.${format}`;

      const response = await fetch(`${API_BASE}/api/nextcloud/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: localStorage.getItem('cakra_token') || '',
          path: '/Cakra_AI_Exports',
          filename: filename,
          content: dataUrl
        })
      });

      if (!response.ok) {
        throw new Error('Gagal upload ke Pincloud');
      }

      toast.success(tToast.uploadCloudSuccess || `Berhasil upload ${format.toUpperCase()} ke Pincloud (Cakra_AI_Exports)`);
    } catch (err) {
      console.error("Gagal upload pincloud", err);
      toast.error(tToast.uploadCloudFail || `Gagal upload ke Pincloud`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className={`relative z-50 flex items-center justify-between px-4 py-3 border-b ${darkMode ? 'bg-[#252526] border-gray-800/60' : 'bg-gray-50/80 border-gray-200'} backdrop-blur-sm rounded-t-xl transition-colors duration-200`}>
      {/* KIRI: Ikon & Judul */}
      <div className="flex items-center gap-3">
        {icon && (
          <div className={`p-1.5 rounded-md ${darkMode ? 'bg-indigo-500/10 text-indigo-400' : 'bg-indigo-100 text-indigo-600'}`}>
            {icon}
          </div>
        )}
        <h3 className={`font-semibold text-[13px] tracking-wide ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
          {title}
        </h3>
      </div>

      {/* KANAN: Aksi */}
      <div className="flex items-center gap-2">
        {/* Dropdown Save */}
        <div className="relative" ref={dropdownRef}>
          <div className="flex items-center">
            {/* Main Button */}
            <button
              onClick={() => handleExport(isTable ? 'csv' : 'png')} // Default action
              disabled={isExporting}
              className={`flex items-center gap-1.5 px-2 py-1.5 rounded-l-md text-xs font-medium border-y border-l transition-colors ${darkMode
                ? 'bg-[#3b3b3b] hover:bg-[#4a4a4a] border-gray-600/50 text-gray-200'
                : 'bg-white hover:bg-gray-50 border-gray-300 text-gray-700 shadow-sm'
                } ${isExporting ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {isExporting ? (
                <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <Download size={14} />
              )}
              <span></span>
            </button>

            {/* Caret Button */}
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              disabled={isExporting}
              className={`flex items-center justify-center px-1.5 py-1.5 rounded-r-md border transition-colors ${darkMode
                ? 'bg-[#3b3b3b] hover:bg-[#4a4a4a] border-gray-600/50 text-gray-200'
                : 'bg-gray-50 hover:bg-gray-100 border-gray-300 text-gray-700 shadow-sm'
                }`}
            >
              <ChevronDown size={14} />
            </button>

            {/* Tombol Expand */}
            {onExpand && (
              <button
                onClick={onExpand}
                className={`ml-2 p-1.5 rounded-md transition-colors ${darkMode ? 'hover:bg-gray-700 text-gray-400 hover:text-gray-200' : 'hover:bg-gray-200 text-gray-500 hover:text-gray-800'}`}
                title={isExpanded ? "Minimize" : "Expand Fullscreen"}
              >
                {isExpanded ? <Minimize2 size={16} strokeWidth={2.5} /> : <Maximize2 size={16} strokeWidth={2.5} />}
              </button>
            )}
          </div>



          {/* Dropdown Menu */}
          {showDropdown && (
            <div className={`absolute right-0 mt-1 w-52 rounded-lg shadow-xl border z-[100] animate-in fade-in zoom-in-95 duration-100 ${darkMode ? 'bg-[#2d2d2d] border-gray-700' : 'bg-white border-gray-200'
              }`}>
              <div className="py-1">
                {isTable ? (
                  <>
                    <button
                      onClick={() => handleExport('csv')}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors ${darkMode ? 'text-gray-300 hover:bg-indigo-500/20 hover:text-indigo-400' : 'text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'
                        }`}
                    >
                      <FileSpreadsheet size={14} />
                      Download Excel (CSV)
                    </button>
                    <button
                      onClick={() => handleUploadPincloud('csv')}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors ${darkMode ? 'text-gray-300 hover:bg-indigo-500/20 hover:text-indigo-400' : 'text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'
                        }`}
                    >
                      <CloudUpload size={14} />
                      Upload Excel to Pincloud
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleExport('png')}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors ${darkMode ? 'text-gray-300 hover:bg-indigo-500/20 hover:text-indigo-400' : 'text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'
                        }`}
                    >
                      <Image size={14} />
                      Download as PNG
                    </button>
                    <button
                      onClick={() => handleExport('svg')}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors ${darkMode ? 'text-gray-300 hover:bg-indigo-500/20 hover:text-indigo-400' : 'text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'
                        }`}
                    >
                      <FileCode2 size={14} />
                      Download as SVG
                    </button>
                    <div className={`my-1 border-b ${darkMode ? 'border-gray-700' : 'border-gray-200'}`}></div>
                    <button
                      onClick={() => handleUploadPincloud('png')}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors ${darkMode ? 'text-gray-300 hover:bg-indigo-500/20 hover:text-indigo-400' : 'text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'
                        }`}
                    >
                      <CloudUpload size={14} />
                      Upload PNG to Pincloud
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
