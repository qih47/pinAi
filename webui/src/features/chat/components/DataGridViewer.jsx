import React, { useMemo, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { translations } from '../../../utils/translations';
import { parsePartialJSON } from '../../../utils/jsonHelper';
import ViewerHeader from './ViewerHeader';
import { TableProperties } from 'lucide-react';

export default function DataGridViewer({ chartCode, darkMode, isStreaming, language = 'id' }) {
  const tGlobal = translations[language] || translations.id;
  const [searchQuery, setSearchQuery] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [isExpanded, setIsExpanded] = useState(false);
  const exportRef = useRef(null);

  // 2. Resilient JSON Parsing & Normalization (Mendukung Full & Streaming Partial JSON)
  const parsedData = useMemo(() => {
    if (!chartCode || chartCode.trim() === '') return null;
    try {
      const clean = chartCode.trim();
      let rawObj = null;

      // Coba direct parse dulu
      try {
        rawObj = JSON.parse(clean);
      } catch (_) {
        rawObj = parsePartialJSON(clean);
      }

      if (!rawObj || typeof rawObj !== 'object') {
        return { error: 'Invalid JSON format for datagrid.' };
      }

      // Normalisasi columns: dukung array string ["A", "B"] atau array object [{ key: "a", label: "A" }]
      let normalizedColumns = [];
      if (Array.isArray(rawObj.columns)) {
        normalizedColumns = rawObj.columns.map((col, idx) => {
          if (typeof col === 'string') {
            return { key: col, label: col };
          }
          if (col && typeof col === 'object') {
            const key = col.key || col.name || col.id || col.field || `col_${idx}`;
            const label = col.label || col.title || col.header || col.name || key;
            return { key, label };
          }
          return { key: `col_${idx}`, label: `Kolom ${idx + 1}` };
        });
      }

      // Normalisasi rows: dukung array object atau array of array
      let normalizedRows = [];
      if (Array.isArray(rawObj.rows)) {
        normalizedRows = rawObj.rows.map((row, rIdx) => {
          if (Array.isArray(row)) {
            // Row berbentuk array: ["MoE", "Dense"] -> map ke keys columns
            const rowObj = {};
            row.forEach((val, cIdx) => {
              const colKey = normalizedColumns[cIdx]?.key || `col_${cIdx}`;
              rowObj[colKey] = val;
            });
            return rowObj;
          }
          if (row && typeof row === 'object') {
            return row;
          }
          return { value: row };
        });
      }

      // Jika columns belum ada tapi rows berbentuk array of objects, buat columns otomatis dari keys row pertama
      if (normalizedColumns.length === 0 && normalizedRows.length > 0 && typeof normalizedRows[0] === 'object') {
        normalizedColumns = Object.keys(normalizedRows[0]).map(k => ({ key: k, label: k }));
      }

      return {
        ...rawObj,
        title: rawObj.title || rawObj.caption || rawObj.name || 'Data Table',
        columns: normalizedColumns,
        rows: normalizedRows
      };
    } catch (e) {
      return { error: 'Invalid JSON format for datagrid.' };
    }
  }, [chartCode]);

  // 4. Data Processing (Search & Sort)
  const filteredAndSortedRows = useMemo(() => {
    if (!parsedData || parsedData.error || !Array.isArray(parsedData.rows)) return [];
    
    let result = [...parsedData.rows];

    // Filter by search
    if (searchQuery.trim() !== '') {
      const lowerQuery = searchQuery.toLowerCase();
      result = result.filter(row => 
        row && typeof row === 'object' && Object.values(row).some(val => 
          String(val).toLowerCase().includes(lowerQuery)
        )
      );
    }

    // Sort
    if (sortConfig.key) {
      result.sort((a, b) => {
        const aVal = a?.[sortConfig.key];
        const bVal = b?.[sortConfig.key];
        
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return result;
  }, [parsedData, searchQuery, sortConfig]);

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const hasValidStructure = Boolean(
    parsedData &&
    !parsedData.error &&
    Array.isArray(parsedData.columns) &&
    parsedData.columns.length > 0 &&
    Array.isArray(parsedData.rows)
  );

  // 1. Loading State (Hanya tampil saat streaming DAN struktur kolom/baris belum terbentuk)
  if (isStreaming && !hasValidStructure) {
    return (
      <div className={`w-full py-8 my-3 flex items-center justify-center rounded-xl border border-dashed ${darkMode ? 'border-gray-700 bg-gray-800/30 text-gray-400' : 'border-gray-300 bg-gray-50 text-gray-500'}`}>
        <div className="flex items-center gap-3">
          <svg className="animate-spin h-5 w-5 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-sm font-medium">Menyusun Data Tabel...</span>
        </div>
      </div>
    );
  }

  // 3. Error Handling (Hanya jika streaming selesai dan data benar-benar korup)
  if (!hasValidStructure) {
    return (
      <div className={`w-full p-4 text-sm rounded-lg border ${darkMode ? 'bg-red-900/10 border-red-900/50 text-red-400' : 'bg-red-50 border-red-200 text-red-600'}`}>
        <div className="flex items-center gap-2 font-semibold mb-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Gagal Membaca Format Tabel Data
        </div>
      </div>
    );
  }

  const content = (
    <div className={
      isExpanded 
        ? `fixed inset-0 z-[9999] p-4 md:p-10 flex flex-col ${darkMode ? 'bg-[#121212]/95 backdrop-blur-sm' : 'bg-gray-100/95 backdrop-blur-sm'}`
        : `my-4 w-full rounded-xl border shadow-sm flex flex-col ${darkMode ? 'bg-[#222225] border-gray-700/60' : 'bg-white border-gray-200'}`
    }>
      <ViewerHeader 
        title={parsedData.title || "Data Table"} 
        icon={<TableProperties size={15} />} 
        onExpand={() => setIsExpanded(!isExpanded)} 
        isExpanded={isExpanded} 
        exportTargetRef={exportRef} 
        darkMode={darkMode}
        isTable={true}
        tableData={parsedData}
      />

      <div 
        ref={exportRef} 
        className={`flex-1 w-full flex flex-col overflow-hidden ${darkMode ? 'bg-[#222225]' : 'bg-white'} ${isExpanded ? 'rounded-b-xl shadow-2xl border-x border-b ' + (darkMode ? 'border-gray-800' : 'border-gray-200') : 'rounded-b-xl'}`}
      >
        {/* Search Toolbar di dalam container tabel */}
        <div className={`p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${darkMode ? 'border-gray-700/60' : 'border-gray-200'} ${isExpanded && parsedData.title ? 'border-b' : ''}`}>
          {isExpanded && parsedData.title ? (
            <h3 className={`text-lg font-bold m-0 ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>
              {parsedData.title}
            </h3>
          ) : <div></div>}
          
          <div className="relative">
            <svg className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input 
              type="text" 
              placeholder="Cari data..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`w-full sm:w-64 pl-9 pr-3 py-1.5 text-sm rounded-lg border outline-none transition-colors ${
                darkMode 
                  ? 'bg-gray-800 border-gray-700 text-gray-200 focus:border-blue-500 placeholder-gray-500' 
                  : 'bg-white border-gray-300 text-gray-700 focus:border-blue-500 placeholder-gray-400'
              }`}
            />
          </div>
        </div>

      {/* Table Container */}
      <div className="w-full overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className={`text-xs uppercase ${darkMode ? 'bg-gray-800/50 text-gray-400 border-b border-gray-700' : 'bg-gray-50 text-gray-500 border-b border-gray-200'}`}>
            <tr>
              {parsedData.columns.map((col, idx) => (
                <th 
                  key={idx} 
                  scope="col" 
                  className="px-4 py-3 cursor-pointer hover:bg-black/5 dark:hover:bg-white/5 transition-colors group"
                  onClick={() => handleSort(col.key)}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    <span className={`w-3 h-3 flex items-center justify-center ${sortConfig.key === col.key ? 'opacity-100' : 'opacity-0 group-hover:opacity-50 transition-opacity'}`}>
                      {sortConfig.key === col.key && sortConfig.direction === 'desc' ? (
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                      ) : (
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" /></svg>
                      )}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedRows.length > 0 ? (
              filteredAndSortedRows.map((row, rowIndex) => (
                <tr 
                  key={rowIndex} 
                  className={`border-b last:border-b-0 transition-colors ${
                    darkMode 
                      ? 'border-gray-800 hover:bg-gray-800/40 text-gray-300' 
                      : 'border-gray-100 hover:bg-gray-50 text-gray-600'
                  }`}
                >
                  {parsedData.columns.map((col, colIndex) => (
                    <td key={colIndex} className="px-4 py-3 whitespace-nowrap">
                      {row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={parsedData.columns.length} className={`px-4 py-8 text-center italic ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                  Data tidak ditemukan
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {/* Footer / Summary */}
      <div className={`p-3 text-xs flex justify-between items-center ${darkMode ? 'bg-gray-800/30 text-gray-500 border-t border-gray-800' : 'bg-gray-50 text-gray-400 border-t border-gray-100'}`}>
        <span>Menampilkan {filteredAndSortedRows.length} dari {parsedData.rows.length} data</span>
      </div>
      </div>
    </div>
  );

  return isExpanded ? createPortal(content, document.body) : content;
}
