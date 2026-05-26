import { API_PREFIX, apiPost } from "../apiClient";

export async function verifySession(token) {
  return fetch(`${API_PREFIX}/verify-session?token=${token}`);
}

export async function login(username, password) {
  return apiPost("/api/login", { username, password });
}

export async function logout(token) {
  return apiPost("/api/logout", { token });
}
