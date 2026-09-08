import { create } from 'zustand';
import axios from 'axios';
import { defaultTemplates } from '../features/doc_writer/templates/defaultTemplates';

export const useDocWriterStore = create((set, get) => ({
  isOpen: false,
  splitWidth: typeof window !== 'undefined' && window.innerWidth < 1200 ? 520 : 640,
  activeDocument: {
    id: 'doc_active',
    title: 'Surat Keputusan Direksi',
    templateId: 'template_skep',
    htmlContent: defaultTemplates['template_skep']?.html || '',
    lastSavedAt: null,
  },
  activeTemplateId: 'template_skep',
  templates: [],
  isLoadingTemplates: false,
  isExporting: false,
  activePatchSection: null, // { sectionId, timestamp }

  openWriter: (templateId = null, initialTitle = null, initialContent = null) => {
    const currentDoc = get().activeDocument;
    const targetTemplateId = templateId || currentDoc.templateId || 'template_skep';
    const fallbackTemplate = defaultTemplates[targetTemplateId] || defaultTemplates['template_blank'];

    set({
      isOpen: true,
      activeTemplateId: targetTemplateId,
      activeDocument: {
        ...currentDoc,
        title: initialTitle || fallbackTemplate.title || currentDoc.title,
        templateId: targetTemplateId,
        htmlContent: initialContent || (currentDoc.htmlContent ? currentDoc.htmlContent : fallbackTemplate.html),
        lastSavedAt: new Date().toISOString(),
      }
    });
  },

  closeWriter: () => set({ isOpen: false }),

  toggleWriter: () => set((state) => ({ isOpen: !state.isOpen })),

  setSplitWidth: (width) => set({ splitWidth: Math.max(380, Math.min(width, window.innerWidth - 380)) }),

  setDocumentContent: (htmlContent) => {
    set((state) => ({
      activeDocument: {
        ...state.activeDocument,
        htmlContent,
        lastSavedAt: new Date().toISOString()
      }
    }));
  },

  setDocumentTitle: (title) => {
    set((state) => ({
      activeDocument: {
        ...state.activeDocument,
        title
      }
    }));
  },

  selectTemplate: (templateId) => {
    const templateDef = defaultTemplates[templateId] || defaultTemplates['template_blank'];
    set((state) => ({
      activeTemplateId: templateId,
      activeDocument: {
        ...state.activeDocument,
        templateId,
        title: templateDef.title || state.activeDocument.title,
        htmlContent: templateDef.html || '',
        lastSavedAt: new Date().toISOString()
      }
    }));
  },

  patchSection: (sectionId, newHtml) => {
    const currentDoc = get().activeDocument;
    let updatedHtml = currentDoc?.htmlContent || '';

    // Cari div data-section="${sectionId}"
    const sectionRegex = new RegExp(`(<div\\s+[^>]*data-section=["']${sectionId}["'][^>]*>)([\\s\\S]*?)(<\\/div>)`, 'i');
    if (sectionRegex.test(updatedHtml)) {
      updatedHtml = updatedHtml.replace(sectionRegex, `$1\n${newHtml}\n$3`);
    } else {
      // Jika belum ada data-section, tambahkan blok seksi baru
      updatedHtml += `\n<div data-section="${sectionId}">\n${newHtml}\n</div>`;
    }

    set({
      activeDocument: {
        ...currentDoc,
        htmlContent: updatedHtml,
        lastSavedAt: new Date().toISOString()
      },
      activePatchSection: { sectionId, timestamp: Date.now() }
    });
  },

  fetchTemplates: async () => {
    set({ isLoadingTemplates: true });
    try {
      const res = await axios.get('/api/doc-writer/templates');
      if (res.data?.success && Array.isArray(res.data?.templates)) {
        set({ templates: res.data.templates, isLoadingTemplates: false });
      }
    } catch (err) {
      console.warn('[DOC_WRITER] Gagal memuat template dari server, menggunakan lokal fallback:', err);
      set({ isLoadingTemplates: false });
    }
  },

  exportDocx: async () => {
    const { activeDocument } = get();
    if (!activeDocument?.htmlContent) return;

    set({ isExporting: true });
    try {
      const response = await axios.post('/api/doc-writer/export-docx', {
        html_content: activeDocument.htmlContent,
        title: activeDocument.title || 'Dokumen_Resmi_PT_Pindad',
        template_id: activeDocument.templateId || 'template_blank',
        metadata: {
          include_kop: true
        }
      }, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      const safeTitle = (activeDocument.title || 'Dokumen_PT_Pindad').trim().replace(/\s+/g, '_');
      link.download = `${safeTitle}.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error('[DOC_WRITER] Gagal ekspor DOCX:', err);
      alert('Gagal mengekspor berkas Word (.docx). Silakan coba kembali.');
    } finally {
      set({ isExporting: false });
    }
  }
}));
