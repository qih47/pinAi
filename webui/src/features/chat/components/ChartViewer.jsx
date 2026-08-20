import React, { useMemo, useState, useRef } from 'react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';
import { createPortal } from 'react-dom';
import { translations } from '../../../utils/translations';

const DEFAULT_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

import ViewerHeader from './ViewerHeader';
import { BarChart2 } from 'lucide-react';

export default function ChartViewer({ chartCode, darkMode, isStreaming, language = 'id' }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const chartRef = useRef(null);
  const tGlobal = translations[language] || translations.id;

  // 1. Parsing the JSON Payload safely
  const parsedData = useMemo(() => {
    try {
      if (!chartCode || chartCode.trim() === '') return null;
      return JSON.parse(chartCode);
    } catch (e) {
      return { error: 'Invalid JSON format for chart data.' };
    }
  }, [chartCode]);

  // If streaming and parsing fails, show a loading placeholder
  if (isStreaming && (parsedData?.error || !parsedData)) {
    return (
      <div className={`w-full h-72 flex items-center justify-center rounded-xl border border-dashed ${darkMode ? 'border-gray-700 bg-gray-800/30 text-gray-400' : 'border-gray-300 bg-gray-50 text-gray-500'}`}>
        <div className="flex flex-col items-center gap-2">
          <svg className="animate-spin h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-sm font-medium">Membuat Grafik...</span>
        </div>
      </div>
    );
  }

  // Handle parsing error when streaming is done
  if (parsedData?.error || !parsedData?.type || !parsedData?.data) {
    return (
      <div className={`w-full p-4 text-sm rounded-lg border ${darkMode ? 'bg-red-900/10 border-red-900/50 text-red-400' : 'bg-red-50 border-red-200 text-red-600'}`}>
        <div className="flex items-center gap-2 font-semibold mb-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Gagal Membaca Data Grafik
        </div>
        <pre className="text-xs mt-2 overflow-x-auto p-2 bg-black/10 rounded">{chartCode}</pre>
      </div>
    );
  }

  const { type, title, data, xAxisKey = 'name', dataKeys = ['value'], colors = DEFAULT_COLORS } = parsedData;

  const textColor = darkMode ? '#e2e8f0' : '#475569';
  const gridColor = darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)';
  const tooltipBg = darkMode ? '#1e293b' : '#ffffff';
  const tooltipBorder = darkMode ? '#334155' : '#e2e8f0';

  const renderChart = () => {
    switch (type.toLowerCase()) {
      case 'bar':
        return (
          <BarChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
            <XAxis dataKey={xAxisKey} stroke={textColor} fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke={textColor} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ backgroundColor: tooltipBg, borderColor: tooltipBorder, borderRadius: '8px', color: textColor, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} />
            <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '13px', color: textColor }} />
            {dataKeys.map((key, idx) => (
              <Bar key={key} dataKey={key} fill={colors[idx % colors.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        );
      case 'line':
        return (
          <LineChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
            <XAxis dataKey={xAxisKey} stroke={textColor} fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke={textColor} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ backgroundColor: tooltipBg, borderColor: tooltipBorder, borderRadius: '8px', color: textColor }} />
            <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '13px', color: textColor }} />
            {dataKeys.map((key, idx) => (
              <Line key={key} type="monotone" dataKey={key} stroke={colors[idx % colors.length]} strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6 }} />
            ))}
          </LineChart>
        );
      case 'area':
        return (
          <AreaChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
            <XAxis dataKey={xAxisKey} stroke={textColor} fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke={textColor} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ backgroundColor: tooltipBg, borderColor: tooltipBorder, borderRadius: '8px', color: textColor }} />
            <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '13px', color: textColor }} />
            {dataKeys.map((key, idx) => (
              <Area key={key} type="monotone" dataKey={key} stroke={colors[idx % colors.length]} fill={colors[idx % colors.length]} fillOpacity={0.3} strokeWidth={2} />
            ))}
          </AreaChart>
        );
      case 'pie':
        return (
          <PieChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
            <Tooltip contentStyle={{ backgroundColor: tooltipBg, borderColor: tooltipBorder, borderRadius: '8px', color: textColor }} />
            <Legend wrapperStyle={{ paddingTop: '20px', fontSize: '13px', color: textColor }} />
            {dataKeys.map((key, idx) => (
              <Pie
                key={key}
                data={data}
                nameKey={xAxisKey}
                dataKey={key}
                cx="50%"
                cy="50%"
                outerRadius={isExpanded ? 180 : 100}
                innerRadius={0}
                paddingAngle={2}
                label
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                ))}
              </Pie>
            ))}
          </PieChart>
        );
      default:
        return (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            Tipe grafik "{type}" tidak didukung.
          </div>
        );
    }
  };

  const content = (
    <div className={
      isExpanded 
        ? `fixed inset-0 z-[9999] p-4 md:p-10 flex flex-col ${darkMode ? 'bg-[#121212]/95 backdrop-blur-sm' : 'bg-gray-100/95 backdrop-blur-sm'}`
        : `my-4 w-full rounded-xl border shadow-sm flex flex-col ${darkMode ? 'bg-[#222225] border-gray-700/60' : 'bg-white border-gray-200'}`
    }>
      <ViewerHeader 
        title={title || "Chart"} 
        icon={<BarChart2 size={15} />} 
        onExpand={() => setIsExpanded(!isExpanded)} 
        isExpanded={isExpanded} 
        exportTargetRef={chartRef} 
        darkMode={darkMode} 
      />
      
      <div 
        ref={chartRef} 
        className={`p-5 flex-1 w-full h-full flex flex-col items-center justify-center ${darkMode ? 'bg-[#222225]' : 'bg-white'} ${isExpanded ? 'rounded-b-xl shadow-2xl border-x border-b ' + (darkMode ? 'border-gray-800' : 'border-gray-200') : 'rounded-b-xl'}`}
      >
        {title && isExpanded && (
          <h3 className={`text-lg font-bold mb-6 text-center ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>
            {title}
          </h3>
        )}
        <div style={{ width: '100%', height: isExpanded ? '100%' : 320, minHeight: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            {renderChart()}
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );

  return isExpanded ? createPortal(content, document.body) : content;
}
