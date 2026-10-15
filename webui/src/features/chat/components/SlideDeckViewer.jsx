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
import { getApiBase } from '../../../services/endpoints';

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
  },
  'emerald-tactical': {
    id: 'emerald-tactical',
    name: 'Tactical Emerald',
    bg: 'linear-gradient(135deg, #062318 0%, #0d3829 50%, #062318 100%)',
    bgSolid: '062318',
    cardBg: 'rgba(255, 255, 255, 0.05)',
    cardBorder: 'rgba(52, 211, 153, 0.25)',
    titleColor: '#F0FDF4',
    accentColor: '#34D399',
    accentHex: '34D399',
    textColor: '#E2E8F0',
    textMuted: '#86EFAC',
    isDark: true
  }
};

function sanitizeJsonString(str) {
  if (!str || typeof str !== 'string') return str;
  // Perbaiki newline / carriage return / tab yang belum di-escape di dalam string literal JSON
  return str.replace(/"([^"\\]*(?:\\.[^"\\]*)*)"/g, (match) => {
    return match
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
  });
}

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

  // 1. Coba parse sebagai JSON murni (dengan fallback sanitasi control character)
  try {
    const parsed = JSON.parse(clean);
    if (parsed && Array.isArray(parsed.slides) && parsed.slides.length > 0) {
      return parsed;
    }
  } catch (_) {
    try {
      const sanitized = sanitizeJsonString(clean);
      const parsed = JSON.parse(sanitized);
      if (parsed && Array.isArray(parsed.slides) && parsed.slides.length > 0) {
        return parsed;
      }
    } catch (_) {}
  }

  // 2. Cari blok JSON di dalam teks jika terbungkus karakter lain
  try {
    const firstBrace = clean.indexOf('{');
    const lastBrace = clean.lastIndexOf('}');
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      const jsonSubstring = clean.substring(firstBrace, lastBrace + 1);
      try {
        const parsed = JSON.parse(jsonSubstring);
        if (parsed && Array.isArray(parsed.slides) && parsed.slides.length > 0) {
          return parsed;
        }
      } catch (_) {
        const parsed = JSON.parse(sanitizeJsonString(jsonSubstring));
        if (parsed && Array.isArray(parsed.slides) && parsed.slides.length > 0) {
          return parsed;
        }
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
            const chunkStr = searchArea.substring(start, i + 1);
            let candidate = null;
            try {
              candidate = JSON.parse(chunkStr);
            } catch (_) {
              try {
                candidate = JSON.parse(sanitizeJsonString(chunkStr));
              } catch (_) {}
            }
            if (candidate && (candidate.title || candidate.layout || candidate.bullets || candidate.heading)) {
              slideObjects.push(candidate);
            }
            start = -1;
          }
        }
      }
    }

    if (slideObjects.length > 0) {
      const titleMatch = clean.match(/"title"\s*:\s*"([^"]+)"/);
      let extractedThemeStyle = null;
      try {
        const themeMatch = clean.match(/"theme_style"\s*:\s*(\{[\s\S]*?\n\s*\})/);
        if (themeMatch) extractedThemeStyle = JSON.parse(sanitizeJsonString(themeMatch[1]));
      } catch (_) {}

      return {
        title: titleMatch ? titleMatch[1] : 'Presentasi Eksekutif',
        theme_style: extractedThemeStyle,
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
  const containerRef = useRef(null);

  const deckData = useMemo(() => parseSlideData(rawContent), [rawContent]);
  const slides = deckData.slides || [];
  const totalSlides = slides.length;

  // Tema Visual Dinamis (Prioritas 1: Langsung dari hasil rancangan AI / PPT Master)
  const theme = useMemo(() => {
    if (deckData?.theme_style && typeof deckData.theme_style === 'object') {
      const ts = deckData.theme_style;
      const isDark = ts.is_dark !== false;
      const bgHex = ts.bg_hex || (isDark ? '#0f172a' : '#f8fafc');
      const cardBgHex = ts.card_bg_hex || (isDark ? 'rgba(255, 255, 255, 0.05)' : '#FFFFFF');
      const accentHex = ts.accent_hex || (isDark ? '#38BDF8' : '#0284C7');
      const titleHex = ts.title_hex || (isDark ? '#FFFFFF' : '#0F172A');
      const textHex = ts.text_hex || (isDark ? '#CBD5E1' : '#334155');

      return {
        id: 'ai-dynamic',
        name: ts.name || 'AI Designed Style',
        bg: ts.bg_gradient || `linear-gradient(135deg, ${bgHex} 0%, ${cardBgHex} 100%)`,
        bgSolid: bgHex.replace('#', ''),
        cardBg: cardBgHex,
        cardBorder: ts.card_border_hex || (accentHex ? `${accentHex}33` : (isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)')),
        titleColor: titleHex,
        accentColor: accentHex,
        accentHex: accentHex.replace('#', ''),
        textColor: textHex,
        textMuted: ts.muted_hex || (isDark ? '#94A3B8' : '#64748B'),
        isDark: isDark,
        backdropEffect: ts.backdrop_effect || (ts.visual_style?.includes('grid') ? 'cyber_grid' : 'dots_particles')
      };
    }

    // Fallback tema modern netral
    return darkMode ? {
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
    } : {
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
    };
  }, [deckData, darkMode]);

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

  // 📥 Ekspor ke File PowerPoint Asli (.PPTX) via PPT Master / PptxGenJS
  const handleExportPptx = async () => {
    if (isExporting || !slides.length) return;

    // 🚀 Prioritaskan file .pptx resmi hasil kompilasi server PPT Master jika tersedia
    if (deckData.download_url) {
      const link = document.createElement('a');
      const rawUrl = deckData.download_url;
      link.href = rawUrl.startsWith('http') ? rawUrl : `${getApiBase()}${rawUrl.startsWith('/') ? '' : '/'}${rawUrl}`;
      link.download = deckData.filename || `${(deckData.title || 'presentasi').replace(/\s+/g, '_')}.pptx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return;
    }

    setIsExporting(true);

    try {
      const pres = new pptxgen();
      pres.layout = 'LAYOUT_16x9';
      pres.title = deckData.title || 'Presentasi Cakra AI';
      pres.author = 'Cakra AI Assistant';
      pres.company = 'PT Pindad (Persero)';

      const accent = theme.accentHex;
      const isDarkTheme = theme.isDark;
      const bgColor = theme.bgSolid;
      const titleColor = isDarkTheme ? 'FFFFFF' : '0F172A';
      const bodyColor = isDarkTheme ? 'CBD5E1' : '334155';
      const mutedColor = isDarkTheme ? '94A3B8' : '64748B';
      const cardFill = isDarkTheme ? '0D2542' : 'FFFFFF';
      const cardSubtle = isDarkTheme ? '0A1D34' : 'F8FAFC';
      const separatorColor = isDarkTheme ? '1E3A5F' : 'E2E8F0';

      slides.forEach((s, idx) => {
        const slide = pres.addSlide();
        slide.background = { color: bgColor };

        const layout = s.layout || (idx === 0 ? 'title' : 'bullets');

        if (layout === 'title') {
          // ── LAYOUT COVER / TITLE (PPT MASTER EXECUTIVE) ──
          const kickerText = s.kicker || 'PAPARAN EKSEKUTIF CAKRA AI';
          slide.addShape(pres.ShapeType.roundRect, {
            x: 1.0,
            y: 1.4,
            w: 3.8,
            h: 0.38,
            fill: { color: cardFill },
            line: { color: accent, width: 1 }
          });
          slide.addText(kickerText.toUpperCase(), {
            x: 1.0,
            y: 1.4,
            w: 3.8,
            h: 0.38,
            fontSize: 10,
            bold: true,
            color: accent,
            fontFace: 'Arial',
            align: 'center',
            valign: 'middle'
          });

          slide.addText(s.title || deckData.title || 'Presentasi Eksekutif', {
            x: 1.0,
            y: 2.0,
            w: 11.3,
            h: 1.6,
            fontSize: 36,
            bold: true,
            color: titleColor,
            fontFace: 'Arial',
            align: 'left',
            valign: 'top'
          });

          if (s.subtitle) {
            slide.addText(s.subtitle, {
              x: 1.0,
              y: 3.7,
              w: 11.3,
              h: 0.8,
              fontSize: 18,
              color: accent,
              fontFace: 'Arial',
              align: 'left',
              valign: 'top'
            });
          }

          // Accent Divider Line
          slide.addShape(pres.ShapeType.rect, {
            x: 1.0,
            y: 4.6,
            w: 2.5,
            h: 0.04,
            fill: { color: accent }
          });

          // Presenter Metadata Container Card
          slide.addShape(pres.ShapeType.roundRect, {
            x: 1.0,
            y: 4.9,
            w: 11.3,
            h: 1.5,
            fill: { color: cardFill },
            line: { color: separatorColor, width: 1 }
          });

          const presenterInfo = s.presenter || 'CAKRA AI • Divisi Sistem Informasi & Teknologi';
          const orgInfo = s.organization || 'PT Pindad (Persero) • Arsitektur Sistem Terpadu';
          slide.addText(presenterInfo, {
            x: 1.3,
            y: 5.15,
            w: 10.7,
            h: 0.45,
            fontSize: 14,
            bold: true,
            color: titleColor,
            fontFace: 'Arial',
            valign: 'top'
          });
          slide.addText(orgInfo, {
            x: 1.3,
            y: 5.65,
            w: 10.7,
            h: 0.4,
            fontSize: 11,
            color: mutedColor,
            fontFace: 'Arial',
            valign: 'top'
          });
        } 
        else {
          // ── HEADER SLIDE UMUM (Kicker, Title, Subtitle, Divider) ──
          const kicker = s.kicker || 'STRATEGIS & ARSITEKTUR';
          slide.addText(kicker.toUpperCase(), {
            x: 0.8,
            y: 0.4,
            w: 11.5,
            h: 0.3,
            fontSize: 10,
            bold: true,
            color: accent,
            fontFace: 'Arial'
          });

          slide.addText(s.title || '', {
            x: 0.8,
            y: 0.7,
            w: 11.5,
            h: 0.65,
            fontSize: 24,
            bold: true,
            color: titleColor,
            fontFace: 'Arial',
            valign: 'top'
          });

          if (s.subtitle) {
            slide.addText(s.subtitle, {
              x: 0.8,
              y: 1.35,
              w: 11.5,
              h: 0.4,
              fontSize: 13,
              color: mutedColor,
              fontFace: 'Arial',
              valign: 'top'
            });
          }

          // Accent line under title
          slide.addShape(pres.ShapeType.rect, {
            x: 0.8,
            y: 1.85,
            w: 1.8,
            h: 0.03,
            fill: { color: accent }
          });

          if (layout === 'two_columns' || layout === 'split') {
            // Kolom Kiri
            const leftTitle = s.left?.heading || 'Pilar A';
            const leftItems = (s.left?.items || []).map(item => ({ text: item, options: { fontSize: 12, color: bodyColor, breakLine: true, paraSpaceAfter: 6 } }));
            slide.addShape(pres.ShapeType.roundRect, { x: 0.8, y: 2.05, w: 5.6, h: 4.65, fill: { color: cardFill }, line: { color: accent, width: 1 } });
            slide.addText(leftTitle, { x: 1.05, y: 2.25, w: 5.1, h: 0.5, fontSize: 16, bold: true, color: accent, fontFace: 'Arial', valign: 'top' });
            if (leftItems.length) {
              slide.addText(leftItems, { x: 1.05, y: 2.85, w: 5.1, h: 3.6, fontFace: 'Arial', bullet: { type: 'bullet' }, valign: 'top' });
            }

            // Kolom Kanan
            const rightTitle = s.right?.heading || 'Pilar B';
            const rightItems = (s.right?.items || []).map(item => ({ text: item, options: { fontSize: 12, color: bodyColor, breakLine: true, paraSpaceAfter: 6 } }));
            slide.addShape(pres.ShapeType.roundRect, { x: 6.7, y: 2.05, w: 5.6, h: 4.65, fill: { color: cardFill }, line: { color: accent, width: 1 } });
            slide.addText(rightTitle, { x: 6.95, y: 2.25, w: 5.1, h: 0.5, fontSize: 16, bold: true, color: accent, fontFace: 'Arial', valign: 'top' });
            if (rightItems.length) {
              slide.addText(rightItems, { x: 6.95, y: 2.85, w: 5.1, h: 3.6, fontFace: 'Arial', bullet: { type: 'bullet' }, valign: 'top' });
            }
          }
          else if (layout === 'stats' || layout === 'metric') {
            // ── LAYOUT STATS / KPI CARDS GRID ──
            const rawStats = s.stats || [
              { value: s.stat || s.value || '99.98%', label: s.stat_label || 'Ketersediaan Sistem', desc: s.highlight || 'Target SLA Uptime Produksi' },
              { value: '4.5x', label: 'Frekuensi Deployment', desc: 'Siklus rilis independen' },
              { value: '< 45ms', label: 'Latensi Respon (P99)', desc: 'Throughput komunikasi optimal' }
            ];
            const numStats = Math.min(rawStats.length, 3);
            const totalW = 11.5;
            const gap = 0.4;
            const statW = (totalW - (gap * (numStats - 1))) / numStats;

            rawStats.slice(0, 3).forEach((stat, stIdx) => {
              const statX = 0.8 + stIdx * (statW + gap);
              slide.addShape(pres.ShapeType.roundRect, {
                x: statX,
                y: 2.05,
                w: statW,
                h: 2.25,
                fill: { color: cardFill },
                line: { color: accent, width: 1 }
              });

              slide.addText(`INDIKATOR ${stIdx + 1}`, {
                x: statX + 0.2,
                y: 2.2,
                w: statW - 0.4,
                h: 0.3,
                fontSize: 9.5,
                bold: true,
                color: accent,
                fontFace: 'Arial',
                align: 'center',
                valign: 'top'
              });

              slide.addText(String(stat.value || stat.stat || ''), {
                x: statX + 0.2,
                y: 2.5,
                w: statW - 0.4,
                h: 0.85,
                fontSize: 38,
                bold: true,
                color: accent,
                fontFace: 'Arial',
                align: 'center',
                valign: 'middle'
              });

              slide.addText(stat.label || stat.stat_label || '', {
                x: statX + 0.2,
                y: 3.35,
                w: statW - 0.4,
                h: 0.45,
                fontSize: 14,
                bold: true,
                color: titleColor,
                fontFace: 'Arial',
                align: 'center',
                valign: 'top'
              });

              if (stat.desc || stat.highlight) {
                slide.addText(stat.desc || stat.highlight, {
                  x: statX + 0.2,
                  y: 3.8,
                  w: statW - 0.4,
                  h: 0.4,
                  fontSize: 10.5,
                  color: mutedColor,
                  fontFace: 'Arial',
                  align: 'center',
                  valign: 'top'
                });
              }
            });

            // Strategic Impact Card di Bawah Kartu KPI
            slide.addShape(pres.ShapeType.roundRect, {
              x: 0.8,
              y: 4.55,
              w: 11.5,
              h: 2.1,
              fill: { color: cardFill },
              line: { color: separatorColor, width: 1 }
            });
            slide.addText('Analisis Capaian & Dampak Strategis', {
              x: 1.1,
              y: 4.75,
              w: 10.9,
              h: 0.4,
              fontSize: 15,
              bold: true,
              color: titleColor,
              fontFace: 'Arial',
              valign: 'top'
            });
            const impactTxt = s.takeaway || s.highlight || '🎯 Target performa diukur secara berkala demi menjamin keandalan sistem dan efisiensi operasional lintas divisi.';
            slide.addText(impactTxt, {
              x: 1.1,
              y: 5.15,
              w: 10.9,
              h: 0.5,
              fontSize: 12,
              color: accent,
              fontFace: 'Arial',
              valign: 'top'
            });
            slide.addText('•  Peningkatan skalabilitas menjamin stabilitas saat lonjakan pemrosesan data.', {
              x: 1.1,
              y: 5.75,
              w: 10.9,
              h: 0.35,
              fontSize: 11,
              color: bodyColor,
              fontFace: 'Arial',
              valign: 'top'
            });
            slide.addText('•  Monitoring real-time mempercepat respon insiden teknis hingga 70%.', {
              x: 1.1,
              y: 6.1,
              w: 10.9,
              h: 0.35,
              fontSize: 11,
              color: bodyColor,
              fontFace: 'Arial',
              valign: 'top'
            });
          }
          else if (layout === 'cards_grid' || layout === 'grid' || layout === 'pillars') {
            // ── LAYOUT CARDS GRID (PPT MASTER PILLARS) ──
            const rawCards = s.cards || s.items || [];
            const cardCount = Math.min(Math.max(rawCards.length, 1), 4);
            const totalWidth = 11.5;
            const cardGap = 0.35;
            const cardWidth = (totalWidth - (cardGap * (cardCount - 1))) / cardCount;

            rawCards.slice(0, 4).forEach((card, cIdx) => {
              const cardX = 0.8 + cIdx * (cardWidth + cardGap);
              const cBadge = card.badge || `PILAR 0${cIdx + 1}`;
              const cTitle = card.title || card.heading || `Pilar ${cIdx + 1}`;
              const cDesc = card.desc || card.description || card.text || (typeof card === 'string' ? card : '');
              const cBullets = card.bullets || [];

              // Card Container
              slide.addShape(pres.ShapeType.roundRect, {
                x: cardX,
                y: 2.05,
                w: cardWidth,
                h: 4.65,
                fill: { color: cardFill },
                line: { color: accent, width: 1 }
              });

              // Badge
              slide.addText(cBadge.toUpperCase(), {
                x: cardX + 0.25,
                y: 2.25,
                w: cardWidth - 0.5,
                h: 0.3,
                fontSize: 10,
                bold: true,
                color: accent,
                fontFace: 'Arial',
                valign: 'top'
              });

              // Title
              slide.addText(cTitle, {
                x: cardX + 0.25,
                y: 2.55,
                w: cardWidth - 0.5,
                h: 0.65,
                fontSize: 16,
                bold: true,
                color: titleColor,
                fontFace: 'Arial',
                valign: 'top'
              });

              // Description
              if (cDesc) {
                slide.addText(cDesc, {
                  x: cardX + 0.25,
                  y: 3.25,
                  w: cardWidth - 0.5,
                  h: 1.1,
                  fontSize: 11.5,
                  color: bodyColor,
                  fontFace: 'Arial',
                  valign: 'top'
                });
              }

              // Deliverables Bullets
              if (cBullets.length > 0) {
                const bulletItems = cBullets.map(b => ({
                  text: b,
                  options: { fontSize: 10.5, color: mutedColor, breakLine: true, paraSpaceAfter: 4 }
                }));
                slide.addText(bulletItems, {
                  x: cardX + 0.25,
                  y: 4.45,
                  w: cardWidth - 0.5,
                  h: 2.1,
                  fontFace: 'Arial',
                  bullet: { type: 'bullet' },
                  valign: 'top'
                });
              }
            });
          }
          else if (layout === 'timeline' || layout === 'roadmap' || layout === 'milestone') {
            // ── LAYOUT TIMELINE / ROADMAP (PPT MASTER SIGNATURE) ──
            const rawSteps = s.steps || s.milestones || s.items || [];
            const stepCount = Math.min(Math.max(rawSteps.length, 1), 4);
            const totalWidth = 11.5;
            const stepGap = 0.45;
            const stepWidth = (totalWidth - (stepGap * (stepCount - 1))) / stepCount;

            // 1. Horizontal Flow Line Across Stages
            const firstNodeX = 0.8 + (stepWidth / 2.0);
            const lastNodeX = 0.8 + ((stepCount - 1) * (stepWidth + stepGap)) + (stepWidth / 2.0);
            const flowWidth = lastNodeX - firstNodeX;
            if (flowWidth > 0) {
              slide.addShape(pres.ShapeType.rect, {
                x: firstNodeX,
                y: 2.15,
                w: flowWidth,
                h: 0.04,
                fill: { color: accent }
              });
            }

            // 2. Stage Cards & Nodes
            rawSteps.slice(0, 4).forEach((step, sIdx) => {
              const stepX = 0.8 + sIdx * (stepWidth + stepGap);
              const nodeX = stepX + (stepWidth / 2.0);
              const sPhase = step.phase || step.step || `TAHAP 0${sIdx + 1}`;
              const sTitle = step.title || step.heading || `Langkah ${sIdx + 1}`;
              const sDesc = step.desc || step.description || step.text || (typeof step === 'string' ? step : '');
              const sBullets = step.bullets || [];

              // Step Node Circle on Flow Line
              slide.addShape(pres.ShapeType.roundRect, {
                x: nodeX - 0.28,
                y: 1.98,
                w: 0.56,
                h: 0.36,
                fill: { color: accent },
                line: { color: accent, width: 1 }
              });
              slide.addText(String(sIdx + 1), {
                x: nodeX - 0.28,
                y: 1.98,
                w: 0.56,
                h: 0.36,
                fontSize: 11,
                bold: true,
                color: isDarkTheme ? '071526' : 'FFFFFF',
                fontFace: 'Arial',
                align: 'center',
                valign: 'middle'
              });

              // Step Card Container
              slide.addShape(pres.ShapeType.roundRect, {
                x: stepX,
                y: 2.45,
                w: stepWidth,
                h: 3.65,
                fill: { color: cardFill },
                line: { color: accent, width: 1 }
              });

              // Phase Tag
              slide.addText(sPhase.toUpperCase(), {
                x: stepX + 0.22,
                y: 2.65,
                w: stepWidth - 0.44,
                h: 0.3,
                fontSize: 10,
                bold: true,
                color: accent,
                fontFace: 'Arial',
                valign: 'top'
              });

              // Title
              slide.addText(sTitle, {
                x: stepX + 0.22,
                y: 2.95,
                w: stepWidth - 0.44,
                h: 0.65,
                fontSize: 15,
                bold: true,
                color: titleColor,
                fontFace: 'Arial',
                valign: 'top'
              });

              // Description
              if (sDesc) {
                slide.addText(sDesc, {
                  x: stepX + 0.22,
                  y: 3.65,
                  w: stepWidth - 0.44,
                  h: 0.95,
                  fontSize: 11.5,
                  color: bodyColor,
                  fontFace: 'Arial',
                  valign: 'top'
                });
              }

              // Deliverables Bullets
              if (sBullets.length > 0) {
                const bulletItems = sBullets.map(b => ({
                  text: b,
                  options: { fontSize: 10, color: mutedColor, breakLine: true, paraSpaceAfter: 3 }
                }));
                slide.addText(bulletItems, {
                  x: stepX + 0.22,
                  y: 4.7,
                  w: stepWidth - 0.44,
                  h: 1.3,
                  fontFace: 'Arial',
                  bullet: { type: 'bullet' },
                  valign: 'top'
                });
              }
            });

            // 3. Takeaway Banner Below Roadmap
            const takeawayText = s.takeaway || '🎯 Pendekatan bertahap (Phased Rollout) memitigasi risiko kegagalan sistem dan menjamin operasional berkelanjutan.';
            slide.addShape(pres.ShapeType.roundRect, {
              x: 0.8,
              y: 6.25,
              w: 11.5,
              h: 0.48,
              fill: { color: cardSubtle },
              line: { color: separatorColor, width: 1 }
            });
            slide.addText(takeawayText, {
              x: 0.9,
              y: 6.25,
              w: 11.3,
              h: 0.48,
              fontSize: 10.5,
              bold: true,
              color: accent,
              fontFace: 'Arial',
              align: 'center',
              valign: 'middle'
            });
          }
          else {
            // ── DEFAULT LAYOUT: BULLETS / EXECUTIVE POINTS ──
            slide.addShape(pres.ShapeType.roundRect, {
              x: 0.8,
              y: 2.05,
              w: 11.5,
              h: 4.65,
              fill: { color: cardFill },
              line: { color: separatorColor, width: 1 }
            });

            if (s.bullets && Array.isArray(s.bullets)) {
              const bulletItems = s.bullets.map(b => ({
                text: b,
                options: {
                  fontSize: 14,
                  color: bodyColor,
                  breakLine: true,
                  paraSpaceAfter: 12
                }
              }));

              slide.addText(bulletItems, {
                x: 1.15,
                y: 2.35,
                w: 10.8,
                h: 4.0,
                fontFace: 'Arial',
                bullet: { type: 'bullet' },
                valign: 'top'
              });
            } else if (s.content) {
              slide.addText(s.content, {
                x: 1.15,
                y: 2.35,
                w: 10.8,
                h: 4.0,
                fontSize: 15,
                color: bodyColor,
                fontFace: 'Arial',
                valign: 'top'
              });
            }
          }

          // ── REFINED SLIDE FOOTER (Subtle line & branding) ──
          slide.addShape(pres.ShapeType.rect, {
            x: 0.8,
            y: 6.85,
            w: 11.5,
            h: 0.01,
            fill: { color: separatorColor }
          });

          const footerOrg = s.organization || deckData?.theme_style?.organization || deckData?.theme_style?.name || deckData?.title || 'EXECUTIVE PRESENTATION';
          slide.addText(`CAKRA AI  •  ${String(footerOrg).toUpperCase()}`, {
            x: 0.8,
            y: 6.92,
            w: 6.0,
            h: 0.35,
            fontSize: 9,
            color: mutedColor,
            fontFace: 'Arial'
          });

          slide.addText(`HALAMAN ${idx + 1} DARI ${slides.length}`, {
            x: 9.3,
            y: 6.92,
            w: 3.0,
            h: 0.35,
            fontSize: 9,
            bold: true,
            color: accent,
            fontFace: 'Arial',
            align: 'right'
          });
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
      case 'title': {
        const coverStyle = s.cover_style || deckData?.theme_style?.cover_style || 'split_editorial';
        const presenterTxt = s.presenter || s.author || 'CAKRA AI • EXECUTIVE PRESENTATION';
        const orgTxt = s.organization || deckData?.theme_style?.organization || deckData?.theme_style?.name || deckData?.title || 'Executive Presentation';
        const dateTxt = s.date || new Date().toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' });

        if (coverStyle === 'centered_hero') {
          return (
            <div className="flex flex-col justify-center items-center h-full px-6 sm:px-14 py-6 text-center">
              <div 
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-4 border"
                style={{ 
                  backgroundColor: theme.cardBg, 
                  borderColor: theme.accentColor,
                  color: theme.accentColor 
                }}
              >
                <Presentation size={13} />
                <span>{s.kicker || s.category || 'Executive Presentation'}</span>
              </div>
              <h1 
                className="text-2xl sm:text-4xl lg:text-5xl font-black tracking-tight leading-tight mb-4 max-w-3xl"
                style={{ color: theme.titleColor }}
              >
                {s.title || deckData?.title}
              </h1>
              {s.subtitle && (
                <p 
                  className="text-sm sm:text-lg font-medium mb-6 leading-relaxed max-w-2xl"
                  style={{ color: theme.accentColor }}
                >
                  {s.subtitle}
                </p>
              )}
              <div className="h-0.5 w-24 rounded mb-6" style={{ backgroundColor: theme.accentColor }} />
              <div 
                className="p-3.5 rounded-xl border flex flex-wrap items-center justify-center gap-4 text-xs max-w-md"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder }}
              >
                <span className="font-bold" style={{ color: theme.titleColor }}>{presenterTxt}</span>
                <span className="opacity-40">•</span>
                <span style={{ color: theme.textColor }}>{orgTxt}</span>
                <span className="opacity-40">•</span>
                <span style={{ color: theme.textMuted }}>{dateTxt}</span>
              </div>
            </div>
          );
        }

        if (coverStyle === 'modern_minimalist') {
          return (
            <div className="flex flex-col justify-between h-full px-8 sm:px-16 py-8 text-left relative overflow-hidden">
              <div className="absolute top-0 bottom-0 left-0 w-2" style={{ backgroundColor: theme.accentColor }} />
              <div>
                <span className="text-xs font-bold uppercase tracking-widest block mb-3" style={{ color: theme.accentColor }}>
                  {s.kicker || 'EXECUTIVE BRIEFING'}
                </span>
                <h1 
                  className="text-3xl sm:text-5xl font-black tracking-tight leading-tight mb-4 max-w-2xl"
                  style={{ color: theme.titleColor }}
                >
                  {s.title || deckData?.title}
                </h1>
                {s.subtitle && (
                  <p className="text-base sm:text-xl font-medium leading-relaxed max-w-xl" style={{ color: theme.textMuted }}>
                    {s.subtitle}
                  </p>
                )}
              </div>
              <div className="pt-6 border-t flex flex-wrap items-center gap-6 text-xs sm:text-sm" style={{ borderColor: theme.cardBorder }}>
                <div>
                  <div className="text-[10px] font-bold uppercase opacity-60" style={{ color: theme.textMuted }}>DIBUAT OLEH</div>
                  <div className="font-bold" style={{ color: theme.titleColor }}>{presenterTxt}</div>
                </div>
                <div className="h-6 w-px bg-slate-700/30" />
                <div>
                  <div className="text-[10px] font-bold uppercase opacity-60" style={{ color: theme.textMuted }}>INSTITUSI</div>
                  <div style={{ color: theme.textColor }}>{orgTxt}</div>
                </div>
                <div className="h-6 w-px bg-slate-700/30" />
                <div>
                  <div className="text-[10px] font-bold uppercase opacity-60" style={{ color: theme.textMuted }}>TANGGAL</div>
                  <div style={{ color: theme.textMuted }}>{dateTxt}</div>
                </div>
              </div>
            </div>
          );
        }

        // Default: split_editorial
        return (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-full p-6 sm:p-8 items-stretch">
            {/* Left Hero Panel */}
            <div 
              className="lg:col-span-4 p-5 rounded-2xl border flex flex-col justify-between relative overflow-hidden"
              style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder }}
            >
              <div className="absolute top-0 left-0 right-0 h-1" style={{ backgroundColor: theme.accentColor }} />
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider block mb-2" style={{ color: theme.accentColor }}>
                  {s.kicker || 'EXECUTIVE PRESENTATION'}
                </span>
                <h3 className="text-xl sm:text-2xl font-black leading-snug" style={{ color: theme.titleColor }}>
                  EXECUTIVE BRIEFING
                </h3>
                <p className="text-xs mt-3 leading-relaxed" style={{ color: theme.textMuted }}>
                  Topik: {s.title || deckData?.title}
                </p>
              </div>
              <div className="pt-4 border-t text-xs space-y-1.5" style={{ borderColor: theme.cardBorder }}>
                <div className="text-[10px] font-bold uppercase" style={{ color: theme.accentColor }}>Presenter:</div>
                <div className="font-semibold" style={{ color: theme.textColor }}>{presenterTxt}</div>
                <div className="text-[11px]" style={{ color: theme.textMuted }}>{orgTxt}</div>
                <div className="text-[10px] opacity-60" style={{ color: theme.textMuted }}>{dateTxt}</div>
              </div>
            </div>

            {/* Right Title & Executive Summary */}
            <div className="lg:col-span-8 flex flex-col justify-between p-2 sm:p-4">
              <div>
                <h1 
                  className="text-2xl sm:text-4xl font-extrabold tracking-tight leading-tight mb-3"
                  style={{ color: theme.titleColor }}
                >
                  {s.title || deckData?.title}
                </h1>
                {s.subtitle && (
                  <p className="text-sm sm:text-lg font-medium leading-relaxed" style={{ color: theme.accentColor }}>
                    {s.subtitle}
                  </p>
                )}
              </div>
              <div 
                className="mt-4 p-4 rounded-xl border"
                style={{ backgroundColor: theme.cardSubtle || theme.cardBg, borderColor: theme.cardBorder }}
              >
                <div className="text-xs font-bold uppercase mb-1 flex items-center gap-1.5" style={{ color: theme.accentColor }}>
                  🎯 Ringkasan Eksekutif
                </div>
                <p className="text-xs sm:text-sm leading-relaxed" style={{ color: theme.textColor }}>
                  {s.takeaway || s.desc || 'Paparan komprehensif disusun untuk menyajikan fondasi arsitektur, pilar strategi, dan roadmap eksekusi berstandar profesional.'}
                </p>
              </div>
            </div>
          </div>
        );
      }

      case 'split_screen':
      case 'hero_split':
      case 'asymmetric': {
        const items = s.items || s.cards || s.bullets || [];
        return (
          <div className="flex flex-col h-full px-6 sm:px-10 py-5">
            <div className="mb-4">
              <span className="text-[10px] font-bold uppercase tracking-wider block mb-0.5" style={{ color: theme.accentColor }}>
                {s.kicker || 'ARSITEKTUR & STRATEGI'}
              </span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: theme.titleColor }}>
                {s.title}
              </h2>
              {s.subtitle && (
                <p className="text-xs sm:text-sm mt-1" style={{ color: theme.textMuted }}>
                  {s.subtitle}
                </p>
              )}
              <div className="h-0.5 w-20 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 sm:gap-4 flex-1 items-stretch overflow-y-auto">
              {/* Left Hero Card */}
              <div
                className="lg:col-span-5 p-5 rounded-xl border flex flex-col justify-between relative overflow-hidden"
                style={{
                  backgroundColor: theme.cardBg,
                  borderColor: theme.cardBorder
                }}
              >
                <div className="absolute top-0 left-0 right-0 h-1" style={{ backgroundColor: theme.accentColor }} />
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: theme.accentColor }}>
                    FOKUS STRATEGIS
                  </span>
                  <h3 className="text-lg sm:text-xl font-bold mt-2" style={{ color: theme.titleColor }}>
                    {s.hero?.title || s.title}
                  </h3>
                  <p className="text-xs sm:text-sm mt-3 leading-relaxed" style={{ color: theme.textColor }}>
                    {s.hero?.desc || s.desc || s.subtitle}
                  </p>
                </div>
                {s.takeaway && (
                  <div className="mt-4 p-2.5 rounded-lg border text-xs" style={{ backgroundColor: theme.cardSubtle || theme.cardBg, borderColor: theme.cardBorder, color: theme.accentColor }}>
                    🎯 {s.takeaway}
                  </div>
                )}
              </div>

              {/* Right Detail Cards */}
              <div className="lg:col-span-7 flex flex-col gap-3 justify-center">
                {items.slice(0, 3).map((itm, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl border flex flex-col justify-center"
                    style={{
                      backgroundColor: theme.cardSubtle || theme.cardBg,
                      borderColor: theme.cardBorder
                    }}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: `${theme.accentColor}25`, color: theme.accentColor }}>
                        {idx + 1}
                      </span>
                      <h4 className="font-bold text-xs sm:text-sm" style={{ color: theme.titleColor }}>
                        {typeof itm === 'object' ? (itm.title || `Pilar ${idx + 1}`) : `Poin ${idx + 1}`}
                      </h4>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: theme.textColor }}>
                      {typeof itm === 'object' ? (itm.desc || itm.description || '') : String(itm)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      }

      case 'feature_list':
      case 'horizontal_rows':
      case 'rows':
      case 'modules': {
        const items = s.items || s.cards || s.modules || s.bullets || [];
        return (
          <div className="flex flex-col h-full px-6 sm:px-10 py-5">
            <div className="mb-4">
              <span className="text-[10px] font-bold uppercase tracking-wider block mb-0.5" style={{ color: theme.accentColor }}>
                {s.kicker || 'MODUL & CAPAIAN'}
              </span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: theme.titleColor }}>
                {s.title}
              </h2>
              {s.subtitle && (
                <p className="text-xs sm:text-sm mt-1" style={{ color: theme.textMuted }}>
                  {s.subtitle}
                </p>
              )}
              <div className="h-0.5 w-20 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
            </div>

            <div className="flex flex-col gap-2.5 flex-1 justify-center overflow-y-auto">
              {items.slice(0, 4).map((itm, idx) => {
                const rTitle = typeof itm === 'object' ? (itm.title || `Modul 0${idx + 1}`) : `Poin 0${idx + 1}`;
                const rBadge = typeof itm === 'object' ? (itm.badge || `BAGIAN 0${idx + 1}`) : `POIN 0${idx + 1}`;
                const rDesc = typeof itm === 'object' ? (itm.desc || itm.description || '') : String(itm);
                return (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl border flex items-center gap-3 relative overflow-hidden transition-all hover:scale-[1.01]"
                    style={{
                      backgroundColor: theme.cardBg,
                      borderColor: theme.cardBorder
                    }}
                  >
                    <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: theme.accentColor }} />
                    <div className="flex-1 pl-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: theme.accentColor }}>
                          {rBadge}
                        </span>
                        <span className="text-xs opacity-40">•</span>
                        <h4 className="font-bold text-xs sm:text-sm" style={{ color: theme.titleColor }}>
                          {rTitle}
                        </h4>
                      </div>
                      {rDesc && (
                        <p className="text-xs leading-relaxed" style={{ color: theme.textColor }}>
                          {rDesc}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      }

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
      case 'kpi_grid':
      case 'metric': {
        const rawStats = Array.isArray(s.stats) ? s.stats : null;
        if (rawStats && rawStats.length > 0) {
          return (
            <div className="flex flex-col h-full px-6 sm:px-10 py-5">
              <div className="mb-4">
                <h2 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: theme.titleColor }}>
                  {s.title}
                </h2>
                {s.subtitle && (
                  <p className="text-xs sm:text-sm mt-1" style={{ color: theme.textMuted }}>
                    {s.subtitle}
                  </p>
                )}
                <div className="h-0.5 w-20 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4 mb-4">
                {rawStats.slice(0, 3).map((st, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border flex flex-col items-center text-center transition-all hover:scale-[1.02]"
                    style={{
                      backgroundColor: theme.cardBg,
                      borderColor: theme.cardBorder
                    }}
                  >
                    <span className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: theme.accentColor }}>
                      Indikator {idx + 1}
                    </span>
                    <div className="text-3xl sm:text-4xl lg:text-5xl font-black my-1" style={{ color: theme.accentColor }}>
                      {st.value || st.stat || ''}
                    </div>
                    <div className="text-sm font-bold mt-1" style={{ color: theme.titleColor }}>
                      {st.label || st.stat_label || ''}
                    </div>
                    {st.desc && (
                      <p className="text-xs mt-1.5 leading-relaxed" style={{ color: theme.textMuted }}>
                        {st.desc}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {(s.takeaway || (s.impact_points && s.impact_points.length > 0)) && (
                <div
                  className="mt-auto p-3.5 rounded-xl border"
                  style={{
                    backgroundColor: theme.cardBg,
                    borderColor: theme.cardBorder
                  }}
                >
                  <h4 className="font-bold text-xs sm:text-sm mb-1" style={{ color: theme.titleColor }}>
                    {s.impact_title || 'Analisis Capaian & Dampak Strategis'}
                  </h4>
                  {s.takeaway && (
                    <p className="text-xs sm:text-sm font-medium mb-1.5" style={{ color: theme.accentColor }}>
                      🎯 {s.takeaway}
                    </p>
                  )}
                  {Array.isArray(s.impact_points) && s.impact_points.map((pt, pIdx) => (
                    <p key={pIdx} className="text-xs leading-relaxed" style={{ color: theme.textColor }}>
                      • {pt}
                    </p>
                  ))}
                </div>
              )}
            </div>
          );
        }

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
            {(s.takeaway || s.highlight || s.description) && (
              <div 
                className="p-3 sm:p-4 rounded-xl border max-w-lg text-xs sm:text-sm leading-relaxed"
                style={{ 
                  backgroundColor: theme.cardBg, 
                  borderColor: theme.cardBorder,
                  color: theme.textColor 
                }}
              >
                {s.takeaway || s.highlight || s.description}
              </div>
            )}
          </div>
        );
      }

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

      case 'cards_grid':
      case 'grid':
      case 'pillars': {
        const cards = s.cards || s.items || [];
        const colsClass = cards.length === 4 ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 sm:grid-cols-3';
        return (
          <div className="flex flex-col h-full px-6 sm:px-10 py-5">
            <div className="mb-4">
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: theme.titleColor }}>
                {s.title}
              </h2>
              {s.subtitle && (
                <p className="text-xs sm:text-sm mt-1" style={{ color: theme.textMuted }}>
                  {s.subtitle}
                </p>
              )}
              <div className="h-0.5 w-20 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
            </div>

            <div className={`grid ${colsClass} gap-3 sm:gap-4 flex-1 items-stretch overflow-y-auto`}>
              {cards.map((card, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl border flex flex-col transition-all hover:scale-[1.02]"
                  style={{
                    backgroundColor: theme.cardBg,
                    borderColor: theme.cardBorder
                  }}
                >
                  <div className="flex items-center gap-2 mb-2.5">
                    <span
                      className="w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: `${theme.accentColor}25`,
                        color: theme.accentColor
                      }}
                    >
                      {idx + 1}
                    </span>
                    <h3 className="font-bold text-sm sm:text-base leading-snug" style={{ color: theme.titleColor }}>
                      {card.title || card.heading || `Pilar ${idx + 1}`}
                    </h3>
                  </div>
                  <p className="text-xs sm:text-sm leading-relaxed flex-1" style={{ color: theme.textColor }}>
                    {card.desc || card.description || card.text || (typeof card === 'string' ? card : '')}
                  </p>
                  {Array.isArray(card.bullets) && card.bullets.length > 0 && (
                    <ul className="mt-2.5 pt-2 border-t space-y-1 text-xs" style={{ borderColor: theme.cardBorder, color: theme.textMuted }}>
                      {card.bullets.map((b, bIdx) => (
                        <li key={bIdx} className="flex items-start gap-1.5">
                          <span style={{ color: theme.accentColor }}>•</span>
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
            {s.highlight && (
              <div
                className="mt-3 p-2.5 rounded-lg border text-xs italic"
                style={{
                  backgroundColor: theme.cardBg,
                  borderColor: theme.cardBorder,
                  color: theme.accentColor
                }}
              >
                💡 {s.highlight}
              </div>
            )}
          </div>
        );
      }

      case 'timeline':
      case 'roadmap':
      case 'milestone': {
        const steps = s.steps || s.milestones || s.items || [];
        return (
          <div className="flex flex-col h-full px-6 sm:px-10 py-5">
            <div className="mb-4">
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: theme.titleColor }}>
                {s.title}
              </h2>
              {s.subtitle && (
                <p className="text-xs sm:text-sm mt-1" style={{ color: theme.textMuted }}>
                  {s.subtitle}
                </p>
              )}
              <div className="h-0.5 w-20 rounded mt-1.5" style={{ backgroundColor: theme.accentColor }} />
            </div>

            <div className="flex-1 flex flex-col justify-center overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 items-stretch">
                {steps.map((st, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border flex flex-col relative"
                    style={{
                      backgroundColor: theme.cardBg,
                      borderColor: theme.cardBorder
                    }}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="px-2 py-0.5 rounded text-[11px] font-bold tracking-wider uppercase border"
                        style={{
                          backgroundColor: `${theme.accentColor}25`,
                          borderColor: theme.accentColor,
                          color: theme.accentColor
                        }}
                      >
                        {st.phase || st.step || `Tahap ${idx + 1}`}
                      </span>
                    </div>
                    <h3 className="font-bold text-sm sm:text-base mb-1.5" style={{ color: theme.titleColor }}>
                      {st.title || st.heading || `Langkah ${idx + 1}`}
                    </h3>
                    <p className="text-xs sm:text-sm leading-relaxed flex-1" style={{ color: theme.textColor }}>
                      {st.desc || st.description || st.text || (typeof st === 'string' ? st : '')}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {s.highlight && (
              <div
                className="mt-3 p-2.5 rounded-lg border text-xs italic"
                style={{
                  backgroundColor: theme.cardBg,
                  borderColor: theme.cardBorder,
                  color: theme.accentColor
                }}
              >
                💡 {s.highlight}
              </div>
            )}
          </div>
        );
      }

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
          {/* AI Theme Indicator Badge */}
          <div 
            className="text-[11px] font-medium px-2.5 py-1 rounded-md border flex items-center gap-1.5 hidden sm:flex select-none"
            style={{ 
              color: theme.textColor, 
              borderColor: theme.cardBorder,
              backgroundColor: theme.cardBg 
            }}
            title="Tema visual disusun secara dinamis oleh AI Architect"
          >
            <Sparkles size={12} style={{ color: theme.accentColor }} />
            <span>{theme.name}</span>
          </div>

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
          {/* ── Dynamic Ambient Mesh, Particle & Texture Backdrop Layer ── */}
          <div className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0">
            {/* 1. Luminous Ambient Radial Glow Orbs */}
            <div 
              className="absolute -top-1/4 -right-1/4 w-[75%] h-[75%] rounded-full blur-3xl opacity-35 transition-all duration-700 pointer-events-none"
              style={{ backgroundColor: theme.accentColor }}
            />
            <div 
              className="absolute -bottom-1/4 -left-1/4 w-[60%] h-[60%] rounded-full blur-3xl opacity-25 transition-all duration-700 pointer-events-none"
              style={{ backgroundColor: theme.isDark ? (theme.cardBg || theme.accentColor) : theme.accentColor }}
            />

            {/* 2. Dynamic Texture Pattern (Grid vs Particles Dots) */}
            {theme.backdropEffect === 'cyber_grid' ? (
              <div 
                className="absolute inset-0 opacity-15 pointer-events-none"
                style={{
                  backgroundImage: `linear-gradient(${theme.accentColor}25 1px, transparent 1px), linear-gradient(90deg, ${theme.accentColor}25 1px, transparent 1px)`,
                  backgroundSize: '36px 36px'
                }}
              />
            ) : (
              <div 
                className="absolute inset-0 opacity-25 pointer-events-none"
                style={{
                  backgroundImage: `radial-gradient(${theme.accentColor}40 1.25px, transparent 1.25px)`,
                  backgroundSize: '24px 24px'
                }}
              />
            )}

            {/* 3. Subtle Vignette Edge Softening */}
            <div 
              className="absolute inset-0 pointer-events-none"
              style={{
                background: `radial-gradient(circle at 50% 50%, transparent 55%, ${theme.isDark ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.45)'} 100%)`
              }}
            />
          </div>

          {/* Slide Content Layer: Native PPTX Vector Preview Showcase */}
          <div key={currentSlide} className="w-full h-full relative z-10 flex items-center justify-center transition-opacity duration-300 animate-fadeIn">
            {(() => {
              const activeSlide = slides[currentSlide];
              const activeSvg = activeSlide?.svg_url || deckData?.slide_svgs?.[currentSlide];
              if (!activeSvg) return renderSlideContent();
              const fullSvgUrl = activeSvg.startsWith('http') ? activeSvg : `${getApiBase()}${activeSvg.startsWith('/') ? '' : '/'}${activeSvg}`;
              return (
                <img 
                  src={fullSvgUrl} 
                  alt={activeSlide?.title || `Slide ${currentSlide + 1}`}
                  className="w-full h-full object-contain select-none transition-opacity duration-300"
                />
              );
            })()}
          </div>
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
