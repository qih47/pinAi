import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, Clock } from 'lucide-react';
import { translations } from '../../../utils/translations';

const UrlFetchTimelineWidget = ({ data, isStreaming, hasStartedResponding, darkMode = true, language = 'id' }) => {
    // Open by default if streaming and hasn't started responding.
    const [isOpen, setIsOpen] = useState(true);

    const t = translations[language]?.webSearch || translations.id.webSearch;

    useEffect(() => {
        if (hasStartedResponding || (!isStreaming && hasStartedResponding)) {
            setIsOpen(false);
        } else {
            setIsOpen(true);
        }
    }, [hasStartedResponding, isStreaming]);

    if (!data) return null;

    const nodes = data.nodes || [];
    const currentFetching = data.fetching;
    const activity = data.activity;

    if (nodes.length === 0 && !currentFetching) return null;

    const headerText = hasStartedResponding 
        ? (t.fetchLinksHeaderDone || "Hasil penelusuran informasi dari tautan")
        : (t.fetchLinksHeader || "Menelusuri informasi dari tautan");

    return (
        <div className="my-4 w-full max-w-3xl font-sans">
            {/* Top Level Accordion Header */}
            <div 
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 mb-3 cursor-pointer select-none group w-fit"
            >
                <span className="text-[14px] font-medium text-[#9e9e9e] transition-colors line-clamp-1 group-hover:text-[#c4c4c4]">
                    {headerText}
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
                {/* Vertical Stepper Timeline */}
                <div className="flex flex-col relative pl-2">
                    {nodes.map((item, idx) => {
                        let hostname = item.domain || '';
                        if (!hostname && item.url) {
                            try {
                                hostname = new URL(item.url).hostname.replace(/^www\./, '');
                            } catch (e) {
                                hostname = item.url;
                            }
                        }

                        const isLastNode = idx === nodes.length - 1 && !activity;

                        return (
                            <div key={idx} className="relative flex flex-col">
                                {/* Connector Line to Next Node */}
                                {!isLastNode && (
                                    <div 
                                        className="absolute left-[15px] top-[26px] bottom-[-6px] w-[1.5px] bg-[#333333] z-0" 
                                        style={{ height: 'calc(100% + 2px)' }}
                                    />
                                )}

                                {/* Node Row */}
                                <a
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={`flex items-center justify-between py-2 px-1.5 rounded-lg transition-colors group cursor-pointer relative z-10 ${
                                        darkMode ? 'hover:bg-[#1f1f23]' : 'hover:bg-gray-100'
                                    }`}
                                >
                                    <div className="flex items-center gap-3.5 overflow-hidden flex-1 pr-4">
                                        {/* Favicon Circle */}
                                        <div className="w-[30px] h-[30px] rounded-full flex-shrink-0 flex items-center justify-center bg-[#222222] border border-[#333333] overflow-hidden">
                                            <img
                                                src={`https://www.google.com/s2/favicons?domain=${hostname}&sz=64`}
                                                className="w-[18px] h-[18px] object-contain opacity-90 group-hover:opacity-100 transition-opacity"
                                                alt=""
                                                onError={(e) => {
                                                    e.target.onerror = null;
                                                    e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%23888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>';
                                                }}
                                            />
                                        </div>

                                        {/* Title / Name */}
                                        <span className="text-[14px] font-medium text-[#d4d4d4] group-hover:text-white truncate transition-colors">
                                            {item.title || item.url}
                                        </span>
                                    </div>

                                    {/* Domain & External Link Icon */}
                                    <div className="flex items-center gap-1.5 flex-shrink-0 text-[12.5px] text-[#777777] group-hover:text-[#aaaaaa] transition-colors">
                                        <span>{hostname}</span>
                                        <ExternalLink className="w-3.5 h-3.5" />
                                    </div>
                                </a>
                            </div>
                        );
                    })}

                    {/* Final Activity Node (Clock Icon) */}
                    {activity && (
                        <div className="relative flex items-center gap-3 pt-2.5 pb-1 px-1 z-10">
                            {nodes.length > 0 && (
                                <div className="absolute left-[15px] top-[-8px] h-[18px] w-[1.5px] bg-[#333333] z-0" />
                            )}
                            <div className="w-[30px] h-[30px] flex-shrink-0 flex items-center justify-center z-10">
                                <Clock className="w-4 h-4 text-[#888888]" />
                            </div>
                            <span className="text-[13.5px] text-[#999999] font-normal leading-relaxed">
                                {activity}
                            </span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default UrlFetchTimelineWidget;
