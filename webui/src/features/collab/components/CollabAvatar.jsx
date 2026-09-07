import React, { useState, useEffect } from 'react';
import { getApiBase } from '../../../services/endpoints';

// Helper warna avatar konsisten berdasarkan string nama/NPP
export const getAvatarColor = (str = '') => {
  const colors = [
    'from-emerald-500 to-teal-700',
    'from-blue-500 to-indigo-700',
    'from-violet-500 to-purple-700',
    'from-amber-500 to-orange-700',
    'from-rose-500 to-pink-700',
    'from-cyan-500 to-blue-700',
  ];
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
};

export const getInitials = (name = '') => {
  return (
    name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((n) => n[0].toUpperCase())
      .join('') || 'U'
  );
};

const CollabAvatar = ({
  npp,
  name = 'User',
  photoUrl = null,
  size = 'md', // 'xs' | 'sm' | 'md' | 'lg' | custom class
  className = '',
  title = ''
}) => {
  const [imgFailed, setImgFailed] = useState(false);

  // Tentukan URL foto prioritas (custom upload -> HRIS Pindad)
  let resolvedUrl = null;
  if (photoUrl) {
    if (photoUrl.startsWith('http://') || photoUrl.startsWith('https://')) {
      resolvedUrl = photoUrl;
    } else {
      resolvedUrl = `${getApiBase()}${photoUrl.startsWith('/') ? '' : '/'}${photoUrl}`;
    }
  } else if (npp) {
    resolvedUrl = `https://hris.pindad.co.id/assets/image/foto_pegawai_bumn/${npp}.jpg`;
  }

  // Reset status kegagalan jika URL berubah
  useEffect(() => {
    setImgFailed(false);
  }, [resolvedUrl]);

  // Ukuran dimensi avatar
  let sizeClasses = 'w-9 h-9 text-xs';
  if (size === 'xs') sizeClasses = 'w-6 h-6 text-[9px]';
  else if (size === 'sm') sizeClasses = 'w-7 h-7 text-[10px]';
  else if (size === 'lg') sizeClasses = 'w-11 h-11 text-sm';
  else if (typeof size === 'string' && size.includes('w-')) sizeClasses = size;

  const initials = getInitials(name);
  const avatarGradient = getAvatarColor(npp || name);
  const tooltip = title || `${name}${npp ? ` (${npp})` : ''}`;

  if (resolvedUrl && !imgFailed) {
    return (
      <div
        className={`relative shrink-0 rounded-full overflow-hidden border border-white/15 shadow-sm bg-neutral-800 ${sizeClasses} ${className}`}
        title={tooltip}
      >
        <img
          src={resolvedUrl}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setImgFailed(true)}
          loading="lazy"
        />
      </div>
    );
  }

  return (
    <div
      className={`relative shrink-0 rounded-full bg-gradient-to-br ${avatarGradient} flex items-center justify-center text-white font-bold shadow-sm border border-white/10 ${sizeClasses} ${className}`}
      title={tooltip}
    >
      <span>{initials}</span>
    </div>
  );
};

export default CollabAvatar;
