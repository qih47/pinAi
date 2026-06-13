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
    },
    codeBlockHeader: {
        background: '#1a1a1c',
        padding: '10px 16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        borderTopLeftRadius: '10px',
        borderTopRightRadius: '10px',
        position: 'relative'
    },
    codeBlockHeaderLang: {
        color: '#38bdf8',
        fontSize: '11px',
        fontWeight: 700,
        fontFamily: "'Inter', sans-serif",
        letterSpacing: '0.8px'
    },
    codeBlockHeaderBtnGroup: {
        display: 'flex',
        gap: '8px',
        alignItems: 'center'
    },
    codeBlockHeaderActionBtn: {
        background: 'rgba(255, 255, 255, 0.03)',
        color: '#cbd5e1',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '5px',
        padding: '4px 10px',
        fontSize: '11px',
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        fontWeight: 500,
        fontFamily: "'Inter', sans-serif",
        transition: 'all 0.15s ease-in-out'
    },
    codeBlockHeaderToast: {
        position: 'fixed',
        top: '24px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: '#1e293b',
        color: '#e2e8f0',
        padding: '10px 20px',
        borderRadius: '8px',
        fontSize: '13px',
        fontWeight: 500,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(99, 102, 241, 0.3)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        animation: 'fadeInUp 0.2s ease-out'
    },
    scrollBottomBtn: {
        position: 'absolute',
        bottom: '24px',
        right: '24px',
        width: '40px',
        height: '40px',
        borderRadius: '50%',
        border: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        fontSize: '18px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        zIndex: 99,
        transition: 'all 0.2s ease-in-out',
        animation: 'fadeInUp 0.2s ease-out'
    },
    msgSearchContainer: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 16px',
        position: 'absolute',
        top: '64px',
        left: 0,
        right: 0,
        zIndex: 30,
        borderBottom: '1px solid',
        animation: 'fadeInUp 0.15s ease-out',
        transition: 'all 0.2s ease'
    }
};

// =========================================================================
// 🎛️ STYLING HELPER FUNCTIONS
// =========================================================================

export const getCustomModeSelectorStyles = (darkMode, disabled) => ({
    container: {
        position: 'relative',
        display: 'inline-block'
    },
    button: {
        background: darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
        border: 'none',
        borderRadius: '20px',
        padding: '6px 20px',
        fontSize: '13px',
        fontWeight: 500,
        color: darkMode ? '#e2e8f0' : '#1f2937',
        cursor: disabled ? 'not-allowed' : 'pointer',
        outline: 'none',
        transition: 'all 0.15s',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        opacity: disabled ? 0.5 : 1
    },
    dropdown: {
        position: 'absolute',
        bottom: '100%',
        left: 0,
        marginBottom: '4px',
        background: darkMode ? '#1e1e20' : '#ffffff',
        border: `1px solid ${darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
        borderRadius: '8px',
        boxShadow: darkMode
            ? '0 4px 12px rgba(0,0,0,0.5)'
            : '0 4px 12px rgba(0,0,0,0.15)',
        minWidth: '120px',
        zIndex: 1000,
        overflow: 'hidden',
        animation: 'fadeInUp 0.15s ease-out'
    },
    item: (selected) => ({
        width: '100%',
        padding: '8px 12px',
        background: selected
            ? (darkMode ? 'rgba(99, 102, 241, 0.15)' : 'rgba(99, 102, 241, 0.1)')
            : 'transparent',
        border: 'none',
        color: darkMode ? '#e2e8f0' : '#1f2937',
        fontSize: '13px',
        fontWeight: selected ? 600 : 400,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '8px',
        transition: 'background 0.1s'
    })
});

export const getHeaderDropdownMenuStyles = (darkMode) => ({
    container: {
        position: 'relative',
        display: 'inline-block'
    },
    button: {
        background: 'transparent',
        border: 'none',
        borderRadius: '50%',
        width: '36px',
        height: '36px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: darkMode ? '#cbd5e1' : '#4b5563',
        cursor: 'pointer',
        transition: 'background 0.2s',
        outline: 'none'
    },
    menu: {
        position: 'absolute',
        top: '100%',
        right: 0,
        marginTop: '6px',
        background: darkMode ? '#1e1e20' : '#ffffff',
        border: `1px solid ${darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
        borderRadius: '10px',
        boxShadow: darkMode ? '0 10px 25px -5px rgba(0,0,0,0.5)' : '0 10px 25px -5px rgba(0,0,0,0.1)',
        minWidth: '160px',
        zIndex: 2000,
        overflow: 'hidden',
        padding: '4px',
        animation: 'fadeInUp 0.15s ease-out'
    },
    loginItem: {
        width: '100%',
        padding: '10px 12px',
        background: 'transparent',
        border: 'none',
        borderRadius: '6px',
        color: darkMode ? '#e2e8f0' : '#1f2937',
        fontSize: '13px',
        fontWeight: 600,
        textAlign: 'left',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        transition: 'background 0.1s'
    },
    divider: {
        height: '1px',
        background: darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
        margin: '4px 0'
    },
    themeItem: {
        width: '100%',
        padding: '10px 12px',
        background: 'transparent',
        border: 'none',
        borderRadius: '6px',
        color: darkMode ? '#cbd5e1' : '#4b5563',
        fontSize: '13px',
        fontWeight: 500,
        textAlign: 'left',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '8px',
        transition: 'background 0.1s'
    }
});

export const getPlusButtonStyles = (darkMode, selectedFiles, isStreaming) => ({
    button: {
        background: selectedFiles.length > 0
            ? (darkMode ? 'rgba(99, 102, 241, 0.2)' : 'rgba(37, 99, 235, 0.1)')
            : 'transparent',
        border: 'none',
        borderRadius: '50%',
        width: '36px',
        height: '36px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        color: selectedFiles.length > 0 ? (darkMode ? '#818cf8' : '#2563eb') : (darkMode ? '#9ca3af' : '#6b7280'),
        cursor: isStreaming ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s ease'
    }
});

export const getSendButtonStyles = (isStreaming, isUploadingFile, input, selectedFiles, theme) => {
    const disabled = isStreaming || isUploadingFile || (!input.trim() && selectedFiles.length === 0);
    return {
        button: {
            ...styles.sendBtn,
            background: theme.sendBtnBg,
            color: theme.sendBtnText,
            opacity: disabled ? 0.35 : 1,
            cursor: (isStreaming || isUploadingFile) ? 'not-allowed' : 'pointer',
            border: 'none',
            borderRadius: '50%',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
        }
    };
};

export const getUserBubbleStyles = (darkMode, isEditing, shouldTruncate, isExpanded, isHovered, isStreaming, editValueText) => ({
    container: {
        ...styles.userChatRow,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        marginBottom: '16px'
    },
    attachmentWrapper: {
        width: 'auto',
        maxWidth: '75%',
        padding: '12px 16px',
        borderRadius: 18,
        background: darkMode ? '#3a3a3f' : '#f3f4f6',
        boxShadow: '0 2px 8px rgba(99, 102, 241, 0.12)',
        marginBottom: '8px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        justifyContent: 'flex-end'
    },
    attachmentItem: {
        width: '60px',
        height: '60px',
        borderRadius: '10px',
        overflow: 'hidden',
        background: darkMode ? '#222225' : '#e5e7eb',
        border: `1px solid ${darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'transform 0.15s ease'
    },
    pdfIconWrapper: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '1px'
    },
    pdfIconText: {
        fontSize: '8px',
        fontWeight: 800,
        color: '#ef4444',
        maxWidth: '48px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
    },
    bubbleContent: {
        width: isEditing ? '75%' : 'auto',
        maxWidth: '75%',
        padding: (shouldTruncate && !isEditing) ? '14px 20px 36px 20px' : '14px 20px',
        borderRadius: 22,
        fontSize: 15,
        lineHeight: 1.55,
        whiteSpace: isEditing ? 'normal' : 'pre-wrap',
        wordBreak: 'break-word',
        boxShadow: '0 2px 8px rgba(99, 102, 241, 0.12)',
        background: darkMode ? '#3a3a3f' : '#f3f4f6',
        color: darkMode ? '#e2e8f0' : '#1f2937',
        position: 'relative',
        transition: 'all 0.2s ease-in-out',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
    },
    editorWrapper: {
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
    },
    editorTextarea: {
        width: '100%',
        background: darkMode ? '#2d2d30' : '#ffffff',
        color: darkMode ? '#e2e8f0' : '#1f2937',
        border: darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid #d1d5db',
        borderRadius: '12px',
        padding: '10px',
        fontSize: '14px',
        fontFamily: 'inherit',
        resize: 'vertical',
        outline: 'none',
        boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.05)'
    },
    editorActions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '8px'
    },
    cancelBtn: {
        background: 'transparent',
        border: 'none',
        color: darkMode ? '#9ca3af' : '#6b7280',
        fontSize: '13px',
        fontWeight: 500,
        cursor: 'pointer',
        padding: '6px 12px',
        borderRadius: '18px'
    },
    submitBtn: {
        background: '#6366f1',
        color: '#ffffff',
        border: 'none',
        fontSize: '13px',
        fontWeight: 600,
        cursor: (editValueText?.trim() && !isStreaming) ? 'pointer' : 'not-allowed',
        padding: '6px 16px',
        borderRadius: '18px',
        opacity: (editValueText?.trim() && !isStreaming) ? 1 : 0.5,
        boxShadow: '0 2px 4px rgba(99, 102, 241, 0.3)'
    },
    truncationOverlay: {
        position: 'absolute',
        bottom: '32px',
        left: 0,
        right: 0,
        height: '20px',
        background: darkMode
            ? 'linear-gradient(to bottom, transparent, #3a3a3f)'
            : 'linear-gradient(to bottom, transparent, #f3f4f6)',
        pointerEvents: 'none'
    },
    expandBtn: {
        position: 'absolute',
        bottom: '6px',
        right: '12px',
        background: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
        border: 'none',
        color: darkMode ? '#cbd5e1' : '#4b5563',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '5px',
        borderRadius: '50%',
        transition: 'transform 0.2s, background 0.15s'
    },
    hoverActionsGroup: {
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        marginRight: '12px',
        marginTop: '4px',
        height: '20px',
        opacity: isHovered ? 1 : 0,
        transition: 'opacity 0.2s ease-in-out',
        pointerEvents: isHovered ? 'auto' : 'none'
    },
    hoverActionBtn: {
        background: 'transparent',
        border: 'none',
        color: '#9ca3af',
        cursor: 'pointer',
        display: 'flex',
        padding: '4px',
        borderRadius: '4px',
        transition: 'color 0.15s, background 0.15s'
    },
    toast: {
        position: 'fixed',
        top: '24px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: '#1e293b',
        color: '#e2e8f0',
        padding: '10px 20px',
        borderRadius: '8px',
        fontSize: '13px',
        fontWeight: 500,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(99, 102, 241, 0.3)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        animation: 'fadeInUp 0.2s ease-out'
    }
});