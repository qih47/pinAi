import React, { useState } from 'react';
import { Network, FileText, ChevronRight, AlertTriangle } from 'lucide-react';

const DUMMY_LINEAGE = [
    {
        id: "doc-1",
        title: "Peraturan Perusahaan Induk 2023",
        status: "active",
        type: "parent"
    },
    {
        id: "doc-2",
        title: "SOP Cuti Karyawan v1.0 (2024)",
        status: "deprecated",
        type: "child",
        issue: "Digantikan oleh v2.0"
    },
    {
        id: "doc-3",
        title: "SOP Cuti Karyawan v2.0 (2025)",
        status: "active",
        type: "child"
    }
];

const LineageGraphWidget = ({ docId, title }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div className="mt-4 mb-4 border border-indigo-200 dark:border-indigo-900/50 rounded-xl overflow-hidden bg-white dark:bg-gray-800 shadow-sm transition-all duration-300">
            <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full bg-indigo-50 dark:bg-indigo-900/40 p-3 border-b border-indigo-100 dark:border-indigo-800/50 flex items-center justify-between hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <Network size={18} className="text-indigo-600 dark:text-indigo-400" />
                    <span className="font-semibold text-sm text-indigo-900 dark:text-indigo-300">
                        Visualisasi Silsilah Kebijakan
                    </span>
                </div>
                <ChevronRight 
                    size={18} 
                    className={`text-indigo-400 transition-transform duration-300 ${isExpanded ? 'rotate-90' : ''}`} 
                />
            </button>

            {isExpanded && (
                <div className="p-4 bg-gray-50 dark:bg-gray-900/50">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                        Menampilkan hirarki dokumen terkait dengan: <span className="font-medium text-gray-700 dark:text-gray-300">{title || "Dokumen Aktif"}</span>
                    </p>
                    
                    <div className="flex flex-col relative pl-2">
                        {/* Connecting Line */}
                        <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-indigo-200 dark:bg-indigo-800/50" />

                        {DUMMY_LINEAGE.map((node, idx) => (
                            <div key={node.id} className="flex gap-4 mb-4 relative z-10 group">
                                <div className={`mt-1 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border-2 
                                    ${node.status === 'active' 
                                        ? 'bg-indigo-100 border-indigo-500 text-indigo-600 dark:bg-indigo-900 dark:border-indigo-400 dark:text-indigo-300' 
                                        : 'bg-red-50 border-red-400 text-red-500 dark:bg-red-900/50 dark:border-red-500 dark:text-red-400'
                                    }`}
                                >
                                    <FileText size={14} />
                                </div>
                                <div className="flex-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-sm group-hover:shadow-md transition-shadow">
                                    <h4 className={`text-sm font-semibold ${node.status === 'deprecated' ? 'text-gray-500 line-through' : 'text-gray-800 dark:text-gray-200'}`}>
                                        {node.title}
                                    </h4>
                                    <div className="flex items-center gap-2 mt-2">
                                        <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded ${
                                            node.status === 'active' 
                                                ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400' 
                                                : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
                                        }`}>
                                            {node.status}
                                        </span>
                                        {node.type === 'parent' && (
                                            <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400">
                                                Induk
                                            </span>
                                        )}
                                    </div>
                                    {node.issue && (
                                        <div className="mt-2 text-xs text-red-600 dark:text-red-400 flex items-center gap-1 bg-red-50 dark:bg-red-900/20 p-1.5 rounded">
                                            <AlertTriangle size={12} />
                                            {node.issue}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default LineageGraphWidget;
