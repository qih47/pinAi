import React from 'react';
import { Rocket, FileText } from 'lucide-react';
import useToast from "../../../hooks/useToast";
import { useChatStore } from '../../../stores/chatStore';
import LineageGraphWidget from './LineageGraphWidget';

export const ActionSkeletonButton = ({ actionName }) => {
    const toast = useToast();
    
    return (
        <button 
            onClick={() => toast.info(`🚀 API Eksekusi untuk aksi "${actionName}" sedang dalam pengembangan.`)}
            className="mt-3 flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-md hover:shadow-lg"
        >
            <Rocket size={18} />
            {actionName || "Eksekusi Aksi Sekarang"}
        </button>
    );
}

export const GhostWriterButton = ({ contentRef }) => {
    const setGhostWriter = useChatStore(state => state.setGhostWriter);
    
    return (
        <button 
            onClick={() => setGhostWriter(true, "")}
            className="mt-3 ml-2 inline-flex items-center gap-2 px-5 py-2.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-xl text-sm font-semibold transition-all shadow-sm"
        >
            <FileText size={18} />
            Buka di Editor (GhostWriter)
        </button>
    );
}

const ChatActionWidgets = ({ rawContent }) => {
    if (!rawContent) return null;

    // 1. Deteksi Skeleton Action Button dari sintaks spesial [ACTION:Nama Aksi]
    const actionRegex = /\[ACTION:(.*?)\]/g;
    const actions = [];
    let match;
    while ((match = actionRegex.exec(rawContent)) !== null) {
        actions.push(match[1].trim());
    }

    // 2. Deteksi GhostWriter Trigger dari sintaks spesial [GHOSTWRITER]
    const hasGhostWriter = /\[GHOSTWRITER\]/i.test(rawContent);

    // 3. Deteksi Lineage Graph Trigger
    const hasLineage = /\[LINEAGE\]/i.test(rawContent);

    if (actions.length === 0 && !hasGhostWriter && !hasLineage) return null;

    return (
        <div className="flex flex-col gap-2 mt-4 mb-3 pt-2 border-t border-gray-100 dark:border-gray-800">
            {hasLineage && <LineageGraphWidget />}
            
            <div className="flex flex-wrap items-center gap-2">
                {actions.map((action, idx) => (
                    <ActionSkeletonButton key={`action-${idx}`} actionName={action} />
                ))}
                
                {hasGhostWriter && (
                    <GhostWriterButton />
                )}
            </div>
        </div>
    );
};

export default ChatActionWidgets;
