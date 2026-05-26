import { API_PREFIX } from "../apiClient";

const LEARNING = `${API_PREFIX}/learning`;

export async function fetchJenisDokumen() {
  return fetch(`${LEARNING}/jenis_dokumen`);
}

export async function prosesCrop(formData) {
  return fetch(`${LEARNING}/proses_crop`, { method: "POST", body: formData });
}

export async function prosesOcr() {
  return fetch(`${LEARNING}/proses_ocr`, { method: "POST" });
}

export async function getLatestOcrText() {
  return fetch(`${LEARNING}/get_latest_ocr_text`);
}

export async function saveEditedOcr(content) {
  return fetch(`${LEARNING}/save_edited_ocr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function uploadDocument(formData) {
  return fetch(`${LEARNING}/upload`, { method: "POST", body: formData });
}

export async function debugChunk(jenis, content) {
  return fetch(`${LEARNING}/debug_chunk/${jenis}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}
