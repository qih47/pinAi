import apiClient from '../apiClient';

/**
 * Mengambil seluruh tugas Nextcloud Deck yang di-assign ke pengguna yang login.
 * @param {number|null} boardId - Opsional filter per board ID
 */
export async function fetchMyDeckTasks(boardId = null) {
  const params = boardId ? { board_id: boardId } : {};
  const response = await apiClient.get('/deck/my-tasks', { params });
  return response.data;
}

/**
 * Mengambil daftar board Nextcloud Deck pengguna
 */
export async function fetchDeckBoards() {
  const response = await apiClient.get('/deck/boards');
  return response.data;
}

/**
 * Mengambil stack dan kartu dari board tertentu
 * @param {number} boardId
 */
export async function fetchBoardStacks(boardId) {
  const response = await apiClient.get(`/deck/boards/${boardId}/stacks`);
  return response.data;
}
