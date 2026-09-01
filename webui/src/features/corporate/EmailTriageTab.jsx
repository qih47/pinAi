import React, { useState, useEffect } from 'react';
import apiClient from '../../services/apiClient';
import DOMPurify from 'dompurify';
import { Mail, Lock, RefreshCw, Bot, CircleDot, CheckCircle2, Send, Forward as ForwardIcon, Hourglass, Ban, ShieldAlert, Key, LogOut, ArrowLeft, PanelLeft } from 'lucide-react';
import { useCorporateStore } from '../../stores/corporateStore';
import { translations } from '../../utils/translations';

export default function EmailTriageTab({ theme, darkMode, userData, language, isMobile = false, toggleSidebar }) {
  const t = translations[language]?.smartMail || translations.id.smartMail;
  const tz = translations[language]?.zimbraAuth || translations.id.zimbraAuth;
  // Gunakan email dari DB jika ada, jika tidak, construct dari NPP
  const userEmail = userData?.email || (userData?.npp ? `${userData.npp}@pindad.com` : "user@pindad.com");

  const zimbraEmails = useCorporateStore(state => state.zimbraEmails);
  const setZimbraEmails = useCorporateStore(state => state.setZimbraEmails);
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

  // Spam Blocker States
  const [unlockedSpamEmails, setUnlockedSpamEmails] = useState(new Set());
  const [unlockPasswordInput, setUnlockPasswordInput] = useState("");
  const [threatAnalysis, setThreatAnalysis] = useState({});
  const [isAnalyzingThreat, setIsAnalyzingThreat] = useState(false);

  // Resize logic
  const [draftHeight, setDraftHeight] = useState(350);
  const [isResizing, setIsResizing] = useState(false);
  const startYRef = React.useRef(0);
  const startHeightRef = React.useRef(0);

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
      fetchEmails();
    } else {
      setIsZimbraAuthenticated(true);
      if (!selectedEmail && zimbraEmails.length > 0) {
         setSelectedEmail(zimbraEmails[0]);
      }
    }
  }, []);

  // Fetch Threat Analysis for Spam Emails
  useEffect(() => {
    if (selectedEmail && selectedEmail.priority && selectedEmail.priority.includes('SPAM') && !unlockedSpamEmails.has(selectedEmail.id)) {
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
  }, [selectedEmail, unlockedSpamEmails]);

  // Background AI Triage Tagging (Sequential to prevent GPU DDoS)
  useEffect(() => {
    const processTriageQueue = async () => {
      const pendingEmails = zimbraEmails.filter(email => (email.priority === '🔴 Unread' || email.priority === '🟢 Read') && !email.has_triage);
      if (pendingEmails.length === 0) return;

      // Mark as scanning locally so we don't re-process on re-renders
      const idsToScan = pendingEmails.map(e => e.id);
      idsToScan.forEach(id => updateZimbraEmail(id, { has_triage: true, priority: '⏳ Scanning...' }));

      // Process sequentially
      for (const email of pendingEmails) {
        try {
          const res = await apiClient.post('/corporate/emails/triage', { 
            email_content: email.content,
            email_subject: email.subject 
          });
          
          if (res.data.status === 'success') {
             updateZimbraEmail(email.id, { priority: res.data.data.priority });
          } else {
             updateZimbraEmail(email.id, { priority: email.priority });
          }
        } catch (err) {
          console.error("Triage failed for", email.id, err);
          updateZimbraEmail(email.id, { priority: email.priority });
        }
      }
    };

    processTriageQueue();
  }, [zimbraEmails, updateZimbraEmail]);

  useEffect(() => {
    if (selectedEmail && !draftContent && !isGenerating) {
      handleGenerate("");
    }
  }, [selectedEmail]);

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

  const fetchEmails = async (isRefresh = false) => {
    setIsLoadingEmails(true);
    setErrorMsg("");
    
    try {
      const response = await apiClient.post('/corporate/emails/fetch', {
        token: localStorage.getItem('cakra_token') || ''
      });
      if (response.data.status === 'success') {
        const fetchedEmails = response.data.data;
        if (isRefresh || zimbraEmails.length > 0) {
           // Merge: only add emails that don't exist in current zimbraEmails cache
           const existingIds = new Set(zimbraEmails.map(e => e.id));
           const newEmails = fetchedEmails.filter(e => !existingIds.has(e.id));
           if (newEmails.length > 0) {
              setZimbraEmails([...newEmails, ...zimbraEmails]);
           }
        } else {
           setZimbraEmails(fetchedEmails);
        }

        if (!selectedEmail && fetchedEmails.length > 0) {
          setSelectedEmail(fetchedEmails[0]);
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

  const handleGenerate = async (customInstruction = instruction) => {
    if (!selectedEmail) return;
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
        body: finalBody
      });
      
      if (response.data.status === 'success') {
        setSendSuccess(true);
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>Inbox (Zimbra)</h3>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={() => fetchEmails(true)} disabled={isLoadingEmails} title="Refresh Email" style={{ background: 'transparent', border: 'none', cursor: isLoadingEmails ? 'not-allowed' : 'pointer', opacity: isLoadingEmails ? 0.5 : 1, display: 'flex', alignItems: 'center', color: theme.textColor }}>
                      <RefreshCw size={18} />
                    </button>
                  </div>
                </div>
                
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
                {isLoadingEmails && zimbraEmails.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>Menyinkronkan ulang...</div>
                ) : errorMsg ? (
                  <div style={{ padding: '12px', background: darkMode ? '#3f1a1a' : '#fee2e2', color: '#ef4444', borderRadius: '8px', fontSize: '12px' }}>
                    {errorMsg}
                  </div>
                ) : zimbraEmails.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>Tidak ada email.</div>
                ) : (
                  zimbraEmails.map((email) => (
                    <div 
                      key={email.id}
                      onClick={() => { 
                        setSelectedEmail(email); 
                        setDraftContent(""); 
                        setInstruction(""); 
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
                        borderLeft: `4px solid ${(email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? '#ef4444' : (email.priority?.includes('APPROVAL') || email.priority?.includes('Scanning')) ? '#f59e0b' : email.priority?.includes('SPAM') ? '#8b5cf6' : '#10b981'}`, 
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
                          color: (email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? '#ef4444' : (email.priority?.includes('APPROVAL') || email.priority?.includes('Scanning')) ? '#f59e0b' : email.priority?.includes('SPAM') ? '#8b5cf6' : '#10b981',
                          background: (email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? 'rgba(239, 68, 68, 0.1)' : (email.priority?.includes('APPROVAL') || email.priority?.includes('Scanning')) ? 'rgba(245, 158, 11, 0.1)' : email.priority?.includes('SPAM') ? 'rgba(139, 92, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)'
                        }}>
                          {(email.priority?.includes('URGENT') || email.priority === '🔴 Unread') ? <CircleDot size={12} /> : email.priority?.includes('Scanning') ? <Hourglass size={12} /> : email.priority?.includes('SPAM') ? <Ban size={12} /> : <CheckCircle2 size={12} />}
                          {email.priority?.replace(/🔴 |🟡 |🟢 |⏳ |🚫 /g, '')}
                        </div>
                      </div>
                      <div style={{ fontWeight: '600', fontSize: '14px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: selectedEmail?.id === email.id ? theme.textColor : theme.secondaryText }}>{email.subject}</div>
                      <div style={{ fontSize: '12px', color: theme.secondaryText, marginTop: '6px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', opacity: 0.8 }}>Dari: {email.sender}</div>
                      <div style={{ fontSize: '10px', color: theme.secondaryText, marginTop: '4px', opacity: 0.6 }}>{formatRelativeDate(email.received_at)}</div>
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
                <span>Kembali ke Kotak Masuk</span>
              </button>
            )}

            {/* Email Reading Bubble */}
            <div style={{ background: darkMode ? '#1E1E22' : 'white', borderRadius: '12px', padding: isMobile ? '16px' : '24px', border: `1px solid ${theme.borderColor}`, flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
              {selectedEmail ? (
                <>
                  <h3 style={{ fontSize: isMobile ? '1.1rem' : '1.2rem', fontWeight: 'bold', marginBottom: '8px' }}>{selectedEmail.subject}</h3>
                  <div style={{ fontSize: '12px', color: theme.secondaryText, marginBottom: '16px' }}>
                    <div>{formatRelativeDate(selectedEmail.received_at)} - {selectedEmail.sender}</div>
                    {selectedEmail.cc && <div style={{ marginTop: '4px', fontStyle: 'italic' }}>CC: {selectedEmail.cc}</div>}
                  </div>
                
                {selectedEmail.priority?.includes('SPAM') && !unlockedSpamEmails.has(selectedEmail.id) ? (
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
                          ADD_ATTR: ['target']
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
              <div style={{ color: theme.secondaryText, textAlign: 'center', marginTop: '20px' }}>Pilih email untuk membaca dan membuat draf balasan.</div>
            )}
          </div>

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
            minHeight: isMobile ? '260px' : undefined,
            flexShrink: 0, 
            background: darkMode ? 'rgba(59, 130, 246, 0.1)' : '#F0F9FF', 
            borderRadius: '12px', 
            padding: isMobile ? '14px' : '20px', 
            border: `1px solid ${darkMode ? 'rgba(59, 130, 246, 0.3)' : '#bae6fd'}`, 
            display: 'flex', 
            flexDirection: 'column',
            marginTop: isMobile ? '12px' : 0
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Bot size={20} style={{ color: darkMode ? '#60A5FA' : '#2563EB' }} />
                <span style={{ fontWeight: '600', fontSize: isMobile ? '13px' : '14px', color: darkMode ? '#60A5FA' : '#2563EB' }}>Draf Balasan Resmi CAKRA</span>
              </div>
              
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
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
            
            <div style={{ display: 'flex', gap: '6px', marginBottom: '10px', flexWrap: 'wrap' }}>
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
                    padding: '5px 10px',
                    borderRadius: '14px',
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

            <textarea 
              style={{ 
                width: '100%', 
                flex: 1,
                minHeight: isMobile ? '100px' : '120px', 
                background: darkMode ? '#2A2A2D' : 'white', 
                border: `1px solid ${theme.borderColor}`,
                borderRadius: '8px',
                padding: '10px',
                color: theme.textColor,
                fontSize: '13px',
                resize: 'none',
                outline: 'none'
              }}
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
            />
            
            <div style={{ display: 'flex', gap: '8px', marginTop: '10px', alignItems: 'center', flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
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
              <div style={{ color: '#10B981', fontSize: '12px', marginTop: '8px', textAlign: 'right', fontWeight: 'bold' }}>
                ✅ Email Berhasil Dikirim ke Zimbra!
              </div>
            )}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
