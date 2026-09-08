import React, { useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table';
import Placeholder from '@tiptap/extension-placeholder';
import { useDocWriterStore } from '../../../stores/docWriterStore';

const DocWriterCanvas = ({ onEditorReady, darkMode = true, theme }) => {
  const {
    activeDocument,
    setDocumentContent,
    activePatchSection
  } = useDocWriterStore();

  const isInternalUpdate = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
      }),
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({
        placeholder: 'Mulai ketik draf resmi di sini atau suruh CAKRA untuk menyusun draf...',
      }),
    ],
    content: activeDocument?.htmlContent || '',
    onUpdate: ({ editor }) => {
      isInternalUpdate.current = true;
      const html = editor.getHTML();
      setDocumentContent(html);
      setTimeout(() => {
        isInternalUpdate.current = false;
      }, 50);
    },
  });

  // Kirim editor instance ke parent toolbar
  useEffect(() => {
    if (editor && onEditorReady) {
      onEditorReady(editor);
    }
  }, [editor, onEditorReady]);

  // Sync saat template berganti dari luar store
  useEffect(() => {
    if (editor && !isInternalUpdate.current) {
      const currentHTML = editor.getHTML();
      if (activeDocument?.htmlContent && activeDocument.htmlContent !== currentHTML) {
        editor.commands.setContent(activeDocument.htmlContent, false);
      }
    }
  }, [activeDocument?.htmlContent, editor]);

  // Handle Targeted Section Patch dari AI CAKRA
  useEffect(() => {
    if (!editor || !activePatchSection) return;
    const { sectionId } = activePatchSection;
    // Cari elemen berdasarkan data-section dan highlight visual halus
    try {
      const el = document.querySelector(`[data-section="${sectionId}"]`);
      if (el) {
        el.classList.add('cakra-ai-patched-section');
        setTimeout(() => {
          el.classList.remove('cakra-ai-patched-section');
        }, 2500);
      }
    } catch (e) {
      // Ignored
    }
  }, [activePatchSection, editor]);

  return (
    <div
      className="doc-writer-canvas-viewport flex-1 overflow-y-auto p-4 md:p-8 flex justify-center custom-scrollbar"
      style={{
        background: darkMode ? '#121214' : '#f1f5f9',
      }}
    >
      <style>{`
        /* ── Canvas Kertas A4 Standar Word ── */
        .tiptap-a4-page {
          width: 100%;
          max-width: 794px; /* Lebar standar A4 96 DPI */
          min-height: 1123px; /* Tinggi standar A4 96 DPI */
          background: #ffffff;
          color: #1a1a1a;
          box-shadow: 0 4px 20px rgba(0,0,0,0.15);
          border-radius: 4px;
          padding: 65px 70px;
          font-family: 'Arial', sans-serif;
          font-size: 11pt;
          line-height: 1.5;
          position: relative;
        }

        .tiptap-a4-page:focus-within {
          outline: none;
        }

        .ProseMirror:focus {
          outline: none;
        }

        /* ── Styling Elemen Rich Text ── */
        .tiptap-a4-page p {
          margin-bottom: 0.65em;
        }

        .tiptap-a4-page h1 {
          font-size: 14pt;
          font-weight: bold;
          margin-top: 1em;
          margin-bottom: 0.4em;
        }

        .tiptap-a4-page h2 {
          font-size: 12pt;
          font-weight: bold;
          margin-top: 0.9em;
          margin-bottom: 0.3em;
        }

        .tiptap-a4-page h3 {
          font-size: 11pt;
          font-weight: bold;
          margin-top: 0.8em;
          margin-bottom: 0.3em;
        }

        .tiptap-a4-page ol {
          list-style-type: decimal;
          padding-left: 24px;
          margin-bottom: 0.6em;
        }

        .tiptap-a4-page ul {
          list-style-type: disc;
          padding-left: 24px;
          margin-bottom: 0.6em;
        }

        .tiptap-a4-page li {
          margin-bottom: 0.3em;
        }

        /* ── Styling Tabel ── */
        .tiptap-a4-page table {
          border-collapse: collapse;
          table-layout: fixed;
          width: 100%;
          margin: 1em 0;
          overflow: hidden;
        }

        .tiptap-a4-page table td,
        .tiptap-a4-page table th {
          min-width: 1em;
          border: 1px solid #71717a;
          padding: 6px 8px;
          vertical-align: top;
          box-sizing: border-box;
          position: relative;
        }

        .tiptap-a4-page table th {
          font-weight: bold;
          text-align: left;
          background-color: #f4f4f5;
        }

        /* ── Efek Highlight AI Saat Diedit CAKRA ── */
        @keyframes cakraPatchGlow {
          0% { background-color: rgba(56, 189, 248, 0.25); border-left: 3px solid #0284c7; }
          70% { background-color: rgba(56, 189, 248, 0.15); border-left: 3px solid #0284c7; }
          100% { background-color: transparent; border-left: none; }
        }

        .cakra-ai-patched-section {
          animation: cakraPatchGlow 2.5s ease-out;
          border-radius: 4px;
          padding: 2px 4px;
        }

        /* Print Media Styles (A4 Page Print) */
        @media print {
          body * {
            visibility: hidden;
          }
          .tiptap-a4-page, .tiptap-a4-page * {
            visibility: visible;
          }
          .tiptap-a4-page {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            margin: 0;
            padding: 20mm;
            box-shadow: none;
          }
        }
      `}</style>

      <div className="tiptap-a4-page animate-fadeIn">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
};

export default DocWriterCanvas;
