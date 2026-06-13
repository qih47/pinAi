import { useContext, useMemo } from 'react';
import { ToastContext } from '../components/ui/ToastProvider';

/**
 * Hook to trigger toast notifications globally.
 * 
 * Usage:
 *   const toast = useToast();
 *   toast.success('File uploaded successfully!');
 *   toast.error('Connection failed.');
 */
export default function useToast() {
  const addToast = useContext(ToastContext);

  if (!addToast) {
    // If not wrapped in provider, fallback to console or alert so it doesn't crash
    return {
      success: (msg) => console.log('Toast SUCCESS:', msg),
      error: (msg) => console.error('Toast ERROR:', msg),
      warning: (msg) => console.warn('Toast WARNING:', msg),
      info: (msg) => console.info('Toast INFO:', msg),
    };
  }

  return useMemo(
    () => ({
      success: (message, duration) => addToast(message, 'success', duration),
      error: (message, duration) => addToast(message, 'error', duration),
      warning: (message, duration) => addToast(message, 'warning', duration),
      info: (message, duration) => addToast(message, 'info', duration),
    }),
    [addToast]
  );
}
