import React, { useState } from 'react';
import { getApiBase } from "../../../services/endpoints";

export default function OllamaThinkTest() {
  const [inputMsg, setInputMsg] = useState('Tolong carikan data detail untuk karyawan dengan NPP 06652 sekarang.');
  const [isThinkEnabled, setIsThinkEnabled] = useState(true); // Default true (/set think)
  const [isStreaming, setIsStreaming] = useState(false);

  // State penampung terpisah murni hasil ekstraksi parameter API resmi Ollama
  const [accumulatedThinking, setAccumulatedThinking] = useState('');
  const [accumulatedAnswer, setAccumulatedAnswer] = useState('');
  const [accumulatedTools, setAccumulatedTools] = useState(null);

  const handleStartStreamTest = async () => {
    setIsStreaming(true);
    setAccumulatedThinking('');
    setAccumulatedAnswer('');
    setAccumulatedTools(null); // Reset data interupsi lama

    // Payload eksperimen dengan injeksi objek tools di root level
    const payload = {
      model: "gemma4:12b",
      messages: [{ role: "user", content: inputMsg }],
      stream: true,
      think: isThinkEnabled,
      tools: [
        {
          "type": "function",
          "function": {
            "name": "ambil_data_karyawan_hris",
            "description": "Mengambil data detail pegawai berdasarkan NPP",
            "parameters": {
              "type": "object",
              "properties": {
                "npp": {"type": "string", "description": "Nomor Pokok Pegawai, contoh: '06652'"}
              },
              "required": ["npp"]
            }
          }
        }
      ],
      options: { temperature: 0.5 }
    };

    try {
      const targetUrl = `${getApiBase()}/api/chat/stream`;

      const response = await fetch(targetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const rawChunk = decoder.decode(value, { stream: true });
        const lines = rawChunk.split('\n');

        for (const line of lines) {
          let cleanLine = line.trim();
          if (!cleanLine) continue;

          if (cleanLine.startsWith('data:')) {
            cleanLine = cleanLine.replace('data:', '').trim();
          }

          try {
            const parsed = JSON.parse(cleanLine);
            const message = parsed.message || {};

            // 🚨 DETEKSI PARAMETER GAIB: INTERUPSI TOOL CALLS DI TENGAH STREAM
            const toolCallsData = parsed.tool_calls || message.tool_calls;
            if (toolCallsData) {
              console.log("🎯 Kena Interupsi Tool Calls di React:", toolCallsData);
              setAccumulatedTools(toolCallsData);
            }

            // 📥 Jalur data thinking murni
            const thinkingData = parsed.thinking || message.thinking;
            if (thinkingData) {
              setAccumulatedThinking(prev => prev + thinkingData);
            }

            // 📝 Jalur data konten teks biasa
            const contentData = parsed.content || message.content;
            if (contentData) {
              setAccumulatedAnswer(prev => prev + contentData);
            }
          } catch (e) {
            // Partial JSON buffer block ignored
          }
        }
      }
    } catch (err) {
      console.error("Koneksi gagal:", err);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'monospace', background: '#0f172a', color: '#e2e8f0', minHeight: '100vh' }}>
      <h2>Ollama Native Thinking Modality Sandbox 🧪</h2>

      {/* CONTROL PANEL SIMULASI TOGGLE SET THINK */}
      <div style={{ display: 'flex', gap: '16px', margin: '20px 0', alignItems: 'center', background: '#1e293b', padding: '16px', borderRadius: '8px' }}>
        <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="radio"
            name="think_toggle"
            checked={isThinkEnabled === true}
            onChange={() => setIsThinkEnabled(true)}
          />
          🟢 Mode: /set think (Enable Native Thinking)
        </label>

        <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="radio"
            name="think_toggle"
            checked={isThinkEnabled === false}
            onChange={() => setIsThinkEnabled(false)}
          />
          🔴 Mode: /set nothink (Bypass Thinking)
        </label>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <textarea
          style={{ width: '100%', padding: '10px', background: '#334155', color: '#fff', border: 'none', borderRadius: '4px' }}
          rows={2}
          value={inputMsg}
          onChange={(e) => setInputMsg(e.target.value)}
        />
      </div>

      <button
        onClick={handleStartStreamTest}
        disabled={isStreaming}
        style={{ padding: '10px 20px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
      >
        {isStreaming ? '⚡ Streaming Data...' : '🚀 Fire Test Prompt'}
      </button>

      <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>

        {/* DISPLAY BLOCK 1: KOSMETIK WRAPPER PENALARAN (AKORDION MODEL) */}
        {accumulatedThinking && (
          <div style={{ background: '#1e1e20', border: '1px solid #3f3f46', padding: '16px', borderRadius: '8px' }}>
            <div style={{ color: '#a1a1aa', fontWeight: 'bold', marginBottom: '8px', fontSize: '13px' }}>
              Thinking... <br />
              Thinking Process:
            </div>
            <div style={{ fontStyle: 'italic', color: '#cbd5e1', whiteSpace: 'pre-wrap', borderLeft: '3px solid #6366f1', paddingLeft: '12px' }}>
              {accumulatedThinking}
            </div>
            <div style={{ color: '#a1a1aa', fontWeight: 'bold', marginTop: '8px', fontSize: '13px' }}>
              ...done thinking.
            </div>
          </div>
        )}

        {/* 🚨 DISPLAY BLOCK INTERUPSI: TOOL CALLS DETECTED (SUDAH DI DALAM RETURN RUANG VALID) */}
        {accumulatedTools && (
          <div style={{ background: '#7c2d12', border: '1px solid #ea580c', padding: '16px', borderRadius: '8px' }}>
            <div style={{ color: '#ffedd5', fontWeight: 'bold', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              🚨 [STREAM INTERRUPTION] MODEL MEMANGGIL FUNGSI LUAR:
            </div>
            <pre style={{ background: '#1c1917', padding: '12px', borderRadius: '6px', color: '#fdba74', overflowX: 'auto', fontSize: '12px' }}>
              {JSON.stringify(accumulatedTools, null, 2)}
            </pre>
            <div style={{ color: '#fed7aa', fontSize: '12px', marginTop: '8px', fontStyle: 'italic' }}>
              *Sistem mendeteksi parameter ini masuk di tengah aliran data stream JSON.
            </div>
          </div>
        )}

        {/* DISPLAY BLOCK 2: JAWABAN AKHIR */}
        {accumulatedAnswer && (
          <div style={{ background: '#020617', border: '1px solid #1e293b', padding: '16px', borderRadius: '8px' }}>
            <div style={{ color: '#38bdf8', fontWeight: 'bold', marginBottom: '8px' }}>CAKRA FINAL RESPONSE:</div>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
              {accumulatedAnswer}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}