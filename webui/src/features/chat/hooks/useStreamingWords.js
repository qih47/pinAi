import { useRef, useState, useEffect } from 'react';

/**
 * useStreamingWords
 *
 * Tracks each streaming chunk from the LLM and produces a stable
 * "rendered content" split between:
 *   - `settledContent` — text that has finished animating (static)
 *   - `newWords` — array of new word tokens to animate in
 *
 * This avoids re-animating the entire text on every render,
 * so only the truly NEW tokens get the fade-in treatment.
 *
 * @param {string} rawContent - Full text content from streaming state
 * @param {boolean} isStreaming - Whether the model is still generating
 * @returns {{ settledContent: string, newWords: string[] }}
 */
export function useStreamingWords(rawContent, isStreaming) {
  // The last fully "settled" text (already rendered, no animation)
  const settledRef = useRef('');
  const [newWords, setNewWords] = useState([]);

  useEffect(() => {
    if (!isStreaming) {
      // Stream ended: collapse everything into settled, clear new words
      settledRef.current = rawContent || '';
      setNewWords([]);
      return;
    }

    const current = rawContent || '';
    const prev = settledRef.current;

    if (!current.startsWith(prev)) {
      // Content replaced entirely (new message) — reset
      settledRef.current = '';
      setNewWords(current.split(/(\s+)/).filter(Boolean));
      return;
    }

    const delta = current.slice(prev.length);
    if (!delta) return;

    // Tokenize delta into word+whitespace tokens so we preserve spacing
    const tokens = delta.split(/(\s+)/).filter(Boolean);
    if (tokens.length === 0) return;

    // Move previous newWords into settled, then set fresh batch
    settledRef.current = prev + (newWords.join(''));
    setNewWords(tokens);

  }, [rawContent, isStreaming]);

  return {
    settledContent: settledRef.current,
    newWords,
  };
}
