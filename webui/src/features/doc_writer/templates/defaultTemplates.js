/**
 * CAKRA AI — Default Document Templates
 * Kerangka awal dokumen resmi PT Pindad untuk Tiptap Editor
 */

export const defaultTemplates = {
  template_skep: {
    id: 'template_skep',
    name: 'Surat Keputusan Direksi (SKEP)',
    title: 'Surat Keputusan Direksi Penetapan',
    description: 'Format baku Surat Keputusan Direksi PT Pindad dengan bagian Menimbang, Mengingat, dan Diktum Keputusan.',
    html: `
      <div data-section="kop" style="text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 15pt; font-weight: bold; letter-spacing: 0.5px;">PT PINDAD (PERSERO)</h2>
        <p style="margin: 2px 0 0 0; font-size: 10pt; font-weight: bold;">DIVISI TEKNOLOGI INFORMASI & KOMUNIKASI</p>
        <p style="margin: 2px 0 0 0; font-size: 8.5pt; color: #666; font-style: italic;">Jl. Gatot Subroto No. 517, Bandung 40284 | www.pindad.com</p>
        <hr style="border: 0; border-top: 2px solid #000; margin: 10px 0 20px 0;" />
      </div>

      <div data-section="judul" style="text-align: center; margin-bottom: 24px;">
        <h3 style="margin: 0; font-size: 13pt; font-weight: bold; text-decoration: underline;">KEPUTUSAN DIREKSI PT PINDAD</h3>
        <p style="margin: 4px 0 0 0; font-size: 11pt;">NOMOR : SKEP / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / PINDAD / 2026</p>
        <p style="margin: 8px 0 0 0; font-size: 11pt; font-weight: bold;">TENTANG</p>
        <p style="margin: 4px 0 0 0; font-size: 11pt; font-weight: bold; text-transform: uppercase;">PENETAPAN TIM KERJA DAN STANDAR TEKNIS IMPLEMENTASI SISTEM</p>
        <p style="margin: 12px 0 0 0; font-size: 11pt; font-weight: bold;">DIREKSI PT PINDAD,</p>
      </div>

      <div data-section="menimbang" style="margin-bottom: 16px;">
        <p style="text-align: justify; line-height: 1.5; margin: 0 0 6px 0;">
          <strong>Menimbang :</strong>
        </p>
        <ol style="margin-top: 4px; padding-left: 24px; text-align: justify; line-height: 1.5;">
          <li>bahwa dalam rangka mempercepat transformasi digital dan standardisasi tata kelola teknologi informasi di lingkungan PT Pindad, dipandang perlu dibentuk Tim Kerja khusus;</li>
          <li>bahwa personil yang namanya tercantum dalam keputusan ini dipandang cakap dan memenuhi syarat untuk melaksanakan tugas tersebut;</li>
          <li>bahwa berdasarkan pertimbangan sebagaimana dimaksud pada huruf a dan b di atas, perlu ditetapkan Keputusan Direksi.</li>
        </ol>
      </div>

      <div data-section="mengingat" style="margin-bottom: 16px;">
        <p style="text-align: justify; line-height: 1.5; margin: 0 0 6px 0;">
          <strong>Mengingat :</strong>
        </p>
        <ol style="margin-top: 4px; padding-left: 24px; text-align: justify; line-height: 1.5;">
          <li>Undang-Undang Nomor 19 Tahun 2003 tentang Badan Usaha Milik Negara;</li>
          <li>Anggaran Dasar PT Pindad beserta segala perubahannya;</li>
          <li>Peraturan Direksi PT Pindad tentang Tata Kelola Sistem Informasi dan Keamanan Siber.</li>
        </ol>
      </div>

      <div data-section="memutuskan" style="margin-bottom: 24px;">
        <p style="text-align: center; font-weight: bold; margin: 16px 0 10px 0;">MEMUTUSKAN :</p>
        <p style="text-align: justify; line-height: 1.5; margin: 0 0 6px 0;">
          <strong>Menetapkan :</strong> KEPUTUSAN DIREKSI PT PINDAD TENTANG PENETAPAN TIM KERJA DAN STANDAR TEKNIS.
        </p>
        <p style="text-align: justify; line-height: 1.5; margin: 8px 0 4px 0;">
          <strong>KESATU :</strong> Menetapkan susunan Tim Kerja Teknologi Informasi PT Pindad sebagaimana tercantum dalam lampiran keputusan ini.
        </p>
        <p style="text-align: justify; line-height: 1.5; margin: 8px 0 4px 0;">
          <strong>KEDUA :</strong> Tim Kerja bertugas merumuskan arsitektur sistem, standardisasi koding, dan pengawasan migrasi infrastruktur terpadu.
        </p>
        <p style="text-align: justify; line-height: 1.5; margin: 8px 0 4px 0;">
          <strong>KETIGA :</strong> Keputusan ini berlaku sejak tanggal ditetapkan dengan ketentuan apabila di kemudian hari terdapat kekeliruan akan diperbaiki sebagaimana mestinya.
        </p>
      </div>

      <div data-section="penutup" style="margin-top: 36px; display: flex; justify-content: flex-end;">
        <table style="width: 280px; margin-left: auto; border: 0; text-align: left;">
          <tr><td>Ditetapkan di</td><td>: Bandung</td></tr>
          <tr><td>Pada tanggal</td><td>: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 2026</td></tr>
          <tr><td colspan="2" style="padding-top: 8px; font-weight: bold;">DIREKSI PT PINDAD</td></tr>
          <tr><td colspan="2" style="height: 60px;"></td></tr>
          <tr><td colspan="2" style="font-weight: bold; text-decoration: underline;">DIREKTUR UTAMA</td></tr>
        </table>
      </div>
    `
  },

  template_se: {
    id: 'template_se',
    name: 'Surat Edaran (SE)',
    title: 'Surat Edaran Pedoman',
    description: 'Format Surat Edaran PT Pindad untuk petunjuk pelaksanaan kebijakan, tata tertib, dan instruksi operasional.',
    html: `
      <div data-section="kop" style="text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 15pt; font-weight: bold;">PT PINDAD (PERSERO)</h2>
        <p style="margin: 2px 0 0 0; font-size: 10pt; font-weight: bold;">DIVISI TEKNOLOGI INFORMASI & KOMUNIKASI</p>
        <hr style="border: 0; border-top: 2px solid #000; margin: 10px 0 20px 0;" />
      </div>

      <div data-section="judul" style="text-align: center; margin-bottom: 24px;">
        <h3 style="margin: 0; font-size: 13pt; font-weight: bold; text-decoration: underline;">SURAT EDARAN</h3>
        <p style="margin: 4px 0 0 0; font-size: 11pt;">NOMOR : SE / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / PINDAD / 2026</p>
        <p style="margin: 8px 0 0 0; font-size: 11pt; font-weight: bold;">TENTANG</p>
        <p style="margin: 4px 0 0 0; font-size: 11pt; font-weight: bold; text-transform: uppercase;">PANDUAN STANDARDISASI PENGEMBANGAN APLIKASI & KEAMANAN SISTEM</p>
      </div>

      <div data-section="latar_belakang" style="margin-bottom: 16px;">
        <h4 style="font-size: 11pt; font-weight: bold; margin: 0 0 6px 0;">1. LATAR BELAKANG</h4>
        <p style="text-align: justify; line-height: 1.5; margin: 0;">
          Dalam rangka meningkatkan efisiensi operasional dan memperkuat postur keamanan informasi di seluruh unit kerja PT Pindad, diperlukan pedoman baku yang mengatur alur pengembangan, arsitektur, dan integrasi antar aplikasi.
        </p>
      </div>

      <div data-section="maksud_tujuan" style="margin-bottom: 16px;">
        <h4 style="font-size: 11pt; font-weight: bold; margin: 0 0 6px 0;">2. MAKSUD DAN TUJUAN</h4>
        <p style="text-align: justify; line-height: 1.5; margin: 0 0 6px 0;">
          Surat Edaran ini dimaksudkan sebagai acuan kerja bagi seluruh developer, staf IT, dan rekanan teknis agar memiliki keselarasan standar teknologi yang handal dan teruji.
        </p>
      </div>

      <div data-section="ruang_lingkup" style="margin-bottom: 16px;">
        <h4 style="font-size: 11pt; font-weight: bold; margin: 0 0 6px 0;">3. RUANG LINGKUP</h4>
        <p style="text-align: justify; line-height: 1.5; margin: 0;">
          Ketentuan dalam Surat Edaran ini berlaku bagi seluruh sistem internal, backend service, antarmuka frontend, dan integrasi Single Sign On (SSO) di PT Pindad.
        </p>
      </div>

      <div data-section="isi_edaran" style="margin-bottom: 20px;">
        <h4 style="font-size: 11pt; font-weight: bold; margin: 0 0 6px 0;">4. KETENTUAN DAN PETUNJUK PELAKSANAAN</h4>
        <ol style="margin-top: 4px; padding-left: 24px; text-align: justify; line-height: 1.5;">
          <li>Seluruh layanan backend wajib mematuhi pemisahan tanggung jawab antara Router, Layanan Bisnis, dan Akses Database.</li>
          <li>Format respons API distandarisasi menggunakan JSON berstruktur seragam dengan atribut success, message, dan data.</li>
          <li>Setiap deployment wajib melalui pipeline otomatisasi CI/CD dan menggunakan container Docker.</li>
        </ol>
      </div>

      <div data-section="penutup" style="margin-top: 36px;">
        <p style="text-align: justify; line-height: 1.5; margin: 0 0 16px 0;">
          Demikian Surat Edaran ini dikeluarkan untuk diperhatikan dan dilaksanakan dengan penuh rasa tanggung jawab.
        </p>
        <table style="width: 280px; margin-left: auto; border: 0; text-align: left;">
          <tr><td>Dikeluarkan di</td><td>: Bandung</td></tr>
          <tr><td>Pada tanggal</td><td>: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 2026</td></tr>
          <tr><td colspan="2" style="padding-top: 8px; font-weight: bold;">PT PINDAD (PERSERO)</td></tr>
          <tr><td colspan="2" style="height: 50px;"></td></tr>
          <tr><td colspan="2" style="font-weight: bold; text-decoration: underline;">KEPALA DIVISI / PEJABAT BERWENANG</td></tr>
        </table>
      </div>
    `
  },

  template_memo: {
    id: 'template_memo',
    name: 'Nota Dinas / Memo Internal',
    title: 'Nota Dinas Koordinasi Teknis',
    description: 'Format komunikasi kedinasan antar divisi / unit kerja di lingkungan PT Pindad.',
    html: `
      <div data-section="kop" style="text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 14pt; font-weight: bold;">PT PINDAD (PERSERO)</h2>
        <h3 style="margin: 2px 0 0 0; font-size: 12pt; font-weight: bold; text-decoration: underline;">NOTA DINAS</h3>
        <p style="margin: 4px 0 0 0; font-size: 10pt;">Nomor : ND / &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / TI / 2026</p>
        <hr style="border: 0; border-top: 2px solid #000; margin: 10px 0 16px 0;" />
      </div>

      <div data-section="metadata" style="margin-bottom: 20px;">
        <table style="width: 100%; border: 0; font-size: 10.5pt; line-height: 1.6;">
          <tr><td style="width: 90px; font-weight: bold;">Kepada Yth.</td><td style="width: 15px;">:</td><td>Kepala Divisi Terkait</td></tr>
          <tr><td style="font-weight: bold;">Dari</td><td>:</td><td>Kepala Divisi Teknologi Informasi & Komunikasi</td></tr>
          <tr><td style="font-weight: bold;">Tanggal</td><td>:</td><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 2026</td></tr>
          <tr><td style="font-weight: bold;">Perihal</td><td>:</td><td><strong>Permohonan Koordinasi Teknis dan Validasi Sistem</strong></td></tr>
        </table>
        <hr style="border: 0; border-top: 1px solid #ccc; margin: 12px 0;" />
      </div>

      <div data-section="isi_memo" style="margin-bottom: 24px;">
        <p style="text-align: justify; line-height: 1.6; margin: 0 0 10px 0;">
          Sehubungan dengan pelaksanaan agenda modernisasi infrastruktur dan sistem informasi terpadu di lingkungan PT Pindad, bersama ini kami sampaikan hal-hal sebagai berikut:
        </p>
        <ol style="padding-left: 20px; line-height: 1.6; text-align: justify;">
          <li>Divisi TI telah menyelesaikan tahap pengujian awal implementasi modul terpusat.</li>
          <li>Diperlukan verifikasi dan masukan dari unit kerja terkait mengenai kesesuaian proses bisnis.</li>
          <li>Kami mengundang perwakilan tim teknis untuk menghadiri sesi validasi bersama yang akan dijadwalkan kemudian.</li>
        </ol>
      </div>

      <div data-section="penutup" style="margin-top: 30px;">
        <p style="margin: 0 0 20px 0;">Demikian nota dinas ini disampaikan. Atas perhatian dan kerja samanya diucapkan terima kasih.</p>
        <table style="width: 250px; margin-left: auto; border: 0; text-align: left;">
          <tr><td style="font-weight: bold;">KEPALA DIVISI TI</td></tr>
          <tr><td style="height: 50px;"></td></tr>
          <tr><td style="font-weight: bold; text-decoration: underline;">NAMA PEJABAT</td></tr>
          <tr><td>NPP. 1234567</td></tr>
        </table>
      </div>
    `
  },

  template_blank: {
    id: 'template_blank',
    name: 'Dokumen Standar PT Pindad (Blank)',
    title: 'Dokumen Kerja PT Pindad',
    description: 'Kertas kerja berformat A4 standar corporate PT Pindad lengkap dengan Kop Surat resmi.',
    html: `
      <div data-section="kop" style="text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 15pt; font-weight: bold;">PT PINDAD (PERSERO)</h2>
        <p style="margin: 2px 0 0 0; font-size: 10pt; font-weight: bold;">DIVISI TEKNOLOGI INFORMASI & KOMUNIKASI</p>
        <p style="margin: 2px 0 0 0; font-size: 8.5pt; color: #666; font-style: italic;">Jl. Gatot Subroto No. 517, Bandung 40284 | www.pindad.com</p>
        <hr style="border: 0; border-top: 2px solid #000; margin: 10px 0 20px 0;" />
      </div>

      <div data-section="body" style="line-height: 1.6;">
        <h3 style="text-align: center; margin-bottom: 16px;">JUDUL DOKUMEN</h3>
        <p style="text-align: justify; margin-bottom: 12px;">
          Mulai ketik isi dokumen Anda di sini atau minta CAKRA di panel chat untuk merumuskan draf pasal, kajian teknis, maupun kebijakan.
        </p>
      </div>
    `
  }
};
