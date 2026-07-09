import { styles } from './main.styles';
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

export const getPlusButtonStyles = (darkMode, selectedFiles, disabled) => ({
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
        cursor: disabled ? 'not-allowed' : 'pointer',
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
        marginBottom: '16px',
        marginTop: '50px'
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