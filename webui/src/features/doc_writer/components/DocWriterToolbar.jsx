import React from 'react';
import {
  Bold, Italic, Underline, AlignLeft, AlignCenter, AlignRight, AlignJustify,
  List, ListOrdered, Table, Download, LayoutTemplate, X, RotateCcw, RotateCw,
  Printer, Loader2, Sparkles
} from 'lucide-react';
import { useDocWriterStore } from '../../../stores/docWriterStore';

const DocWriterToolbar = ({ editor, onOpenTemplates, darkMode = true, theme }) => {
  const { isExporting, exportDocx, activeTemplateId } = useDocWriterStore();

  if (!editor) return null;

  const bgToolbar = darkMode ? '#1c1c1f' : '#f9fafb';
  const borderColor = darkMode ? '#2d2d32' : '#e5e7eb';
  const textColor = theme?.textColor || (darkMode ? '#e2e8f0' : '#1f2937');
  const activeBtnBg = darkMode ? '#334155' : '#e2e8f0';

  const btnStyle = (isActive) => ({
    padding: '5px 7px',
    borderRadius: '6px',
    background: isActive ? activeBtnBg : 'transparent',
    color: isActive ? '#38bdf8' : textColor,
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.15s ease',
  });

  const handlePrintPdf = () => {
    window.print();
  };

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-1 px-3 py-2 border-b select-none"
      style={{ background: bgToolbar, borderColor: borderColor }}
    >
      {/* ── Group 1: History Undo / Redo ── */}
      <div className="flex items-center gap-0.5 pr-2 border-r" style={{ borderColor }}>
        <button
          type="button"
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          style={btnStyle(false)}
          title="Undo (Ctrl+Z)"
          className="disabled:opacity-30"
        >
          <RotateCcw size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          style={btnStyle(false)}
          title="Redo (Ctrl+Y)"
          className="disabled:opacity-30"
        >
          <RotateCw size={14} />
        </button>
      </div>

      {/* ── Group 2: Typography & Formatting ── */}
      <div className="flex items-center gap-0.5 px-2 border-r" style={{ borderColor }}>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          style={btnStyle(editor.isActive('bold'))}
          title="Bold (Ctrl+B)"
        >
          <Bold size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          style={btnStyle(editor.isActive('italic'))}
          title="Italic (Ctrl+I)"
        >
          <Italic size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          style={btnStyle(editor.isActive('underline'))}
          title="Underline (Ctrl+U)"
        >
          <Underline size={14} />
        </button>

        {/* Headings Selector */}
        <select
          className="text-xs px-2 py-1 rounded ml-1 bg-transparent border cursor-pointer focus:outline-none"
          style={{ borderColor, color: textColor }}
          value={
            editor.isActive('heading', { level: 1 }) ? 'h1' :
            editor.isActive('heading', { level: 2 }) ? 'h2' :
            editor.isActive('heading', { level: 3 }) ? 'h3' : 'p'
          }
          onChange={(e) => {
            const val = e.target.value;
            if (val === 'p') editor.chain().focus().setParagraph().run();
            else if (val === 'h1') editor.chain().focus().toggleHeading({ level: 1 }).run();
            else if (val === 'h2') editor.chain().focus().toggleHeading({ level: 2 }).run();
            else if (val === 'h3') editor.chain().focus().toggleHeading({ level: 3 }).run();
          }}
        >
          <option value="p">Normal</option>
          <option value="h1">Heading 1</option>
          <option value="h2">Heading 2</option>
          <option value="h3">Heading 3</option>
        </select>
      </div>

      {/* ── Group 3: Alignment ── */}
      <div className="flex items-center gap-0.5 px-2 border-r" style={{ borderColor }}>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign('left').run()}
          style={btnStyle(editor.isActive({ textAlign: 'left' }))}
          title="Rata Kiri"
        >
          <AlignLeft size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign('center').run()}
          style={btnStyle(editor.isActive({ textAlign: 'center' }))}
          title="Rata Tengah"
        >
          <AlignCenter size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign('right').run()}
          style={btnStyle(editor.isActive({ textAlign: 'right' }))}
          title="Rata Kanan"
        >
          <AlignRight size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign('justify').run()}
          style={btnStyle(editor.isActive({ textAlign: 'justify' }))}
          title="Rata Kanan-Kiri (Justify)"
        >
          <AlignJustify size={14} />
        </button>
      </div>

      {/* ── Group 4: Lists & Tables ── */}
      <div className="flex items-center gap-0.5 px-2 border-r" style={{ borderColor }}>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          style={btnStyle(editor.isActive('bulletList'))}
          title="Daftar Butir (Bullet)"
        >
          <List size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          style={btnStyle(editor.isActive('orderedList'))}
          title="Daftar Bernomor (Numbering)"
        >
          <ListOrdered size={14} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
          style={btnStyle(editor.isActive('table'))}
          title="Sisipkan Tabel 3x3"
        >
          <Table size={14} />
        </button>
      </div>

      {/* ── Group 5: Template & Export Actions ── */}
      <div className="flex items-center gap-1 ml-auto">
        <button
          type="button"
          onClick={onOpenTemplates}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all hover:opacity-90"
          style={{
            background: darkMode ? '#1e293b' : '#f1f5f9',
            border: `1px solid ${borderColor}`,
            color: '#38bdf8'
          }}
          title="Pilih Template Dokumen"
        >
          <LayoutTemplate size={13} />
          <span>Template</span>
        </button>

        <button
          type="button"
          onClick={handlePrintPdf}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-all hover:opacity-90"
          style={{
            background: darkMode ? '#1e293b' : '#f1f5f9',
            border: `1px solid ${borderColor}`,
            color: textColor
          }}
          title="Cetak / Simpan PDF (A4)"
        >
          <Printer size={13} />
        </button>

        <button
          type="button"
          onClick={exportDocx}
          disabled={isExporting}
          className="flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold shadow-sm transition-all hover:opacity-90 disabled:opacity-50"
          style={{
            background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
            color: '#ffffff'
          }}
          title="Ekspor ke Microsoft Word (.docx)"
        >
          {isExporting ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Download size={13} />
          )}
          <span>Word (.docx)</span>
        </button>
      </div>
    </div>
  );
};

export default DocWriterToolbar;
