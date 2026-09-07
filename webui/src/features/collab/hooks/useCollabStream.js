import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Hook untuk mengalirkan Server-Sent Events (SSE) dari room Collab.
 * Mendengarkan pesan baru, typing indicator, dan pembaruan draf dokumen.
 */
export const useCollabStream = ({
  roomId,
  onNewMessage,
  onMessageEdited,
  onTyping,
  onDocumentUpdated,
  onMembersUpdated,
  onCakraStreamStart,
  onCakraStreamChunk,
  onCakraStreamEnd
}) => {
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    if (!roomId) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const token = localStorage.getItem('cakra_token') || '';
    // Single entry point: Gateway port 8000
    const baseUrl = import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;
    const streamUrl = `${baseUrl}/api/collab/rooms/${roomId}/stream?token=${encodeURIComponent(token)}`;

    try {
      const es = new EventSource(streamUrl);
      eventSourceRef.current = es;

      es.onopen = () => {
        setIsConnected(true);
      };

      es.onmessage = (e) => {
        if (!e.data) return;
        try {
          const payload = JSON.parse(e.data);
          switch (payload.type) {
            case 'connected':
              setIsConnected(true);
              break;
            case 'new_message':
              if (payload.message && onNewMessage) {
                onNewMessage(payload.message);
              }
              break;
            case 'message_edited':
              if (payload.message && onMessageEdited) {
                onMessageEdited(payload.message);
              }
              break;
            case 'cakra_stream_start':
              if (onCakraStreamStart) {
                onCakraStreamStart(payload);
              }
              break;
            case 'cakra_stream_chunk':
              if (onCakraStreamChunk) {
                onCakraStreamChunk(payload);
              }
              break;
            case 'cakra_stream_end':
              if (onCakraStreamEnd) {
                onCakraStreamEnd(payload);
              }
              break;
            case 'typing':
              if (onTyping) {
                onTyping(payload);
              }
              break;
            case 'document_updated':
              if (payload.document_content !== undefined && onDocumentUpdated) {
                onDocumentUpdated(payload);
              }
              break;
            case 'members_updated':
              if (onMembersUpdated) {
                onMembersUpdated(payload);
              }
              break;
            default:
              break;
          }
        } catch (err) {
          console.debug('[COLLAB_SSE] Non-JSON payload received:', e.data);
        }
      };

      es.onerror = (err) => {
        setIsConnected(false);
        es.close();
        eventSourceRef.current = null;
        // Auto-reconnect after 3 seconds
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };
    } catch (err) {
      console.error('[COLLAB_SSE] Connection initialization error:', err);
    }
  }, [roomId, onNewMessage, onTyping, onDocumentUpdated, onMembersUpdated]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
    };
  }, [connect]);

  return { isConnected };
};
