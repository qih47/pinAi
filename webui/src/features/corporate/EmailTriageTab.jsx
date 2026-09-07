import React, { useState, useEffect, useRef } from 'react';
import apiClient from '../../services/apiClient';
import DOMPurify from 'dompurify';
import { 
  Mail, Lock, RefreshCw, Bot, CircleDot, CheckCircle2, Send, Forward as ForwardIcon, 
  Hourglass, Ban, ShieldAlert, Key, LogOut, ArrowLeft, PanelLeft,
  Paperclip, Download, FileText, Inbox, SendHorizontal, PenSquare, Sparkles, X, Plus,
  Trash2, Bold, Italic, Underline, Strikethrough, AlignLeft, AlignCenter, AlignRight,
  List, ListOrdered, Quote, Code, Link2, RotateCcw, RotateCw, Save, ChevronDown
} from 'lucide-react';
import { useCorporateStore } from '../../stores/corporateStore';
import { translations } from '../../utils/translations';

export default function EmailTriageTab({ theme, darkMode, userData, language, isMobile = false, toggleSidebar }) {
  const t = translations[language]?.smartMail || translations.id.smartMail;
  const tz = translations[language]?.zimbraAuth || translations.id.zimbraAuth;
  // Gunakan email dari DB jika ada, jika tidak, construct dari NPP
  const userEmail = userData?.email || (userData?.npp ? `${userData.npp}@pindad.com` : "user@pindad.com");

  const [activeFolder, setActiveFolder] = useState('inbox'); // 'inbox' | 'sent' | 'drafts'
  const zimbraEmails = useCorporateStore(state => state.zimbraEmails);
  const zimbraSentEmails = useCorporateStore(state => state.zimbraSentEmails);
  const zimbraDraftEmails = useCorporateStore(state => state.zimbraDraftEmails);
  const setZimbraEmails = useCorporateStore(state => state.setZimbraEmails);
  const setZimbraSentEmails = useCorporateStore(state => state.setZimbraSentEmails);
  const setZimbraDraftEmails = useCorporateStore(state => state.setZimbraDraftEmails);
  const addOrUpdateZimbraDraft = useCorporateStore(state => state.addOrUpdateZimbraDraft);
  const removeZimbraDraft = useCorporateStore(state => state.removeZimbraDraft);
  const updateZimbraEmail = useCorporateStore(state => state.updateZimbraEmail);
  const clearZimbraEmails = useCorporateStore(state => state.clearZimbraEmails);

  const [selectedEmail, setSelectedEmail] = useState(null);
  const [mobileView, setMobileView] = useState('list'); // 'list' | 'detail'
  const [isLoadingEmails, setIsLoadingEmails] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [isZimbraAuthenticated, setIsZimbraAuthenticated] = useState(false);

  const [draftContent, setDraftContent] = useState("");
  const [instruction, setInstruction] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [sendSuccess, setSendSuccess] = useState(false);
  const [replyAll, setReplyAll] = useState(false);
  const [isForwarding, setIsForwarding] = useState(false);
  const [forwardTo, setForwardTo] = useState("");

  // Compose New Email States
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState(null);
  const [composeTo, setComposeTo] = useState("");
  const [composeCc, setComposeCc] = useState("");
  const [showCcField, setShowCcField] = useState(false);
  const [composeSubject, setComposeSubject] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeAiPrompt, setComposeAiPrompt] = useState("");
  const [composeTone, setComposeTone] = useState("formal");
  const [isGeneratingCompose, setIsGeneratingCompose] = useState(false);
  const [isSendingCompose, setIsSendingCompose] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [composeAttachments, setComposeAttachments] = useState([]);
  const [isDraggingAttachment, setIsDraggingAttachment] = useState(false);
  const [composeStatusMsg, setComposeStatusMsg] = useState({ type: '', text: '' });
  
  const fileInputRef = useRef(null);
  const composeTextareaRef = useRef(null);

  // Spam Blocker States
  const [unlockedSpamEmails, setUnlockedSpamEmails] = useState(new Set());
  const [unlockPasswordInput, setUnlockPasswordInput] = useState("");
  const [threatAnalysis, setThreatAnalysis] = useState({});
  const [isAnalyzingThreat, setIsAnalyzingThreat] = useState(false);

  // Status Karantina: True jika email terindikasi SPAM/Phishing dan belum dibuka kuncinya oleh pengguna
  const isSelectedEmailQuarantined = Boolean(
    selectedEmail &&
    selectedEmail.priority?.includes('SPAM') &&
    !unlockedSpamEmails.has(selectedEmail.id)
  );

  // Reply Attachments & Formatting States
  const [replyAttachments, setReplyAttachments] = useState([]);
  const [isDraggingReplyAttachment, setIsDraggingReplyAttachment] = useState(false);
  const replyFileInputRef = useRef(null);
  const replyTextareaRef = useRef(null);

  // Resize logic
  const [draftHeight, setDraftHeight] = useState(390);
  const [isResizing, setIsResizing] = useState(false);
  const startYRef = useRef(0);
  const startHeightRef = useRef(0);
  const isProcessingTriageRef = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      const deltaY = startYRef.current - e.clientY;
      // Batasi minimal 200px, maksimal 800px agar tidak merusak UI
      const newHeight = Math.max(200, Math.min(800, startHeightRef.current + deltaY));
      setDraftHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none'; // Cegah teks ter-highlight saat drag
    } else {
      document.body.style.userSelect = 'auto';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    if (zimbraEmails.length === 0) {
      fetchEmails(false, 'inbox');
    } else {
      setIsZimbraAuthenticated(true);
      if (!selectedEmail && zimbraEmails.length > 0) {
         setSelectedEmail(zimbraEmails[0]);
      }
    }
  }, []);

  // Fetch Threat Analysis for Spam Emails
  useEffect(() => {
    if (isSelectedEmailQuarantined) {
      if (!threatAnalysis[selectedEmail.id]) {
        setIsAnalyzingThreat(true);
        apiClient.post('/corporate/emails/threat-analysis', {
          email_content: selectedEmail.content
        }).then(res => {
          if (res.data.status === 'success') {
            setThreatAnalysis(prev => ({...prev, [selectedEmail.id]: res.data.data.threat_reason}));
          }
        }).catch(err => {
          console.error("Failed to analyze threat:", err);
          setThreatAnalysis(prev => ({...prev, [selectedEmail.id]: "Gagal menghubungi AI SOC Analyst."}));
        }).finally(() => {
          setIsAnalyzingThreat(false);
        });
      }
    }
  }, [selectedEmail, isSelectedEmailQuarantined]);

  // Background AI Triage Tagging (Hanya untuk Inbox, Sequential & Single-Lock untuk cegah scan ulang)
  useEffect(() => {
    if (activeFolder !== 'inbox' || isProcessingTriageRef.current) return;

    const processTriageQueue = async () => {
      const pendingEmails = zimbraEmails.filter(email => !email.has_triage && (email.priority === '🔴 Unread' || email.priority === '🟢 Read'));
      if (pendingEmails.length === 0) return;

      isProcessingTriageRef.current = true;

      // Mark as scanning locally so we don't re-process on re-renders
      const idsToScan = pendingEmails.map(e => e.id);
      idsToScan.forEach(id => updateZimbraEmail(id, { priority: '⏳ Scanning...' }));

      // Process sequentially
      for (const email of pendingEmails) {
        try {
          const res = await apiClient.post('/corporate/emails/triage', { 
            token: localStorage.getItem('cakra_token') || '',
            message_id: email.message_id || '',
            email_uid: email.id || email.uid || '',
            email_content: email.content,
            email_subject: email.subject,
            sender: email.sender || ''
          });
          
          if (res.data.status === 'success') {
             updateZimbraEmail(email.id, { priority: res.data.data.priority, has_triage: true });
          } else {
             updateZimbraEmail(email.id, { priority: email.priority, has_triage: true });
          }
        } catch (err) {
          console.error("Triage failed for", email.id, err);
          updateZimbraEmail(email.id, { priority: email.priority, has_triage: true });
        }
      }

      isProcessingTriageRef.current = false;
    };

    processTriageQueue();
  }, [zimbraEmails, activeFolder]);

  // Bersihkan draft jika berpindah atau terpilih email yang dikarantina
  useEffect(() => {
    if (isSelectedEmailQuarantined && draftContent) {
      setDraftContent("");
    }
  }, [isSelectedEmailQuarantined]);

  // Generate draft hanya jika folder inbox dan email TIDAK sedang dalam karantina
  useEffect(() => {
    if (activeFolder !== 'inbox' || isSelectedEmailQuarantined) {
      return;
    }
    if (selectedEmail && !draftContent && !isGenerating) {
      handleGenerate("");
    }
  }, [selectedEmail, isSelectedEmailQuarantined, activeFolder]);

  const formatRelativeDate = (dateString) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.round(diffMs / 60000);
      const diffHours = Math.round(diffMs / 3600000);
      const diffDays = Math.round(diffMs / 86400000);
      
      if (diffMins < 60) return `${diffMins} menit yang lalu`;
      if (diffHours < 24) return `${diffHours} jam yang lalu`;
      if (diffDays === 1) return `Kemarin, ${date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}`;
      
      return date.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch(e) {
      return dateString;
    }
  };

  const fetchDrafts = async () => {
    setIsLoadingEmails(true);
    setErrorMsg("");
    try {
      const token = localStorage.getItem('cakra_token') || '';
      const response = await apiClient.get(`/corporate/emails/drafts?token=${encodeURIComponent(token)}`);
      if (response.data?.status === 'success') {
        const fetchedDrafts = response.data.data || [];
        setZimbraDraftEmails(fetchedDrafts);
        if (!selectedEmail && fetchedDrafts.length > 0) {
          setSelectedEmail(fetchedDrafts[0]);
        }
      }
    } catch (err) {
      console.error("Gagal mengambil daftar draf:", err);
    } finally {
      setIsLoadingEmails(false);
    }
  };

  const fetchEmails = async (isRefresh = false, folderTarget = activeFolder) => {
    if (folderTarget === 'drafts') {
      return fetchDrafts();
    }
    setIsLoadingEmails(true);
    setErrorMsg("");
    
    try {
      const response = await apiClient.post('/corporate/emails/fetch', {
        token: localStorage.getItem('cakra_token') || '',
        folder: folderTarget,
        limit: 30
      });
      if (response.data.status === 'success') {
        const fetchedEmails = response.data.data || [];
        if (folderTarget === 'sent') {
          if (isRefresh || zimbraSentEmails.length > 0) {
            const existingIds = new Set(zimbraSentEmails.map(e => e.message_id || e.id));
            const newEmails = fetchedEmails.filter(e => !existingIds.has(e.message_id || e.id));
            setZimbraSentEmails([...newEmails, ...zimbraSentEmails]);
          } else {
            setZimbraSentEmails(fetchedEmails);
          }
          if (!selectedEmail && fetchedEmails.length > 0) {
            setSelectedEmail(fetchedEmails[0]);
          }
        } else {
          if (isRefresh || zimbraEmails.length > 0) {
            const existingIds = new Set(zimbraEmails.map(e => e.message_id || e.id));
            const newEmails = fetchedEmails.filter(e => !existingIds.has(e.message_id || e.id));
            setZimbraEmails([...newEmails, ...zimbraEmails]);
          } else {
            setZimbraEmails(fetchedEmails);
          }
          if (!selectedEmail && fetchedEmails.length > 0) {
            setSelectedEmail(fetchedEmails[0]);
          }
        }
        setIsZimbraAuthenticated(true);
      } else {
        setErrorMsg(response.data.message || "Gagal autentikasi ke Zimbra.");
        setIsZimbraAuthenticated(false);
      }
    } catch (error) {
      console.error("Gagal mengambil email dari Zimbra:", error);
      setErrorMsg("Koneksi ke mail.pindad.com gagal atau kredensial salah.");
      setIsZimbraAuthenticated(false);
    } finally {
      setIsLoadingEmails(false);
    }
  };

  const handleDownloadAttachment = async (emailUid, partIndex, filename) => {
    try {
      const token = localStorage.getItem('cakra_token') || '';
      const url = `/corporate/emails/${emailUid}/attachments/${partIndex}/download?token=${encodeURIComponent(token)}&folder=${activeFolder}`;
      const res = await apiClient.get(url, { responseType: 'blob' });
      const blobUrl = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.setAttribute('download', filename || 'lampiran');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Gagal mengunduh lampiran:", err);
      alert("Gagal mengunduh file lampiran dari server Zimbra.");
    }
  };

  const handleGenerate = async (customInstruction = instruction) => {
    if (!selectedEmail || isSelectedEmailQuarantined) return;
    setIsGenerating(true);
    setDraftContent("AI sedang berpikir...");
    try {
      const response = await apiClient.post(`/corporate/emails/${selectedEmail.id}/draft`, {
        instruction: customInstruction,
        email_content: selectedEmail.content,
        user_name: userData?.name || 'CAKRA',
        user_role: userData?.role || 'Asisten AI PT Pindad (Persero)'
      });
      if (response.data.status === 'success') {
        setDraftContent(response.data.data.draft_content);
      }
    } catch (error) {
      console.error("Gagal generate email draft", error);
      setDraftContent("Mohon maaf, terjadi kesalahan saat memproses draft email dari AI.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedEmail || !draftContent) return;
    setIsSending(true);
    setSendSuccess(false);
    
    let finalTo = "";
    let finalCc = "";
    let finalSubject = selectedEmail.subject;
    let finalBody = draftContent;

    if (isForwarding) {
      if (!forwardTo) {
        alert("Silakan isi alamat email tujuan forward.");
        setIsSending(false);
        return;
      }
      finalTo = forwardTo;
      if (!finalSubject.toLowerCase().startsWith("fwd:") && !finalSubject.toLowerCase().startsWith("fw:")) {
         finalSubject = `Fwd: ${finalSubject}`;
      }
      finalBody = `${draftContent}\n\n---------- Forwarded message ---------\nDari: ${selectedEmail.sender}\nTanggal: ${selectedEmail.received_at}\nSubjek: ${selectedEmail.subject}\n\n${selectedEmail.content}`;
    } else {
      let toAddr = selectedEmail.sender;
      const match = toAddr.match(/<(.+)>/);
      if (match) toAddr = match[1];
      finalTo = toAddr;
      if (replyAll && selectedEmail.cc) {
         finalCc = selectedEmail.cc;
      }
    }
    
    try {
      const response = await apiClient.post('/corporate/emails/reply', {
        token: localStorage.getItem('cakra_token') || '',
        to: finalTo,
        cc: finalCc,
        subject: finalSubject,
        body: finalBody,
        attachments: replyAttachments
      });
      
      if (response.data.status === 'success') {
        setSendSuccess(true);
        setReplyAttachments([]);
        setTimeout(() => setSendSuccess(false), 3000);
      } else {
        alert("Gagal mengirim email: " + response.data.message);
      }
    } catch (error) {
      console.error("Gagal send", error);
      alert("Koneksi gagal saat mengirim email.");
    } finally {
      setIsSending(false);
    }
  };

  const composeToneOptions = [
    { id: 'formal', label: '👔 Formal Korporat' },
    { id: 'concise', label: '⚡ Ringkas & Tegas' },
    { id: 'polite', label: '🤝 Santun & Kolaboratif' },
    { id: 'announcement', label: '📢 Pengumuman Resmi' }
  ];

  const handleOpenDraftInComposer = (draft) => {
    setCurrentDraftId(draft.id);
    setComposeTo(draft.to || "");
    setComposeCc(draft.cc || "");
    setShowCcField(Boolean(draft.cc));
    setComposeSubject(draft.subject || "");
    setComposeBody(draft.body || "");
    setComposeAttachments(draft.attachments || []);
    setIsComposeOpen(true);
    setComposeStatusMsg({ type: '', text: '' });
  };

  const handleDeleteDraft = async (e, draftId) => {
    e.stopPropagation();
    if (!confirm("Hapus draf email ini?")) return;
    try {
      const token = localStorage.getItem('cakra_token') || '';
      await apiClient.delete(`/corporate/emails/drafts/${draftId}?token=${encodeURIComponent(token)}`);
      removeZimbraDraft(draftId);
      if (selectedEmail?.id === draftId) {
        setSelectedEmail(null);
      }
    } catch (err) {
      console.error("Gagal hapus draf:", err);
      alert("Gagal menghapus draf email.");
    }
  };

  const handleSaveDraft = async () => {
    if (!composeTo.trim() && !composeSubject.trim() && !composeBody.trim()) {
      alert("Draf masih kosong. Isi setidaknya penerima, subjek, atau isi pesan.");
      return;
    }
    setIsSavingDraft(true);
    setComposeStatusMsg({ type: '', text: '' });
    try {
      const res = await apiClient.post('/corporate/emails/drafts/save', {
        token: localStorage.getItem('cakra_token') || '',
        draft_id: currentDraftId,
        to: composeTo.trim(),
        cc: composeCc.trim(),
        subject: composeSubject.trim(),
        body: composeBody,
        attachments: composeAttachments
      });
      if (res.data?.status === 'success') {
        const savedData = res.data.data;
        setCurrentDraftId(savedData.id);
        addOrUpdateZimbraDraft(savedData);
        setComposeStatusMsg({ type: 'success', text: '💾 Draf berhasil disimpan!' });
        setTimeout(() => setComposeStatusMsg({ type: '', text: '' }), 3000);
      } else {
        setComposeStatusMsg({ type: 'error', text: 'Gagal menyimpan draf: ' + (res.data?.message || '') });
      }
    } catch (err) {
      console.error("Gagal simpan draf:", err);
      setComposeStatusMsg({ type: 'error', text: 'Koneksi gagal saat menyimpan draf.' });
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleFileSelect = (files) => {
    if (!files || files.length === 0) return;
    Array.from(files).forEach(file => {
      if (file.size > 15 * 1024 * 1024) {
        alert(`File ${file.name} melebihi batas ukuran maksimal 15MB.`);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        setComposeAttachments(prev => [
          ...prev,
          {
            filename: file.name,
            size: file.size,
            content_base64: reader.result,
            content_type: file.type || 'application/octet-stream'
          }
        ]);
      };
      reader.readAsDataURL(file);
    });
  };

  const handleRemoveAttachment = (index) => {
    setComposeAttachments(prev => prev.filter((_, idx) => idx !== index));
  };

  const applyFormatting = (type) => {
    const textarea = composeTextareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selectedText = text.substring(start, end);

    let replacement = '';
    let cursorOffset = 0;

    switch (type) {
      case 'bold':
        replacement = `**${selectedText || 'teks tebal'}**`;
        cursorOffset = selectedText ? replacement.length : 2;
        break;
      case 'italic':
        replacement = `*${selectedText || 'teks miring'}*`;
        cursorOffset = selectedText ? replacement.length : 1;
        break;
      case 'underline':
        replacement = `<u>${selectedText || 'teks garis bawah'}</u>`;
        cursorOffset = selectedText ? replacement.length : 3;
        break;
      case 'strikethrough':
        replacement = `~~${selectedText || 'teks coret'}~~`;
        cursorOffset = selectedText ? replacement.length : 2;
        break;
      case 'clear':
        replacement = selectedText.replace(/[*_~`#<>]/g, '');
        cursorOffset = replacement.length;
        break;
      case 'bullet':
        replacement = `\n- ${selectedText || 'poin list'}\n`;
        cursorOffset = replacement.length;
        break;
      case 'number':
        replacement = `\n1. ${selectedText || 'poin berurutan'}\n`;
        cursorOffset = replacement.length;
        break;
      case 'quote':
        replacement = `\n> ${selectedText || 'kutipan'}\n`;
        cursorOffset = replacement.length;
        break;
      case 'code':
        replacement = `\`${selectedText || 'kode'}\``;
        cursorOffset = selectedText ? replacement.length : 1;
        break;
      case 'link':
        const url = prompt("Masukkan URL tautan:", "https://");
        if (url) {
          replacement = `[${selectedText || 'Teks Tautan'}](${url})`;
          cursorOffset = replacement.length;
        } else {
          return;
        }
        break;
      default:
        return;
    }

    const newBody = text.substring(0, start) + replacement + text.substring(end);
    setComposeBody(newBody);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + cursorOffset, start + cursorOffset);
    }, 50);
  };

  const applyReplyFormatting = (type) => {
    const textarea = replyTextareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selectedText = text.substring(start, end);

    let replacement = '';
    let cursorOffset = 0;

    switch (type) {
      case 'bold':
        replacement = `**${selectedText || 'teks tebal'}**`;
        cursorOffset = selectedText ? replacement.length : 2;
        break;
      case 'italic':
        replacement = `*${selectedText || 'teks miring'}*`;
        cursorOffset = selectedText ? replacement.length : 1;
        break;
      case 'underline':
        replacement = `<u>${selectedText || 'teks garis bawah'}</u>`;
        cursorOffset = selectedText ? replacement.length : 3;
        break;
      case 'strikethrough':
        replacement = `~~${selectedText || 'teks coret'}~~`;
        cursorOffset = selectedText ? replacement.length : 2;
        break;
      case 'clear':
        replacement = selectedText.replace(/[*_~`#<>]/g, '');
        cursorOffset = replacement.length;
        break;
      case 'bullet':
        replacement = `\n- ${selectedText || 'poin list'}\n`;
        cursorOffset = replacement.length;
        break;
      case 'number':
        replacement = `\n1. ${selectedText || 'poin berurutan'}\n`;
        cursorOffset = replacement.length;
        break;
      case 'quote':
        replacement = `\n> ${selectedText || 'kutipan'}\n`;
        cursorOffset = replacement.length;
        break;
      case 'code':
        replacement = `\`${selectedText || 'kode'}\``;
        cursorOffset = selectedText ? replacement.length : 1;
        break;
      case 'link':
        const url = prompt("Masukkan URL tautan:", "https://");
        if (url) {
          replacement = `[${selectedText || 'Teks Tautan'}](${url})`;
          cursorOffset = replacement.length;
        } else {
          return;
        }
        break;
      default:
        return;
    }

    const newDraft = text.substring(0, start) + replacement + text.substring(end);
    setDraftContent(newDraft);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + cursorOffset, start + cursorOffset);
    }, 50);
  };

  const handleReplyFileSelect = (files) => {
    if (!files || files.length === 0) return;
    Array.from(files).forEach(file => {
      if (file.size > 15 * 1024 * 1024) {
        alert(`File ${file.name} melebihi batas ukuran maksimal 15MB.`);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        setReplyAttachments(prev => [
          ...prev,
          {
            filename: file.name,
            size: file.size,
            content_base64: reader.result,
            content_type: file.type || 'application/octet-stream'
          }
        ]);
      };
      reader.readAsDataURL(file);
    });
  };

  const handleRemoveReplyAttachment = (index) => {
    setReplyAttachments(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleGenerateComposeAi = async (toneOverride) => {
    if (!composeAiPrompt.trim()) {
      alert("Silakan masukkan instruksi atau poin pesan yang ingin dibuat oleh AI.");
      return;
    }
    const toneToUse = toneOverride || composeTone;
    setIsGeneratingCompose(true);
    setComposeStatusMsg({ type: '', text: '' });
    try {
      const res = await apiClient.post('/corporate/emails/compose-ai', {
        instruction: composeAiPrompt.trim(),
        tone: toneToUse,
        user_name: userData?.full_name || userData?.username || 'Karyawan Pindad',
        user_role: userData?.role || 'Karyawan PT Pindad (Persero)'
      });
      if (res.data?.status === 'success' && res.data?.data) {
        if (res.data.data.subject) {
          setComposeSubject(res.data.data.subject);
        }
        setComposeBody(res.data.data.body || '');
        setComposeStatusMsg({ type: 'success', text: '✨ Draf pesan berhasil dibuat oleh AI!' });
      }
    } catch (err) {
      console.error("Gagal generate compose AI", err);
      setComposeStatusMsg({ type: 'error', text: 'Gagal membuat draf dengan AI. Silakan coba lagi.' });
    } finally {
      setIsGeneratingCompose(false);
    }
  };

  const handleSendCompose = async () => {
    if (!composeTo.trim()) {
      alert("Alamat penerima (Kepada) wajib diisi.");
      return;
    }
    if (!composeSubject.trim()) {
      alert("Subjek email wajib diisi.");
      return;
    }
    if (!composeBody.trim()) {
      alert("Isi pesan email tidak boleh kosong.");
      return;
    }
    setIsSendingCompose(true);
    setComposeStatusMsg({ type: '', text: '' });
    try {
      const res = await apiClient.post('/corporate/emails/reply', {
        token: localStorage.getItem('cakra_token') || '',
        to: composeTo.trim(),
        cc: composeCc.trim(),
        subject: composeSubject.trim(),
        body: composeBody,
        is_reply: false,
        attachments: composeAttachments,
        draft_id: currentDraftId
      });
      if (res.data?.status === 'success') {
        if (currentDraftId) {
          removeZimbraDraft(currentDraftId);
        }
        setComposeStatusMsg({ type: 'success', text: '✅ Email berhasil dikirim ke Zimbra!' });
        setTimeout(() => {
          setIsComposeOpen(false);
          setCurrentDraftId(null);
          setComposeTo("");
          setComposeCc("");
          setShowCcField(false);
          setComposeSubject("");
          setComposeBody("");
          setComposeAiPrompt("");
          setComposeAttachments([]);
          setComposeStatusMsg({ type: '', text: '' });
          // Beralih ke folder sent dan refresh
          setActiveFolder('sent');
          setSelectedEmail(null);
          fetchEmails(true, 'sent');
        }, 1200);
      } else {
        setComposeStatusMsg({ type: 'error', text: 'Gagal mengirim email: ' + (res.data?.message || 'Error Zimbra') });
      }
    } catch (err) {
      console.error("Gagal kirim compose", err);
      setComposeStatusMsg({ type: 'error', text: 'Koneksi gagal saat mengirim email.' });
    } finally {
      setIsSendingCompose(false);
    }
  };

  const quickActions = [
    { label: "✨ Lebih Sopan", prompt: "Ubah draft ini menjadi jauh lebih sopan, formal, dan berterima kasih." },
    { label: "⚡ Ringkas & Tegas", prompt: "Buat draft ini menjadi sangat singkat, to the point, dan tegas." },
    { label: "✅ Setujui", prompt: "Buat balasan yang menyetujui permintaan/penawaran di email ini dengan baik." },
    { label: "❌ Tolak Halus", prompt: "Buat balasan yang menolak permintaan/penawaran ini dengan sangat halus karena alasan anggaran/SOP." }
  ];

  return (
    <div style={{ flex: 1, padding: isMobile ? '12px' : '20px', color: theme.textColor, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {isZimbraAuthenticated ? (
        <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', justifyContent: 'space-between', alignItems: isMobile ? 'flex-start' : 'center', marginBottom: '14px', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: isMobile ? '100%' : 'auto' }}>
            <h2 style={{ fontSize: isMobile ? '1.25rem' : '1.5rem', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Mail size={isMobile ? 20 : 24} /> {t.title}
            </h2>

            {isMobile && toggleSidebar && (
              <button
                onClick={toggleSidebar}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: theme.textColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "6px",
                  borderRadius: "8px",
                }}
                title="Menu Sidebar"
              >
                <PanelLeft size={22} />
              </button>
            )}
          </div>
          <div style={{ fontSize: '13px', background: darkMode ? '#2A2A2D' : '#F3F4F6', padding: '5px 12px', borderRadius: '20px', color: theme.secondaryText, marginRight: isMobile ? '0' : '24px' }}>
            Kotak Masuk: <strong style={{ color: theme.textColor }}>{userEmail}</strong>
          </div>
        </div>
      ) : isMobile && toggleSidebar && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
          <button
            onClick={toggleSidebar}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: theme.textColor,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "6px",
              borderRadius: "8px",
            }}
            title="Menu Sidebar"
          >
            <PanelLeft size={22} />
          </button>
        </div>
      )}
      <div style={{ 
        display: 'flex', 
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? '12px' : '20px', 
        flex: 1, 
        minHeight: 0, 
        height: '100%',
        justifyContent: isZimbraAuthenticated ? 'flex-start' : 'center',
        alignItems: isZimbraAuthenticated ? 'stretch' : 'center'
      }}>
        {/* Kiri: Inbox List */}
        {(!isMobile || mobileView === 'list') && (
          <div style={{ 
            width: isMobile ? '100%' : '380px', 
            background: darkMode ? '#1E1E22' : '#F9FAFB', 
            borderRadius: '12px', 
            padding: isMobile ? '12px' : '16px', 
            border: `1px solid ${theme.borderColor}`, 
            display: 'flex', 
            flexDirection: 'column', 
            minHeight: 0,
            flex: isMobile ? 1 : undefined,
            height: isZimbraAuthenticated ? '100%' : 'auto'
          }}>
            
            {!isZimbraAuthenticated ? (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'center' }}>

                {isLoadingEmails ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
                    <div className="spinner" style={{ width: '32px', height: '32px', border: `3px solid ${darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`, borderTopColor: '#3B82F6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                    <p style={{ color: theme.secondaryText, fontSize: '14px', fontWeight: 500 }}>Menyambungkan...</p>
                    <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
                  </div>
                ) : (
                  <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'center' }}>
                    <p style={{ fontSize: '14px', textAlign: 'center', color: theme.textColor, fontWeight: 'bold' }}>
                      Koneksi Smart Mail Terputus atau Gagal
                    </p>
                    <p style={{ fontSize: '12px', textAlign: 'center', color: theme.secondaryText }}>
                      Silakan buka menu <strong>Pengaturan &gt; Akun</strong> untuk menyambungkan ulang atau memperbarui kredensial Anda. 
                    </p>
                    <button 
                      onClick={() => fetchEmails()} 
                      disabled={isLoadingEmails}
                      style={{ 
                        background: '#3B82F6', 
                        color: 'white', 
                        padding: '8px 16px', 
                        borderRadius: '8px', 
                        fontWeight: 'bold', 
                        border: 'none', 
                        cursor: isLoadingEmails ? 'not-allowed' : 'pointer',
                        opacity: isLoadingEmails ? 0.7 : 1,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginTop: '12px'
                      }}
                    >
                      <RefreshCw size={16} className={isLoadingEmails ? "spin" : ""} />
                      Coba Lagi
                    </button>
                  </div>
                )}

                {errorMsg && (
                  <div style={{ padding: '10px', background: darkMode ? '#3f1a1a' : '#fee2e2', color: '#ef4444', borderRadius: '8px', fontSize: '12px', marginTop: '16px', textAlign: 'center' }}>
                    {errorMsg}
                  </div>
                )}
              </div>
            ) : (
              <>
                {/* Tombol Tulis Pesan Baru */}
                <button
                  type="button"
                  onClick={() => {
                    setIsComposeOpen(true);
                    setComposeStatusMsg({ type: '', text: '' });
                  }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    fontSize: '13px',
                    fontWeight: '600',
                    border: 'none',
                    cursor: 'pointer',
                    background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
                    color: 'white',
                    marginBottom: '12px',
                    boxShadow: '0 4px 14px rgba(37, 99, 235, 0.28)',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-1px)';
                    e.currentTarget.style.boxShadow = '0 6px 18px rgba(37, 99, 235, 0.38)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'none';
                    e.currentTarget.style.boxShadow = '0 4px 14px rgba(37, 99, 235, 0.28)';
                  }}
                >
                  <PenSquare size={16} />
                  <span>Tulis Pesan Baru</span>
                </button>

                {/* Tab Switcher: 3 Kolom Compact (Masuk, Terkirim, Draf) */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(3, 1fr)', 
                  gap: '4px', 
                  background: darkMode ? 'rgba(255,255,255,0.05)' : '#f3f4f6', 
                  padding: '3px', 
                  borderRadius: '10px', 
                  marginBottom: '14px' 
                }}>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveFolder('inbox');
                      setSelectedEmail(null);
                      if (zimbraEmails.length === 0) fetchEmails(false, 'inbox');
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      padding: '7px 4px',
                      borderRadius: '7px',
                      fontSize: '11px',
                      fontWeight: '600',
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      background: activeFolder === 'inbox' ? '#3B82F6' : 'transparent',
                      color: activeFolder === 'inbox' ? 'white' : (darkMode ? '#9ca3af' : '#4b5563')
                    }}
                    title="Kotak Masuk"
                  >
                    <Inbox size={13} />
                    <span>Masuk</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveFolder('sent');
                      setSelectedEmail(null);
                      if (zimbraSentEmails.length === 0) fetchEmails(false, 'sent');
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      padding: '7px 4px',
                      borderRadius: '7px',
                      fontSize: '11px',
                      fontWeight: '600',
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      background: activeFolder === 'sent' ? '#3B82F6' : 'transparent',
                      color: activeFolder === 'sent' ? 'white' : (darkMode ? '#9ca3af' : '#4b5563')
                    }}
                    title="Pesan Terkirim"
                  >
                    <SendHorizontal size={13} />
                    <span>Terkirim</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveFolder('drafts');
                      setSelectedEmail(null);
                      fetchDrafts();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      padding: '7px 4px',
                      borderRadius: '7px',
                      fontSize: '11px',
                      fontWeight: '600',
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      background: activeFolder === 'drafts' ? '#3B82F6' : 'transparent',
                      color: activeFolder === 'drafts' ? 'white' : (darkMode ? '#9ca3af' : '#4b5563')
                    }}
                    title="Draf Tersimpan"
                  >
                    <FileText size={13} />
                    <span>Draf</span>
                    {zimbraDraftEmails.length > 0 && (
                      <span style={{ 
                        fontSize: '9px', 
                        padding: '1px 5px', 
                        borderRadius: '10px', 
                        background: activeFolder === 'drafts' ? 'rgba(255,255,255,0.25)' : (darkMode ? '#374151' : '#E5E7EB'),
                        color: activeFolder === 'drafts' ? 'white' : theme.textColor 
                      }}>
                        {zimbraDraftEmails.length}
                      </span>
                    )}
                  </button>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', paddingLeft: '4px', paddingRight: '4px' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: '600', color: theme.secondaryText }}>
                    {activeFolder === 'sent' ? 'Pesan Terkirim (Zimbra)' : activeFolder === 'drafts' ? 'Draf Tersimpan' : 'Kotak Masuk (Zimbra)'}
                  </span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={() => fetchEmails(true, activeFolder)} disabled={isLoadingEmails} title="Refresh" style={{ background: 'transparent', border: 'none', cursor: isLoadingEmails ? 'not-allowed' : 'pointer', opacity: isLoadingEmails ? 0.5 : 1, display: 'flex', alignItems: 'center', color: theme.textColor }}>
                      <RefreshCw size={16} className={isLoadingEmails ? "spin" : ""} />
                    </button>
                  </div>
                </div>
                
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
                {isLoadingEmails && (activeFolder === 'sent' ? zimbraSentEmails.length === 0 : activeFolder === 'drafts' ? zimbraDraftEmails.length === 0 : zimbraEmails.length === 0) ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>Menyinkronkan data...</div>
                ) : errorMsg ? (
                  <div style={{ padding: '12px', background: darkMode ? '#3f1a1a' : '#fee2e2', color: '#ef4444', borderRadius: '8px', fontSize: '12px' }}>
                    {errorMsg}
                  </div>
                ) : activeFolder === 'drafts' ? (
                  zimbraDraftEmails.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>
                      Belum ada draf tersimpan.
                    </div>
                  ) : (
                    zimbraDraftEmails.map((draft) => (
                      <div 
                        key={`draft-${draft.id}`}
                        onClick={() => { 
                          setSelectedEmail(draft);
                          if (isMobile) setMobileView('detail');
                        }}
                        onDoubleClick={() => handleOpenDraftInComposer(draft)}
                        style={{ 
                          padding: '12px', 
                          background: selectedEmail?.id === draft.id ? (darkMode ? '#2A2A2D' : 'white') : (darkMode ? 'rgba(255,255,255,0.02)' : 'white'), 
                          borderRadius: '10px', 
                          borderLeft: '4px solid #F59E0B', 
                          marginBottom: '8px', 
                          cursor: 'pointer',
                          borderTop: selectedEmail?.id === draft.id ? `1px solid ${theme.borderColor}` : '1px solid transparent',
                          borderRight: selectedEmail?.id === draft.id ? `1px solid ${theme.borderColor}` : '1px solid transparent',
                          borderBottom: selectedEmail?.id === draft.id ? `1px solid ${theme.borderColor}` : '1px solid transparent',
                          transition: 'all 0.2s ease',
                          boxShadow: selectedEmail?.id === draft.id ? '0 4px 6px -1px rgba(0, 0, 0, 0.1)' : 'none'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ 
                            fontSize: '10px', fontWeight: 'bold', padding: '1px 6px', borderRadius: '4px',
                            color: '#F59E0B', background: 'rgba(245, 158, 11, 0.12)'
                          }}>
                            📝 Draf
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteDraft(e, draft.id)}
                            title="Hapus Draf"
                            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: theme.secondaryText, padding: '2px' }}
                          >
                            <Trash2 size={13} className="hover:text-red-500" />
                          </button>
                        </div>
                        <div style={{ fontWeight: '600', fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: selectedEmail?.id === draft.id ? theme.textColor : theme.secondaryText }}>
                          {draft.subject || '(Tanpa Subjek)'}
                        </div>
                        <div style={{ fontSize: '11px', color: theme.secondaryText, marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          Kepada: {draft.to || '(Tanpa Penerima)'}
                        </div>
                        <div style={{ fontSize: '10px', color: theme.secondaryText, marginTop: '4px', opacity: 0.75 }}>
                          {formatRelativeDate(draft.updated_at)}
                        </div>
                      </div>
                    ))
                  )
                ) : (activeFolder === 'sent' ? zimbraSentEmails.length === 0 : zimbraEmails.length === 0) ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>
                    {activeFolder === 'sent' ? 'Belum ada email terkirim.' : 'Tidak ada email masuk.'}
                  </div>
                ) : (
                  (activeFolder === 'sent' ? zimbraSentEmails : zimbraEmails).map((email) => (
                    <div 
                      key={email.id || email.message_id}
                      onClick={() => { 
                        setSelectedEmail(email); 
                        setDraftContent(""); 
                        setInstruction(""); 
                        setReplyAttachments([]);
                        if (isMobile) {
                          setMobileView('detail');
                        }
                      }}
                      onMouseEnter={(e) => {
                        if (selectedEmail?.id !== email.id) {
                          e.currentTarget.style.transform = 'translateY(-2px)';
                          e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (selectedEmail?.id !== email.id) {
                          e.currentTarget.style.transform = 'none';
                          e.currentTarget.style.boxShadow = 'none';
                        }
                      }}
                      style={{ 
                        padding: '14px', 
                        background: selectedEmail?.id === email.id ? (darkMode ? '#2A2A2D' : 'white') : (darkMode ? 'rgba(255,255,255,0.02)' : 'white'), 
                        borderRadius: '10px', 
                        borderLeft: `4px solid ${activeFolder === 'sent' ? '#3B82F6' : (email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? '#ef4444' : (email.priority?.includes('APPROVAL') || email.priority?.includes('Scanning')) ? '#f59e0b' : email.priority?.includes('SPAM') ? '#8b5cf6' : '#10b981'}`, 
                        marginBottom: '10px', 
                        cursor: 'pointer',
                        borderTop: selectedEmail?.id === email.id ? `1px solid ${theme.borderColor}` : '1px solid transparent',
                        borderRight: selectedEmail?.id === email.id ? `1px solid ${theme.borderColor}` : '1px solid transparent',
                        borderBottom: selectedEmail?.id === email.id ? `1px solid ${theme.borderColor}` : '1px solid transparent',
                        transition: 'all 0.2s ease',
                        boxShadow: selectedEmail?.id === email.id ? '0 4px 6px -1px rgba(0, 0, 0, 0.1)' : 'none'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <div style={{ 
                          display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', fontWeight: 'bold', padding: '2px 6px', borderRadius: '4px',
                          color: activeFolder === 'sent' ? '#3B82F6' : (email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? '#ef4444' : (email.priority?.includes('APPROVAL') || email.priority?.includes('Scanning')) ? '#f59e0b' : email.priority?.includes('SPAM') ? '#8b5cf6' : '#10b981',
                          background: activeFolder === 'sent' ? 'rgba(59, 130, 246, 0.1)' : (email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? 'rgba(239, 68, 68, 0.1)' : (email.priority?.includes('APPROVAL') || email.priority?.includes('Scanning')) ? 'rgba(245, 158, 11, 0.1)' : email.priority?.includes('SPAM') ? 'rgba(139, 92, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)'
                        }}>
                          {activeFolder === 'sent' ? <SendHorizontal size={12} /> : (email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? <CircleDot size={12} /> : email.priority?.includes('Scanning') ? <Hourglass size={12} /> : email.priority?.includes('SPAM') ? <Ban size={12} /> : <CheckCircle2 size={12} />}
                          {email.priority?.replace(/🔴 |🟡 |🟢 |⏳ |🚫 |📤 /g, '')}
                        </div>
                        {email.attachments && email.attachments.length > 0 && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '10px', color: theme.secondaryText }}>
                            <Paperclip size={11} className="text-blue-400" />
                            <span>{email.attachments.length}</span>
                          </div>
                        )}
                      </div>
                      <div style={{ fontWeight: '600', fontSize: '14px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: selectedEmail?.id === email.id ? theme.textColor : theme.secondaryText }}>{email.subject}</div>
                      <div style={{ fontSize: '12px', color: theme.secondaryText, marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {activeFolder === 'sent' ? `Kepada: ${email.recipient || '(Tanpa Penerima)'}` : (email.sender || 'Pindad System')}
                      </div>
                      <div style={{ fontSize: '10px', color: theme.secondaryText, marginTop: '4px', opacity: 0.8 }}>
                        {formatRelativeDate(email.received_at)}
                      </div>
                    </div>
                  ))
                )}
                </div>
              </>
            )}
          </div>
        )}

        {/* Kanan: AI Assistant & Detail */}
        {isZimbraAuthenticated && (!isMobile || mobileView === 'detail') && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, width: isMobile ? '100%' : undefined }}>
            {/* Tombol Back ke Kotak Masuk di Mobile */}
            {isMobile && (
              <button
                onClick={() => setMobileView('list')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 14px',
                  borderRadius: '8px',
                  background: darkMode ? '#27272a' : '#f3f4f6',
                  border: `1px solid ${darkMode ? '#3f3f46' : '#e5e7eb'}`,
                  color: theme.textColor,
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  marginBottom: '10px',
                  alignSelf: 'flex-start'
                }}
              >
                <ArrowLeft size={16} />
                <span>Kembali ke Daftar Email</span>
              </button>
            )}

            {/* Email Reading Bubble */}
            <div style={{ background: darkMode ? '#1E1E22' : 'white', borderRadius: '12px', padding: isMobile ? '16px' : '24px', border: `1px solid ${theme.borderColor}`, flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
              {selectedEmail ? (
                <>
                  <h3 style={{ fontSize: isMobile ? '1.1rem' : '1.2rem', fontWeight: 'bold', marginBottom: '8px' }}>{selectedEmail.subject}</h3>
                  <div style={{ fontSize: '12px', color: theme.secondaryText, marginBottom: '16px' }}>
                    <div>
                      {formatRelativeDate(selectedEmail.received_at)} - {activeFolder === 'sent' ? `Kepada: ${selectedEmail.recipient || '-'}` : selectedEmail.sender}
                    </div>
                    {selectedEmail.cc && <div style={{ marginTop: '4px', fontStyle: 'italic' }}>CC: {selectedEmail.cc}</div>}
                  </div>

                  {/* 📎 Attachment Chips (Jika email memiliki lampiran file dokumen) */}
                  {selectedEmail.attachments && selectedEmail.attachments.length > 0 && (
                    <div style={{ 
                      marginBottom: '16px', 
                      padding: '12px 14px', 
                      background: darkMode ? 'rgba(255,255,255,0.03)' : '#f8fafc', 
                      borderRadius: '10px', 
                      border: `1px solid ${darkMode ? '#3f3f46' : '#e2e8f0'}` 
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '600', marginBottom: '10px', color: theme.textColor }}>
                        <Paperclip size={14} className="text-blue-500" />
                        <span>Dokumen Lampiran ({selectedEmail.attachments.length})</span>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {selectedEmail.attachments.map((att, idx) => (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px',
                              padding: '8px 12px',
                              background: darkMode ? '#27272a' : 'white',
                              borderRadius: '8px',
                              border: `1px solid ${darkMode ? '#3f3f46' : '#e2e8f0'}`,
                              fontSize: '12px',
                              boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
                            }}
                          >
                            <FileText size={16} className="text-blue-500 flex-shrink-0" />
                            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, maxWidth: '220px' }}>
                              <span style={{ fontWeight: 600, color: theme.textColor, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={att.filename}>
                                {att.filename}
                              </span>
                              <span style={{ fontSize: '10px', color: theme.secondaryText }}>
                                {att.size_kb ? `${att.size_kb} KB` : 'Dokumen'}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleDownloadAttachment(selectedEmail.id || selectedEmail.uid, att.part_index, att.filename)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: '5px',
                                borderRadius: '6px',
                                background: darkMode ? '#3f3f46' : '#f1f5f9',
                                border: 'none',
                                cursor: 'pointer',
                                color: theme.textColor,
                                marginLeft: '6px',
                                transition: 'background 0.15s ease'
                              }}
                              title={`Unduh ${att.filename}`}
                            >
                              <Download size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                
                {isSelectedEmailQuarantined ? (
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: darkMode ? 'rgba(239, 68, 68, 0.05)' : 'rgba(239, 68, 68, 0.05)', border: '1px solid #ef4444', borderRadius: '12px', padding: '32px', textAlign: 'center' }}>
                    <ShieldAlert size={64} color="#ef4444" style={{ marginBottom: '16px' }} />
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#ef4444', marginBottom: '12px' }}>Karantina Keamanan</h2>
                    <p style={{ color: theme.secondaryText, marginBottom: '24px', maxWidth: '400px' }}>
                      Email ini diindikasi sebagai SPAM, SCAM, atau Phishing berbahaya. CAKRA telah mengunci tautan dan konten aslinya.
                    </p>
                    
                    <div style={{ background: darkMode ? '#18181A' : 'white', border: `1px solid ${darkMode ? '#ef444433' : '#ef444455'}`, padding: '16px', borderRadius: '8px', marginBottom: '24px', width: '100%', maxWidth: '500px', textAlign: 'left' }}>
                      <div style={{ fontWeight: 'bold', color: '#ef4444', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Bot size={16} /> Analisis Ancaman (AI SOC)
                      </div>
                      <div style={{ fontSize: '14px', color: theme.textColor, lineHeight: '1.5' }}>
                        {isAnalyzingThreat && !threatAnalysis[selectedEmail.id] ? "Memeriksa taktik rekayasa sosial..." : (threatAnalysis[selectedEmail.id] || "Tidak ada detail lanjutan.")}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', width: '100%', maxWidth: '300px' }}>
                      <input 
                        type="password"
                        placeholder="Masukkan password Zimbra"
                        value={unlockPasswordInput}
                        onChange={(e) => setUnlockPasswordInput(e.target.value)}
                        style={{ width: '100%', padding: '10px 14px', borderRadius: '6px', background: darkMode ? '#18181A' : 'white', border: `1px solid ${theme.borderColor}`, color: theme.textColor, outline: 'none' }}
                      />
                      <button 
                        onClick={() => {
                          if (unlockPasswordInput === zimbraPassword) {
                            setUnlockedSpamEmails(prev => new Set(prev).add(selectedEmail.id));
                            setUnlockPasswordInput("");
                          } else {
                            alert("Password Zimbra salah!");
                          }
                        }}
                        style={{ width: '100%', padding: '10px 16px', background: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                      >
                        <Key size={16} /> Buka Karantina (Risiko Pribadi)
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div 
                      className="email-html-content"
                      style={{ 
                        fontSize: '14px', 
                        lineHeight: '1.6', 
                        overflowX: 'auto',
                        background: 'white',
                        color: 'black',
                        padding: '20px',
                        borderRadius: '8px',
                        border: '1px solid #e5e7eb'
                      }}
                      dangerouslySetInnerHTML={{ 
                        __html: DOMPurify.sanitize(selectedEmail.content_html || selectedEmail.content, {
                          ADD_ATTR: ['target'],
                          ADD_DATA_URI_TAGS: ['img']
                        })
                      }}
                    />
                    <style>
                      {`
                        .email-html-content img {
                          max-width: 100%;
                          height: auto;
                        }
                        .email-html-content a {
                          color: #3B82F6 !important;
                          text-decoration: underline;
                        }
                        .email-html-content table {
                          border-collapse: collapse;
                        }
                        .email-html-content td, .email-html-content th {
                          padding: 0;
                        }
                        .email-html-content p {
                          margin-bottom: 1em;
                        }
                      `}
                    </style>
                  </>
                )}
              </>
            ) : (
              <div style={{ color: theme.secondaryText, textAlign: 'center', marginTop: '20px' }}>Pilih email untuk membaca dan melihat detailnya.</div>
            )}
          </div>

          {/* Draf Balasan Resmi CAKRA & Resizer - HANYA tampil jika folder Masuk (Inbox) dan email TIDAK sedang dikarantina */}
          {activeFolder === 'inbox' && !isSelectedEmailQuarantined && (
            <>
              {/* Resizer Divider (Desktop Only) */}
              {!isMobile && (
                <div 
                  onMouseDown={(e) => {
                    setIsResizing(true);
                    startYRef.current = e.clientY;
                    startHeightRef.current = draftHeight;
                  }}
                  style={{ 
                    height: '12px', 
                    cursor: 'row-resize', 
                    display: 'flex', 
                    justifyContent: 'center', 
                    alignItems: 'center',
                    margin: '6px 0',
                    opacity: isResizing ? 1 : 0.6,
                    transition: 'opacity 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = 1}
                  onMouseLeave={(e) => { if(!isResizing) e.currentTarget.style.opacity = 0.6 }}
                >
                  <div style={{ width: '60px', height: '4px', background: darkMode ? '#4B5563' : '#D1D5DB', borderRadius: '2px' }} />
                </div>
              )}

              {/* AI Draft Area */}
              <div style={{ 
                height: isMobile ? 'auto' : `${draftHeight}px`, 
                minHeight: isMobile ? '280px' : undefined,
                flexShrink: 0, 
                background: darkMode ? 'rgba(59, 130, 246, 0.08)' : '#F0F9FF', 
                borderRadius: '12px', 
                padding: isMobile ? '12px' : '14px 18px', 
                border: `1px solid ${darkMode ? 'rgba(59, 130, 246, 0.3)' : '#bae6fd'}`, 
                display: 'flex', 
                flexDirection: 'column',
                marginTop: isMobile ? '12px' : 0
              }}>
                {/* 1. Baris Judul & Opsi Teruskan/Reply All */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Bot size={18} style={{ color: darkMode ? '#60A5FA' : '#2563EB' }} />
                    <span style={{ fontWeight: '600', fontSize: isMobile ? '13px' : '14px', color: darkMode ? '#60A5FA' : '#2563EB' }}>Draf Balasan Resmi CAKRA</span>
                  </div>
                  
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    {!isForwarding && selectedEmail?.cc && (
                      <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', color: theme.secondaryText }}>
                        <input type="checkbox" checked={replyAll} onChange={(e) => setReplyAll(e.target.checked)} />
                        Reply All
                      </label>
                    )}
                    
                    <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', color: isForwarding ? '#10B981' : theme.secondaryText, fontWeight: isForwarding ? 'bold' : 'normal' }}>
                      <input type="checkbox" checked={isForwarding} onChange={(e) => setIsForwarding(e.target.checked)} />
                      Teruskan (Forward)
                    </label>
                    
                    {isForwarding && (
                      <input 
                        type="email" 
                        placeholder="Email tujuan..." 
                        value={forwardTo}
                        onChange={(e) => setForwardTo(e.target.value)}
                        style={{
                          background: darkMode ? '#1E1E22' : 'white',
                          border: `1px solid ${theme.borderColor}`,
                          borderRadius: '4px',
                          padding: '4px 8px',
                          color: theme.textColor,
                          fontSize: '12px',
                          outline: 'none',
                          width: isMobile ? '100%' : '180px'
                        }}
                      />
                    )}
                  </div>
                </div>

                {/* 2. Attachment Bar (Kiri) & Quick Actions Pilihan Balasan (Kanan) */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 2px',
                  marginBottom: '6px',
                  flexWrap: 'wrap',
                  gap: '8px'
                }}>
                  {/* Sisi Kiri: Tombol Attach + Tip + Chips Lampiran */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <input
                      type="file"
                      ref={replyFileInputRef}
                      multiple
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          handleReplyFileSelect(e.target.files);
                          e.target.value = '';
                        }
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => replyFileInputRef.current?.click()}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        border: `1px solid ${theme.borderColor}`,
                        background: darkMode ? '#27272a' : '#f3f4f6',
                        color: theme.textColor,
                        fontSize: '11px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = darkMode ? '#3f3f46' : '#e5e7eb'}
                      onMouseLeave={(e) => e.currentTarget.style.background = darkMode ? '#27272a' : '#f3f4f6'}
                    >
                      <Paperclip size={12} />
                      <span>Attach</span>
                      <ChevronDown size={11} />
                    </button>
                    <span style={{ fontSize: '11px', color: theme.secondaryText, fontStyle: 'italic' }}>
                      Tip: drag and drop files from your desktop to add attachments to this message.
                    </span>

                    {/* Chips File Terlampir */}
                    {replyAttachments.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {replyAttachments.map((att, idx) => (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: darkMode ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff',
                              border: `1px solid ${darkMode ? 'rgba(59, 130, 246, 0.35)' : '#bfdbfe'}`,
                              fontSize: '11px',
                              color: theme.textColor
                            }}
                          >
                            <FileText size={11} className="text-blue-500" />
                            <span style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={att.filename}>
                              {att.filename}
                            </span>
                            <span style={{ fontSize: '10px', color: theme.secondaryText }}>
                              ({Math.round(att.size / 1024)} KB)
                            </span>
                            <button
                              type="button"
                              onClick={() => handleRemoveReplyAttachment(idx)}
                              style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '1px', display: 'flex', color: theme.secondaryText }}
                              title="Hapus lampiran"
                            >
                              <X size={11} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Sisi Kanan: Pilihan Balasan Sopan, Ringkas, Setujui, Tolak Halus */}
                  <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                    {quickActions.map(action => (
                      <button
                        key={action.label}
                        onClick={() => {
                          setInstruction(action.prompt);
                          handleGenerate(action.prompt);
                        }}
                        disabled={isGenerating}
                        style={{
                          background: darkMode ? '#374151' : '#E5E7EB',
                          color: theme.textColor,
                          border: 'none',
                          padding: '4px 8px',
                          borderRadius: '12px',
                          fontSize: '11px',
                          cursor: isGenerating ? 'not-allowed' : 'pointer',
                          transition: 'all 0.2s ease',
                          opacity: isGenerating ? 0.5 : 1
                        }}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Formatting Toolbar (Tersambung langsung dengan Textarea) */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '3px',
                  flexWrap: 'wrap',
                  padding: '4px 8px',
                  background: darkMode ? '#222226' : '#f8fafc',
                  border: `1px solid ${theme.borderColor}`,
                  borderRadius: '8px 8px 0 0',
                  borderBottom: 'none'
                }}>
                  <select
                    onChange={(e) => {
                      if (replyTextareaRef.current) {
                        replyTextareaRef.current.style.fontFamily = e.target.value;
                      }
                    }}
                    style={{
                      background: darkMode ? '#27272a' : 'white',
                      border: `1px solid ${theme.borderColor}`,
                      borderRadius: '4px',
                      padding: '2px 5px',
                      fontSize: '11px',
                      color: theme.textColor,
                      outline: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="sans-serif">Sans Serif</option>
                    <option value="serif">Serif</option>
                    <option value="monospace">Monospace</option>
                  </select>

                  <select
                    onChange={(e) => {
                      if (replyTextareaRef.current) {
                        replyTextareaRef.current.style.fontSize = e.target.value;
                      }
                    }}
                    defaultValue="13px"
                    style={{
                      background: darkMode ? '#27272a' : 'white',
                      border: `1px solid ${theme.borderColor}`,
                      borderRadius: '4px',
                      padding: '2px 5px',
                      fontSize: '11px',
                      color: theme.textColor,
                      outline: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="11px">10pt</option>
                    <option value="13px">12pt</option>
                    <option value="15px">14pt</option>
                    <option value="18px">18pt</option>
                  </select>

                  <div style={{ width: '1px', height: '16px', background: theme.borderColor, margin: '0 3px' }} />

                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('bold')} 
                    title="Tebal (Bold)" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Bold size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('italic')} 
                    title="Miring (Italic)" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Italic size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('underline')} 
                    title="Garis Bawah (Underline)" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Underline size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('strikethrough')} 
                    title="Coret (Strikethrough)" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Strikethrough size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('clear')} 
                    title="Hapus Pemformatan" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '2px 5px', cursor: 'pointer', color: theme.textColor, fontSize: '11px', fontWeight: 'bold' }}
                  >
                    T<span style={{ fontSize: '9px' }}>x</span>
                  </button>

                  <div style={{ width: '1px', height: '16px', background: theme.borderColor, margin: '0 3px' }} />

                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('bullet')} 
                    title="Bullet List" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <List size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('number')} 
                    title="Numbered List" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <ListOrdered size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('quote')} 
                    title="Kutipan (Quote)" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Quote size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('code')} 
                    title="Kode / Monospace" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Code size={12} />
                  </button>
                  <button 
                    type="button" 
                    onClick={() => applyReplyFormatting('link')} 
                    title="Sisipkan Tautan (Link)" 
                    style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '3px 5px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                  >
                    <Link2 size={12} />
                  </button>
                </div>

                {/* 4. Textarea Terintegrasi dengan Dropzone */}
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
                  <textarea 
                    ref={replyTextareaRef}
                    placeholder="Isi draf balasan pesan atau seret file lampiran ke sini..."
                    style={{ 
                      width: '100%', 
                      flex: 1,
                      minHeight: isMobile ? '90px' : '110px', 
                      background: darkMode ? '#27272A' : '#FAFAFA', 
                      border: `1px solid ${isDraggingReplyAttachment ? '#3B82F6' : theme.borderColor}`,
                      borderTop: 'none',
                      borderRadius: '0 0 8px 8px',
                      padding: '10px 12px',
                      color: theme.textColor,
                      fontSize: '13px',
                      lineHeight: '1.6',
                      resize: 'none',
                      outline: 'none',
                      boxShadow: isDraggingReplyAttachment ? '0 0 0 2px rgba(59, 130, 246, 0.25)' : 'none',
                      transition: 'border 0.2s ease'
                    }}
                    value={draftContent}
                    onChange={(e) => setDraftContent(e.target.value)}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDraggingReplyAttachment(true);
                    }}
                    onDragLeave={(e) => {
                      e.preventDefault();
                      setIsDraggingReplyAttachment(false);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDraggingReplyAttachment(false);
                      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                        handleReplyFileSelect(e.dataTransfer.files);
                      }
                    }}
                  />
                </div>
                
                {/* 5. Baris Kontrol Bawah (Instruksi, Generate, Kirim) */}
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px', alignItems: 'center', flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
                  <input 
                    type="text" 
                    placeholder="Instruksi tambahan (Opsional)..."
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                    disabled={isGenerating}
                    style={{
                      flex: isMobile ? '1 1 100%' : 1,
                      background: darkMode ? '#1E1E22' : 'white',
                      border: `1px solid ${theme.borderColor}`,
                      borderRadius: '6px',
                      padding: '8px 12px',
                      color: theme.textColor,
                      fontSize: '13px',
                      outline: 'none',
                      width: isMobile ? '100%' : 'auto'
                    }}
                  />
                  <button 
                    onClick={() => handleGenerate()}
                    disabled={isGenerating}
                    style={{ 
                      flex: isMobile ? 1 : undefined,
                      background: isGenerating ? '#9CA3AF' : '#3B82F6', 
                      color: 'white', 
                      padding: '8px 16px', 
                      borderRadius: '6px', 
                      fontSize: '13px',
                      fontWeight: '500', 
                      border: 'none', 
                      cursor: isGenerating ? 'not-allowed' : 'pointer',
                      whiteSpace: 'nowrap',
                      textAlign: 'center'
                    }}
                  >
                    {isGenerating ? 'Loading...' : 'Generate'}
                  </button>
                  <button
                    onClick={handleSendEmail}
                    disabled={isSending || isGenerating || !draftContent}
                    style={{
                      flex: isMobile ? 1 : undefined,
                      background: isSending ? '#9CA3AF' : (isForwarding ? '#F59E0B' : '#10B981'),
                      color: 'white',
                      padding: '8px 16px',
                      borderRadius: '6px',
                      fontSize: '13px',
                      fontWeight: '500',
                      border: 'none',
                      cursor: (isSending || isGenerating || !draftContent) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    {isForwarding ? <ForwardIcon size={14} /> : <Send size={14} />}
                    {isSending ? 'Mengirim...' : (isForwarding ? 'Kirim Forward' : 'Kirim Reply')}
                  </button>
                </div>
                
                {sendSuccess && (
                  <div style={{ color: '#10B981', fontSize: '12px', marginTop: '6px', textAlign: 'right', fontWeight: 'bold' }}>
                    ✅ Email Berhasil Dikirim ke Zimbra!
                  </div>
                )}
              </div>
            </>
          )}
        </div>
        )}
      </div>

      {/* Modal Composer Modern (Tulis Pesan Baru / Edit Draf dengan AI Assistant, Lampiran, & Toolbar Formatting) */}
      {isComposeOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 9999,
          padding: '16px'
        }}>
          <div style={{
            background: darkMode ? '#18181B' : '#FFFFFF',
            borderRadius: '16px',
            border: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.14)' : 'rgba(0, 0, 0, 0.12)'}`,
            boxShadow: '0 25px 60px -12px rgba(0, 0, 0, 0.55)',
            width: '95vw',
            maxWidth: '960px',
            height: '92vh',
            maxHeight: '92vh',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            color: theme.textColor
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '14px 22px',
              borderBottom: `1px solid ${theme.borderColor}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: darkMode ? 'rgba(255, 255, 255, 0.02)' : '#F9FAFB'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: '9px',
                  background: 'linear-gradient(135deg, #2563EB, #1D4ED8)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  boxShadow: '0 2px 8px rgba(37, 99, 235, 0.35)'
                }}>
                  <PenSquare size={17} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>
                    {currentDraftId ? 'Lanjutkan Edit Draf' : 'Tulis Pesan Baru'}
                  </h3>
                  <span style={{ fontSize: '11px', color: theme.secondaryText }}>Smart Mail Zimbra PT Pindad (Persero)</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsComposeOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: theme.secondaryText,
                  cursor: 'pointer',
                  padding: '6px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Form Content */}
            <div style={{ padding: '16px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {/* Field Kepada (To) & CC Toggle */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '64px', fontSize: '13px', fontWeight: '600', color: theme.secondaryText }}>Kepada:</span>
                <input
                  type="text"
                  placeholder="rekan@pindad.com, mitra@perusahaan.com"
                  value={composeTo}
                  onChange={(e) => setComposeTo(e.target.value)}
                  style={{
                    flex: 1,
                    background: darkMode ? '#27272A' : '#F3F4F6',
                    border: `1px solid ${theme.borderColor}`,
                    borderRadius: '8px',
                    padding: '7px 12px',
                    color: theme.textColor,
                    fontSize: '13px',
                    outline: 'none'
                  }}
                />
                {!showCcField && (
                  <button
                    type="button"
                    onClick={() => setShowCcField(true)}
                    style={{
                      background: 'transparent',
                      border: `1px dashed ${theme.borderColor}`,
                      borderRadius: '6px',
                      padding: '6px 10px',
                      fontSize: '11px',
                      color: theme.secondaryText,
                      cursor: 'pointer'
                    }}
                  >
                    + CC
                  </button>
                )}
              </div>

              {/* Field CC (Optional) */}
              {showCcField && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '64px', fontSize: '13px', fontWeight: '600', color: theme.secondaryText }}>CC:</span>
                  <input
                    type="text"
                    placeholder="atasan@pindad.com, manager@pindad.com"
                    value={composeCc}
                    onChange={(e) => setComposeCc(e.target.value)}
                    style={{
                      flex: 1,
                      background: darkMode ? '#27272A' : '#F3F4F6',
                      border: `1px solid ${theme.borderColor}`,
                      borderRadius: '8px',
                      padding: '7px 12px',
                      color: theme.textColor,
                      fontSize: '13px',
                      outline: 'none'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => { setShowCcField(false); setComposeCc(""); }}
                    style={{ background: 'transparent', border: 'none', color: theme.secondaryText, cursor: 'pointer', padding: '4px' }}
                    title="Hapus CC"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              {/* Field Subjek */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '64px', fontSize: '13px', fontWeight: '600', color: theme.secondaryText }}>Subjek:</span>
                <input
                  type="text"
                  placeholder="Subjek pesan..."
                  value={composeSubject}
                  onChange={(e) => setComposeSubject(e.target.value)}
                  style={{
                    flex: 1,
                    background: darkMode ? '#27272A' : '#F3F4F6',
                    border: `1px solid ${theme.borderColor}`,
                    borderRadius: '8px',
                    padding: '7px 12px',
                    color: theme.textColor,
                    fontSize: '13px',
                    fontWeight: '500',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Modern AI Assistant Composer Box */}
              <div style={{
                background: darkMode ? 'linear-gradient(135deg, rgba(37, 99, 235, 0.12) 0%, rgba(139, 92, 246, 0.08) 100%)' : 'linear-gradient(135deg, #EFF6FF 0%, #F5F3FF 100%)',
                border: `1px solid ${darkMode ? 'rgba(59, 130, 246, 0.3)' : '#BFDBFE'}`,
                borderRadius: '12px',
                padding: '10px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Sparkles size={15} style={{ color: '#38BDF8' }} />
                    <span style={{ fontSize: '12px', fontWeight: '700', color: darkMode ? '#93C5FD' : '#1D4ED8' }}>
                      Cakra AI Mail Generator
                    </span>
                  </div>
                  {/* Pilihan Tone Generator */}
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {composeToneOptions.map(tOption => (
                      <button
                        key={tOption.id}
                        type="button"
                        onClick={() => setComposeTone(tOption.id)}
                        style={{
                          background: composeTone === tOption.id ? (darkMode ? '#2563EB' : '#1D4ED8') : (darkMode ? 'rgba(255,255,255,0.06)' : 'white'),
                          color: composeTone === tOption.id ? 'white' : theme.textColor,
                          border: `1px solid ${composeTone === tOption.id ? '#2563EB' : theme.borderColor}`,
                          padding: '3px 8px',
                          borderRadius: '12px',
                          fontSize: '10px',
                          fontWeight: composeTone === tOption.id ? '600' : 'normal',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {tOption.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Tuliskan poin/instruksi pesan (misal: Rapat evaluasi teknis sistem hari Kamis jam 09.00 WIB)..."
                    value={composeAiPrompt}
                    onChange={(e) => setComposeAiPrompt(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleGenerateComposeAi()}
                    disabled={isGeneratingCompose}
                    style={{
                      flex: 1,
                      background: darkMode ? '#1E1E22' : 'white',
                      border: `1px solid ${theme.borderColor}`,
                      borderRadius: '8px',
                      padding: '7px 12px',
                      color: theme.textColor,
                      fontSize: '12px',
                      outline: 'none'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => handleGenerateComposeAi()}
                    disabled={isGeneratingCompose || !composeAiPrompt.trim()}
                    style={{
                      background: isGeneratingCompose ? '#9CA3AF' : 'linear-gradient(135deg, #3B82F6 0%, #6366F1 100%)',
                      color: 'white',
                      padding: '7px 14px',
                      borderRadius: '8px',
                      fontSize: '12px',
                      fontWeight: '600',
                      border: 'none',
                      cursor: (isGeneratingCompose || !composeAiPrompt.trim()) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    <Sparkles size={13} className={isGeneratingCompose ? "spin" : ""} />
                    <span>{isGeneratingCompose ? 'Membuat Draf...' : 'Buat dengan AI'}</span>
                  </button>
                </div>
              </div>

              {/* 1. Baris Attachment (Mirip Gambar ke-2) */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                flexWrap: 'wrap',
                padding: '6px 2px',
                borderBottom: `1px solid ${theme.borderColor}`
              }}>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  multiple 
                  style={{ display: 'none' }} 
                  onChange={(e) => handleFileSelect(e.target.files)} 
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '5px 12px',
                    borderRadius: '6px',
                    border: `1px solid ${theme.borderColor}`,
                    background: darkMode ? '#27272a' : '#f3f4f6',
                    color: theme.textColor,
                    fontSize: '12px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = darkMode ? '#3f3f46' : '#e5e7eb'}
                  onMouseLeave={(e) => e.currentTarget.style.background = darkMode ? '#27272a' : '#f3f4f6'}
                >
                  <Paperclip size={13} />
                  <span>Attach</span>
                  <ChevronDown size={12} />
                </button>
                <span style={{ fontSize: '11px', color: theme.secondaryText, fontStyle: 'italic' }}>
                  Tip: drag and drop files from your desktop to add attachments to this message.
                </span>
              </div>

              {/* Chips File Terlampir */}
              {composeAttachments.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', padding: '2px 0' }}>
                  {composeAttachments.map((att, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        background: darkMode ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff',
                        border: `1px solid ${darkMode ? 'rgba(59, 130, 246, 0.35)' : '#bfdbfe'}`,
                        fontSize: '11px',
                        color: theme.textColor
                      }}
                    >
                      <FileText size={13} className="text-blue-500" />
                      <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: '500' }} title={att.filename}>
                        {att.filename}
                      </span>
                      <span style={{ fontSize: '10px', color: theme.secondaryText }}>
                        ({Math.round(att.size / 1024)} KB)
                      </span>
                      <button
                        type="button"
                        onClick={() => handleRemoveAttachment(idx)}
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '1px', display: 'flex', color: theme.secondaryText }}
                        title="Hapus lampiran"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* 2. Formatting Toolbar (Mirip Gambar ke-2) */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                flexWrap: 'wrap',
                padding: '6px 10px',
                background: darkMode ? '#222226' : '#f8fafc',
                border: `1px solid ${theme.borderColor}`,
                borderRadius: '8px 8px 0 0',
                borderBottom: 'none'
              }}>
                <select
                  onChange={(e) => {
                    if (composeTextareaRef.current) {
                      composeTextareaRef.current.style.fontFamily = e.target.value;
                    }
                  }}
                  style={{
                    background: darkMode ? '#27272a' : 'white',
                    border: `1px solid ${theme.borderColor}`,
                    borderRadius: '4px',
                    padding: '3px 6px',
                    fontSize: '11px',
                    color: theme.textColor,
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="sans-serif">Sans Serif</option>
                  <option value="serif">Serif</option>
                  <option value="monospace">Monospace</option>
                </select>

                <select
                  onChange={(e) => {
                    if (composeTextareaRef.current) {
                      composeTextareaRef.current.style.fontSize = e.target.value;
                    }
                  }}
                  defaultValue="13px"
                  style={{
                    background: darkMode ? '#27272a' : 'white',
                    border: `1px solid ${theme.borderColor}`,
                    borderRadius: '4px',
                    padding: '3px 6px',
                    fontSize: '11px',
                    color: theme.textColor,
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="11px">10pt</option>
                  <option value="13px">12pt</option>
                  <option value="15px">14pt</option>
                  <option value="18px">18pt</option>
                </select>

                <div style={{ width: '1px', height: '18px', background: theme.borderColor, margin: '0 4px' }} />

                <button 
                  type="button" 
                  onClick={() => applyFormatting('bold')} 
                  title="Tebal (Bold)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Bold size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('italic')} 
                  title="Miring (Italic)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Italic size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('underline')} 
                  title="Garis Bawah (Underline)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Underline size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('strikethrough')} 
                  title="Coret (Strikethrough)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Strikethrough size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('clear')} 
                  title="Hapus Pemformatan (Clear Formatting)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '2px 6px', cursor: 'pointer', color: theme.textColor, fontSize: '11px', fontWeight: 'bold' }}
                >
                  T<span style={{ fontSize: '9px' }}>x</span>
                </button>

                <div style={{ width: '1px', height: '18px', background: theme.borderColor, margin: '0 4px' }} />

                <button 
                  type="button" 
                  onClick={() => applyFormatting('bullet')} 
                  title="Bullet List" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <List size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('number')} 
                  title="Numbered List" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <ListOrdered size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('quote')} 
                  title="Kutipan (Quote)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Quote size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('code')} 
                  title="Kode / Monospace" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Code size={13} />
                </button>
                <button 
                  type="button" 
                  onClick={() => applyFormatting('link')} 
                  title="Sisipkan Tautan (Link)" 
                  style={{ background: 'transparent', border: `1px solid ${theme.borderColor}`, borderRadius: '4px', padding: '4px 6px', cursor: 'pointer', color: theme.textColor, display: 'flex' }}
                >
                  <Link2 size={13} />
                </button>
              </div>

              {/* Textarea Isi Pesan dengan Dropzone */}
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
                <textarea
                  ref={composeTextareaRef}
                  placeholder="Ketik isi pesan atau seret file lampiran ke sini..."
                  value={composeBody}
                  onChange={(e) => setComposeBody(e.target.value)}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDraggingAttachment(true);
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault();
                    setIsDraggingAttachment(false);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    setIsDraggingAttachment(false);
                    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                      handleFileSelect(e.dataTransfer.files);
                    }
                  }}
                  style={{
                    width: '100%',
                    flex: 1,
                    minHeight: '220px',
                    background: darkMode ? '#27272A' : '#FAFAFA',
                    border: `1px solid ${isDraggingAttachment ? '#3B82F6' : theme.borderColor}`,
                    borderTop: 'none',
                    borderRadius: '0 0 8px 8px',
                    padding: '14px',
                    color: theme.textColor,
                    fontSize: '13px',
                    lineHeight: '1.6',
                    resize: 'none',
                    outline: 'none',
                    boxShadow: isDraggingAttachment ? '0 0 0 2px rgba(59, 130, 246, 0.25)' : 'none',
                    transition: 'border 0.2s ease'
                  }}
                />
              </div>

              {/* Notification Banner */}
              {composeStatusMsg.text && (
                <div style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: '500',
                  background: composeStatusMsg.type === 'success' ? (darkMode ? 'rgba(16, 185, 129, 0.15)' : '#ECFDF5') : (darkMode ? 'rgba(239, 68, 68, 0.15)' : '#FEF2F2'),
                  color: composeStatusMsg.type === 'success' ? '#10B981' : '#EF4444',
                  border: `1px solid ${composeStatusMsg.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
                }}>
                  {composeStatusMsg.text}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '12px 22px',
              borderTop: `1px solid ${theme.borderColor}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: darkMode ? 'rgba(255, 255, 255, 0.02)' : '#F9FAFB'
            }}>
              <div style={{ fontSize: '12px', color: theme.secondaryText }}>
                Pengirim: <strong style={{ color: theme.textColor }}>{userEmail}</strong>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setIsComposeOpen(false)}
                  disabled={isSendingCompose || isSavingDraft}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    border: `1px solid ${theme.borderColor}`,
                    background: 'transparent',
                    color: theme.textColor,
                    cursor: (isSendingCompose || isSavingDraft) ? 'not-allowed' : 'pointer'
                  }}
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleSaveDraft}
                  disabled={isSendingCompose || isSavingDraft}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: '600',
                    border: `1px solid ${theme.borderColor}`,
                    background: darkMode ? '#27272A' : '#F3F4F6',
                    color: theme.textColor,
                    cursor: (isSendingCompose || isSavingDraft) ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Save size={14} className={isSavingDraft ? "spin" : ""} />
                  <span>{isSavingDraft ? 'Menyimpan...' : 'Simpan Draf'}</span>
                </button>
                <button
                  type="button"
                  onClick={handleSendCompose}
                  disabled={isSendingCompose || isSavingDraft || !composeTo.trim() || !composeSubject.trim() || !composeBody.trim()}
                  style={{
                    padding: '8px 18px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: '600',
                    border: 'none',
                    background: (isSendingCompose || isSavingDraft || !composeTo.trim() || !composeSubject.trim() || !composeBody.trim()) ? '#9CA3AF' : 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                    color: 'white',
                    cursor: (isSendingCompose || isSavingDraft || !composeTo.trim() || !composeSubject.trim() || !composeBody.trim()) ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)'
                  }}
                >
                  <Send size={14} />
                  <span>{isSendingCompose ? 'Mengirim...' : 'Kirim Email'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
