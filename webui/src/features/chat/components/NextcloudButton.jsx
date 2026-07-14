import React from 'react';
import { Cloud } from 'lucide-react';
import { getPlusButtonStyles } from '../chatPage.styles';
import useNextcloudStore from '../../../stores/nextcloudStore';

export default function NextcloudButton({ disabled, darkMode }) {
  const openModal = useNextcloudStore(state => state.openModal);
  
  // Reuse plus button styles for consistency
  const buttonStyles = getPlusButtonStyles(darkMode, [], disabled);
  
  // Custom tweaks to differentiate slightly or add color
  const nextcloudStyles = {
    ...buttonStyles.button,
    marginLeft: '4px'
  };

  return (
    <button
      type="button"
      onClick={() => openModal()}
      disabled={disabled}
      style={nextcloudStyles}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = darkMode
            ? 'rgba(255,255,255,0.08)'
            : 'rgba(0,0,0,0.05)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
      }}
      title="Pilih File dari Nextcloud Pindad"
    >
      <Cloud size={20} strokeWidth={2.5} color={darkMode ? '#9ca3af' : '#6b7280'} className="hover:text-blue-500 transition-colors" />
    </button>
  );
}
