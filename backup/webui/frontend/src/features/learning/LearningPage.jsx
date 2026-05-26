import React, {useState, useEffect, useRef} from "react";
import Swal from "sweetalert2";

import { API_PREFIX as API_BASE } from "@/services/config";

const LearningPage = () => {
    const [file, setFile] = useState(null);
    const [namaFile, setNamaFile] = useState("");
    const [formData, setFormData] = useState({
        judul_dokumen: "",
        nomor_dokumen: "",
        jenis_dokumen: "",
        tanggal_dokumen: "",
        tempat_dokumen: ""
    });

    const [jenisDokumenList, setJenisDokumenList] = useState([]);
    const [ocrText, setOcrText] = useState("");
    const [originalText, setOriginalText] = useState("");
    const [logs, setLogs] = useState(["<span class='text-blue-400 font-bold'>🪄 Log Proses:</span><br>📄 Siap untuk mengunggah dokumen...<br>"]);
    const [btnSubmitDisabled, setBtnSubmitDisabled] = useState(true);
    const [isProcessing, setIsProcessing] = useState(false);

    const logBoxRef = useRef(null);

    // =================================================================
    // EFFECTS
    // =================================================================
    useEffect(() => {
        fetch(`${API_BASE}/learning/jenis_dokumen`).then((res) => res.json()).then((data) => setJenisDokumenList(data)).catch((err) => appendLog(`<span class='text-red-500'>❌ Gagal ambil jenis dokumen: ${
            err.message
        }</span>`));
    }, []);

    useEffect(() => {
        if (logBoxRef.current) {
            logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
        }
    }, [logs]);

    useEffect(() => {
        const {
            judul_dokumen,
            nomor_dokumen,
            jenis_dokumen,
            tanggal_dokumen,
            tempat_dokumen
        } = formData;
        const allFilled = [
            judul_dokumen,
            nomor_dokumen,
            jenis_dokumen,
            tanggal_dokumen,
            tempat_dokumen
        ].every((val) => val && val.trim() !== "");
        setBtnSubmitDisabled(! allFilled);
    }, [formData]);

    const appendLog = (message, showTime = true, isProgress = false) => {
        setLogs((prev) => {
            const cleanMessage = message.replace(/\n/g, "");
            const timeStamp = showTime ? `[${
                new Date().toLocaleTimeString()
            }] ` : "";
            const newEntry = `${timeStamp}${cleanMessage}`;

            // Jika pesan mengandung "Done!", kita paksa cari baris "Preparing" sebelumnya untuk ditimpa
            const isDoneMessage = message.includes("Done!");

            if (isProgress || isDoneMessage) { // Cari baris terakhir yang ada indikator progress-nya
                const lastIndex = prev.findLastIndex(l => l.includes("🤖") || l.includes("Preparing") || l.includes("Analyzing"));

                if (lastIndex !== -1) {
                    const updated = [...prev];
                    updated[lastIndex] = newEntry; // Timpa baris "Preparing..." dengan "Done!"
                    return updated;
                }
            }

            return [
                ...prev,
                newEntry
            ];
        });
    };

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setNamaFile(selectedFile.name);
            appendLog(`📄 <span class='text-green-400'>${
                selectedFile.name
            }</span> siap diproses.<br>`);
        }
    };

    const handleInputChange = (e) => {
        const {name, value} = e.target;
        setFormData((prev) => ({
            ...prev,
            [name]: value
        }));
    };

    // =================================================================
    // CORE LOGIC
    // =================================================================
    const handleProsesDoc = async () => {
        if (!file) {
            appendLog("<span class='text-red-400'>❌ Tidak ada file dipilih.</span><br>");
            return;
        }

        appendLog(`🚀 Memulai proses dokumen: ${
            file.name
        }...<br>`);
        setIsProcessing(true);

        const data = new FormData();
        data.append("file", file);

        try {
            // ==========================================
            // 1. PROSES CROP (STREAMING LOG)
            // ==========================================
            appendLog("✂️ Memotong margin dokumen PDF...<br>");

            const response = await fetch(`${API_BASE}/learning/proses_crop`, {
                method: "POST",
                body: data
            });

            if (! response.ok) 
                throw new Error("Gagal menghubungi server untuk proses crop.");
            


            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const {value, done} = await reader.read();
                if (done) 
                    break;
                


                const chunk = decoder.decode(value, {stream: true});
                const lines = chunk.split("\n").filter(l => l.trim() !== "");

                lines.forEach(line => {
                    if (line.startsWith("PROGRESS:")) { // Hilangkan prefix "PROGRESS:" dan timpa baris sebelumnya
                        appendLog(`📄 ${
                            line.replace("PROGRESS:", "")
                        }`, false, true);
                    } else { // Baris header "===" jangan dikasih jam
                        const useTime = !line.includes("=");
                        appendLog(line, useTime, false);
                    }
                });
            }

            // ==========================================
            // 2. PROSES OCR (STREAMING LOG) - BIAR REALTIME ASU
            // ==========================================
            appendLog("🚀 Memulai proses OCR VLM (Qwen3-VL)...<br>");

            try {
                const ocrResponse = await fetch(`${API_BASE}/learning/proses_ocr`, {method: "POST"});

                if (! ocrResponse.ok) 
                    throw new Error("Gagal koneksi ke server OCR.");
                


                const reader = ocrResponse.body.getReader();
                const decoder = new TextDecoder();
                let buffer = ""; // Penampung potongan data

                while (true) {
                    const {value, done} = await reader.read();
                    if (done) 
                        break;
                    


                    // Dekode chunk biner jadi teks
                    buffer += decoder.decode(value, {stream: true});

                    // Pisahin per baris (\n) karena backend kirim JSON per baris
                    let lines = buffer.split("\n");

                    // Simpan sisa baris yang belum lengkap balik ke buffer
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (line.trim() === "") 
                            continue;
                        


                        try {
                            const data = JSON.parse(line);
                            const msg = data.message;

                            // Tampilkan log secara realtime
                            if (msg.includes("PROGRESS:")) { // Pake flag isProgress (true) biar baris ditimpa (misal hitung mundur)
                                appendLog(`🤖 ${
                                    msg.replace("PROGRESS:", "")
                                }`, false, true);
                            } else {
                                const useTime = ! msg.includes("=");
                                appendLog(msg, useTime, false);
                            }
                        } catch (e) {
                            console.error("Gagal parse chunk JSON:", line);
                        }
                    }
                }
            } catch (err) {
                appendLog(`<span class='text-red-500'>❌ Error OCR: ${
                    err.message
                }</span><br>`);
                setIsProcessing(false);
                return; // Stop kalau OCR gagal
            }

            // ==========================================
            // 3. AMBIL HASIL TEKS AKHIR
            // ==========================================
            appendLog("📥 Mengambil hasil file .txt terbaru...<br>");
            const textRes = await fetch(`${API_BASE}/learning/get_latest_ocr_text`);
            const textData = await textRes.json();

            if (textRes.ok) {
                setOcrText(textData.content);
                setOriginalText(textData.content);
                appendLog(`✅ Berhasil muat: ${
                    textData.filename
                }<br>`);
            }

        } catch (err) {
            appendLog(`<span class='text-red-500'>❌ Error: ${
                err.message
            }</span><br>`);
        } finally {
            setIsProcessing(false);
        }
    };
    const handleFinalSubmit = async (e) => {
        e.preventDefault();
        setIsProcessing(true);
        appendLog("🚀 Mengunggah dokumen ke database...<br>");

        const finalFormData = new FormData();
        finalFormData.append("file", file);
        Object.keys(formData).forEach(key => finalFormData.append(key, formData[key]));
        finalFormData.append("ocr_text", ocrText);

        try {
            const res = await fetch(`${API_BASE}/learning/upload`, {
                method: "POST",
                body: finalFormData
            });
            const data = await res.json();
            if (data.status === "success") {
                Swal.fire("Berhasil!", "Dokumen masuk database.", "success");
                appendLog("<span class='text-green-400 font-bold'>✅ Selesai! Dokumen siap digunakan.</span><br>");
            }
        } catch (err) {
            appendLog(`❌ Gagal: ${
                err.message
            }<br>`);
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-900 text-slate-200 p-4 md:p-8 font-sans">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <header className="flex items-center gap-4 bg-slate-800/50 p-6 rounded-2xl border border-slate-700 shadow-xl">
                    <div className="bg-blue-600 p-3 rounded-xl shadow-lg shadow-blue-500/30">
                        <span className="text-2xl">🧠</span>
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">Cakra AI</h1>
                        <p className="text-slate-400 text-sm italic">Learning Management System Cakra</p>
                    </div>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

                    {/* Form Utama */}
                    <div className="lg:col-span-7 bg-slate-800 border border-slate-700 p-6 rounded-2xl shadow-lg">
                        <form onSubmit={handleFinalSubmit}
                            className="space-y-4">

                            <div className="group">
                                <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Pilih Dokumen (PDF)</label>
                                <input type="file" accept=".pdf"
                                    onChange={handleFileChange}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer"/>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Judul Dokumen</label>
                                    <input type="text" name="judul_dokumen"
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none transition-all"/>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Nomor Dokumen</label>
                                    <input type="text" name="nomor_dokumen"
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none transition-all"/>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Jenis</label>
                                    <select name="jenis_dokumen"
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none">
                                        <option value="">-- Pilih --</option>
                                        {
                                        jenisDokumenList.map((jd) => <option key={
                                                jd.id
                                            }
                                            value={
                                                jd.id
                                        }>
                                            {
                                            jd.nama
                                        }</option>)
                                    } </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Tanggal</label>
                                    <input type="date" name="tanggal_dokumen"
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"/>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Tempat</label>
                                    <input type="text" name="tempat_dokumen"
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"/>
                                </div>
                            </div>

                            <div className="flex gap-4 pt-4">
                                <button type="button"
                                    onClick={handleProsesDoc}
                                    disabled={isProcessing}
                                    className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl shadow-lg transition-all disabled:opacity-50">
                                    🚀 {
                                    isProcessing ? "Processing..." : "Proses Dokumen"
                                } </button>
                                <button type="submit"
                                    disabled={
                                        btnSubmitDisabled || isProcessing
                                    }
                                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl shadow-lg transition-all disabled:opacity-50">
                                    💾 {
                                    isProcessing ? "Loading..." : "Proses Parsing"
                                } </button>
                            </div>
                        </form>
                    </div>

                    {/* Terminal Logs */}
                    <div className="lg:col-span-5 flex flex-col h-[500px] bg-black border border-slate-700 rounded-2xl overflow-hidden shadow-2xl">
                        <div className="bg-slate-800 px-4 py-2 border-b border-slate-700 flex items-center justify-between">
                            <span className="text-[10px] font-mono font-bold text-blue-400 uppercase tracking-widest">System Monitor</span>
                            <div className="flex gap-1.5">
                                <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50"></div>
                                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
                                <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50"></div>
                            </div>
                        </div>
                        <div ref={logBoxRef}
                            className="p-4 font-mono text-[13px] overflow-y-auto flex-1 leading-relaxed custom-scrollbar"
                            dangerouslySetInnerHTML={
                                {__html: logs.join("<br>")}
                            }/>
                    </div>
                </div>

                {/* OCR Area */}
                <div className="bg-slate-800 border border-slate-700 p-6 rounded-2xl">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-lg font-bold flex items-center gap-2">
                            <span>📄</span>
                            Hasil OCR (Teks Mentah)
                        </h2>
                        {
                        ocrText !== originalText && (
                            <button onClick={
                                    () => {}
                                }
                                className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-4 py-2 rounded-lg font-bold transition-all">
                                💾 Simpan Perubahan
                            </button>
                        )
                    } </div>
                    <textarea value={ocrText}
                        onChange={
                            (e) => setOcrText(e.target.value)
                        }
                        className="w-full h-96 bg-slate-900 border border-slate-700 rounded-xl p-4 font-mono text-sm focus:ring-2 focus:ring-blue-500 outline-none text-slate-300 custom-scrollbar"
                        placeholder="Hasil pembacaan dokumen akan muncul di sini..."></textarea>
                </div>
            </div>
        </div>
    );
};

export default LearningPage;
