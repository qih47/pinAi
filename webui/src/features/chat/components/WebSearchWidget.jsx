import React, { useState, useEffect } from 'react';
import { Globe, ChevronDown, ChevronUp, Clock, CheckCircle2 } from 'lucide-react';
import { translations } from '../../../utils/translations';

const WebSearchWidget = ({ searchData, isStreaming, hasStartedResponding, darkMode = true, language = 'id' }) => {
    // Open by default if streaming and hasn't started responding.
    const [isOpen, setIsOpen] = useState(true);
    const [elapsedSec, setElapsedSec] = useState(0);

    const t = translations[language]?.webSearch || translations.id.webSearch;

    const results = Array.isArray(searchData) ? searchData : (searchData?.results || []);
    const isLoading = isStreaming && results.length === 0;
    
    // Status Analisis:
    // Selama results sudah ada tapi respons teks LLM belum mulai keluar -> sedang menganalisis (prefill LLM)
    const isAnalyzing = isStreaming && results.length > 0 && !hasStartedResponding;
    // Begitu respons teks mulai keluar atau streaming selesai -> analisis & pencarian selesai!
    const isSearchComplete = hasStartedResponding || (!isStreaming && results.length > 0);

    useEffect(() => {
        let timer;
        if (isLoading) {
            timer = setInterval(() => {
                setElapsedSec(prev => +(prev + 0.1).toFixed(1));
            }, 100);
        }
        return () => {
            if (timer) clearInterval(timer);
        };
    }, [isLoading]);

    useEffect(() => {
        if (isSearchComplete) {
            // Beri jeda 800ms agar mata user sempat melihat status 'Selesai' (centang hijau) sebelum accordion menutup
            const timer = setTimeout(() => {
                setIsOpen(false);
            }, 800);
            return () => clearTimeout(timer);
        } else {
            setIsOpen(true);
        }
    }, [isSearchComplete]);

    if (!searchData && !isStreaming) return null;
    
    let originalQuery = !Array.isArray(searchData) && searchData?.query 
        ? searchData.query 
        : (results[0]?.title || "");
        
    let displayQuery = originalQuery
        ? (t.searchingReferencesFor || "mencari referensi terkait {query}").replace('{query}', originalQuery.toLowerCase())
        : (t.searchingWebReferences || "mencari referensi web");
    
    return (
        <div className="my-4 w-full max-w-3xl font-sans">
            {/* Top Level Accordion Header */}
            <div 
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 mb-3 cursor-pointer select-none group w-fit"
            >
                <span className="text-[14px] font-medium text-[#9e9e9e] transition-colors line-clamp-1 group-hover:text-[#c4c4c4] flex items-center gap-2">
                    {isLoading ? (
                        <>
                            <span className="inline-block w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
                            <span>{(t.searchingInfoWithTime || "Menelusuri informasi dari web ({elapsed}s)").replace('{elapsed}', elapsedSec)}</span>
                        </>
                    ) : isAnalyzing ? (
                        <>
                            <span className="inline-block w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                            <span>{t.analyzingResults || "Menganalisis hasil pencarian..."}</span>
                        </>
                    ) : isSearchComplete ? (
                        t.searchResults || "Hasil penelusuran informasi dari web"
                    ) : (
                        t.searchingInfo || "Menelusuri informasi dari web"
                    )}
                </span>
                <span className="text-[#888888] flex items-center justify-center">
                    {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </span>
            </div>

            {/* Collapsible Main Container */}
            <div 
                className={`transition-all duration-300 ease-in-out origin-top overflow-hidden relative ${
                    isOpen ? 'max-h-[600px] opacity-100 scale-y-100' : 'max-h-0 opacity-0 scale-y-0'
                }`}
            >
                {/* Timeline Vertical Line */}
                <div className="absolute left-[9px] top-[14px] bottom-[14px] w-[2px] bg-[#333333] z-0"></div>

                <div className="flex flex-col gap-4 relative z-10 pl-0">
                    
                    {/* Step 1: Web Search */}
                    <div>
                        <div className="flex items-center gap-3 mb-3">
                            <div className="bg-[#1e1e1e] py-1 rounded-full z-10 relative">
                                <Globe className="w-[14px] h-[14px] text-[#888888] flex-shrink-0" />
                            </div>
                            <span className="text-[13.5px] font-medium text-[#888888] truncate flex-grow">
                                "{displayQuery}"
                            </span>
                            <span className="text-[12px] text-[#666666] whitespace-nowrap">
                                {(t.resultsCount || "{count} results").replace('{count}', results.length)}
                            </span>
                        </div>
                        
                        <div className="ml-[26px]">
                            <div className="rounded-xl border border-[#2a2a2a] bg-[#1c1c1c] overflow-hidden shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
                                <div className="flex flex-col max-h-[240px] overflow-y-auto p-1 pr-1 custom-scrollbar" 
                                     style={{
                                         scrollbarWidth: 'thin',
                                         scrollbarColor: '#444 transparent'
                                     }}>
                                    <style dangerouslySetInnerHTML={{__html: `
                                        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
                                        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                                        .custom-scrollbar::-webkit-scrollbar-thumb { background-color: #444; border-radius: 10px; }
                                    `}} />
                                    
                                    {isLoading ? (
                                        <div className="p-3 text-xs text-gray-400 flex items-center gap-2">
                                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" />
                                            <span>{t.searchingWeb || "Mencari informasi di web..."}</span>
                                        </div>
                                    ) : (
                                        results.map((item, idx) => {
                                            let hostname = '';
                                            try {
                                                hostname = new URL(item.url).hostname;
                                                hostname = hostname.replace(/^www\./, '');
                                            } catch(e) {
                                                hostname = item.url || '';
                                            }
                                            
                                            return (
                                                <a 
                                                    key={idx} 
                                                    href={item.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="flex items-center justify-between p-2.5 rounded-lg hover:bg-[#252525] transition-all group/item cursor-pointer"
                                                >
                                                    <div className="flex items-center gap-3 overflow-hidden flex-1 pr-4">
                                                         <div className="w-[18px] h-[18px] flex-shrink-0 flex items-center justify-center bg-transparent">
                                                            <img 
                                                                src={`https://www.google.com/s2/favicons?domain=${hostname}&sz=32`}
                                                                className="w-full h-full object-contain opacity-80 group-hover/item:opacity-100 transition-opacity"
                                                                alt=""
                                                                onError={(e) => { 
                                                                    e.target.onerror = null; 
                                                                    e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%23666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>';
                                                                }}
                                                            />
                                                        </div>
                                                        <span className="text-[13.5px] font-medium text-[#d4d4d4] group-hover/item:text-white truncate transition-colors">
                                                            {item.title}
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center gap-3 flex-shrink-0">
                                                        <span className="text-[12px] text-[#666666]">{hostname}</span>
                                                    </div>
                                                </a>
                                            );
                                        })
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Analyzing / Done */}
                    {results.length > 0 && (
                        <div className="flex flex-col gap-3 mt-1 ml-[1px]">
                            <div className="flex items-center gap-3">
                                <div className="bg-[#1e1e1e] py-0.5 rounded-full z-10 relative flex items-center justify-center w-[18px]">
                                    {isAnalyzing ? (
                                        <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
                                    ) : (
                                        <Clock className="w-[14px] h-[14px] text-[#888888]" />
                                    )}
                                </div>
                                <span className={`text-[13.5px] ${isAnalyzing ? 'text-indigo-300 font-medium' : 'text-[#888888]'}`}>
                                    {t.analyzingResults || "Menganalisis hasil pencarian..."}
                                </span>
                            </div>

                            {isSearchComplete && (
                                <div className="flex items-center gap-3">
                                    <div className="bg-[#1e1e1e] py-0.5 rounded-full z-10 relative flex items-center justify-center w-[18px]">
                                        <CheckCircle2 className="w-[14px] h-[14px] text-emerald-400" />
                                    </div>
                                    <span className="text-[13.5px] font-medium text-emerald-400">
                                        {t.done || "Selesai"}
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default WebSearchWidget;
