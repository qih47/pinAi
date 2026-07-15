import React, { useState } from 'react';
import apiClient from '../../services/apiClient';
import { FileText, File, Settings } from 'lucide-react';
import { translations } from '../../utils/translations';

export default function DocumentGeneratorTab({ theme, darkMode, language }) {
  const t = translations[language]?.documentGen || translations.id.documentGen;
  const [instruction, setInstruction] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDoc, setGeneratedDoc] = useState(null);

  const handleGenerate = async () => {
    if (!instruction.trim()) return;
    setIsGenerating(true);
    setGeneratedDoc(null);
    
    try {
      const response = await apiClient.post('/corporate/document/generate', {
        instruction: instruction
      });
      if (response.data.status === 'success') {
        setGeneratedDoc(response.data.data.document_html);
      }
    } catch (error) {
      console.error("Gagal generate nota dinas", error);
      setGeneratedDoc(`<div style='color:red; text-align:center;'>${t.error}</div>`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div style={{ flex: 1, padding: '20px', color: theme.textColor, display: 'flex', flexDirection: 'column' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <FileText size={24} /> {t.title}
      </h2>
      <div style={{ display: 'flex', gap: '20px', flex: 1 }}>
        
        {/* Kiri: Instruksi */}
        <div style={{ width: '350px', background: darkMode ? '#1E1E22' : '#F9FAFB', borderRadius: '12px', padding: '16px', border: `1px solid ${theme.borderColor}`, display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '16px' }}>{t.docInstruction}</h3>
          
          <p style={{ fontSize: '12px', color: theme.secondaryText, marginBottom: '12px' }}>
            {t.docDesc}
          </p>
          
          <textarea 
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder={t.placeholder}
            style={{ 
              width: '100%', 
              flex: 1, 
              background: darkMode ? '#2A2A2D' : 'white', 
              border: `1px solid ${theme.borderColor}`,
              borderRadius: '8px',
              padding: '12px',
              color: theme.textColor,
              fontSize: '14px',
              resize: 'none',
              outline: 'none',
              marginBottom: '16px'
            }}
          />
          
          <button 
            onClick={handleGenerate}
            disabled={isGenerating || !instruction.trim()}
            style={{ 
              background: isGenerating ? '#9CA3AF' : '#10B981', 
              color: 'white', 
              padding: '12px', 
              borderRadius: '8px', 
              fontWeight: 'bold', 
              border: 'none', 
              cursor: isGenerating ? 'not-allowed' : 'pointer' 
            }}
          >
            {isGenerating ? t.generating : t.generateBtn}
          </button>
        </div>

        {/* Kanan: Preview Dokumen */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: darkMode ? '#1E1E22' : 'white', borderRadius: '12px', border: `1px solid ${theme.borderColor}`, overflow: 'hidden' }}>
          <div style={{ padding: '12px 20px', background: darkMode ? '#2A2A2D' : '#F3F4F6', borderBottom: `1px solid ${theme.borderColor}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: '600', fontSize: '14px' }}>{t.preview}</span>
            {generatedDoc && (
              <button style={{ background: '#3B82F6', color: 'white', padding: '6px 16px', borderRadius: '4px', fontSize: '12px', border: 'none', cursor: 'pointer' }}>
                {t.download}
              </button>
            )}
          </div>
          
          <div style={{ flex: 1, padding: '40px', overflowY: 'auto', display: 'flex', justifyContent: 'center', background: '#e5e7eb' }}>
            {isGenerating ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#4b5563' }}>
                <Settings size={30} style={{ animation: 'spin 2s linear infinite', color: '#6b7280' }} />
                <p style={{ marginTop: '16px', fontWeight: '500' }}>{t.adjusting}</p>
              </div>
            ) : generatedDoc ? (
              <div 
                style={{ background: 'white', color: 'black', width: '100%', maxWidth: '850px', display: 'flex', justifyContent: 'center' }}
                dangerouslySetInnerHTML={{ __html: generatedDoc }} 
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}>
                <File size={40} style={{ opacity: 0.5, marginBottom: '16px' }} />
                <p>{t.empty}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
