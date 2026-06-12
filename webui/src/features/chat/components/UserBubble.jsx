import React, { useState, memo } from 'react';
import { useChatStore, getUploadUrl } from '../../../stores/chatStore';
import { getUserBubbleStyles } from '../chatPage.styles';

const UserBubble = memo(function UserBubble({
  msg,
  idx,
  darkMode,
  theme,
  executeTextCopy,
  showToast,
  toastMsg
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(msg.content || '');

  const editAndRegenerate = useChatStore((state) => state.editAndRegenerate);
  const isStreaming = useChatStore((state) => state.isStreaming);

  const CHARACTER_LIMIT = 300;
  const shouldTruncate = msg.content && msg.content.length > CHARACTER_LIMIT;

  const displayContent =
    shouldTruncate && !isExpanded && !isEditing
      ? `${msg.content.slice(0, CHARACTER_LIMIT)}...`
      : msg.content;

  const handleEditSubmit = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!editValue.trim()) return;
    if (isStreaming) return;

    const newContent = editValue;
    setIsEditing(false);
    editAndRegenerate(idx, newContent);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditValue(msg.content || '');
  };

  const bubbleStyles = getUserBubbleStyles(
    darkMode,
    isEditing,
    shouldTruncate,
    isExpanded,
    isHovered,
    isStreaming,
    editValue
  );

  return (
    <div
      style={bubbleStyles.container}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* 📎 BUBBLE ATTACHMENT TERPISAH */}
      {!isEditing && msg.attachments && msg.attachments.length > 0 && (
        <div style={bubbleStyles.attachmentWrapper}>
          {msg.attachments.map((file, fIdx) => {
            const fileName = file.file_name || file.original_filename || 'lampiran';
            const assetUrl = getUploadUrl(file.file_path);
            const isPDF =
              file.mime_type === 'application/pdf' ||
              fileName.toLowerCase().endsWith('.pdf');
            return (
              <div
                key={`attach-${file.id || fIdx}`}
                title={fileName}
                onClick={() => {
                  if (assetUrl) window.open(assetUrl, '_blank');
                }}
                style={bubbleStyles.attachmentItem}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'scale(1.04)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                {isPDF ? (
                  <div style={bubbleStyles.pdfIconWrapper}>
                    <span style={{ fontSize: '20px' }}>📄</span>
                    <span style={bubbleStyles.pdfIconText}>PDF</span>
                  </div>
                ) : assetUrl ? (
                  <img
                    src={assetUrl}
                    alt={fileName}
                    onError={(e) => {
                      e.target.style.display = 'none';
                      e.target.parentNode.innerHTML = '<span style="font-size:20px;">🖼️</span>';
                    }}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <span style={{ fontSize: '20px' }}>🖼️</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 💬 BUBBLE TEXT TERPISAH — sembunyikan jika hanya lampiran */}
      {(isEditing || (msg.content && msg.content.trim())) && (
        <div style={bubbleStyles.bubbleContent}>
          {isEditing ? (
            /* ✏️ MODE: INLINE FORM EDITOR */
            <div style={bubbleStyles.editorWrapper}>
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleEditSubmit(e);
                  }
                }}
                rows={3}
                style={bubbleStyles.editorTextarea}
                autoFocus
              />
              <div style={bubbleStyles.editorActions}>
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  style={bubbleStyles.cancelBtn}
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleEditSubmit}
                  disabled={!editValue.trim() || isStreaming}
                  style={bubbleStyles.submitBtn}
                >
                  Kirim
                </button>
              </div>
            </div>
          ) : (
            /* 💬 MODE: TAMPILAN TEXT CHAT NORMAL */
            <>
              {displayContent ? <div>{displayContent}</div> : null}

              {shouldTruncate && !isExpanded && (
                <div style={bubbleStyles.truncationOverlay} />
              )}

              {shouldTruncate && (
                <button
                  type="button"
                  onClick={() => setIsExpanded(!isExpanded)}
                  title={
                    isExpanded ? 'Sembunyikan pesan' : 'Tampilkan selengkapnya'
                  }
                  style={bubbleStyles.expandBtn}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = darkMode
                      ? 'rgba(255,255,255,0.1)'
                      : 'rgba(0,0,0,0.06)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = darkMode
                      ? 'rgba(255,255,255,0.05)'
                      : 'rgba(0,0,0,0.03)';
                  }}
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{
                      transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s ease-in-out'
                    }}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* 🛰️ HOVER ACTIONS */}
      {!isEditing && (
        <div style={bubbleStyles.hoverActionsGroup}>
          <button
            type="button"
            onClick={() => executeTextCopy(msg.content)}
            title="Salin Pesan"
            style={bubbleStyles.hoverActionBtn}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = darkMode ? '#e2e8f0' : '#1f2937';
              e.currentTarget.style.background = darkMode
                ? 'rgba(255,255,255,0.08)'
                : 'rgba(0,0,0,0.05)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#9ca3af';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
          </button>
          {!isStreaming && (
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              title="Edit Perintah"
              style={bubbleStyles.hoverActionBtn}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = darkMode ? '#e2e8f0' : '#1f2937';
                e.currentTarget.style.background = darkMode
                  ? 'rgba(255,255,255,0.08)'
                  : 'rgba(0,0,0,0.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#9ca3af';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
          )}
        </div>
      )}
      {showToast && <div style={bubbleStyles.toast}>{toastMsg}</div>}
    </div>
  );
});

export default UserBubble;
