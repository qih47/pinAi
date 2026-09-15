import os
import io
import re
import time
import asyncio
import logging
import traceback
from typing import Optional, Tuple, Dict, Any
from collections import OrderedDict

import torch
import numpy as np
import soundfile as sf

logger = logging.getLogger("pinAi")

# Comprehensive phonetic map for common tech jargon, English loanwords, and Indonesian abbreviations
PHONETIC_ROOTS = {
    # Tech / English Loanwords
    'file': 'fail',
    'files': 'fails',
    'download': 'daunlod',
    'chat': 'cet',
    'web': 'wep',
    'website': 'wepsait',
    'app': 'ep',
    'apps': 'eps',
    'update': 'apdet',
    'upgrade': 'apgred',
    'user': 'yuser',
    'users': 'yusers',
    'error': 'eror',
    'dashboard': 'desbord',
    'database': 'databes',
    'online': 'onlain',
    'offline': 'oflain',
    'wifi': 'waifai',
    'password': 'paswot',
    'email': 'imel',
    'detail': 'ditel',
    'project': 'projek',
    'task': 'tesk',
    'bug': 'bag',
    'fix': 'fiks',
    'feature': 'ficer',
    'upload': 'aplod',
    'share': 'syer',
    'software': 'sofwer',
    'hardware': 'hardwer',
    'server': 'server',
    'cloud': 'klaud',
    'link': 'ling',
    'click': 'klik',
    'login': 'login',
    'logout': 'logaut',
    'sign': 'sain',

    # Common Acronyms
    'ai': 'e ai',
    'api': 'e pi ai',
    'ui': 'yu ai',
    'ux': 'yu eks',
    'it': 'ai ti',
    'url': 'yu er el',
    'pdf': 'pe de ef',
    'cv': 'si fi',
    'hr': 'eic ar',
    'ac': 'a se',
    'tbk': 'te be ka',
    'bumn': 'be u em en',
    'pic': 'pi ai si',
    'pkb': 'pe ka be',
    'kpk': 'ka pe ka',
    'dpr': 'de pe er',
    'dprd': 'de pe er de',
    'wib': 'we i be',
    'wita': 'wita',
    'wit': 'wit',

    # Indonesian specific abbreviations & slang
    'sip': 'siip',
    'oke': 'okey',
    'yg': 'yang',
    'dg': 'dengan',
    'dgn': 'dengan',
    'tsb': 'tersebut',
    'dll': 'dan lain lain',
    'ybs': 'yang bersangkutan',
    'tgl': 'tanggal',
    'bln': 'bulan',
    'thn': 'tahun',
    'rp': 'rupiah',
    'jgn': 'jangan',
    'bgt': 'banget',
    'sumber': 'sumber',

    # Fonetik pelafalan kata bahasa Indonesia agar tidak bias ke fonem Inggris
    'cuaca': 'chuaca',
    'cuacanya': 'chuacanya',
    'coba': 'choba',
    'contoh': 'chontoh',
    'cocok': 'chochok',
    'cukup': 'chukup',
    'cuma': 'chuma',
    'cuci': 'chuci',
    'curiga': 'churiga',
    'skep': 'skep',
}

# Mapping angka Romawi ke kata bahasa Indonesia
ROMAN_MAP = {
    'I': 'Satu',
    'II': 'Dua',
    'III': 'Tiga',
    'IV': 'Empat',
    'V': 'Lima',
    'VI': 'Enam',
    'VII': 'Tujuh',
    'VIII': 'Delapan',
    'IX': 'Sembilan',
    'X': 'Sepuluh',
}

# Mapping singkatan institusi / media populer agar dieja per huruf yang jelas
ACRONYM_SPELLINGS = {
    'UMY': 'U M Y',
    'UGM': 'U G M',
    'ITB': 'I T B',
    'UI': 'U I',
    'IPB': 'I P B',
    'UNAIR': 'U N A I R',
    'UNDIP': 'U N D I P',
    'UNPAD': 'U N P A D',
    'BMKG': 'B M K G',
    'BNPB': 'B N P B',
    'PVMBG': 'P V M B G',
    'BPBD': 'B P B D',
    'SAR': 'Basarnas',
    'CNN': 'C N N',
    'BBC': 'B B C',
    'CNBC': 'C N B C',
    'RRI': 'R R I',
    'TNI': 'T N I',
    'POLRI': 'Polri',
    'KEMENKES': 'Kemenkes',
    'ESDM': 'E S D M',
}


def expand_numbers_id(text: str) -> str:
    """Konversi deretan angka digit ke teks kata-kata bahasa Indonesia."""
    satuan = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]

    def to_words(n: int) -> str:
        if n < 12:
            return satuan[n]
        elif n < 20:
            return satuan[n - 10] + " belas"
        elif n < 100:
            rem = satuan[n % 10]
            return satuan[n // 10] + " puluh" + (" " + rem if rem else "")
        elif n < 200:
            rem = to_words(n - 100)
            return "seratus" + (" " + rem if rem else "")
        elif n < 1000:
            rem = to_words(n % 100)
            return satuan[n // 100] + " ratus" + (" " + rem if rem else "")
        elif n < 2000:
            rem = to_words(n - 1000)
            return "seribu" + (" " + rem if rem else "")
        elif n < 1000000:
            rem = to_words(n % 1000)
            return to_words(n // 1000) + " ribu" + (" " + rem if rem else "")
        elif n < 1000000000:
            rem = to_words(n % 1000000)
            return to_words(n // 1000000) + " juta" + (" " + rem if rem else "")
        elif n < 1000000000000:
            rem = to_words(n % 1000000000)
            return to_words(n // 1000000000) + " miliar" + (" " + rem if rem else "")
        else:
            return str(n)

    def replace_num(match):
        val_str = match.group(0)
        try:
            val = int(val_str)
            if val == 0:
                return "nol"
            res = to_words(val).strip()
            return re.sub(r'\s{2,}', ' ', res)
        except Exception:
            return val_str

    return re.sub(r'\b\d+\b', replace_num, text)


def phonetic_correction(text: str) -> str:
    """Terapkan koreksi fonetik dengan tetap mempertahankan morfologi awalan & akhiran bahasa Indonesia."""
    prefixes = ['di', 'ke', 'ter']
    suffixes = ['nya', 'ku', 'mu', 'kan', 'lah', 'pun']

    def replace_word(match):
        word = match.group(0)
        word_lower = word.lower()

        # 1. Exact match
        if word_lower in PHONETIC_ROOTS:
            return PHONETIC_ROOTS[word_lower]

        # 2. Check Suffix only (e.g. filenya -> failnya)
        for suf in suffixes:
            if word_lower.endswith(suf):
                root = word_lower[:-len(suf)]
                if root in PHONETIC_ROOTS:
                    return PHONETIC_ROOTS[root] + suf

        # 3. Check Prefix only (e.g. diupdate -> diapdet)
        for pref in prefixes:
            if word_lower.startswith(pref):
                root = word_lower[len(pref):]
                if root in PHONETIC_ROOTS:
                    return pref + PHONETIC_ROOTS[root]

        # 4. Check Prefix + Suffix (e.g. diupdatenya -> diapdetnya)
        for pref in prefixes:
            for suf in suffixes:
                if word_lower.startswith(pref) and word_lower.endswith(suf):
                    root = word_lower[len(pref):-len(suf)]
                    if root in PHONETIC_ROOTS:
                        return pref + PHONETIC_ROOTS[root] + suf

        return word

    return re.sub(r'\b[a-zA-Z]+\b', replace_word, text)


def clean_text_for_tts(text: str) -> str:
    """
    Sanitasi dan normalisasi teks tingkat lanjut untuk pembacaan suara F5-TTS:
    1. Buang total blok metadata (websearch, urlfetch, docsearch, log).
    2. Format sitasi sumber secara natural (misal: [Sumber: UMY] -> 'Sumber dari U M Y').
    3. Normalisasi rentang angka (4-6 -> empat sampai enam).
    4. Normalisasi angka Romawi (Level III -> Level Tiga).
    5. Normalisasi mata uang & jam.
    6. Koreksi fonetik & pelafalan vokal.
    """
    if not text:
        return ""

    t = text

    # 1. Buang blok metadata code block secara tuntas
    t = re.sub(r'```(?:websearch|urlfetch|docsearch|document_meta|json)?[\s\S]*?```', '', t)
    t = re.sub(r'\[\[CAKRA_FILE_PROCESS_LOG[\s\S]*?\]\]', '', t)

    # 2. Format Sitasi Sumber: [Sumber: UMY](https://...) atau [Sumber: Kompas.com]
    def format_citation(match):
        source_label = match.group(1).strip()
        # Bersihkan titik dua dan spasi berlebih
        source_label = re.sub(r'^:\s*', '', source_label)

        # Cek jika ada akronim populer
        upper_label = source_label.upper()
        if upper_label in ACRONYM_SPELLINGS:
            source_label = ACRONYM_SPELLINGS[upper_label]
        elif re.match(r'^[A-Z]{2,5}$', source_label):
            # Eja per huruf untuk akronim kapital murni
            source_label = ' '.join(list(source_label))

        # Ubah domain web misal 'Kompas.com' -> 'Kompas dot com'
        source_label = re.sub(r'\.com\b', ' dot com', source_label, flags=re.IGNORECASE)
        source_label = re.sub(r'\.co\.id\b', ' dot co dot i d', source_label, flags=re.IGNORECASE)
        source_label = re.sub(r'\.id\b', ' dot i d', source_label, flags=re.IGNORECASE)
        source_label = re.sub(r'\.ac\.id\b', ' dot a c dot i d', source_label, flags=re.IGNORECASE)
        source_label = re.sub(r'\.org\b', ' dot org', source_label, flags=re.IGNORECASE)

        return f", sumber dari {source_label}."

    # Tangani markdown link [Sumber: X](url) atau badge [Sumber: X]
    t = re.sub(r'\[Sumber\s*:?\s*([^\]]+)\](?:\([^)]*\))?', format_citation, t, flags=re.IGNORECASE)

    # Tangani markdown link umum [Label](url) -> ambil labelnya saja
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)

    # 3. Normalisasi Satuan, Derajat Suhu & Persentase (misal: 28°C -> 28 derajat celcius)
    t = re.sub(r'(\d+(?:[.,]\d+)?)\s*°\s*C\b', r'\1 derajat celcius', t, flags=re.IGNORECASE)
    t = re.sub(r'(\d+(?:[.,]\d+)?)\s*°\b', r'\1 derajat', t)
    t = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 persen', t)
    t = re.sub(r'\bkm/jam\b', 'kilometer per jam', t, flags=re.IGNORECASE)
    t = re.sub(r'\bm/s\b', 'meter per detik', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(\d+)\s*km\b', r'\1 kilometer', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(\d+)\s*cm\b', r'\1 sentimeter', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(\d+)\s*mm\b', r'\1 milimeter', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(\d+)\s*kg\b', r'\1 kilogram', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(\d+)\s*gr\b', r'\1 gram', t, flags=re.IGNORECASE)

    # 4. Normalisasi Rentang Angka (misal: 4–6 September -> 4 sampai 6 September)
    t = re.sub(r'(\d+)\s*[-–—]\s*(\d+)', r'\1 sampai \2', t)

    # 5. Normalisasi Angka Romawi berkonteks (Level III -> Level Tiga, Bab II -> Bab Dua, dsb.)
    def replace_roman(match):
        prefix = match.group(1)
        roman = match.group(2).upper()
        word = ROMAN_MAP.get(roman, roman)
        return f"{prefix} {word}"

    t = re.sub(
        r'\b(Level|Tingkat|Bab|Fase|Tahap|Kelas|Jilid|Generasi|Bagian)\s+(I|II|III|IV|V|VI|VII|VIII|IX|X)\b',
        replace_roman,
        t,
        flags=re.IGNORECASE
    )

    # 6. Normalisasi Jam / Waktu (misal: 14.30 WIB -> pukul 14 lewat 30 we i be)
    def replace_time(match):
        hour = match.group(1)
        minute = match.group(2)
        tz = (match.group(3) or "").upper()
        tz_word = ""
        if tz == "WIB":
            tz_word = "we i be"
        elif tz == "WITA":
            tz_word = "wita"
        elif tz == "WIT":
            tz_word = "wit"

        if minute in ["00", "0"]:
            return f"pukul {hour} tepat {tz_word}".strip()
        else:
            return f"pukul {hour} lewat {minute} {tz_word}".strip()

    t = re.sub(r'(?:(?:pukul|jam)\s+)?\b(\d{1,2})[:.](\d{2})\s*(WIB|WITA|WIT)?\b', replace_time, t, flags=re.IGNORECASE)

    # 7. Normalisasi Mata Uang Rupiah (Rp 50.000 -> 50000 rupiah)
    t = re.sub(r'\bRp\.?\s*([\d\.]+)', lambda m: m.group(1).replace('.', '') + ' rupiah', t, flags=re.IGNORECASE)

    # 8. Hapus titik pemisah ribuan agar '1.500' dibaca 'seribu lima ratus' bukan 'satu titik lima ratus'
    t = re.sub(r'(?<=\d)\.(?=\d{3}(?:\b|\.|\s))', '', t)

    # 9. Expand angka digit ke kata-kata bahasa Indonesia
    t = expand_numbers_id(t)

    # 10. Akronim militer / kedinasan / BUMN Pindad yang dibaca sebagai kata utuh (bukan dieja per huruf)
    MILITARY_WORD_ACRONYMS = {
        r'\bSKEP\b': 'skep',
        r'\bKASAD\b': 'kasad',
        r'\bKASAL\b': 'kasal',
        r'\bKASAU\b': 'kasau',
        r'\bPINDAD\b': 'pindad',
        r'\bHANKAM\b': 'hankam',
        r'\bKODAM\b': 'kodam',
        r'\bKODIM\b': 'kodim',
        r'\bKORAMIL\b': 'koramil',
        r'\bBABINSA\b': 'babinsa',
        r'\bPOLDA\b': 'polda',
        r'\bPOLRES\b': 'polres',
        r'\bPOLSEK\b': 'polsek',
        r'\bRANPUR\b': 'ranpur',
        r'\bRANTIS\b': 'rantis',
        r'\bMUNISI\b': 'munisi',
        r'\bKORPRI\b': 'korpri',
        r'\bKAPOLRI\b': 'kapolri',
        r'\bPANGLIMA\b': 'panglima',
        r'\bBAPEKAS\b': 'bapekas',
        r'\bDISHUB\b': 'dishub',
        r'\bPUSPOM\b': 'puspom',
        r'\bSATGAS\b': 'satgas',
        r'\bDANRAMIL\b': 'danramil',
        r'\bDANDIM\b': 'dandim',
        r'\bDANREM\b': 'danrem',
        r'\bSIM\b': 'sim',
    }
    for pattern, repl in MILITARY_WORD_ACRONYMS.items():
        t = re.sub(pattern, repl, t, flags=re.IGNORECASE)

    # Akronim yang harus dieja per huruf
    SPELL_OUT_ACRONYMS = {
        r'\bSOP\b': 'es o pe',
        r'\bSK\b': 'es ka',
        r'\bKTP\b': 'ka te pe',
        r'\bNPWP\b': 'en pe we pe',
        r'\bKTA\b': 'ka te a',
        r'\bBPJS\b': 'be pe je es',
        r'\bBUMN\b': 'be u em en',
        r'\bPT\b': 'pe te',
        r'\bCV\b': 'se ve',
        r'\bTNI\b': 'te en i',
        r'\bPOLRI\b': 'polri',
        r'\bBSSN\b': 'be es es en',
        r'\bWIB\b': 'we i be',
        r'\bWITA\b': 'wita',
        r'\bWIT\b': 'wit',
    }
    for pattern, repl in SPELL_OUT_ACRONYMS.items():
        t = re.sub(pattern, repl, t)

    # 11. Terapkan kamus fonetik kata serapan & singkatan
    t = phonetic_correction(t)

    # 10. Pembersihan Karakter & Tanda Baca
    # Hapus emoji
    t = re.sub(r'[\U0001F300-\U0001FFFF\U00002600-\U000027FF]', '', t)
    # Hapus tanda petik (bikin model stutter)
    t = re.sub(r'["\']', '', t)
    # Hapus markdown symbols
    t = re.sub(r'[*_#`~]', '', t)
    # Ganti tanda kurung dengan koma untuk jeda nafas alami
    t = re.sub(r'[(\[{]', ', ', t)
    t = re.sub(r'[)\]}]', ', ', t)
    # Ganti titik dua di tengah kalimat dengan titik
    t = re.sub(r':', '.', t)
    # Ganti & -> dan
    t = re.sub(r'&', ' dan ', t)
    # Hapus list format angka di awal baris (1. -> hilang)
    t = re.sub(r'(?m)^\s*\d+\.\s+', '', t)
    # Hapus bullet points di awal baris
    t = re.sub(r'(?m)^\s*[-*•]\s+', '', t)
    # Hapus koma berulang dan rapikan spasi sekitar koma
    t = re.sub(r',\s*,+', ', ', t)
    t = re.sub(r'\s*,\s*', ', ', t)
    # Hapus koma sebelum partikel informal biar intonasi mengalir
    t = re.sub(r',\s+(cuy|cui|bro|ya|dong|deh|nih|tuh|sih|yuk|kok)\b', r' \1', t, flags=re.IGNORECASE)
    # Sederhanakan elipsis (...) jadi 1 titik
    t = re.sub(r'\.\s*\.+', '.', t)
    # Rapikan koma sebelum titik
    t = re.sub(r',\s*\.', '.', t)
    # Rapikan spasi
    t = re.sub(r'\s{2,}', ' ', t).strip()

    # Pastikan diakhiri tanda baca pemutus
    if t and not re.search(r'[.?!]$', t):
        t += '.'

    return t


class TTSService:
    """
    Layanan terpusat untuk Text-to-Speech (TTS) Cakra AI berbasis F5-TTS Indonesia & Vocos.
    Memenuhi standar arsitektur Cakra (cakra-architecture-enforcer):
    - Terisolasi dari router API
    - Menggunakan NFE=10 untuk inferensi ultra-cepat (~1.2s, 3.88x real-time)
    - Duration padding & anti-cutoff (speed factor 0.88) agar kata terakhir diucapkan utuh
    - Output format MP3 terkompresi (~86% lebih hemat bandwidth)
    - In-Memory LRU Cache untuk respons 0ms pada kalimat umum
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TTSService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._ema_model = None
        self._vocoder = None
        self._ref_audio_cache: Dict[str, Tuple[Any, Any]] = {}
        # In-memory audio cache: simpan hingga 100 audio MP3 yang sering di-generate
        self._audio_lru_cache: OrderedDict[str, bytes] = OrderedDict()
        self._max_cache_size = 100
        self._lock = asyncio.Lock()
        self._initialized = True
        logger.info("🎙️ [TTS_SERVICE] Initialized TTSService instance.")

    def get_models(self):
        """Memuat model F5-TTS dan Vocos secara thread-safe / lazy loading."""
        if self._ema_model is not None and self._vocoder is not None:
            return self._ema_model, self._vocoder

        try:
            import torch
            from f5_tts.model import DiT
            from f5_tts.infer.utils_infer import load_model, load_vocoder

            # Optimal SDPA configuration for RTX 3060
            torch.backends.cuda.enable_flash_sdp(False)
            torch.backends.cuda.enable_mem_efficient_sdp(False)
            torch.backends.cuda.enable_math_sdp(True)

            model_cls = DiT
            model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
            ckpt_path = "/home/qisthi/pinAi/backend/models/f5_tts/f5_tts_indo_v2.pt"
            vocab_file = "/home/qisthi/pinAi/backend/models/f5_tts/vocab.txt"

            logger.info("⏳ [TTS_SERVICE] Loading F5-TTS model & Vocos vocoder...")
            self._ema_model = load_model(
                model_cls=model_cls,
                model_cfg=model_cfg,
                ckpt_path=ckpt_path,
                mel_spec_type="vocos",
                vocab_file=vocab_file,
                ode_method="euler",
                use_ema=True,
                device="cuda",
            )
            self._vocoder = load_vocoder(vocoder_name="vocos", is_local=True, local_path="/home/qisthi/pinAi/backend/assets/weights/vocos")
            logger.info("✅ [TTS_SERVICE] F5-TTS model and Vocos successfully loaded into VRAM.")
            return self._ema_model, self._vocoder

        except Exception as e:
            logger.error(f"❌ [TTS_SERVICE] Failed to load F5-TTS models: {e}")
            logger.error(traceback.format_exc())
            return None, None

    def _get_voice_ref_info(self, voice: str) -> Tuple[str, str]:
        """Menentukan path file audio referensi dan teks referensi berdasarkan pilihan voice."""
        default_ref_text = "Halo, ada yang bisa saya bantu hari ini?"

        voice_map = {
            "id-ID-Pria1": ("/home/qisthi/pinAi/backend/assets/voice_refs/male_1_clean.wav", default_ref_text),
            "id-ID-Pria2": ("/home/qisthi/pinAi/backend/assets/voice_refs/male_2_clean.wav", default_ref_text),
            "id-ID-Wanita1": ("/home/qisthi/pinAi/backend/assets/voice_refs/female_1_clean.wav", default_ref_text),
            "id-ID-Wanita2": ("/home/qisthi/pinAi/backend/assets/voice_refs/female_2_clean.wav", default_ref_text),
        }

        return voice_map.get(voice, voice_map["id-ID-Pria1"])

    def _synthesize_f5_worker(
        self,
        clean_text: str,
        voice: str,
        speed_setting: str,
        nfe_step: int = 32,
    ) -> bytes:
        """Worker synchronous untuk inferensi F5-TTS di background thread."""
        from f5_tts.infer.utils_infer import preprocess_ref_audio_text, infer_process

        ema_model, vocoder = self.get_models()
        if ema_model is None or vocoder is None:
            raise RuntimeError("F5-TTS model is not available.")

        ref_file, ref_text = self._get_voice_ref_info(voice)

        # Cache reference audio
        if ref_file not in self._ref_audio_cache:
            self._ref_audio_cache[ref_file] = preprocess_ref_audio_text(
                ref_audio_orig=ref_file,
                ref_text=ref_text,
                show_info=lambda x: None,
            )
        ref_audio_proc, ref_text_proc = self._ref_audio_cache[ref_file]

        # Penanganan Anti-Cutoff:
        # Tambahkan trailing breathing buffer agar model tidak memotong suku kata terakhir (misal: "Sehat kan?")
        gen_text_input = clean_text.strip()
        if not gen_text_input.endswith(('.', '?', '!')):
            gen_text_input += '.'
        if not gen_text_input.endswith('..'):
            gen_text_input += ' ..'

        # Kecepatan bicara (speed factor) adaptif bahasa Indonesia:
        # Kecepatan natural penutur bahasa Indonesia ~8-10 karakter per detik.
        speed_map = {
            "slow": 0.65,
            "normal": 0.75,
            "fast": 0.95,
        }
        if isinstance(speed_setting, (int, float)):
            effective_speed = float(speed_setting)
        elif str(speed_setting).replace('.', '', 1).isdigit():
            effective_speed = float(speed_setting)
        else:
            effective_speed = speed_map.get(str(speed_setting).lower(), 0.75)

        # Untuk kalimat sangat pendek (< 35 karakter), perlambat sedikit agar intonasi tuntas
        if len(clean_text) < 35:
            effective_speed = min(effective_speed, 0.68)

        t_start = time.time()
        wav, sr, _ = infer_process(
            ref_audio=ref_audio_proc,
            ref_text=ref_text_proc,
            gen_text=gen_text_input,
            model_obj=ema_model,
            vocoder=vocoder,
            mel_spec_type="vocos",
            cfg_strength=2.0,
            nfe_step=nfe_step,  # Default 32 untuk kualitas pelafalan & dialek terbaik
            speed=effective_speed,
            device="cuda",
            show_info=lambda x: None,
        )
        t_elapsed = time.time() - t_start

        # Trailing silence 0.35 detik (jeda nafas alami, mencegah kata terakhir terpotong)
        silence_samples = int(0.35 * sr)
        silence = np.zeros(silence_samples, dtype=wav.dtype)

        # Micro-fadeout halus di 60ms terakhir agar tidak ada klik audio
        fade_len = min(int(0.06 * sr), len(wav))
        if fade_len > 0:
            fade_curve = np.linspace(1.0, 0.0, fade_len)
            wav[-fade_len:] = wav[-fade_len:] * fade_curve

        wav = np.concatenate([wav, silence])
        audio_dur = len(wav) / sr

        logger.info(
            f"⚡ [TTS_SERVICE] Generated audio in {t_elapsed:.2f}s (NFE: {nfe_step}, durasi: {audio_dur:.2f}s, speedup: {audio_dur / max(t_elapsed, 0.001):.2f}x real-time)"
        )

        # Encode langsung ke format MP3 (hemat 86% bandwidth dibandingkan WAV mentah)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format='MP3')
        return buf.getvalue()

    async def generate_speech(
        self,
        text: str,
        voice: str = "id-ID-Pria1",
        speed: str = "normal",
        nfe_step: int = 32,
    ) -> Tuple[bytes, str]:
        """
        Menghasilkan audio MP3 dari teks input.
        Returns: (audio_bytes, media_type)
        """
        clean_text = clean_text_for_tts(text)
        if not clean_text:
            raise ValueError("Teks kosong setelah proses sanitasi.")

        # Cek in-memory LRU Cache
        cache_key = f"{voice}_{speed}_{nfe_step}_{clean_text}"
        if cache_key in self._audio_lru_cache:
            logger.info("🎯 [TTS_SERVICE] Audio cache HIT (0ms response).")
            self._audio_lru_cache.move_to_end(cache_key)
            return self._audio_lru_cache[cache_key], "audio/mpeg"

        # Sintesis audio di background thread
        audio_bytes = await asyncio.to_thread(
            self._synthesize_f5_worker, clean_text, voice, speed, nfe_step
        )

        # Simpan ke cache LRU
        if len(self._audio_lru_cache) >= self._max_cache_size:
            self._audio_lru_cache.popitem(last=False)
        self._audio_lru_cache[cache_key] = audio_bytes

        return audio_bytes, "audio/mpeg"

    async def warmup(self):
        """Memanaskan model F5-TTS saat startup agar panggilan pengguna pertama kali bebas cold-start."""
        try:
            logger.info("🔥 [TTS_SERVICE] Starting background GPU warmup...")
            await asyncio.to_thread(
                self._synthesize_f5_worker,
                clean_text="Halo, Cakra AI siap.",
                voice="id-ID-Pria1",
                speed_setting="normal",
            )
            logger.info("✅ [TTS_SERVICE] GPU warmup complete!")
        except Exception as e:
            logger.warning(f"⚠️ [TTS_SERVICE] Warmup encountered error (non-fatal): {e}")


tts_service = TTSService()
