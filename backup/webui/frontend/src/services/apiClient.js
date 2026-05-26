import { API_BASE, API_PREFIX } from "./config";

export async function apiGet(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { ...options, method: "GET" });
  return res;
}

export async function apiPost(path, body, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const isFormData = body instanceof FormData;
  const res = await fetch(url, {
    ...options,
    method: "POST",
    headers: isFormData
      ? options.headers
      : { "Content-Type": "application/json", ...options.headers },
    body: isFormData ? body : JSON.stringify(body),
  });
  return res;
}

export async function apiPostStream(path, body, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  return fetch(url, {
    ...options,
    method: "POST",
    headers: { "Content-Type": "application/json", ...options.headers },
    body: JSON.stringify(body),
  });
}

export { API_BASE, API_PREFIX };
