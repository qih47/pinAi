import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, FileCheck2, ScrollText, Mail, FileText, Check, AlertCircle } from 'lucide-react';
import { useDocWriterStore } from '../../../stores/docWriterStore';
import { defaultTemplates } from '../templates/defaultTemplates';

const iconMap = {
  FileCheck2: FileCheck2,
  ScrollText: ScrollText,
  Mail: Mail,
  FileText: FileText,
};

const TemplateSelectorModal = ({ isOpen, onClose, darkMode = true, theme }) => {
  const {
    templates,
    fetchTemplates,
    activeTemplateId,
    selectTemplate
  } = useDocWriterStore();

  useEffect(() => {
    if (isOpen) {
      fetchTemplates();
    }
  }, [isOpen, fetchTemplates]);

  if (!isOpen) return null;

  const bgCard = darkMode ? '#1e1e22' : '#ffffff';
  const borderColor = darkMode ? '#2d2d32' : '#e5e7eb';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const secondaryTextColor = theme?.secondaryText || (darkMode ? '#94a3b8' : '#6b7280');

  // Gabungkan template default lokal dengan template server jika ada
  const templateList = templates.length > 0 ? templates : Object.values(defaultTemplates);

  const handleSelect = (templateId) => {
    selectTemplate(templateId);
    onClose();
  };

  const modalContent = (
    <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div
        className="w-full max-w-2xl rounded-xl shadow-2xl border flex flex-col overflow-hidden animate-scaleUp"
        style={{
          background: darkMode ? '#18181b' : '#ffffff',
          borderColor: borderColor,
          maxHeight: '85vh',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor }}
        >
          <div>
            <h3 className="text-base font-semibold" style={{ color: textColor }}>
              Pilih Format Template Dokumen
            </h3>
            <p className="text-xs mt-0.5" style={{ color: secondaryTextColor }}>
              Gunakan struktur baku kedinasan PT Pindad untuk mempercepat pembuatan draf.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg hover:opacity-75 transition-opacity"
            style={{ color: secondaryTextColor }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Template Cards Grid */}
        <div className="p-5 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-3.5 custom-scrollbar">
          {templateList.map((tpl) => {
            const isSelected = activeTemplateId === tpl.id;
            const IconComponent = iconMap[tpl.icon] || FileText;

            return (
              <div
                key={tpl.id}
                onClick={() => handleSelect(tpl.id)}
                className={`p-4 rounded-xl border cursor-pointer transition-all duration-200 relative group flex flex-col justify-between ${
                  isSelected
                    ? 'border-sky-500 bg-sky-500/10 shadow-sm'
                    : 'hover:border-sky-500/50 hover:bg-white/5'
                }`}
                style={{
                  background: isSelected
                    ? (darkMode ? 'rgba(14, 165, 233, 0.12)' : '#f0f9ff')
                    : bgCard,
                  borderColor: isSelected ? '#0284c7' : borderColor,
                }}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center"
                        style={{
                          background: isSelected ? '#0284c7' : (darkMode ? '#27272a' : '#f1f5f9'),
                          color: isSelected ? '#ffffff' : '#38bdf8'
                        }}
                      >
                        <IconComponent size={16} />
                      </div>
                      <span className="text-[11px] px-2 py-0.5 rounded-full font-medium" style={{
                        background: darkMode ? '#27272a' : '#f1f5f9',
                        color: secondaryTextColor
                      }}>
                        {tpl.category || 'Dokumen Resmi'}
                      </span>
                    </div>

                    {isSelected && (
                      <div className="w-5 h-5 rounded-full bg-sky-500 flex items-center justify-center text-white">
                        <Check size={12} />
                      </div>
                    )}
                  </div>

                  <h4 className="text-sm font-semibold mb-1" style={{ color: textColor }}>
                    {tpl.name}
                  </h4>
                  <p className="text-xs leading-relaxed line-clamp-3" style={{ color: secondaryTextColor }}>
                    {tpl.description}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t flex items-center justify-between text-[11px]" style={{ borderColor }}>
                  <span className="text-sky-400 font-medium group-hover:underline">
                    Gunakan Template Ini →
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer info */}
        <div
          className="px-5 py-3 border-t flex items-center justify-between text-xs"
          style={{ background: darkMode ? '#131316' : '#f8fafc', borderColor }}
        >
          <div className="flex items-center gap-1.5 text-amber-400 text-[11px]">
            <AlertCircle size={13} />
            <span>Memilih template baru akan mereset kanvas ke draf baku template.</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg border text-xs font-medium hover:opacity-80 transition-opacity"
            style={{ borderColor, color: textColor }}
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== 'undefined' ? createPortal(modalContent, document.body) : modalContent;
};

export default TemplateSelectorModal;
