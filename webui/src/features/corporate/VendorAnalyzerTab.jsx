import React, { useState } from 'react';
import { BarChart2, FolderOpen, Sparkles, Star } from 'lucide-react';

export default function VendorAnalyzerTab({ theme, darkMode }) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showResult, setShowResult] = useState(false);

  const handleSimulateUpload = () => {
    setIsAnalyzing(true);
    setTimeout(() => {
      setIsAnalyzing(false);
      setShowResult(true);
    }, 3000);
  };

  return (
    <div style={{ flex: 1, padding: '20px', color: theme.textColor, display: 'flex', flexDirection: 'column' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <BarChart2 size={24} /> CAKRA Vendor Benchmarking (Matrix Analyzer)
      </h2>
      
      {!isAnalyzing && !showResult && (
        <div style={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          justifyContent: 'center',
          border: `2px dashed ${theme.borderColor}`,
          borderRadius: '16px',
          background: darkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
          margin: '20px 0'
        }}>
          <FolderOpen size={48} style={{ marginBottom: '16px', color: theme.secondaryText }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '8px' }}>Tarik & Lepas Dokumen Penawaran Vendor (PDF/Word)</h3>
          <p style={{ color: theme.secondaryText, marginBottom: '24px' }}>Unggah minimal 2 dokumen untuk dianalisa dan dibuat matriks perbandingannya.</p>
          <button 
            onClick={handleSimulateUpload}
            style={{ 
              background: '#8B5CF6', 
              color: 'white', 
              padding: '12px 32px', 
              borderRadius: '8px', 
              fontWeight: 'bold', 
              border: 'none', 
              cursor: 'pointer' 
            }}
          >
            Simulasikan Unggahan 3 Vendor
          </button>
        </div>
      )}

      {isAnalyzing && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '60px', height: '60px', border: '4px solid #8B5CF6', borderTopColor: 'transparent', borderRadius: '50%', animation: 'cakraSpin 1s linear infinite', marginBottom: '24px' }}></div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Mengekstrak Data Spesifikasi & Harga...</h3>
          <p style={{ color: theme.secondaryText, marginTop: '8px' }}>Menganalisa dokumen Vendor A, Vendor B, dan Vendor C menggunakan CAKRA OCR & NLP.</p>
        </div>
      )}

      {showResult && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ background: darkMode ? 'rgba(16, 185, 129, 0.1)' : '#ECFDF5', padding: '16px', borderRadius: '12px', border: `1px solid ${darkMode ? 'rgba(16,185,129,0.3)' : '#a7f3d0'}` }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 'bold', color: '#10B981', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={16} /> Kesimpulan Analisa CAKRA
            </h3>
            <p style={{ fontSize: '14px', lineHeight: '1.5' }}>
              <strong>Vendor A</strong> menawarkan harga paling rendah (Rp 500 Juta). Namun secara teknis dan kepatuhan SOP Pengadaan, <strong>Vendor B</strong> lebih unggul karena memberikan SLA Support 24x7 dan Masa Garansi 3 Tahun yang sesuai dengan batas minimal regulasi Pindad (SOP-004).
            </p>
          </div>

          <div style={{ background: darkMode ? '#1E1E22' : 'white', borderRadius: '12px', border: `1px solid ${theme.borderColor}`, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: darkMode ? '#2A2A2D' : '#F9FAFB', textAlign: 'left' }}>
                  <th style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>Kriteria Penilaian</th>
                  <th style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>Vendor A (PT Maju)</th>
                  <th style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, background: darkMode ? 'rgba(59, 130, 246, 0.1)' : '#EFF6FF' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Vendor B (CV Tekno) <Star size={14} fill="#F59E0B" color="#F59E0B" />
                    </div>
                  </th>
                  <th style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>Vendor C (UD Abadi)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, fontWeight: '600' }}>Total Harga Penawaran</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, color: '#10B981', fontWeight: 'bold' }}>Rp 500.000.000 (Terendah)</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, background: darkMode ? 'rgba(59, 130, 246, 0.05)' : '#F8FAFC' }}>Rp 550.000.000</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>Rp 580.000.000</td>
                </tr>
                <tr>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, fontWeight: '600' }}>Waktu Pengerjaan</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>45 Hari Kalender</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, background: darkMode ? 'rgba(59, 130, 246, 0.05)' : '#F8FAFC', color: '#10B981', fontWeight: 'bold' }}>30 Hari Kalender (Tercepat)</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>40 Hari Kalender</td>
                </tr>
                <tr>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, fontWeight: '600' }}>Masa Garansi</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, color: '#EF4444' }}>1 Tahun (Di bawah SOP)</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, background: darkMode ? 'rgba(59, 130, 246, 0.05)' : '#F8FAFC', color: '#10B981', fontWeight: 'bold' }}>3 Tahun (Sesuai SOP)</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>2 Tahun</td>
                </tr>
                <tr>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, fontWeight: '600' }}>SLA Support</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>8x5 (Jam Kerja)</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}`, background: darkMode ? 'rgba(59, 130, 246, 0.05)' : '#F8FAFC', color: '#10B981', fontWeight: 'bold' }}>24x7 (Prioritas)</td>
                  <td style={{ padding: '16px', borderBottom: `1px solid ${theme.borderColor}` }}>8x5 (Jam Kerja)</td>
                </tr>
              </tbody>
            </table>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
            <button 
              onClick={() => setShowResult(false)}
              style={{ background: 'transparent', color: theme.secondaryText, padding: '10px 20px', border: `1px solid ${theme.borderColor}`, borderRadius: '8px', cursor: 'pointer', marginRight: '12px' }}
            >
              Ulangi Analisa
            </button>
            <button style={{ background: '#10B981', color: 'white', padding: '10px 24px', borderRadius: '8px', fontWeight: 'bold', border: 'none', cursor: 'pointer' }}>
              Download PDF Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
