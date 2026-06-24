import { useEffect, useRef, useCallback } from 'react';
import apiClient from '../services/apiClient';

/**
 * W14 — LLM Title Generation Indicator
 *
 * Polls backend every 2s for sessions that still have generic "Chat Baru" title.
 * Once LLM generates a better title, updates the chatHistory state immediately
 * with a smooth transition.
 *
 * @param {Array} chatHistory - Current list of chat sessions
 * @param {Function} setChatHistory - State setter to update sessions
 * @param {string|null} currentSessionId - UUID of the currently open session
 * @param {boolean} enabled - Whether to enable polling (only for authenticated users)
 */
export const useSessionTitle = (chatHistory, setChatHistory, currentSessionId, enabled = true) => {
  const pollingTimers = useRef(new Map()); // uuid -> intervalId
  const generatingTitles = useRef(new Set()); // Set of uuids being tracked

  /**
   * Poll a specific session for title updates
   */
  const pollSessionTitle = useCallback(async (sessionUuid) => {
    try {
      const response = await apiClient.get(`/chat/sessions/${sessionUuid}`);
      const data = response.data;

      // Support both direct object and wrapped { data: {...} }
      const session = data?.data || data;

      const newTitle = session?.judul || session?.title;

      if (newTitle && newTitle !== 'Chat Baru' && newTitle !== 'Obrolan Baru' && newTitle !== 'Sedang membuat judul...' && newTitle.trim() !== '') {
        // 🎉 LLM generated a real title — update the sidebar!
        setChatHistory((prev) =>
          prev.map((c) =>
            c.session_uuid === sessionUuid
              ? { ...c, judul: newTitle, _titleUpdated: true }
              : c
          )
        );

        // Stop polling for this session
        stopPolling(sessionUuid);
      }
    } catch (err) {
      // Session might not exist yet or network error — stop polling after errors
      console.debug(`[W14] Title poll failed for ${sessionUuid}:`, err.message);
      stopPolling(sessionUuid);
    }
  }, [setChatHistory]);

  /**
   * Stop polling a specific session
   */
  const stopPolling = useCallback((sessionUuid) => {
    if (pollingTimers.current.has(sessionUuid)) {
      clearInterval(pollingTimers.current.get(sessionUuid));
      pollingTimers.current.delete(sessionUuid);
      generatingTitles.current.delete(sessionUuid);
    }
  }, []);

  /**
   * Start polling a session for title generation
   */
  const startPolling = useCallback((sessionUuid) => {
    if (pollingTimers.current.has(sessionUuid)) return; // Already polling

    generatingTitles.current.add(sessionUuid);

    // Poll every 2 seconds, max 30 attempts (1 minute)
    let attempts = 0;
    const MAX_ATTEMPTS = 30;

    const intervalId = setInterval(() => {
      attempts++;
      if (attempts > MAX_ATTEMPTS) {
        stopPolling(sessionUuid);
        return;
      }
      pollSessionTitle(sessionUuid);
    }, 2000);

    pollingTimers.current.set(sessionUuid, intervalId);
  }, [pollSessionTitle, stopPolling]);

  /**
   * Effect: Watch chatHistory for sessions with "Chat Baru" title
   * and start polling them for LLM-generated titles.
   */
  useEffect(() => {
    if (!enabled || !chatHistory?.length) return;

    const genericTitles = ['Chat Baru', 'New Chat', 'Obrolan Baru', 'Sedang membuat judul...', ''];

    chatHistory.forEach((chat) => {
      const title = (chat.judul || '').trim();
      const isGeneric = genericTitles.some(
        (g) => title.toLowerCase() === g.toLowerCase() || title === ''
      );

      if (isGeneric && !pollingTimers.current.has(chat.session_uuid)) {
        // Only poll for recent sessions (within last 5 minutes)
        const createdAt = chat.created_at ? new Date(chat.created_at) : null;
        const isRecent = !createdAt || (Date.now() - createdAt.getTime()) < 5 * 60 * 1000;

        if (isRecent || chat.session_uuid === currentSessionId) {
          startPolling(chat.session_uuid);
        }
      }

      // Stop polling if title is no longer generic (was updated externally)
      if (!isGeneric && pollingTimers.current.has(chat.session_uuid)) {
        stopPolling(chat.session_uuid);
      }
    });
  }, [chatHistory, currentSessionId, enabled, startPolling, stopPolling]);

  /**
   * Cleanup all timers on unmount
   */
  useEffect(() => {
    return () => {
      pollingTimers.current.forEach((intervalId) => clearInterval(intervalId));
      pollingTimers.current.clear();
      generatingTitles.current.clear();
    };
  }, []);

  /**
   * Check if a specific session title is currently being generated
   */
  const isTitleGenerating = useCallback((sessionUuid) => {
    return generatingTitles.current.has(sessionUuid);
  }, []);

  return { isTitleGenerating, startPolling, stopPolling };
};
