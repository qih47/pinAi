// =========================================================================
// 🎨 SKEMA WARNA TEMA (THEME CONFIGURATION)
// =========================================================================
export const lightColors = {
    rootBg: '#ffffff',
    sidebarBg: '#f9fafb',
    mainBg: '#ffffff',
    borderColor: '#e5e7eb',
    textColor: '#1f2937',
    secondaryText: '#6b7280',
    iconColor: '#4b5563',
    inputBg: '#f3f4f6',
    inputBorder: '#e5e7eb',
    inputAreaBg: 'rgba(255,255,255,1)',
    inputShadow: '0 2px 12px rgba(0,0,0,0.04)',
    sendBtnBg: '#111827',
    sendBtnText: '#ffffff',
    suggestionCardBg: '#ffffff',
};

export const darkColors = {
    rootBg: '#151517',
    sidebarBg: '#151517',
    mainBg: '#151517',
    borderColor: '#2a2a2d',
    textColor: '#e2e8f0',
    secondaryText: '#94a3b8',
    iconColor: '#cbd5e1',
    inputBg: '#1e1e20',
    inputBorder: '#2a2a2d',
    inputAreaBg: 'rgba(21,21,23,1)',
    inputShadow: '0 2px 12px rgba(0,0,0,0.4)',
    sendBtnBg: '#6366f1',
    sendBtnText: '#ffffff',
    suggestionCardBg: '#171717',
};

// =========================================================================
// ⚙️ SKEMA GAYA INTERFACE (🎯 RUMAH UTAMA TEMA & STYLING LOGO/AI RESPONSE)
// =========================================================================
export const styles = {
    root: {
        display: 'flex',
        height: '100vh',
        width: '100%',
        fontFamily: "'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: 'hidden',
        transition: 'background 0.2s'
    },
    sidebar: {
        width: 260,
        display: 'flex',
        flexDirection: 'column',
        padding: '12px 8px',
        flexShrink: 0,
        transition: 'background 0.2s, border-color 0.2s'
    },
    sidebarTop: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '4px 8px 12px'
    },
    menuBtn: {
        width: 40, height: 40, borderRadius: 10, border: 'none', background: 'transparent',
        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
    },
    newChatBtn: {
        width: 40, height: 40, borderRadius: 10, border: 'none', background: 'transparent',
        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
    },
    historySection: {
        flex: 1, overflowY: 'auto', padding: '8px 4px'
    },
    historyLabel: {
        fontSize: 12, fontWeight: 600, padding: '8px 12px', letterSpacing: '0.3px'
    },
    historyItem: {
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
        borderRadius: 10, cursor: 'pointer', fontSize: 13, transition: 'background 0.15s'
    },
    historyText: {
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
    },
    sidebarBottom: {
        paddingTop: 12, padding: '12px 8px 4px', transition: 'border-color 0.2s'
    },
    upgradeCard: {
        display: 'flex', alignItems: 'center', gap: 10, padding: 12,
        background: 'linear-gradient(135deg, #eef2ff 0%, #faf5ff 100%)',
        borderRadius: 12, marginBottom: 12, cursor: 'pointer', border: '1px solid #e0e7ff'
    },
    upgradeIcon: { fontSize: 20 },
    upgradeText: { color: '#4338ca', lineHeight: 1.3 },
    userRow: {
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px',
        borderRadius: 10, cursor: 'pointer', transition: 'background 0.15s'
    },
    userAvatar: {
        width: 32, height: 32, borderRadius: '50%',
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        color: '#fff', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 13, fontWeight: 600, flexShrink: 0
    },
    userInfo: { overflow: 'hidden', flex: 1 },
    userName: { fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
    userEmail: { fontSize: 11 },

    main: {
        flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0,
        position: 'relative', transition: 'background 0.2s'
    },
    header: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', flexShrink: 0
    },
    modelSelector: {
        display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px',
        borderRadius: 10, cursor: 'pointer', fontSize: 16, fontWeight: 600,
        transition: 'background 0.15s'
    },
    modelName: { letterSpacing: '-0.2px' },
    headerActions: { display: 'flex', alignItems: 'center', gap: 8 },
    loginBtn: {
        padding: '8px 18px', borderRadius: 20, border: '1px solid',
        background: 'transparent', fontSize: 13, fontWeight: 600, cursor: 'pointer',
        transition: 'all 0.15s'
    },

    scrollArea: {
        flex: 1, overflowY: 'auto', overflowX: 'hidden',
        display: 'flex', flexDirection: 'column'
    },
    chatInner: {
        maxWidth: 865, width: '100%', margin: '0 auto',
        padding: '24px 24px 40px', display: 'flex', flexDirection: 'column', gap: 24
    },

    emptyState: {
        flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', textAlign: 'center', padding: '40px 20px', minHeight: '60vh'
    },
    emptyLogoWrap: { marginBottom: 24, animation: 'logoFloat 4s ease-in-out infinite' },
    emptyLogo: {
        width: 72, height: 72, borderRadius: 20,
        filter: 'drop-shadow(0 8px 24px rgba(99, 102, 241, 0.25))'
    },
    emptyTitle: {
        margin: '0 0 8px 0', fontSize: 36, fontWeight: 600, letterSpacing: '-0.8px',
        background: 'linear-gradient(135deg, #111827 0%, #6366f1 100%)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
    },
    emptySubtitle: { margin: '0 0 40px 0', fontSize: 16, fontWeight: 400 },
    suggestionGrid: {
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, maxWidth: 640, width: '100%'
    },
    suggestionCard: {
        display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px',
        borderRadius: 14, cursor: 'pointer', textAlign: 'left', transition: 'all 0.2s ease',
        fontFamily: 'inherit', fontSize: 'inherit', border: '1px solid'
    },
    suggestionIcon: { fontSize: 22, flexShrink: 0 },
    suggestionTextWrap: { flex: 1, minWidth: 0 },
    suggestionTitle: { fontSize: 14, fontWeight: 600, marginBottom: 2 },
    suggestionDesc: { fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },

    userChatRow: {
        display: 'flex', justifyContent: 'flex-end', animation: 'fadeInUp 0.3s ease-out'
    },
    assistantRow: {
        display: 'flex', alignItems: 'flex-start', animation: 'fadeInUp 0.3s ease-out'
    },
    assistantMessageWrapper: {
        flex: 1, 
        minWidth: 0,
        // Smooth entrance untuk seluruh bubble
        animation: 'geminiFadeIn 0.4s ease-out',
    },
    assistantHeader: {
        display: 'flex', alignItems: 'center', marginBottom: 6
    },
    avatarWrap: {
        position: 'relative', display: 'inline-flex', flexShrink: 0
    },
    statusDot: {
        position: 'absolute',
        top: -3,
        right: -3,
        width: 8,
        height: 8,
        borderRadius: '50%',
        border: '1px solid',
        transition: 'background 0.2s'
    },
    avatarLabel: {
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: '-0.1px',
        whiteSpace: 'nowrap'
    },
    thinkingInline: {
        fontSize: 12,
        fontStyle: 'italic',
        whiteSpace: 'nowrap'
    },
    assistantContent: {
        wordBreak: 'break-word',
        paddingLeft: 20,
        paddingRight: 25
    },

    // 🔥 IMPROVEMENT STREAMING: Transisi warna dan rendering text selembut Gemini
    assistantText: {
        lineHeight: 1.8,
        whiteSpace: 'normal',
        margin: 0,
        fontSize: '15px',
        color: 'transparent', // Wajib transparent agar gradient-nya kelihatan
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',

        opacity: 0,  // Mulai dari invisible
        animation: 'geminiReveal 0.5s cubic-bezier(0.22, 0.61, 0.36, 1) forwards',  // Easing natural
        transition: 'all 0.3s ease-out',  // Smooth transition untuk update

        // Optional: Gradient fade di ujung kanan (kayak Gemini)
        backgroundImage: 'linear-gradient(to right, currentColor 85%, transparent 100%)',

    },

    inputArea: {
        flexShrink: 0, padding: '8px 24px 16px', transition: 'background 0.2s'
    },
    inputContainer: { maxWidth: 768, margin: '0 auto', width: '100%' },
    inputForm: {
        display: 'flex', alignItems: 'flex-end', gap: 8,
        borderRadius: 28, padding: '10px 10px 10px 20px', transition: 'all 0.2s'
    },
    textarea: {
        flex: 1, border: 'none', outline: 'none', background: 'transparent',
        fontSize: 15, lineHeight: 1.5, resize: 'none', padding: '8px 0',
        fontFamily: 'inherit', maxHeight: 220, minHeight: 24
    },
    inputActions: { display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 },
    iconBtn: {
        width: 36, height: 36, borderRadius: '50%', border: 'none',
        background: 'transparent', cursor: 'pointer', display: 'flex',
        alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s'
    },
    sendBtn: {
        width: 36, height: 36, borderRadius: '50%', border: 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, transition: 'all 0.2s'
    },
    inputFooter: {
        textAlign: 'center', fontSize: 11, marginTop: 10, padding: '0 12px'
    }

};