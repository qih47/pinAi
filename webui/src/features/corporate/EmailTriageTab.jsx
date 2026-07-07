import React, { useState, useEffect } from 'react';
import apiClient from '../../services/apiClient';
import DOMPurify from 'dompurify';
import { Mail, Lock, RefreshCw, Bot, CircleDot, CheckCircle2, Send, Forward as ForwardIcon, Hourglass, Ban, ShieldAlert, Key } from 'lucide-react';

export default function EmailTriageTab({ theme, darkMode, userData }) {
  // Gunakan email dari DB jika ada, jika tidak, construct dari NPP
  const userEmail = userData?.email || (userData?.npp ? `${userData.npp}@pindad.com` : "user@pindad.com");

  const [emails, setEmails] = useState([]);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [isLoadingEmails, setIsLoadingEmails] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [zimbraPassword, setZimbraPassword] = useState(() => sessionStorage.getItem('cakra_zimbra_pw') || "");
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
    if (zimbraPassword) {
      fetchEmails(zimbraPassword);
    }
  }, [zimbraPassword]);

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
      const pendingEmails = emails.filter(email => (email.priority === '🔴 Unread' || email.priority === '🟢 Read') && !email.has_triage);
      if (pendingEmails.length === 0) return;

      // Mark as scanning locally so we don't re-process on re-renders
      const idsToScan = pendingEmails.map(e => e.id);
      setEmails(prev => prev.map(e => idsToScan.includes(e.id) ? { ...e, has_triage: true, priority: '⏳ Scanning...' } : e));

      // Process sequentially
      for (const email of pendingEmails) {
        try {
          const res = await apiClient.post('/corporate/emails/triage', { 
            email_content: email.content,
            email_subject: email.subject 
          });
          
          if (res.data.status === 'success') {
             setEmails(prev => prev.map(e => e.id === email.id ? { ...e, priority: res.data.data.priority } : e));
          } else {
             setEmails(prev => prev.map(e => e.id === email.id ? { ...e, priority: email.priority } : e));
          }
        } catch (err) {
          console.error("Triage failed for", email.id, err);
          setEmails(prev => prev.map(e => e.id === email.id ? { ...e, priority: email.priority } : e));
        }
      }
    };

    processTriageQueue();
  }, [emails]);

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

  const fetchEmails = async (passwordOverride = null) => {
    const passwordToUse = passwordOverride || zimbraPassword;
    if (!passwordToUse) return;

    setIsLoadingEmails(true);
    setErrorMsg("");
    
    try {
      const response = await apiClient.post('/corporate/emails/fetch', {
        email: userEmail,
        password: passwordToUse
      });
      if (response.data.status === 'success') {
        setEmails(response.data.data);
        if (response.data.data.length > 0) {
          setSelectedEmail(response.data.data[0]);
        }
        setIsZimbraAuthenticated(true);
        sessionStorage.setItem('cakra_zimbra_pw', passwordToUse);
      } else {
        setErrorMsg(response.data.message || "Gagal autentikasi ke Zimbra.");
        setIsZimbraAuthenticated(false);
        sessionStorage.removeItem('cakra_zimbra_pw');
      }
    } catch (error) {
      console.error("Gagal mengambil email dari Zimbra:", error);
      setErrorMsg("Koneksi ke mail.pindad.com gagal atau kredensial salah.");
      setIsZimbraAuthenticated(false);
      sessionStorage.removeItem('cakra_zimbra_pw');
    } finally {
      setIsLoadingEmails(false);
    }
  };

  const handleLoginZimbra = (e) => {
    e.preventDefault();
    if (zimbraPassword.trim()) {
      fetchEmails(zimbraPassword);
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
    if (!selectedEmail || !draftContent || !zimbraPassword) return;
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
        email: userEmail,
        password: zimbraPassword,
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
    <div style={{ flex: 1, padding: '20px', color: theme.textColor, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Mail size={24} /> CAKRA Smart Mail (Triage & Auto-Draft)
        </h2>
        <div style={{ fontSize: '14px', background: darkMode ? '#2A2A2D' : '#F3F4F6', padding: '6px 12px', borderRadius: '20px', color: theme.secondaryText, marginRight: '24px' }}>
          Kotak Masuk: <strong style={{ color: theme.textColor }}>{userEmail}</strong>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: 0, height: '100%' }}>
        {/* Kiri: Inbox List */}
        <div style={{ width: '380px', background: darkMode ? '#1E1E22' : '#F9FAFB', borderRadius: '12px', padding: '16px', border: `1px solid ${theme.borderColor}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          
          {!isZimbraAuthenticated ? (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'center' }}>
              <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                <Lock size={40} style={{ margin: '0 auto', color: theme.secondaryText }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginTop: '12px', marginBottom: '8px' }}>Otentikasi Zimbra</h3>
                <p style={{ fontSize: '12px', color: theme.secondaryText }}>Masukkan password email Pindad Anda untuk menarik kotak masuk.</p>
                <div style={{ fontSize: '12px', background: darkMode ? '#2A2A2D' : '#e5e7eb', padding: '4px 8px', borderRadius: '4px', marginTop: '8px', display: 'inline-block' }}>{userEmail}</div>
              </div>
              
              <form onSubmit={handleLoginZimbra} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <input 
                  type="password" 
                  placeholder="Password Zimbra..."
                  value={zimbraPassword}
                  onChange={(e) => setZimbraPassword(e.target.value)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: `1px solid ${theme.borderColor}`,
                    background: darkMode ? '#2A2A2D' : 'white',
                    color: theme.textColor,
                    outline: 'none'
                  }}
                  required
                />
                <button 
                  type="submit" 
                  disabled={isLoadingEmails}
                  style={{ 
                    background: '#3B82F6', 
                    color: 'white', 
                    padding: '10px', 
                    borderRadius: '8px', 
                    fontWeight: 'bold', 
                    border: 'none', 
                    cursor: isLoadingEmails ? 'not-allowed' : 'pointer',
                    opacity: isLoadingEmails ? 0.7 : 1
                  }}
                >
                  {isLoadingEmails ? 'Menghubungkan...' : 'Login ke Zimbra'}
                </button>
              </form>

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
                <button onClick={() => fetchEmails()} disabled={isLoadingEmails} style={{ background: 'transparent', border: 'none', cursor: isLoadingEmails ? 'not-allowed' : 'pointer', opacity: isLoadingEmails ? 0.5 : 1, display: 'flex', alignItems: 'center', color: theme.textColor }}>
                  <RefreshCw size={18} />
                </button>
              </div>
              
              <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
              {isLoadingEmails ? (
                <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>Menyinkronkan ulang...</div>
              ) : errorMsg ? (
                <div style={{ padding: '12px', background: darkMode ? '#3f1a1a' : '#fee2e2', color: '#ef4444', borderRadius: '8px', fontSize: '12px' }}>
                  {errorMsg}
                </div>
              ) : emails.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: theme.secondaryText }}>Tidak ada email.</div>
              ) : (
                emails.map((email) => (
                  <div 
                    key={email.id}
                    onClick={() => { setSelectedEmail(email); setDraftContent(""); setInstruction(""); }}
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

        {/* Kanan: AI Assistant & Detail */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {/* Email Reading Bubble */}
          <div style={{ background: darkMode ? '#1E1E22' : 'white', borderRadius: '12px', padding: '24px', border: `1px solid ${theme.borderColor}`, flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
            {selectedEmail ? (
              <>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '8px' }}>{selectedEmail.subject}</h3>
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

          {/* Resizer Divider */}
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

          {/* AI Draft Area */}
          <div style={{ height: `${draftHeight}px`, flexShrink: 0, background: darkMode ? 'rgba(59, 130, 246, 0.1)' : '#F0F9FF', borderRadius: '12px', padding: '20px', border: `1px solid ${darkMode ? 'rgba(59, 130, 246, 0.3)' : '#bae6fd'}`, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Bot size={24} style={{ color: darkMode ? '#60A5FA' : '#2563EB' }} />
                <span style={{ fontWeight: '600', color: darkMode ? '#60A5FA' : '#2563EB' }}>Draf Balasan Resmi CAKRA</span>
              </div>
              
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                {!isForwarding && selectedEmail?.cc && (
                  <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', color: theme.secondaryText }}>
                    <input type="checkbox" checked={replyAll} onChange={(e) => setReplyAll(e.target.checked)} />
                    Reply All (Balas ke CC)
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
                      width: '180px'
                    }}
                  />
                )}
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
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
                    padding: '6px 12px',
                    borderRadius: '16px',
                    fontSize: '12px',
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
                minHeight: '120px', 
                background: darkMode ? '#2A2A2D' : 'white', 
                border: `1px solid ${theme.borderColor}`,
                borderRadius: '8px',
                padding: '12px',
                color: theme.textColor,
                fontSize: '14px',
                resize: 'none',
                outline: 'none'
              }}
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
            />
            
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'center' }}>
              <input 
                type="text" 
                placeholder="Instruksi tambahan (Opsional)..."
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                disabled={isGenerating}
                style={{
                  flex: 1,
                  background: darkMode ? '#1E1E22' : 'white',
                  border: `1px solid ${theme.borderColor}`,
                  borderRadius: '6px',
                  padding: '8px 12px',
                  color: theme.textColor,
                  fontSize: '13px',
                  outline: 'none'
                }}
              />
              <button 
                onClick={() => handleGenerate()}
                disabled={isGenerating}
                style={{ 
                  background: isGenerating ? '#9CA3AF' : '#3B82F6', 
                  color: 'white', 
                  padding: '8px 16px', 
                  borderRadius: '6px', 
                  fontSize: '13px',
                  fontWeight: '500', 
                  border: 'none', 
                  cursor: isGenerating ? 'not-allowed' : 'pointer',
                  whiteSpace: 'nowrap'
                }}
              >
                {isGenerating ? 'Loading...' : 'Generate'}
              </button>
              <button
                onClick={handleSendEmail}
                disabled={isSending || isGenerating || !draftContent}
                style={{
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
      </div>
    </div>
  );
}
