import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  ChevronLeft, 
  ChevronRight, 
  Maximize2, 
  Minimize2, 
  Download, 
  Copy, 
  Check, 
  Presentation, 
  Sparkles,
  Layers,
  FileText
} from 'lucide-react';
import pptxgen from 'pptxgenjs';
import { translations } from '../../../utils/translations';

// Tema Warna Presets
const THEMES = {
  'pindad-dark': {
    id: 'pindad-dark',
    name: 'Pindad Navy & Gold',
    bg: 'linear-gradient(135deg, #071526 0%, #0d2542 50%, #071526 100%)',
    bgSolid: '071526',
    cardBg: 'rgba(255, 255, 255, 0.05)',
    cardBorder: 'rgba(243, 183, 44, 0.2)',
    titleColor: '#FFFFFF',
    accentColor: '#F3B72C',
    accentHex: 'F3B72C',
    textColor: '#E2E8F0',
    textMuted: '#94A3B8',
    isDark: true
  },
  'modern-dark': {
    id: 'modern-dark',
    name: 'Modern Slate',
    bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    bgSolid: '0F172A',
    cardBg: 'rgba(255, 255, 255, 0.04)',
    cardBorder: 'rgba(56, 189, 248, 0.2)',
    titleColor: '#F8FAFC',
    accentColor: '#38BDF8',
    accentHex: '38BDF8',
    textColor: '#CBD5E1',
    textMuted: '#64748B',
    isDark: true
  },
  'clean-light': {
    id: 'clean-light',
    name: 'Clean Corporate',
    bg: 'linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%)',
    bgSolid: 'F8FAFC',
    cardBg: '#FFFFFF',
    cardBorder: 'rgba(14, 165, 233, 0.25)',
    titleColor: '#0F172A',
    accentColor: '#0284C7',
    accentHex: '0284C7',
    textColor: '#334155',
    textMuted: '#64748B',
    isDark: false
  }
};

/**
 * Parser resilien untuk konten kode slide.
 * Mampu memulihkan JSON yang belum tertutup (misal saat streaming atau terputus)
 * dan mem-parsing format Markdown tanpa menampilkan artefak sintaks JSON.
 */
function parseSlideData(rawContent) {
  if (!rawContent || typeof rawContent !== 'string') {
    return { title: 'Presentasi', slides: [] };
  }

  const clean = rawContent.trim();
  if (!clean) {
    return { title: 'Presentasi', slides: [] };
  }

  // 1. Coba parse sebagai JSON murni
  try {
    const parsed = JSON.parse(clean);
    if (parsed && Array.isArray(parsed.slides) && parsed.slides.length > 0) {
      return parsed;
    }
  } catch (_) {}

  // 2. Cari blok JSON di dalam teks jika terbungkus karakter lain
  try {
    const firstBrace = clean.indexOf('{');
    const lastBrace = clean.lastIndexOf('}');
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      const jsonSubstring = clean.substring(firstBrace, lastBrace + 1);
      const parsed = JSON.parse(jsonSubstring);
      if (parsed && Array.isArray(parsed.slides) && parsed.slides.length > 0) {
        return parsed;
      }
    }
  } catch (_) {}

  // 3. Pemulihan Parsial (Self-Healing untuk streaming / JSON terpotong):
  // Jika konten merupakan format JSON (ada "slides" atau diawali {), ekstrak semua slide yang sudah lengkap
  const isJsonLike = clean.startsWith('{') || clean.includes('"slides"') || clean.includes('"theme"');
  if (isJsonLike) {
    const slideObjects = [];
    const slidesIndex = clean.indexOf('"slides"');
    const searchArea = slidesIndex !== -1 ? clean.substring(slidesIndex) : clean;

    let depth = 0;
    let start = -1;
    let inStr = false;

    for (let i = 0; i < searchArea.length; i++) {
      const ch = searchArea[i];
      if (ch === '"' && searchArea[i - 1] !== '\\') {
        inStr = !inStr;
      } else if (!inStr) {
        if (ch === '{') {
          if (depth === 0) start = i;
          depth++;
        } else if (ch === '}') {
          depth--;
          if (depth === 0 && start !== -1) {
            try {
              const candidate = JSON.parse(searchArea.substring(start, i + 1));
              if (candidate && (candidate.title || candidate.layout || candidate.bullets)) {
                slideObjects.push(candidate);
              }
            } catch (_) {}
            start = -1;
          }
        }
      }
    }

    if (slideObjects.length > 0) {
      const titleMatch = clean.match(/"title"\s*:\s*"([^"]+)"/);
      return {
        title: titleMatch ? titleMatch[1] : 'Presentasi Eksekutif',
        slides: slideObjects
      };
    }

    // Jika JSON baru mulai di-stream dan belum ada slide yang tertutup sempurna
    return {
      title: 'Menyiapkan Slide...',
      slides: [
        {
          layout: 'title',
          title: 'Menyiapkan Slide Presentasi...',
          subtitle: 'Sedang menyusun materi presentasi secara interaktif...',
          presenter: 'Cakra AI'
        }
      ]
    };
  }

  // 4. Fallback: Parse format Markdown dengan pemisah '---' (bukan JSON)
  const sections = clean.split(/^---$/m).map(s => s.trim()).filter(Boolean);
  if (sections.length > 0) {
    const slides = sections.map((sec, idx) => {
      const rawLines = sec.split('\n').map(l => l.trim()).filter(Boolean);
      // Buang baris yang berupa artefak kurung kurawal atau JSON rusak
      const lines = rawLines.filter(l => !l.startsWith('{') && !l.startsWith('}') && !l.startsWith('"'));
      if (!lines.length) return null;

      let title = `Slide ${idx + 1}`;
      const bullets = [];
      let subtitle = '';

      for (const line of lines) {
        if (line.startsWith('# ')) {
          title = line.replace(/^#\s*/, '');
        } else if (line.startsWith('## ')) {
          if (idx === 0) subtitle = line.replace(/^##\s*/, '');
          else title = line.replace(/^##\s*/, '');
        } else if (line.startsWith('- ') || line.startsWith('* ')) {
          bullets.push(line.replace(/^[-*]\s*/, ''));
        } else if (line.startsWith('1. ') || line.startsWith('2. ') || line.startsWith('3. ')) {
          bullets.push(line.replace(/^[0-9]+\.\s*/, ''));
        } else if (!bullets.length && idx === 0 && !subtitle) {
          subtitle = line;
        }
      }

      if (idx === 0) {
        return {
          layout: 'title',
          title: title || 'Presentasi',
          subtitle: subtitle || 'Dokumen Ringkasan',
          presenter: 'Cakra AI'
        };
      }

      return {
        layout: bullets.length ? 'bullets' : 'content',
        title,
        bullets,
        content: bullets.length ? undefined : lines.slice(1).join(' ')
      };
    }).filter(Boolean);

    if (slides.length > 0) {
      return {
        title: slides[0]?.title || 'Presentasi',
        slides
      };
    }
  }

  // 5. Fallback Default
  return {
    title: 'Slide Presentasi',
    slides: [
      {
        layout: 'title',
        title: 'Presentasi Dokumen',
        subtitle: 'Dihasilkan oleh Cakra AI'
      }
    ]
  };
}

const SlideDeckViewer = ({ rawContent, darkMode = true, language = 'id' }) => {
  const t = translations[language]?.slideDeck || translations.id.slideDeck || {};
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [activeThemeKey, setActiveThemeKey] = useState(darkMode ? 'pindad-dark' : 'clean-light');

  const containerRef = useRef(null);

  // Sync theme with system darkMode prop if changed
  useEffect(() => {
    setActiveThemeKey(darkMode ? 'pindad-dark' : 'clean-light');
  }, [darkMode]);

  const deckData = useMemo(() => parseSlideData(rawContent), [rawContent]);
  const slides = deckData.slides || [];
  const totalSlides = slides.length;
  const theme = THEMES[activeThemeKey] || THEMES['pindad-dark'];

  // Safe current index clamp
  const safeCurrentIndex = Math.min(Math.max(0, currentSlide), Math.max(0, totalSlides - 1));
  const activeSlideData = slides[safeCurrentIndex] || {};

  // Navigasi Slide
  const goToNext = useCallback(() => {
    setCurrentSlide(prev => Math.min(prev + 1, totalSlides - 1));
  }, [totalSlides]);

  const goToPrev = useCallback(() => {
    setCurrentSlide(prev => Math.max(prev - 1, 0));
  }, []);

  // Keyboard Navigation Listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Hanya aktif jika fullscreen atau sedang fokus di dalam container
      if (isFullscreen) {
        if (e.key === 'ArrowRight' || e.key === 'Space' || e.key === 'PageDown') {
          e.preventDefault();
          goToNext();
        } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
          e.preventDefault();
          goToPrev();
        } else if (e.key === 'Escape') {
          setIsFullscreen(false);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, goToNext, goToPrev]);

  // Handle Fullscreen Toggle
  const toggleFullscreen = () => {
    if (!isFullscreen) {
      if (containerRef.current?.requestFullscreen) {
        containerRef.current.requestFullscreen().catch(() => {
          setIsFullscreen(true); // Fallback overlay mode
        });
      } else {
        setIsFullscreen(true);
      }
    } else {
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      setIsFullscreen(false);
    }
  };

  // Listen to browser native fullscreen change (e.g. user pressed Esc)
  useEffect(() => {
    const onFsChange = () => {
      if (!document.fullscreenElement) {
        setIsFullscreen(false);
      }
    };
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  // Salin Outline Slide ke Clipboard
  const handleCopyText = () => {
    let text = `# ${deckData.title || 'Presentasi'}\n\n`;
    slides.forEach((s, i) => {
      text += `--- Slide ${i + 1}: ${s.title || ''} ---\n`;
      if (s.subtitle) text += `${s.subtitle}\n`;
      if (s.bullets && Array.isArray(s.bullets)) {
        s.bullets.forEach(b => { text += `• ${b}\n`; });
      }
      if (s.content) text += `${s.content}\n`;
      if (s.highlight) text += `*Catatan: ${s.highlight}*\n`;
      text += '\n';
    });

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 📥 Ekspor ke File PowerPoint Asli (.PPTX) via PptxGenJS
  const handleExportPptx = async () => {
    if (isExporting || !slides.length) return;
    setIsExporting(true);

    try {
      const pres = new pptxgen();
      pres.layout = 'LAYOUT_16x9';
      pres.title = deckData.title || 'Presentasi Cakra AI';
      pres.author = 'Cakra AI Assistant';
      pres.company = 'PT Pindad';

      const accent = theme.accentHex;
      const isDarkTheme = theme.isDark;
      const bgColor = theme.bgSolid;
      const titleColor = isDarkTheme ? 'FFFFFF' : '0F172A';
      const bodyColor = isDarkTheme ? 'CBD5E1' : '334155';
      const cardFill = isDarkTheme ? '111E33' : 'F1F5F9';

      slides.forEach((s, idx) => {
        const slide = pres.addSlide();
        slide.background = { color: bgColor };

        // Footer watermarking
        slide.addText(`Slide ${idx + 1} of ${slides.length}  |  Dihasilkan oleh Cakra AI`, {
          x: 0.5,
          y: 7.0,
          w: '90%',
          h: 0.3,
          fontSize: 9,
          color: isDarkTheme ? '64748B' : '94A3B8',
          fontFace: 'Arial'
        });

        const layout = s.layout || (idx === 0 ? 'title' : 'bullets');

        if (layout === 'title') {
          // Layout Title / Cover
          slide.addText(s.title || deckData.title || 'Presentasi', {
            x: 0.8,
            y: 2.2,
            w: 11.5,
            h: 1.8,
            fontSize: 38,
            bold: true,
            color: titleColor,
            fontFace: 'Arial',
            align: 'left'
          });

          if (s.subtitle) {
            slide.addText(s.subtitle, {
              x: 0.8,
              y: 4.1,
              w: 11.5,
              h: 0.9,
              fontSize: 20,
              color: accent,
              fontFace: 'Arial',
              align: 'left'
            });
          }

          const presenterInfo = s.presenter || 'Divisi TI — PT Pindad';
          slide.addText(presenterInfo, {
            x: 0.8,
            y: 5.2,
            w: 11.5,
            h: 0.6,
            fontSize: 14,
            color: bodyColor,
            fontFace: 'Arial'
          });
        } 
        else if (layout === 'two_columns' || layout === 'split') {
          // Layout Two-Columns
          slide.addText(s.title || '', {
            x: 0.8,
            y: 0.6,
            w: 11.5,
            h: 0.9,
            fontSize: 26,
            bold: true,
            color: titleColor,
            fontFace: 'Arial'
          });

          // Kolom Kiri
          const leftTitle = s.left?.heading || 'Bagian 1';
          const leftItems = (s.left?.items || []).map(item => ({ text: item, options: { fontSize: 13, color: bodyColor, breakLine: true } }));
          slide.addShape(pres.ShapeType.rect, { x: 0.8, y: 1.6, w: 5.4, h: 4.8, fill: { color: cardFill }, line: { color: accent, width: 1 } });
          slide.addText(leftTitle, { x: 1.0, y: 1.8, w: 5.0, h: 0.5, fontSize: 18, bold: true, color: accent, fontFace: 'Arial' });
          if (leftItems.length) {
            slide.addText(leftItems, { x: 1.0, y: 2.4, w: 5.0, h: 3.8, fontFace: 'Arial', bullet: { type: 'bullet' } });
          }

          // Kolom Kanan
          const rightTitle = s.right?.heading || 'Bagian 2';
          const rightItems = (s.right?.items || []).map(item => ({ text: item, options: { fontSize: 13, color: bodyColor, breakLine: true } }));
          slide.addShape(pres.ShapeType.rect, { x: 6.6, y: 1.6, w: 5.4, h: 4.8, fill: { color: cardFill }, line: { color: accent, width: 1 } });
          slide.addText(rightTitle, { x: 6.8, y: 1.8, w: 5.0, h: 0.5, fontSize: 18, bold: true, color: accent, fontFace: 'Arial' });
          if (rightItems.length) {
            slide.addText(rightItems, { x: 6.8, y: 2.4, w: 5.0, h: 3.8, fontFace: 'Arial', bullet: { type: 'bullet' } });
          }
        }
        else if (layout === 'stats' || layout === 'metric') {
          // Layout Metric / Stats
          slide.addText(s.title || '', {
            x: 0.8,
            y: 0.6,
            w: 11.5,
            h: 0.9,
            fontSize: 26,
            bold: true,
            color: titleColor,
            fontFace: 'Arial'
          });

          const statNumber = s.stat || s.value || '100%';
          const statLabel = s.stat_label || s.subtitle || 'Capaian Kinerja';
          slide.addText(statNumber, {
            x: 0.8,
            y: 2.0,
            w: 11.5,
            h: 2.0,
            fontSize: 72,
            bold: true,
            color: accent,
            fontFace: 'Arial',
            align: 'center'
          });
          slide.addText(statLabel, {
            x: 0.8,
            y: 4.2,
            w: 11.5,
            h: 0.8,
            fontSize: 22,
            color: titleColor,
            fontFace: 'Arial',
            align: 'center'
          });
          if (s.highlight || s.description) {
            slide.addText(s.highlight || s.description, {
              x: 1.5,
              y: 5.2,
              w: 10.0,
              h: 1.2,
              fontSize: 14,
              color: bodyColor,
              fontFace: 'Arial',
              align: 'center'
            });
          }
        }
        else if (layout === 'quote' || layout === 'closing') {
          // Layout Quote / Closing
          slide.addText('“', {
            x: 0.8,
            y: 1.5,
            w: 11.5,
            h: 1.2,
            fontSize: 80,
            bold: true,
            color: accent,
            fontFace: 'Georgia',
            align: 'center'
          });
          slide.addText(s.quote || s.title || 'Terima Kasih', {
            x: 1.2,
            y: 2.8,
            w: 10.5,
            h: 2.0,
            fontSize: 24,
            italic: true,
            color: titleColor,
            fontFace: 'Arial',
            align: 'center'
          });
          if (s.author) {
            slide.addText(`— ${s.author}`, {
              x: 1.2,
              y: 5.0,
              w: 10.5,
              h: 0.6,
              fontSize: 16,
              bold: true,
              color: accent,
              fontFace: 'Arial',
              align: 'center'
            });
          }
        }
        else {
          // Default Layout: Bullets
          slide.addText(s.title || '', {
            x: 0.8,
            y: 0.6,
            w: 11.5,
            h: 0.9,
            fontSize: 26,
            bold: true,
            color: titleColor,
            fontFace: 'Arial'
          });

          // Accent line under title
          slide.addShape(pres.ShapeType.rect, {
            x: 0.8,
            y: 1.5,
            w: 2.5,
            h: 0.05,
            fill: { color: accent }
          });

          if (s.bullets && Array.isArray(s.bullets)) {
            const bulletItems = s.bullets.map(b => ({
              text: b,
              options: {
                fontSize: 15,
                color: bodyColor,
                breakLine: true,
                paraSpaceAfter: 12
              }
            }));

            slide.addText(bulletItems, {
              x: 0.8,
              y: 1.8,
              w: 11.2,
              h: 4.2,
              fontFace: 'Arial',
              bullet: { type: 'bullet' }
            });
          } else if (s.content) {
            slide.addText(s.content, {
              x: 0.8,
              y: 1.8,
              w: 11.2,
              h: 4.2,
              fontSize: 16,
              color: bodyColor,
              fontFace: 'Arial'
            });
          }

          if (s.highlight) {
            slide.addShape(pres.ShapeType.rect, {
              x: 0.8,
              y: 5.8,
              w: 11.2,
              h: 0.9,
              fill: { color: cardFill },
              line: { color: accent, width: 1 }
            });
            slide.addText(`💡 Catatan Kunci: ${s.highlight}`, {
              x: 1.0,
              y: 5.9,
              w: 10.8,
              h: 0.7,
              fontSize: 12,
              italic: true,
              color: accent,
              fontFace: 'Arial'
            });
          }
        }
      });

      const safeTitle = (deckData.title || 'Presentasi_Cakra_AI')
        .replace(/[^a-zA-Z0-9_\-]/g, '_')
        .slice(0, 40);
      await pres.writeFile({ fileName: `${safeTitle}.pptx` });
    } catch (err) {
      console.error('[SLIDE_VIEWER] Gagal ekspor PPTX:', err);
      alert('Maaf, terjadi kesalahan saat mengekspor slide ke PowerPoint.');
    } finally {
      setIsExporting(false);
    }
  };

  if (!slides.length) {
    return (
      <div className={`p-4 rounded-xl border text-sm text-center ${darkMode ? 'bg-slate-900 border-slate-800 text-slate-400' : 'bg-slate-50 border-slate-200 text-slate-600'}`}>
        Format slide tidak memuat data yang valid.
      </div>
    );
  }

  // ── Render Konten Berdasarkan Layout Slide Aktif ──
  const renderSlideContent = () => {
    const s = activeSlideData;
    const layout = s.layout || (safeCurrentIndex === 0 ? 'title' : 'bullets');

    switch (layout) {
      case 'title':
        return (
          <div className="flex flex-col justify-center items-start h-full px-6 sm:px-12 py-6 text-left">
            <div 
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-4 border"
              style={{ 
                backgroundColor: theme.cardBg, 
                borderColor: theme.cardBorder,
                color: theme.accentColor 
              }}
            >
              <Presentation size={13} />
              <span>{s.category || 'Executive Presentation'}</span>
            </div>
            <h1 
              className="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight leading-tight mb-4"
              style={{ color: theme.titleColor }}
            >
              {s.title || deckData.title}
            </h1>
            {s.subtitle && (
              <p 
                className="text-base sm:text-xl font-medium mb-6 leading-relaxed max-w-2xl"
                style={{ color: theme.accentColor }}
              >
                {s.subtitle}
              </p>
            )}
            <div className="mt-auto pt-4 flex flex-wrap items-center gap-4 text-xs sm:text-sm" style={{ color: theme.textMuted }}>
              <span className="font-semibold" style={{ color: theme.textColor }}>
                {s.presenter || 'Divisi TI — PT Pindad'}
              </span>
              <span>•</span>
              <span>{s.date || new Date().toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
            </div>
          </div>
        );

      case 'two_columns':
      case 'split':
        return (
          <div className="flex flex-col h-full px-6 sm:px-10 py-5">
            <div className="mb-4">
              <h2 className="text-xl sm:text-2xl font-bold" style={{ color: theme.titleColor }}>
                {s.title}
              </h2>
              <div className="h-0.5 w-16 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4 flex-1 overflow-y-auto">
              {/* Kolom Kiri */}
              <div 
                className="p-4 rounded-xl border flex flex-col"
                style={{ 
                  backgroundColor: theme.cardBg, 
                  borderColor: theme.cardBorder 
                }}
              >
                <h3 className="font-bold text-sm sm:text-base mb-2.5 flex items-center gap-2" style={{ color: theme.accentColor }}>
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: theme.accentColor }} />
                  {s.left?.heading || 'Bagian 1'}
                </h3>
                <ul className="space-y-2 text-xs sm:text-sm flex-1" style={{ color: theme.textColor }}>
                  {(s.left?.items || []).map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="opacity-60">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Kolom Kanan */}
              <div 
                className="p-4 rounded-xl border flex flex-col"
                style={{ 
                  backgroundColor: theme.cardBg, 
                  borderColor: theme.cardBorder 
                }}
              >
                <h3 className="font-bold text-sm sm:text-base mb-2.5 flex items-center gap-2" style={{ color: theme.accentColor }}>
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: theme.accentColor }} />
                  {s.right?.heading || 'Bagian 2'}
                </h3>
                <ul className="space-y-2 text-xs sm:text-sm flex-1" style={{ color: theme.textColor }}>
                  {(s.right?.items || []).map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="opacity-60">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        );

      case 'stats':
      case 'metric':
        return (
          <div className="flex flex-col justify-center items-center h-full px-6 sm:px-12 py-6 text-center">
            <h2 className="text-lg sm:text-xl font-bold mb-4" style={{ color: theme.titleColor }}>
              {s.title}
            </h2>
            <div 
              className="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight mb-3"
              style={{ color: theme.accentColor }}
            >
              {s.stat || s.value || '100%'}
            </div>
            <p className="text-base sm:text-xl font-semibold mb-4" style={{ color: theme.titleColor }}>
              {s.stat_label || s.subtitle}
            </p>
            {(s.highlight || s.description) && (
              <div 
                className="p-3 sm:p-4 rounded-xl border max-w-lg text-xs sm:text-sm leading-relaxed"
                style={{ 
                  backgroundColor: theme.cardBg, 
                  borderColor: theme.cardBorder,
                  color: theme.textColor 
                }}
              >
                {s.highlight || s.description}
              </div>
            )}
          </div>
        );

      case 'quote':
      case 'closing':
        return (
          <div className="flex flex-col justify-center items-center h-full px-6 sm:px-14 py-6 text-center">
            <span className="text-5xl font-serif mb-2 opacity-50" style={{ color: theme.accentColor }}>
              “
            </span>
            <p 
              className="text-lg sm:text-2xl font-medium italic leading-relaxed mb-4 max-w-2xl"
              style={{ color: theme.titleColor }}
            >
              {s.quote || s.title || 'Terima Kasih'}
            </p>
            {s.author && (
              <span className="text-sm sm:text-base font-semibold" style={{ color: theme.accentColor }}>
                — {s.author}
              </span>
            )}
            {s.subtext && (
              <p className="text-xs sm:text-sm mt-3" style={{ color: theme.textMuted }}>
                {s.subtext}
              </p>
            )}
          </div>
        );

      case 'bullets':
      default:
        return (
          <div className="flex flex-col h-full px-6 sm:px-10 py-5">
            <div className="mb-4">
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: theme.titleColor }}>
                {s.title}
              </h2>
              <div className="h-0.5 w-20 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
            </div>

            <div className="flex-1 flex flex-col justify-center overflow-y-auto">
              {s.bullets && Array.isArray(s.bullets) && s.bullets.length > 0 ? (
                <div className="space-y-2.5 sm:space-y-3.5">
                  {s.bullets.map((bullet, idx) => (
                    <div 
                      key={idx}
                      className="p-3 rounded-lg border flex items-start gap-3 transition-all hover:translate-x-1"
                      style={{ 
                        backgroundColor: theme.cardBg, 
                        borderColor: theme.cardBorder 
                      }}
                    >
                      <div 
                        className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-bold mt-0.5"
                        style={{ backgroundColor: theme.accentColor, color: theme.isDark ? '#071526' : '#FFFFFF' }}
                      >
                        {idx + 1}
                      </div>
                      <p className="text-xs sm:text-sm leading-relaxed" style={{ color: theme.textColor }}>
                        {bullet}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm leading-relaxed" style={{ color: theme.textColor }}>
                  {s.content}
                </div>
              )}
            </div>

            {s.highlight && (
              <div 
                className="mt-3 p-2.5 rounded-lg border flex items-center gap-2 text-xs"
                style={{ 
                  backgroundColor: theme.cardBg, 
                  borderColor: theme.cardBorder,
                  color: theme.accentColor 
                }}
              >
                <Sparkles size={14} className="flex-shrink-0" />
                <span className="font-medium italic truncate">{s.highlight}</span>
              </div>
            )}
          </div>
        );
    }
  };

  return (
    <div 
      ref={containerRef}
      className={`my-4 rounded-2xl overflow-hidden shadow-2xl border transition-all duration-300 flex flex-col ${
        isFullscreen 
          ? 'fixed inset-0 z-[9999] w-screen h-screen rounded-none' 
          : 'w-full max-w-3xl mx-auto border-slate-700/40'
      }`}
      style={{
        background: theme.bg,
        boxShadow: isFullscreen ? 'none' : '0 20px 40px -15px rgba(0, 0, 0, 0.5)'
      }}
    >
      {/* ── Top Bar Toolbar ── */}
      <div 
        className="flex items-center justify-between px-3.5 sm:px-5 py-2.5 border-b backdrop-blur-md"
        style={{ 
          borderColor: theme.cardBorder,
          backgroundColor: theme.isDark ? 'rgba(0,0,0,0.3)' : 'rgba(255,255,255,0.6)'
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div 
            className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 shadow-inner"
            style={{ backgroundColor: theme.accentColor, color: theme.isDark ? '#071526' : '#FFFFFF' }}
          >
            <Presentation size={15} />
          </div>
          <div className="min-w-0">
            <span className="text-xs sm:text-sm font-bold truncate block" style={{ color: theme.titleColor }}>
              {deckData.title || 'Slide Presentasi'}
            </span>
            <span className="text-[10px] hidden sm:block opacity-60" style={{ color: theme.textMuted }}>
              Tekan panah ← / → di keyboard untuk navigasi
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          {/* Theme Selector Pill */}
          <select
            value={activeThemeKey}
            onChange={(e) => setActiveThemeKey(e.target.value)}
            className="text-[11px] font-medium px-2 py-1 rounded-md border bg-transparent cursor-pointer outline-none hidden sm:block"
            style={{ 
              color: theme.textColor, 
              borderColor: theme.cardBorder,
              backgroundColor: theme.cardBg 
            }}
            title={t.changeTheme || "Ganti Tema Warna"}
          >
            <option value="pindad-dark" className="text-slate-900 bg-white">Pindad Navy</option>
            <option value="modern-dark" className="text-slate-900 bg-white">Modern Slate</option>
            <option value="clean-light" className="text-slate-900 bg-white">Clean Light</option>
          </select>

          {/* Copy Outline Button */}
          <button
            onClick={handleCopyText}
            className="p-1.5 rounded-lg border transition-all text-xs flex items-center gap-1"
            style={{ 
              color: theme.textColor, 
              borderColor: theme.cardBorder,
              backgroundColor: theme.cardBg 
            }}
            title={t.copySlide || "Salin teks slide"}
          >
            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
            <span className="hidden md:inline text-[11px]">{copied ? (t.slideCopied || 'Tersalin') : (t.copySlide || 'Salin')}</span>
          </button>

          {/* Download PPTX Button */}
          <button
            onClick={handleExportPptx}
            disabled={isExporting}
            className="px-2.5 py-1.5 rounded-lg border font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
            style={{ 
              backgroundColor: theme.accentColor, 
              color: theme.isDark ? '#071526' : '#FFFFFF',
              borderColor: 'transparent'
            }}
            title={t.downloadPptx || "Download PowerPoint (.pptx)"}
          >
            <Download size={14} />
            <span className="text-[11px]">{isExporting ? 'Mengekspor...' : 'PPTX'}</span>
          </button>

          {/* Fullscreen Toggle Button */}
          <button
            onClick={toggleFullscreen}
            className="p-1.5 rounded-lg border transition-all"
            style={{ 
              color: theme.textColor, 
              borderColor: theme.cardBorder,
              backgroundColor: theme.cardBg 
            }}
            title={isFullscreen ? (t.exitFullscreen || 'Keluar Fullscreen (Esc)') : (t.fullscreenMode || 'Mode Presentasi Layar Penuh')}
          >
            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>

      {/* ── Main Canvas (16:9 Presentation Aspect Ratio) ── */}
      <div 
        className={`relative w-full select-none overflow-hidden transition-all duration-300 ${
          isFullscreen 
            ? 'flex-1 flex items-center justify-center p-4 sm:p-8' 
            : 'aspect-[16/9] min-h-[300px]'
        }`}
      >
        <div 
          className={`w-full h-full relative transition-all duration-300 ease-out ${
            isFullscreen ? 'max-w-6xl max-h-[85vh] aspect-[16/9] rounded-2xl shadow-2xl border' : ''
          }`}
          style={{
            background: isFullscreen ? theme.bg : 'transparent',
            borderColor: isFullscreen ? theme.cardBorder : 'transparent'
          }}
        >
          {renderSlideContent()}
        </div>
      </div>

      {/* ── Bottom Navigation Bar ── */}
      <div 
        className="flex items-center justify-between px-4 sm:px-6 py-2.5 border-t backdrop-blur-md"
        style={{ 
          borderColor: theme.cardBorder,
          backgroundColor: theme.isDark ? 'rgba(0,0,0,0.3)' : 'rgba(255,255,255,0.6)'
        }}
      >
        {/* Tombol Prev */}
        <button
          onClick={goToPrev}
          disabled={safeCurrentIndex <= 0}
          className="p-1.5 sm:px-3 sm:py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1 transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:bg-white/10"
          style={{ 
            color: theme.textColor, 
            borderColor: theme.cardBorder 
          }}
          title={t.prevSlide || "Slide Sebelumnya (←)"}
        >
          <ChevronLeft size={16} />
          <span className="hidden sm:inline">{t.prevSlide ? t.prevSlide.replace(/\s*\(.*\)/, '') : "Sebelumnya"}</span>
        </button>

        {/* Slide Counter & Interactive Dots */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {slides.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentSlide(idx)}
                className={`transition-all rounded-full ${
                  idx === safeCurrentIndex 
                    ? 'w-6 h-2 shadow-sm' 
                    : 'w-2 h-2 opacity-40 hover:opacity-80'
                }`}
                style={{ 
                  backgroundColor: idx === safeCurrentIndex ? theme.accentColor : theme.textMuted 
                }}
                title={t.goToSlide ? t.goToSlide.replace('{number}', idx + 1) : `Pindah ke Slide ${idx + 1}`}
              />
            ))}
          </div>

          <span 
            className="text-xs font-semibold tabular-nums px-2 py-0.5 rounded"
            style={{ 
              backgroundColor: theme.cardBg, 
              color: theme.textColor 
            }}
          >
            {safeCurrentIndex + 1} / {totalSlides}
          </span>
        </div>

        {/* Tombol Next */}
        <button
          onClick={goToNext}
          disabled={safeCurrentIndex >= totalSlides - 1}
          className="p-1.5 sm:px-3 sm:py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1 transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:bg-white/10"
          style={{ 
            color: theme.textColor, 
            borderColor: theme.cardBorder 
          }}
          title={t.nextSlide || "Slide Selanjutnya (→)"}
        >
          <span className="hidden sm:inline">{t.nextSlide ? t.nextSlide.replace(/\s*\(.*\)/, '') : "Selanjutnya"}</span>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};

export default SlideDeckViewer;
