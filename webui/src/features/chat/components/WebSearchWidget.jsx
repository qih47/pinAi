import React, { useState, useEffect } from 'react';
import { Globe, ChevronDown, ChevronUp, Clock, CheckCircle2 } from 'lucide-react';

const WebSearchWidget = ({ searchData, isStreaming, hasStartedResponding }) => {
    // Open by default if streaming and hasn't started responding.
    const [isOpen, setIsOpen] = useState(true);

    useEffect(() => {
        if (hasStartedResponding || (!isStreaming && hasStartedResponding)) {
            setIsOpen(false);
        } else {
            setIsOpen(true);
        }
    }, [hasStartedResponding, isStreaming]);

    if (!searchData) return null;
    
    const results = Array.isArray(searchData) ? searchData : (searchData.results || []);
    if (results.length === 0) return null;

    let originalQuery = !Array.isArray(searchData) && searchData.query 
        ? searchData.query 
        : (results[0]?.title || "Penelusuran Web");
        
    let displayQuery = originalQuery
        ? `mencari referensi terkait ${originalQuery.toLowerCase()}`
        : "mencari referensi web";
    
    return (
        <div className="my-4 w-full max-w-3xl font-sans">
            {/* Top Level Accordion Header */}
            <div 
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 mb-3 cursor-pointer select-none group w-fit"
            >
                <span className="text-[14px] font-medium text-[#9e9e9e] transition-colors line-clamp-1 group-hover:text-[#c4c4c4]">
                    {hasStartedResponding ? "Hasil penelusuran informasi dari web" : "Menelusuri informasi dari web"}
                </span>
                <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[#888888] flex items-center justify-center">
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
                                {results.length} results
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
                                    
                                    {results.map((item, idx) => {
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
                                                            src={`https://icons.duckduckgo.com/ip3/${hostname}.ico`}
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
                                    })}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Analyzing / Done */}
                    {hasStartedResponding && (
                        <div className="flex flex-col gap-4 mt-1">
                            <div className="flex items-center gap-3">
                                <div className="bg-[#1e1e1e] py-1 rounded-full z-10 relative">
                                    <Clock className="w-[14px] h-[14px] text-[#888888] flex-shrink-0" />
                                </div>
                                <span className="text-[13.5px] text-[#a3a3a3]">
                                    Menganalisis hasil pencarian...
                                </span>
                            </div>

                            {!isStreaming && (
                                <div className="flex items-center gap-3">
                                    <div className="bg-[#1e1e1e] py-1 rounded-full z-10 relative">
                                        <CheckCircle2 className="w-[14px] h-[14px] text-[#888888] flex-shrink-0" />
                                    </div>
                                    <span className="text-[13.5px] text-[#a3a3a3]">
                                        Selesai
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
