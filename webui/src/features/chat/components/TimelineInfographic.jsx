import { getApiBase } from '@/services/endpoints';
import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { toPng, toSvg } from 'html-to-image';
import { 
  Target, ClipboardList, Gift, Calendar, CheckCircle, Trophy, 
  Maximize2, Minimize2, Download, ChevronRight, CheckCircle2,
  Sun, CloudRain, CloudSun, Cloud, Wind, Droplets, ThermometerSun,
  Layers, ArrowRight, TrendingUp, TrendingDown, Sparkles, Compass
} from 'lucide-react';

import { parsePartialJSON } from '../../../utils/jsonHelper';
import { translations } from '../../../utils/translations';

const API_BASE = getApiBase();

// ── Weather Layout Component ────────────────────────────────────────────────
const WeatherInfographicLayout = ({ data, activeDarkMode }) => {
  const days = data.days || data.forecast || data.items || [];
  
  const getWeatherIcon = (condition = '') => {
    const c = condition.toLowerCase();
    if (c.includes('hujan lebat') || c.includes('petir') || c.includes('badai')) return <CloudRain size={28} className="text-blue-400 animate-pulse" />;
    if (c.includes('hujan')) return <CloudRain size={28} className="text-blue-400" />;
    if (c.includes('berawan') || c.includes('mendung')) return <CloudSun size={28} className="text-amber-400" />;
    if (c.includes('angin') || c.includes('kabut')) return <Wind size={28} className="text-cyan-400" />;
    return <Sun size={28} className="text-yellow-400" />;
  };

  return (
    <div className="flex flex-col">
      {/* Weather Header */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider mb-2 bg-gradient-to-r from-amber-500/20 to-blue-500/20 text-amber-300 border border-amber-500/30">
          <ThermometerSun size={14} />
          {data.location || data.subtitle || 'Prakiraan Cuaca'}
        </div>
        <h2 className="text-xl md:text-2xl font-black uppercase tracking-tight" style={{ color: activeDarkMode ? '#E3B432' : '#101878' }}>
          {data.title || 'PRAKIRAAN CUACA'}
        </h2>
        <div className="h-0.5 w-24 bg-gradient-to-r from-amber-400 to-blue-500 mx-auto mt-2 rounded-full"></div>
      </div>

      {/* Weather Cards Grid */}
      <div className="flex flex-row flex-wrap md:flex-nowrap gap-3 mb-5 overflow-x-visible">
        {days.map((day, idx) => (
          <div key={idx} className="flex flex-col flex-1 min-w-[180px] group">
            {/* Day Header Badge */}
            <div className={`p-2.5 rounded-t-xl text-center border border-b-0 ${activeDarkMode ? 'bg-gray-800/80 border-gray-700 text-gray-200' : 'bg-gray-100 border-gray-200 text-gray-800'}`}>
              <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                {day.day || day.date || `Hari ${idx + 1}`}
              </div>
              <div className="text-[10px] text-gray-400 truncate">
                {day.date_detail || day.period || ''}
              </div>
            </div>

            {/* Weather Card Body */}
            <div className={`p-4 rounded-b-xl border flex flex-col items-center justify-between gap-3 shadow-sm transition-all duration-300 group-hover:shadow-lg group-hover:-translate-y-0.5 ${
              activeDarkMode ? 'bg-[#222225]/60 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              {/* Weather Icon & Condition */}
              <div className="flex flex-col items-center gap-1.5 mt-1">
                <div className="p-3 rounded-full bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700/50 shadow-inner">
                  {getWeatherIcon(day.condition || day.status || day.weather)}
                </div>
                <span className="text-xs font-bold text-center">
                  {day.condition || day.status || day.weather || 'Cerah'}
                </span>
              </div>

              {/* Temperature Pill */}
              <div className="w-full flex items-center justify-center gap-2 py-1.5 px-3 rounded-lg bg-gray-900/40 border border-gray-800">
                <span className="text-sm font-black text-amber-400">{day.temp_max || day.temp || '32°C'}</span>
                {day.temp_min && (
                  <>
                    <span className="text-gray-500">/</span>
                    <span className="text-xs font-semibold text-blue-400">{day.temp_min}</span>
                  </>
                )}
              </div>

              {/* Metrics (Humidity / Wind / UV) */}
              <div className="w-full flex flex-col gap-1.5 text-[10.5px] text-gray-400 border-t border-dashed border-gray-700/50 pt-2.5">
                {day.humidity && (
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1"><Droplets size={12} className="text-blue-400" /> Kelembapan</span>
                    <span className="font-semibold text-gray-300">{day.humidity}</span>
                  </div>
                )}
                {day.wind && (
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1"><Wind size={12} className="text-cyan-400" /> Angin</span>
                    <span className="font-semibold text-gray-300">{day.wind}</span>
                  </div>
                )}
              </div>

              {/* Note / Recommendation */}
              {(day.note || day.advice || day.activities) && (
                <div className="w-full p-2 rounded-md bg-amber-500/10 border border-amber-500/20 text-[10px] text-amber-300 leading-snug">
                  {day.note || day.advice || (Array.isArray(day.activities) ? day.activities[0] : day.activities)}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Summary Footer */}
      {(data.note || data.summary || data.recommendation) && (
        <div className={`flex items-center gap-3 p-3.5 rounded-xl border mt-3 ${activeDarkMode ? 'bg-[#222225] border-gray-700' : 'bg-amber-50/50 border-amber-100'}`}>
          <Sparkles size={20} className="text-[#E3B432] shrink-0" />
          <div className="text-[11.5px] leading-snug">
            <span className="font-bold text-amber-400 mr-1.5">Saran Aktivitas:</span>
            {data.note || data.summary || data.recommendation}
          </div>
        </div>
      )}
    </div>
  );
};

// ── Stepper / SOP Flow Layout Component ─────────────────────────────────────
const StepperInfographicLayout = ({ data, activeDarkMode }) => {
  const steps = data.steps || data.stages || data.items || [];

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider mb-2 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
          <Layers size={14} />
          {data.subtitle || 'Alur Proses & Prosedur'}
        </div>
        <h2 className="text-xl md:text-2xl font-black uppercase tracking-tight" style={{ color: activeDarkMode ? '#E3B432' : '#101878' }}>
          {data.title || 'PROSEDUR & ALUR KERJA'}
        </h2>
        <div className="h-0.5 w-24 bg-gradient-to-r from-indigo-500 to-emerald-400 mx-auto mt-2 rounded-full"></div>
      </div>

      {/* Stepper Steps Grid */}
      <div className="flex flex-row flex-wrap md:flex-nowrap gap-3 mb-5">
        {steps.map((step, idx) => (
          <div key={idx} className="flex flex-col flex-1 min-w-[200px] group">
            {/* Step Number Top Banner */}
            <div className="flex items-center gap-2 mb-3 relative">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-600 to-blue-500 text-white font-bold text-xs flex items-center justify-center shadow-md z-10">
                {idx + 1}
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">
                {step.step || `Langkah ${idx + 1}`}
              </span>
              {idx < (steps.length - 1) && (
                <div className="absolute top-4 left-8 right-0 h-[2px] bg-gradient-to-r from-indigo-500 to-transparent -z-0"></div>
              )}
            </div>

            {/* Step Card */}
            <div className={`p-4 rounded-xl border flex flex-col justify-between gap-2 shadow-sm transition-all duration-300 group-hover:shadow-lg group-hover:-translate-y-0.5 ${
              activeDarkMode ? 'bg-[#222225]/60 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <div className="text-xs font-bold text-gray-200">{step.title}</div>
              <div className="text-[11px] text-gray-400 leading-snug">{step.desc || step.description}</div>
              {step.pic && (
                <div className="mt-2 text-[10px] font-medium text-gray-500 flex items-center gap-1">
                  <span>PIC:</span> <span className="text-gray-400 font-semibold">{step.pic}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── KPI / Metrics Layout Component ──────────────────────────────────────────
const KpiInfographicLayout = ({ data, activeDarkMode }) => {
  const metrics = data.metrics || data.stats || data.items || [];

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-xl md:text-2xl font-black uppercase tracking-tight" style={{ color: activeDarkMode ? '#E3B432' : '#101878' }}>
          {data.title || 'RINGKASAN METRIK & KPI'}
        </h2>
        <div className="h-0.5 w-24 bg-gradient-to-r from-[#101878] to-[#E3B432] mx-auto mt-2 rounded-full"></div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        {metrics.map((m, idx) => (
          <div key={idx} className={`p-4 rounded-xl border flex flex-col gap-1 shadow-sm ${
            activeDarkMode ? 'bg-[#222225]/60 border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-gray-400">{m.label || m.name}</span>
            <span className="text-2xl font-black text-amber-400 my-1">{m.value}</span>
            {m.trend && (
              <div className="flex items-center gap-1 text-[10.5px] font-semibold text-emerald-400">
                <TrendingUp size={13} />
                <span>{m.trend}</span>
              </div>
            )}
            {m.desc && <span className="text-[10px] text-gray-500 mt-1">{m.desc}</span>}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Original Project Roadmap / Timeline Layout Component ───────────────────
const TimelineRoadmapLayout = ({ data, activeDarkMode }) => {
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

  const months = data.months || data.phases || [];

  return (
    <>
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-xl md:text-2xl font-black uppercase tracking-tight" style={{ color: activeDarkMode ? '#E3B432' : '#101878' }}>
          {data.title || 'PROJECT TIMELINE'}
        </h2>
        <div className="h-0.5 w-24 bg-gradient-to-r from-[#101878] to-[#E3B432] mx-auto mt-2 rounded-full"></div>
      </div>

      {/* Timeline Grid */}
      <div className="flex flex-row gap-3 mb-5">
        {/* Legend Sidebar */}
        <div className="flex flex-col gap-3 w-40 shrink-0 pt-[74px]">
          <div className={`flex flex-col items-center justify-center p-3 rounded-xl shadow-sm ${activeDarkMode ? 'bg-gray-700/40' : 'bg-gray-50'} border ${activeDarkMode ? 'border-gray-600' : 'border-gray-200'} min-h-[64px]`}>
            <Target size={20} className="mb-1 text-[#101878] dark:text-[#E3B432]" />
            <span className="text-[11px] font-bold text-center uppercase tracking-wider">Tujuan Utama</span>
          </div>
          <div className={`flex flex-col items-center justify-center p-3 rounded-xl shadow-sm ${activeDarkMode ? 'bg-gray-700/40' : 'bg-gray-50'} border ${activeDarkMode ? 'border-gray-600' : 'border-gray-200'} h-36`}>
            <ClipboardList size={20} className="mb-1 text-[#101878] dark:text-[#E3B432]" />
            <span className="text-[11px] font-bold text-center uppercase tracking-wider">Kegiatan Utama</span>
          </div>
          <div className={`flex flex-col items-center justify-center p-3 rounded-xl shadow-sm ${activeDarkMode ? 'bg-gray-700/40' : 'bg-gray-50'} border ${activeDarkMode ? 'border-gray-600' : 'border-gray-200'} h-28`}>
            <Gift size={20} className="mb-1 text-[#101878] dark:text-[#E3B432]" />
            <span className="text-[11px] font-bold text-center uppercase tracking-wider">Output / Deliverable</span>
          </div>
        </div>

        {/* Month Columns */}
        <div className="flex flex-row flex-1 gap-3 overflow-x-visible">
          {months.map((month, index) => (
            <div key={index} className="flex flex-col flex-1 min-w-[220px] group">
              {/* Month Badge */}
              <div className="flex flex-col items-center mb-3 relative">
                <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getMonthColor(index)} text-white flex items-center justify-center font-black text-base mb-2 shadow-[0_0_15px_rgba(0,0,0,0.2)] z-10 transition-transform duration-300 group-hover:scale-110`}>
                  {month.month || (index + 1)}
                </div>
                {/* Connection Line */}
                {index < (months.length - 1) && (
                  <div className="absolute top-5 left-1/2 w-[calc(100%+0.75rem)] h-[2px] bg-gradient-to-r from-gray-300 to-gray-200 dark:from-gray-600 dark:to-gray-700 -z-0"></div>
                )}
                <div className={`w-full text-center py-2 rounded-t-xl bg-gradient-to-r ${getMonthColor(index)} text-white font-bold text-[11px] uppercase tracking-wider shadow-md`}>
                  BULAN {month.month || (index + 1)}
                </div>
                <div className={`w-full text-center py-1.5 px-2 text-[10px] font-bold uppercase min-h-[40px] flex items-center justify-center ${activeDarkMode ? 'bg-gray-700/80 text-gray-200' : 'bg-gray-100 text-gray-700'}`}>
                  {month.title}
                </div>
              </div>

              {/* Card Body Container */}
              <div className={`flex flex-col rounded-b-xl border border-t-0 shadow-sm transition-all duration-300 group-hover:shadow-lg group-hover:-translate-y-0.5 ${activeDarkMode ? 'border-gray-700 bg-[#222225]/40' : 'border-gray-200 bg-white'}`}>
                {/* Main Objective */}
                <div className="p-3 text-[11.5px] text-center font-medium min-h-[64px] flex items-center justify-center border-b border-dashed border-gray-200 dark:border-gray-700">
                  {month.mainObjective}
                </div>

                {/* Activities List */}
                <div className="p-3 text-[10.5px] h-36 overflow-y-auto custom-scrollbar border-b border-dashed border-gray-200 dark:border-gray-700">
                  <ul className="space-y-2">
                    {month.activities?.map((act, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ChevronRight size={13} className="text-blue-500 mt-0.5 shrink-0" />
                        <span className="leading-snug">{act}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Outputs List */}
                <div className={`p-3 text-[10.5px] h-28 overflow-y-auto custom-scrollbar ${activeDarkMode ? 'bg-[#222225]/60' : 'bg-gray-50'} rounded-b-xl`}>
                  <ul className="space-y-2">
                    {month.outputs?.map((out, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <CheckCircle2 size={13} className="text-green-500 mt-0.5 shrink-0" />
                        <span className="leading-snug font-medium">{out}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Bottom Color Bar */}
                <div className={`h-1.5 w-full rounded-b-xl bg-gradient-to-r ${getMonthColor(index)} opacity-90 group-hover:opacity-100 transition-opacity`}></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer Summary */}
      <div className="flex flex-row flex-wrap gap-3 mt-4">
        <div className={`flex items-center gap-2.5 p-3 rounded-xl border flex-1 ${activeDarkMode ? 'bg-[#222225] border-gray-700' : 'bg-blue-50/50 border-blue-100'}`}>
          <Calendar size={20} className="text-[#101878] dark:text-[#E3B432]" />
          <div>
            <div className="text-[9px] font-bold uppercase text-gray-500">Durasi Total</div>
            <div className="text-xs font-bold">{data.duration || `${months.length} BULAN`}</div>
          </div>
        </div>

        <div className={`flex items-center gap-2.5 p-3 rounded-xl border flex-[2] ${activeDarkMode ? 'bg-[#222225] border-gray-700' : 'bg-purple-50/50 border-purple-100'}`}>
          <CheckCircle size={20} className="text-purple-600 dark:text-purple-400" />
          <div>
            <div className="text-[9px] font-bold uppercase text-gray-500">Catatan</div>
            <div className="text-[11px] leading-snug">{data.note || 'Timeline dapat menyesuaikan dengan kondisi di lapangan.'}</div>
          </div>
        </div>

        <div className={`flex items-center gap-2.5 p-3 rounded-xl border flex-[2] ${activeDarkMode ? 'bg-[#222225] border-gray-700' : 'bg-yellow-50/50 border-yellow-100'}`}>
          <Trophy size={20} className="text-[#E3B432]" />
          <div>
            <div className="text-[9px] font-bold uppercase text-gray-500">Hasil Akhir</div>
            <div className="text-[11px] leading-snug">{data.result || 'Proyek selesai tepat waktu dan siap digunakan.'}</div>
          </div>
        </div>
      </div>
    </>
  );
};

// ── Main Dynamic Infographic Container ──────────────────────────────────────
const TimelineInfographic = ({ chartCode, darkMode, isStreaming, language = 'id' }) => {
  const tGlobal = translations[language] || translations.id;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDownloadMenuOpen, setIsDownloadMenuOpen] = useState(false);
  const printRef = useRef(null);
  const outerRef = useRef(null);
  const [scale, setScale] = useState(1);
  const [scaledHeight, setScaledHeight] = useState('auto');

  const activeDarkMode = isExporting ? false : darkMode;

  useEffect(() => {
    if (!chartCode) return;

    const parsed = parsePartialJSON(chartCode);

    if (!parsed) {
      if (!isStreaming) {
        setError(tGlobal.render.timelineRenderFail);
      }
      return;
    }

    setData(parsed);
    setError(null);
  }, [chartCode, isStreaming]);

  // Auto-Scale Effect based on Container Width
  useEffect(() => {
    if (isFullscreen) {
      setScale(1);
      setScaledHeight('auto');
      return;
    }

    const updateScale = () => {
      if (outerRef.current && printRef.current) {
        const outerWidth = outerRef.current.clientWidth;
        const contentWidth = printRef.current.scrollWidth;
        const contentHeight = printRef.current.scrollHeight;
        
        if (contentWidth > outerWidth && outerWidth > 0) {
          const newScale = outerWidth / contentWidth;
          setScale(newScale);
          setScaledHeight(contentHeight * newScale);
        } else {
          setScale(1);
          setScaledHeight('auto');
        }
      }
    };

    const resizeObserver = new ResizeObserver(() => {
      window.requestAnimationFrame(updateScale);
    });

    if (outerRef.current) {
      resizeObserver.observe(outerRef.current);
    }

    setTimeout(updateScale, 50);
    return () => resizeObserver.disconnect();
  }, [data, isFullscreen]);

  const toggleFullscreen = () => setIsFullscreen(!isFullscreen);

  const executeDownload = async (format) => {
    try {
      const targetWidth = printRef.current.scrollWidth;
      const targetHeight = printRef.current.scrollHeight;

      const config = {
        quality: 1,
        pixelRatio: 2,
        backgroundColor: '#ffffff',
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
      filenameInput.value = `cakra-infographic-${new Date().getTime()}.${format}`;
      form.appendChild(filenameInput);

      const mimeInput = document.createElement('input');
      mimeInput.type = 'hidden';
      mimeInput.name = 'mime_type';
      mimeInput.value = format === 'png' ? 'image/png' : 'image/svg+xml';
      form.appendChild(mimeInput);

      document.body.appendChild(form);
      form.submit();

      setTimeout(() => {
        document.body.removeChild(form);
      }, 1000);

    } catch (err) {
      console.error('Error downloading infographic:', err);
      alert(tGlobal.render.downloadFail);
    }
  };

  const handleDownload = (format) => {
    if (!printRef.current) return;
    setIsDownloading(true);
    setIsDownloadMenuOpen(false);

    if (darkMode) {
      setIsExporting(true);
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

  if (error) {
    return (
      <div className="p-4 border border-red-500 bg-red-50 text-red-700 rounded-lg text-sm mt-4">
        <strong>Error:</strong> {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className={`p-6 my-4 border border-dashed rounded-xl flex items-center justify-center gap-3 transition-colors ${
        activeDarkMode ? 'border-gray-700 bg-gray-800/30 text-gray-300' : 'border-gray-300 bg-gray-50 text-gray-600'
      }`}>
        <Sparkles size={18} className="text-amber-400 animate-spin" />
        <span className="text-xs font-semibold tracking-wide">
          {tGlobal.render?.loadingTimeline || tGlobal.render?.preparingTimeline || "Menyiapkan visual infografis..."}
        </span>
      </div>
    );
  }

  // ── Layout Selector ───────────────────────────────────────────────────────
  const renderDynamicLayout = () => {
    const layout = (data.layout || '').toLowerCase();
    const title = (data.title || '').toLowerCase();

    // 1. Weather Layout
    if (layout === 'weather' || layout === 'weather_forecast' || data.days || data.forecast || (/cuaca|weather|suhu/i.test(title) && !data.months)) {
      return <WeatherInfographicLayout data={data} activeDarkMode={activeDarkMode} />;
    }

    // 2. Stepper / SOP Steps Layout
    if (layout === 'steps' || layout === 'stepper' || layout === 'sop' || data.steps || data.stages) {
      return <StepperInfographicLayout data={data} activeDarkMode={activeDarkMode} />;
    }

    // 3. KPI / Metrics Layout
    if (layout === 'kpi' || layout === 'metrics' || layout === 'stats' || data.metrics) {
      return <KpiInfographicLayout data={data} activeDarkMode={activeDarkMode} />;
    }

    // 4. Default: Timeline Roadmap Layout
    return <TimelineRoadmapLayout data={data} activeDarkMode={activeDarkMode} />;
  };

  const viewerContent = (
    <div className={`group rounded-xl border flex flex-col transition-all duration-300 custom-scrollbar ${activeDarkMode ? 'bg-[#222225] border-gray-700' : 'bg-white border-gray-200'
      } ${isFullscreen ? 'w-full h-full shadow-2xl overflow-auto' : 'relative w-full my-4 overflow-hidden'}`}>

      {/* Toolbar */}
      <div className={`flex justify-end items-center gap-2 px-3 py-2 border-b ${activeDarkMode ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'
        }`}>
        <span className={`text-xs font-semibold mr-auto ${activeDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          Cakra Infographic
        </span>

        {/* Download Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsDownloadMenuOpen(!isDownloadMenuOpen)}
            disabled={isDownloading}
            className={`p-1.5 rounded-md transition-colors flex items-center gap-1 ${activeDarkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
              } disabled:opacity-50`}
            title="Download Infographic"
          >
            <Download size={14} />
          </button>

          {isDownloadMenuOpen && (
            <div className={`absolute right-0 top-full mt-1 w-32 rounded-lg shadow-xl overflow-hidden z-50 border ${activeDarkMode ? 'bg-[#222225] border-gray-700' : 'bg-white border-gray-200'
              }`}>
              <button
                onClick={() => handleDownload('png')}
                className={`w-full text-left px-4 py-2 text-xs font-semibold transition-colors ${activeDarkMode ? 'text-gray-200 hover:bg-gray-700' : 'text-gray-700 hover:bg-gray-100'
                  }`}
              >
                {tGlobal.render.downloadPng}
              </button>
              <button
                onClick={() => handleDownload('svg')}
                className={`w-full text-left px-4 py-2 text-xs font-semibold transition-colors border-t ${activeDarkMode ? 'text-gray-200 hover:bg-gray-700 border-gray-700' : 'text-gray-700 hover:bg-gray-100 border-gray-100'
                  }`}
              >
                {tGlobal.render.downloadSvg}
              </button>
            </div>
          )}
        </div>

        <button title={isFullscreen ? tGlobal.render.exitFullscreen : tGlobal.render.fullscreen} onClick={toggleFullscreen} className={`p-1.5 rounded-md transition-colors ${activeDarkMode ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-200 text-gray-600'
          }`}>
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Scrollable Container (Outer Ref) */}
      <div 
        className="w-full overflow-hidden rounded-b-xl custom-scrollbar" 
        ref={outerRef}
        style={{ height: isFullscreen ? 'auto' : scaledHeight }}
      >
        
        {/* Scale Wrapper: Hanya aktif jika tidak fullscreen */}
        <div style={{ 
          transform: isFullscreen ? 'none' : `scale(${scale})`, 
          transformOrigin: 'top left',
          width: isFullscreen ? '100%' : `${(1 / scale) * 100}%`
        }}>
          
          {/* Main Infographic Content (Print Ref) */}
          <div ref={printRef} className={`p-5 md:p-6 ${activeDarkMode ? 'text-gray-100 bg-[#222225]' : 'text-gray-800 bg-white'}`} style={{ width: 'max-content', minWidth: 'max(100%, 960px)' }}>
            {renderDynamicLayout()}
          </div>
          {/* End of Print Ref Content */}
        
        </div>
        {/* End of Scale Wrapper */}

      </div>
      {/* End of Outer Ref Scrollable Wrapper */}
    </div>
  );

  if (isFullscreen) {
    return (
      <>
        {/* Placeholder in the chat bubble so it doesn't collapse entirely */}
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

export default TimelineInfographic;
