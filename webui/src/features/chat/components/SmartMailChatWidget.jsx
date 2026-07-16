import React, { useState } from 'react';
import { Mail, Send, CheckCircle2, UserCircle2, Eye, Edit3 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import apiClient from '../../../services/apiClient';
import { translations } from '../../../utils/translations';

export default function SmartMailChatWidget({ initialData, darkMode, theme, language = 'id' }) {
    const tGlobal = translations[language] || translations.id;
    const [viewMode, setViewMode] = useState('edit'); // 'edit' or 'preview'
    const [draftData, setDraftData] = useState(() => {
        try {
            return typeof initialData === 'string' ? JSON.parse(initialData) : initialData;
        } catch(e) {
            return { to: "", subject: "Draft Email", body: initialData };
        }
    });

    React.useEffect(() => {
        if (!initialData) return;
        try {
            const parsed = typeof initialData === 'string' ? JSON.parse(initialData) : initialData;
            if (parsed.body) {
                // Ensure literal \n are converted to real newlines permanently
                parsed.body = parsed.body.replace(/\\n/g, '\n');
            }
            setDraftData(parsed);
        } catch(e) {
            // Selama masa streaming (JSON belum tertutup utuh), tampilkan data mentah di body agar efek ngetik terlihat
            setDraftData(prev => ({ ...prev, body: initialData.replace(/\\n/g, '\n') }));
        }
    }, [initialData]);

    const [isSending, setIsSending] = useState(false);
    
    // Gunakan hash sederhana dari initialData sebagai ID unik untuk menyimpan status "Terkirim" di localStorage
    const messageId = React.useMemo(() => {
        if (!initialData) return "empty";
        // Simple hash function for string
        let hash = 0;
        for (let i = 0; i < initialData.length; i++) {
            const char = initialData.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return `smartmail_sent_${Math.abs(hash)}`;
    }, [initialData]);

    const [sendSuccess, setSendSuccess] = useState(() => {
        return localStorage.getItem(messageId) === 'true';
    });
    const [errorMsg, setErrorMsg] = useState("");
    
    // Asumsikan kita butuh email & password dari sessionStorage
    const zimbraEmail = sessionStorage.getItem('cakra_zimbra_email') || "";
    const zimbraPassword = sessionStorage.getItem('cakra_zimbra_pw') || "";
    
    // Jika tidak ada password atau email, tampilkan prompt
    const [showAuthPrompt, setShowAuthPrompt] = useState(!zimbraPassword || !zimbraEmail);
    const [tempEmail, setTempEmail] = useState(zimbraEmail || "");
    const [tempPassword, setTempPassword] = useState("");

    const handleSend = async () => {
        if (showAuthPrompt) {
            if (!tempEmail || !tempPassword) {
                setErrorMsg("Email dan Password Zimbra wajib diisi.");
                return;
            }
            sessionStorage.setItem('cakra_zimbra_email', tempEmail);
            sessionStorage.setItem('cakra_zimbra_pw', tempPassword);
            setShowAuthPrompt(false);
        }

        const currentEmail = sessionStorage.getItem('cakra_zimbra_email');
        const currentPassword = sessionStorage.getItem('cakra_zimbra_pw');
        if (!currentPassword || !currentEmail) return;

        setIsSending(true);
        setErrorMsg("");
        
        try {
            const response = await apiClient.post('/corporate/emails/reply', {
                email: currentEmail,
                password: currentPassword,
                to: draftData.to,
                cc: draftData.cc || "",
                subject: draftData.subject,
                body: draftData.body
            });
            
            if (response.data.status === 'success') {
                setSendSuccess(true);
                localStorage.setItem(messageId, 'true');
            } else {
                setErrorMsg(`${tGlobal.render.fail} ` + (response.data.message || tGlobal.smartMail.failConnection));
            }
        } catch (error) {
            console.error("Gagal mengirim:", error);
            setErrorMsg(tGlobal.smartMail.failServer);
        } finally {
            setIsSending(false);
        }
    };

    if (sendSuccess) {
        return (
            <div className={`my-4 p-5 rounded-xl border ${darkMode ? 'bg-green-900/20 border-green-800/50' : 'bg-green-50 border-green-200'} flex items-center gap-3`}>
                <CheckCircle2 className="w-8 h-8 text-green-500 flex-shrink-0" />
                <div>
                    <h3 className={`font-bold ${darkMode ? 'text-green-400' : 'text-green-700'}`}>{tGlobal.smartMail.emailSent}</h3>
                    <p className={`text-sm mt-1 ${darkMode ? 'text-green-200/70' : 'text-green-600/80'}`}>
                        {tGlobal.smartMail.emailForwarded}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className={`my-4 rounded-xl border overflow-hidden shadow-lg ${darkMode ? 'bg-[#1E1E22] border-slate-700' : 'bg-white border-slate-200'}`}>
            {/* Header */}
            <div className={`px-4 py-3 flex items-center justify-between border-b ${darkMode ? 'bg-[#252529] border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
                <div className="flex items-center gap-2">
                    <Mail className={`w-5 h-5 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} />
                    <span className="font-bold text-sm tracking-wide">{tGlobal.smartMail.draftTitle}</span>
                </div>
                <div className={`px-2 py-1 rounded text-xs font-semibold ${darkMode ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                    {tGlobal.smartMail.readyToSend}
                </div>
            </div>

            {/* Form Fields */}
            <div className="p-4 flex flex-col gap-3">
                <div className="flex items-center gap-3">
                    <span className={`text-xs font-bold w-12 ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>{tGlobal.smartMail.to}</span>
                    <input 
                        type="text" 
                        value={draftData.to || ""}
                        onChange={(e) => setDraftData({...draftData, to: e.target.value})}
                        className={`flex-1 px-3 py-1.5 rounded-md text-sm border focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow ${darkMode ? 'bg-[#2A2A2D] border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-900'}`}
                        placeholder={tGlobal.smartMail.recipientPlaceholder}
                    />
                </div>
                
                {draftData.cc && (
                    <div className="flex items-center gap-3">
                        <span className={`text-xs font-bold w-12 ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>{tGlobal.smartMail.cc}</span>
                        <input 
                            type="text" 
                            value={draftData.cc || ""}
                            onChange={(e) => setDraftData({...draftData, cc: e.target.value})}
                            className={`flex-1 px-3 py-1.5 rounded-md text-sm border focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow ${darkMode ? 'bg-[#2A2A2D] border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-900'}`}
                            placeholder={tGlobal.smartMail.ccPlaceholder}
                        />
                    </div>
                )}

                <div className="flex items-center gap-3">
                    <span className={`text-xs font-bold w-12 ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>{tGlobal.smartMail.subject}</span>
                    <input 
                        type="text" 
                        value={draftData.subject || ""}
                        onChange={(e) => setDraftData({...draftData, subject: e.target.value})}
                        className={`flex-1 px-3 py-1.5 rounded-md text-sm border focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow font-semibold ${darkMode ? 'bg-[#2A2A2D] border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-900'}`}
                        placeholder={tGlobal.smartMail.subjectPlaceholder}
                    />
                </div>

                <div className="flex items-center justify-between mt-1">
                    <span className={`text-xs font-bold ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>{tGlobal.smartMail.messageLabel}</span>
                    <div className="flex items-center gap-1 bg-slate-200/50 dark:bg-slate-800/50 p-1 rounded-md">
                        <button 
                            onClick={() => setViewMode('edit')}
                            className={`px-3 py-1 text-xs font-medium rounded transition-all flex items-center gap-1.5 ${viewMode === 'edit' ? (darkMode ? 'bg-[#3b82f6] text-white' : 'bg-white shadow text-blue-600') : (darkMode ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-800')}`}
                        >
                            <Edit3 className="w-3.5 h-3.5" /> {tGlobal.smartMail.edit}
                        </button>
                        <button 
                            onClick={() => setViewMode('preview')}
                            className={`px-3 py-1 text-xs font-medium rounded transition-all flex items-center gap-1.5 ${viewMode === 'preview' ? (darkMode ? 'bg-[#3b82f6] text-white' : 'bg-white shadow text-blue-600') : (darkMode ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-800')}`}
                        >
                            <Eye className="w-3.5 h-3.5" /> {tGlobal.smartMail.preview}
                        </button>
                    </div>
                </div>

                <div className="mt-1">
                    {viewMode === 'edit' ? (
                        <textarea 
                            value={draftData.body || ""}
                            onChange={(e) => setDraftData({...draftData, body: e.target.value})}
                            className={`w-full min-h-[250px] p-4 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow resize-y ${darkMode ? 'bg-[#2A2A2D] border-slate-600 text-slate-200' : 'bg-slate-50 border-slate-300 text-slate-800'}`}
                            placeholder="Tulis pesan email di sini..."
                        />
                    ) : (
                        <div className={`w-full min-h-[250px] p-4 rounded-lg text-sm border overflow-auto prose ${darkMode ? 'bg-[#1E1E22] border-slate-600 prose-invert max-w-none' : 'bg-slate-50 border-slate-300 max-w-none'}`}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {draftData.body || ""}
                            </ReactMarkdown>
                        </div>
                    )}
                </div>

                {errorMsg && (
                    <div className="p-2.5 rounded-md bg-red-100 text-red-600 text-xs font-medium border border-red-200">
                        {errorMsg}
                    </div>
                )}
            </div>

            {/* Footer Actions */}
            <div className={`px-4 py-3 flex items-center justify-between border-t ${darkMode ? 'bg-[#252529] border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
                {showAuthPrompt ? (
                    <div className="flex items-center gap-2 flex-1 mr-4">
                        <UserCircle2 className={`w-4 h-4 flex-shrink-0 ${darkMode ? 'text-slate-400' : 'text-slate-500'}`} />
                        <input 
                            type="text"
                            placeholder={tGlobal.smartMail.webmailPlaceholder}
                            value={tempEmail}
                            onChange={(e) => setTempEmail(e.target.value)}
                            className={`w-1/3 px-3 py-1.5 rounded-md text-xs border focus:outline-none ${darkMode ? 'bg-[#1E1E22] border-slate-600 text-white' : 'bg-white border-slate-300'}`}
                        />
                        <input 
                            type="password"
                            placeholder={tGlobal.smartMail.passwordPlaceholder}
                            value={tempPassword}
                            onChange={(e) => setTempPassword(e.target.value)}
                            className={`w-1/3 px-3 py-1.5 rounded-md text-xs border focus:outline-none ${darkMode ? 'bg-[#1E1E22] border-slate-600 text-white' : 'bg-white border-slate-300'}`}
                        />
                    </div>
                ) : (
                    <div className="flex items-center gap-3">
                        <div className={`text-xs ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                            {tGlobal.smartMail.sentAs} <span className="font-semibold">{sessionStorage.getItem('cakra_zimbra_email')}</span>
                        </div>
                        <button 
                            onClick={() => setShowAuthPrompt(true)}
                            className={`text-[10px] underline ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}
                        >
                            {tGlobal.smartMail.switchAccount}
                        </button>
                    </div>
                )}

                <button 
                    onClick={handleSend}
                    disabled={isSending || !draftData.to}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all
                        ${isSending 
                            ? 'bg-slate-400 text-white cursor-not-allowed' 
                            : 'bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg'
                        }
                    `}
                >
                    <Send className="w-4 h-4" />
                    {isSending ? tGlobal.smartMail.sending : tGlobal.smartMail.sendEmail}
                </button>
            </div>
        </div>
    );
}
