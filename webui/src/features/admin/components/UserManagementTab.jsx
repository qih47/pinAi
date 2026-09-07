import React, { useState, useEffect, useCallback } from 'react';
import { 
  Users, 
  UserPlus, 
  RefreshCw, 
  Search, 
  Shield, 
  Building, 
  Key, 
  Trash2, 
  Edit3, 
  CheckCircle2, 
  AlertCircle, 
  X, 
  Copy, 
  Check, 
  ExternalLink,
  Lock,
  Mail,
  UserCheck,
  ChevronLeft,
  ChevronRight,
  Database,
  Eye,
  EyeOff,
  UserCog
} from 'lucide-react';
import apiClient from '../../../services/apiClient';

export const UserManagementTab = () => {
  // State Utama
  const [users, setUsers] = useState([]);
  const [statistics, setStatistics] = useState({
    total_all: 0,
    total_manual: 0,
    total_hris: 0,
    roles: { ADMIN: 0, TRAINER: 0, USER: 0 }
  });
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 15,
    total_items: 0,
    total_pages: 1
  });
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Feedback Toast
  const [toast, setToast] = useState(null);

  // Modal States
  const [showManualModal, setShowManualModal] = useState(false);
  const [showHrisModal, setShowHrisModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Target User for Edit/Action
  const [selectedUser, setSelectedUser] = useState(null);

  // Manual User Form State
  const [manualForm, setManualForm] = useState({
    npp: '',
    fullname: '',
    divisi: '',
    role: 'USER',
    password: '',
    email: ''
  });
  const [showManualPassword, setShowManualPassword] = useState(false);
  const [isSubmittingManual, setIsSubmittingManual] = useState(false);

  // HRIS Search & Import State
  const [hrisQuery, setHrisQuery] = useState('');
  const [hrisResults, setHrisResults] = useState([]);
  const [isSearchingHris, setIsSearchingHris] = useState(false);
  const [hrisRoleSelection, setHrisRoleSelection] = useState({});
  const [importingNpp, setImportingNpp] = useState(null);

  // Edit Role State
  const [targetRole, setTargetRole] = useState('USER');
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);

  // Reset Password State
  const [newPassword, setNewPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [isResettingPassword, setIsResettingPassword] = useState(false);

  // Delete State
  const [isDeleting, setIsDeleting] = useState(false);

  // Copy helper
  const [copiedNpp, setCopiedNpp] = useState(null);

  const showNotification = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchUsers = useCallback(async (page = pagination.page) => {
    setIsLoading(true);
    try {
      const res = await apiClient.get('/admin/users', {
        params: {
          page,
          page_size: pagination.page_size,
          search: searchQuery,
          role: roleFilter,
          type: typeFilter
        }
      });
      if (res.data?.status === 'success') {
        const { users: userList, pagination: pg, statistics: stats } = res.data.data;
        setUsers(userList || []);
        if (pg) setPagination(pg);
        if (stats) setStatistics(stats);
      }
    } catch (err) {
      console.error('Failed to fetch users:', err);
      showNotification(err.response?.data?.detail || 'Gagal memuat daftar pengguna.', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [pagination.page, pagination.page_size, searchQuery, roleFilter, typeFilter]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchUsers(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, roleFilter, typeFilter]);

  // Handle Tambah User Manual
  const handleCreateManualUser = async (e) => {
    e.preventDefault();
    if (!manualForm.npp.trim() || !manualForm.fullname.trim() || !manualForm.password.trim()) {
      showNotification('ID Pengguna, Nama, dan Password wajib diisi.', 'error');
      return;
    }
    if (manualForm.password.length < 6) {
      showNotification('Password minimal 6 karakter.', 'error');
      return;
    }

    setIsSubmittingManual(true);
    try {
      const res = await apiClient.post('/admin/users/manual', manualForm);
      if (res.data?.status === 'success') {
        showNotification(res.data.message || 'Pengguna berhasil ditambahkan.');
        setShowManualModal(false);
        setManualForm({
          npp: '',
          fullname: '',
          divisi: '',
          role: 'USER',
          password: '',
          email: ''
        });
        fetchUsers(1);
      }
    } catch (err) {
      console.error('Failed to create manual user:', err);
      showNotification(err.response?.data?.detail || 'Gagal menambahkan pengguna.', 'error');
    } finally {
      setIsSubmittingManual(false);
    }
  };

  // Search HRIS (Read-Only SELECT)
  const handleSearchHris = async (e) => {
    if (e) e.preventDefault();
    if (!hrisQuery.trim() || hrisQuery.trim().length < 2) {
      showNotification('Ketik minimal 2 karakter untuk mencari di HRIS.', 'error');
      return;
    }

    setIsSearchingHris(true);
    try {
      const res = await apiClient.get('/admin/users/hris-search', {
        params: { q: hrisQuery.trim(), limit: 30 }
      });
      if (res.data?.status === 'success') {
        setHrisResults(res.data.data || []);
      }
    } catch (err) {
      console.error('HRIS search error:', err);
      showNotification(err.response?.data?.detail || 'Gagal mencari personil HRIS.', 'error');
    } finally {
      setIsSearchingHris(false);
    }
  };

  // Import HRIS User
  const handleImportHris = async (npp) => {
    const chosenRole = hrisRoleSelection[npp] || 'USER';
    setImportingNpp(npp);
    try {
      const res = await apiClient.post('/admin/users/import-hris', {
        npp,
        role: chosenRole
      });
      if (res.data?.status === 'success') {
        showNotification(res.data.message || 'Karyawan berhasil disinkronkan.');
        // Update status di hasil pencarian
        setHrisResults((prev) =>
          prev.map((item) =>
            item.npp === npp ? { ...item, is_imported: true, current_role: chosenRole } : item
          )
        );
        fetchUsers();
      }
    } catch (err) {
      console.error('Import HRIS error:', err);
      showNotification(err.response?.data?.detail || 'Gagal mengimpor karyawan HRIS.', 'error');
    } finally {
      setImportingNpp(null);
    }
  };

  // Handle Update Role
  const handleUpdateRole = async () => {
    if (!selectedUser) return;
    setIsUpdatingRole(true);
    try {
      const res = await apiClient.put(`/admin/users/${selectedUser.npp}/role`, {
        role: targetRole
      });
      if (res.data?.status === 'success') {
        showNotification(res.data.message || 'Role pengguna berhasil diperbarui.');
        setShowRoleModal(false);
        fetchUsers();
      }
    } catch (err) {
      console.error('Update role error:', err);
      showNotification(err.response?.data?.detail || 'Gagal memperbarui role.', 'error');
    } finally {
      setIsUpdatingRole(false);
    }
  };

  // Handle Reset Password
  const handleResetPassword = async () => {
    if (!selectedUser || !newPassword.trim()) {
      showNotification('Password baru tidak boleh kosong.', 'error');
      return;
    }
    if (newPassword.length < 6) {
      showNotification('Password minimal 6 karakter.', 'error');
      return;
    }

    setIsResettingPassword(true);
    try {
      const res = await apiClient.put(`/admin/users/${selectedUser.npp}/password`, {
        password: newPassword.trim()
      });
      if (res.data?.status === 'success') {
        showNotification(res.data.message || 'Password berhasil di-reset.');
        setShowPasswordModal(false);
        setNewPassword('');
        fetchUsers();
      }
    } catch (err) {
      console.error('Reset password error:', err);
      showNotification(err.response?.data?.detail || 'Gagal mereset password.', 'error');
    } finally {
      setIsResettingPassword(false);
    }
  };

  // Handle Delete User
  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    setIsDeleting(true);
    try {
      const res = await apiClient.delete(`/admin/users/${selectedUser.npp}`);
      if (res.data?.status === 'success') {
        showNotification(res.data.message || 'Pengguna berhasil dihapus.');
        setShowDeleteModal(false);
        fetchUsers();
      }
    } catch (err) {
      console.error('Delete user error:', err);
      showNotification(err.response?.data?.detail || 'Gagal menghapus pengguna.', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  const copyNpp = (npp) => {
    navigator.clipboard.writeText(npp);
    setCopiedNpp(npp);
    setTimeout(() => setCopiedNpp(null), 2000);
  };

  return (
    <div className="flex flex-col gap-6 text-gray-200">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl border backdrop-blur-md transition-all duration-300 ${
          toast.type === 'error' 
            ? 'bg-red-950/90 border-red-700 text-red-200' 
            : 'bg-emerald-950/90 border-emerald-600 text-emerald-200'
        }`}>
          {toast.type === 'error' ? <AlertCircle size={20} className="text-red-400" /> : <CheckCircle2 size={20} className="text-emerald-400" />}
          <span className="text-sm font-medium">{toast.message}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-[#0E1726] to-[#0A0E1A] p-6 rounded-2xl border border-cyan-900/40 shadow-lg relative overflow-hidden">
        <div className="absolute -right-10 -bottom-10 w-48 h-48 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
        
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="p-2.5 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
              <Users size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
                User Access & Identity Governance
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-950 border border-cyan-700 text-cyan-300 font-normal">
                  RAGDB & HRIS Sync
                </span>
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Kelola hak akses pengguna CAKRA, buat akun personil non-resmi/mitra, dan sinkronkan karyawan resmi dari HRIS DB (Read-Only).
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <button
            onClick={() => setShowManualModal(true)}
            className="flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-cyan-900/30 border border-cyan-400/30 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <UserPlus size={16} />
            <span>Tambah User Non-Resmi</span>
          </button>

          <button
            onClick={() => {
              setShowHrisModal(true);
              setHrisQuery('');
              setHrisResults([]);
            }}
            className="flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-[#121B2B] hover:bg-[#1A263D] text-cyan-300 text-xs font-semibold rounded-xl border border-cyan-700/50 hover:border-cyan-500 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Database size={16} />
            <span>Cari & Sinkron HRIS</span>
          </button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#0B0F19] p-4 rounded-xl border border-gray-800 flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Total Pengguna RAGDB</span>
            <Users size={16} className="text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">{statistics.total_all || 0}</span>
            <span className="text-[11px] text-gray-500">Akun Terdaftar</span>
          </div>
        </div>

        <div className="bg-[#0B0F19] p-4 rounded-xl border border-gray-800 flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Karyawan Resmi HRIS</span>
            <Building size={16} className="text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-blue-400">{statistics.total_hris || 0}</span>
            <span className="text-[11px] text-gray-500">Synced Pindad</span>
          </div>
        </div>

        <div className="bg-[#0B0F19] p-4 rounded-xl border border-gray-800 flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>User Non-Resmi / Manual</span>
            <UserCheck size={16} className="text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-purple-400">{statistics.total_manual || 0}</span>
            <span className="text-[11px] text-gray-500">Mitra / Non-Tetap</span>
          </div>
        </div>

        <div className="bg-[#0B0F19] p-4 rounded-xl border border-gray-800 flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-center justify-between text-gray-400 text-xs">
            <span>Hak Akses Khusus</span>
            <Shield size={16} className="text-emerald-400" />
          </div>
          <div className="mt-2 flex items-center gap-3">
            <div>
              <span className="text-sm font-bold text-emerald-400">{statistics.roles?.ADMIN || 0}</span>
              <span className="text-[10px] text-gray-500 block">ADMIN</span>
            </div>
            <div className="h-6 w-px bg-gray-800" />
            <div>
              <span className="text-sm font-bold text-amber-400">{statistics.roles?.TRAINER || 0}</span>
              <span className="text-[10px] text-gray-500 block">TRAINER</span>
            </div>
            <div className="h-6 w-px bg-gray-800" />
            <div>
              <span className="text-sm font-bold text-gray-300">{statistics.roles?.USER || 0}</span>
              <span className="text-[10px] text-gray-500 block">USER</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col md:flex-row gap-3 items-center justify-between bg-[#0B0F19] p-4 rounded-xl border border-gray-800">
        <div className="flex items-center gap-3 w-full md:w-auto flex-1">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Cari NPP, nama lengkap, divisi, atau email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#121826] border border-gray-700/70 focus:border-cyan-500 rounded-lg pl-10 pr-4 py-2 text-xs text-gray-200 placeholder-gray-500 focus:outline-none transition-colors"
            />
          </div>

          <button
            onClick={() => fetchUsers(pagination.page)}
            disabled={isLoading}
            title="Refresh Data"
            className="p-2 bg-gray-800/80 hover:bg-gray-700 text-gray-300 rounded-lg border border-gray-700 transition-colors"
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin text-cyan-400' : ''} />
          </button>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 whitespace-nowrap">Filter Role:</span>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">Semua Role</option>
              <option value="ADMIN">ADMIN</option>
              <option value="TRAINER">TRAINER</option>
              <option value="USER">USER</option>
              <option value="SUPERADMIN">SUPERADMIN</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 whitespace-nowrap">Tipe Akun:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">Semua Tipe</option>
              <option value="HRIS">Karyawan HRIS</option>
              <option value="MANUAL">Non-Resmi / Manual</option>
            </select>
          </div>
        </div>
      </div>

      {/* Tabel Pengguna RAGDB */}
      <div className="bg-[#0B0F19] rounded-xl border border-gray-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-[#101624] border-b border-gray-800 text-gray-400 uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">Pengguna</th>
                <th className="py-3 px-4">NPP / ID</th>
                <th className="py-3 px-4">Unit Kerja / Divisi</th>
                <th className="py-3 px-4">Tipe Akun</th>
                <th className="py-3 px-4">Role Akses</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4 text-center">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {isLoading ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-gray-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RefreshCw size={24} className="animate-spin text-cyan-400" />
                      <span>Memuat data pengguna dari RAGDB...</span>
                    </div>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-gray-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Users size={32} className="text-gray-600" />
                      <span className="text-sm">Tidak ada data pengguna yang sesuai dengan filter.</span>
                    </div>
                  </td>
                </tr>
              ) : (
                users.map((user) => {
                  const isHris = user.account_type === 'HRIS';
                  return (
                    <tr key={user.npp} className="hover:bg-[#121826]/70 transition-colors">
                      {/* Avatar & Nama */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs uppercase border ${
                            isHris 
                              ? 'bg-blue-950/60 border-blue-600/50 text-blue-300' 
                              : 'bg-purple-950/60 border-purple-600/50 text-purple-300'
                          }`}>
                            {user.fullname?.charAt(0) || 'U'}
                          </div>
                          <div>
                            <span className="font-semibold text-gray-200 block text-xs">
                              {user.fullname}
                            </span>
                            {user.preferred_name && (
                              <span className="text-[10px] text-gray-500 block">
                                Panggilan: "{user.preferred_name}"
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* NPP / ID */}
                      <td className="py-3.5 px-4 font-mono text-gray-300">
                        <div className="flex items-center gap-2">
                          <span className="bg-[#161F30] px-2 py-0.5 rounded border border-gray-700/60 text-cyan-300">
                            {user.npp}
                          </span>
                          <button
                            onClick={() => copyNpp(user.npp)}
                            title="Salin ID"
                            className="text-gray-500 hover:text-cyan-400 transition-colors"
                          >
                            {copiedNpp === user.npp ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                          </button>
                        </div>
                      </td>

                      {/* Divisi */}
                      <td className="py-3.5 px-4 text-gray-300">
                        <div className="flex items-center gap-1.5">
                          <Building size={14} className="text-gray-500 shrink-0" />
                          <span className="truncate max-w-[200px]" title={user.divisi}>
                            {user.divisi || '-'}
                          </span>
                        </div>
                      </td>

                      {/* Tipe Akun */}
                      <td className="py-3.5 px-4">
                        {isHris ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-blue-950/80 border border-blue-700 text-blue-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                            Karyawan HRIS
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-purple-950/80 border border-purple-700 text-purple-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                            Non-Resmi / Manual
                          </span>
                        )}
                      </td>

                      {/* Role Akses */}
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                          user.role === 'ADMIN' || user.role === 'SUPERADMIN'
                            ? 'bg-emerald-950/80 border-emerald-700 text-emerald-300'
                            : user.role === 'TRAINER'
                            ? 'bg-amber-950/80 border-amber-700 text-amber-300'
                            : 'bg-gray-800 border-gray-700 text-gray-300'
                        }`}>
                          <Shield size={11} />
                          {user.role}
                        </span>
                      </td>

                      {/* Email */}
                      <td className="py-3.5 px-4 text-gray-400">
                        <div className="flex items-center gap-1.5">
                          <Mail size={13} className="text-gray-500 shrink-0" />
                          <span className="truncate max-w-[180px]" title={user.email}>
                            {user.email || '-'}
                          </span>
                        </div>
                      </td>

                      {/* Aksi */}
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => {
                              setSelectedUser(user);
                              setTargetRole(user.role || 'USER');
                              setShowRoleModal(true);
                            }}
                            title="Ubah Hak Akses Role"
                            className="p-1.5 bg-gray-800/80 hover:bg-cyan-950 text-gray-300 hover:text-cyan-400 rounded-lg border border-gray-700 hover:border-cyan-700 transition-colors"
                          >
                            <UserCog size={15} />
                          </button>

                          <button
                            onClick={() => {
                              setSelectedUser(user);
                              setNewPassword('');
                              setShowPasswordModal(true);
                            }}
                            title="Reset Password Akun"
                            className="p-1.5 bg-gray-800/80 hover:bg-amber-950 text-gray-300 hover:text-amber-400 rounded-lg border border-gray-700 hover:border-amber-700 transition-colors"
                          >
                            <Key size={15} />
                          </button>

                          <button
                            onClick={() => {
                              setSelectedUser(user);
                              setShowDeleteModal(true);
                            }}
                            title="Hapus Akun dari CAKRA"
                            className="p-1.5 bg-gray-800/80 hover:bg-red-950 text-gray-300 hover:text-red-400 rounded-lg border border-gray-700 hover:border-red-700 transition-colors"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 bg-[#101624] border-t border-gray-800 flex items-center justify-between text-xs text-gray-400">
          <div>
            Menampilkan <span className="font-semibold text-gray-200">{users.length}</span> dari{' '}
            <span className="font-semibold text-gray-200">{pagination.total_items}</span> pengguna
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchUsers(pagination.page - 1)}
              disabled={pagination.page <= 1 || isLoading}
              className="p-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            <span>
              Halaman <span className="font-semibold text-gray-200">{pagination.page}</span> dari{' '}
              <span className="font-semibold text-gray-200">{pagination.total_pages || 1}</span>
            </span>
            <button
              onClick={() => fetchUsers(pagination.page + 1)}
              disabled={pagination.page >= pagination.total_pages || isLoading}
              className="p-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MODAL 1: TAMBAH USER NON-RESMI / MANUAL                                   */}
      {/* ========================================================================= */}
      {showManualModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0B0F19] border border-cyan-800/60 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
            <div className="p-5 bg-gradient-to-r from-[#101726] to-[#0D121F] border-b border-gray-800 flex justify-between items-center">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-cyan-500/10 border border-cyan-500/30 rounded-lg text-cyan-400">
                  <UserPlus size={18} />
                </div>
                <div>
                  <h3 className="font-bold text-white text-sm">Tambah Pengguna Non-Resmi</h3>
                  <p className="text-[11px] text-gray-400">Untuk tenaga kontrak, magang, mitra, atau konsultan luar</p>
                </div>
              </div>
              <button 
                onClick={() => setShowManualModal(false)}
                className="text-gray-500 hover:text-gray-300 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateManualUser} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                    ID / NPP Non-Resmi <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="misal: EXT-001, MAGANG-01"
                    value={manualForm.npp}
                    onChange={(e) => setManualForm({ ...manualForm, npp: e.target.value })}
                    className="w-full bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500 font-mono"
                  />
                  <span className="text-[10px] text-gray-500 mt-1 block">Digunakan sebagai username saat login.</span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                    Role Hak Akses <span className="text-red-400">*</span>
                  </label>
                  <select
                    value={manualForm.role}
                    onChange={(e) => setManualForm({ ...manualForm, role: e.target.value })}
                    className="w-full bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                  >
                    <option value="USER">USER (Standar)</option>
                    <option value="TRAINER">TRAINER (Knowledge/Prompt)</option>
                    <option value="ADMIN">ADMIN (Full Dashboard)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                  Nama Lengkap <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="Nama lengkap personil..."
                  value={manualForm.fullname}
                  onChange={(e) => setManualForm({ ...manualForm, fullname: e.target.value })}
                  className="w-full bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                    Unit / Divisi / Instansi
                  </label>
                  <input
                    type="text"
                    placeholder="misal: Magang IT, Konsultan Cyber"
                    value={manualForm.divisi}
                    onChange={(e) => setManualForm({ ...manualForm, divisi: e.target.value })}
                    className="w-full bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                    Email (Opsional)
                  </label>
                  <input
                    type="email"
                    placeholder="email@instansi.com"
                    value={manualForm.email}
                    onChange={(e) => setManualForm({ ...manualForm, email: e.target.value })}
                    className="w-full bg-[#121826] border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                  Password Akun <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showManualPassword ? 'text' : 'password'}
                    required
                    minLength={6}
                    placeholder="Minimal 6 karakter..."
                    value={manualForm.password}
                    onChange={(e) => setManualForm({ ...manualForm, password: e.target.value })}
                    className="w-full bg-[#121826] border border-gray-700 rounded-lg pl-3 pr-10 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowManualPassword(!showManualPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                  >
                    {showManualPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                <span className="text-[10px] text-gray-500 mt-1 block">
                  Password langsung di-hash bcrypt dan disimpan ke RAGDB. Pengguna dapat langsung login.
                </span>
              </div>

              <div className="pt-4 border-t border-gray-800 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg transition-colors"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingManual}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs rounded-lg shadow-lg shadow-cyan-900/30 transition-all disabled:opacity-50"
                >
                  {isSubmittingManual ? 'Menyimpan...' : 'Simpan ke RAGDB'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: CARI & SINKRONISASI DARI HRIS DB (READ-ONLY SELECT)              */}
      {/* ========================================================================= */}
      {showHrisModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0B0F19] border border-cyan-800/60 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-5 bg-gradient-to-r from-[#101726] to-[#0D121F] border-b border-gray-800 flex justify-between items-center">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400">
                  <Database size={18} />
                </div>
                <div>
                  <h3 className="font-bold text-white text-sm">Pencarian & Sinkronisasi HRIS DB</h3>
                  <p className="text-[11px] text-gray-400">
                    Query MURNI SELECT ke database kepegawaian resmi PT Pindad
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setShowHrisModal(false)}
                className="text-gray-500 hover:text-gray-300 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 flex-1 overflow-y-auto space-y-4">
              {/* Info Notice */}
              <div className="p-3 bg-blue-950/40 border border-blue-800/50 rounded-xl text-xs text-blue-300 flex items-start gap-2.5">
                <Shield size={16} className="text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block">Prinsip Read-Only HRIS:</span>
                  Sistem hanya membaca data personil dari HRIS DB. Saat Anda menekan tombol "Sinkronkan", data profil disalin ke database lokal CAKRA (<span className="text-cyan-300 font-mono">ragdb</span>) tanpa pernah mengubah isi HRIS.
                </div>
              </div>

              {/* Search HRIS Form */}
              <form onSubmit={handleSearchHris} className="flex gap-2">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    type="text"
                    autoFocus
                    placeholder="Ketik NPP atau Nama Karyawan Pindad..."
                    value={hrisQuery}
                    onChange={(e) => setHrisQuery(e.target.value)}
                    className="w-full bg-[#121826] border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSearchingHris}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isSearchingHris ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
                  <span>Cari HRIS</span>
                </button>
              </form>

              {/* Hasil Pencarian HRIS */}
              <div className="space-y-2 mt-4">
                <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                  Hasil Pencarian HRIS ({hrisResults.length})
                </div>

                {isSearchingHris ? (
                  <div className="py-10 text-center text-gray-500 text-xs">
                    <RefreshCw size={20} className="animate-spin text-blue-400 mx-auto mb-2" />
                    Menghubungi HRIS Database...
                  </div>
                ) : hrisResults.length === 0 ? (
                  <div className="py-8 text-center text-gray-500 text-xs bg-[#101624] rounded-xl border border-gray-800/80">
                    Ketik nama atau NPP karyawan Pindad di atas lalu klik "Cari HRIS".
                  </div>
                ) : (
                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                    {hrisResults.map((emp) => {
                      const isImportingThis = importingNpp === emp.npp;
                      return (
                        <div
                          key={emp.npp}
                          className="flex items-center justify-between p-3 bg-[#101624] border border-gray-800 rounded-xl hover:border-gray-700 transition-colors"
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-gray-200 text-xs">{emp.nama}</span>
                              <span className="bg-[#182338] px-2 py-0.5 rounded text-[11px] font-mono text-cyan-300 border border-cyan-800/40">
                                {emp.npp}
                              </span>
                            </div>
                            <div className="text-[11px] text-gray-400 flex items-center gap-2">
                              <span>{emp.divisi}</span>
                              <span>•</span>
                              <span className="text-gray-500">{emp.email}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            {emp.is_imported ? (
                              <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-950/60 border border-emerald-700 rounded-lg text-emerald-300 text-[11px] font-semibold">
                                <CheckCircle2 size={13} />
                                <span>Sudah di CAKRA ({emp.current_role})</span>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <select
                                  value={hrisRoleSelection[emp.npp] || 'USER'}
                                  onChange={(e) =>
                                    setHrisRoleSelection({
                                      ...hrisRoleSelection,
                                      [emp.npp]: e.target.value
                                    })
                                  }
                                  className="bg-[#162032] border border-gray-700 rounded-lg px-2 py-1 text-[11px] text-gray-200 focus:outline-none focus:border-blue-500"
                                >
                                  <option value="USER">USER</option>
                                  <option value="TRAINER">TRAINER</option>
                                  <option value="ADMIN">ADMIN</option>
                                </select>

                                <button
                                  onClick={() => handleImportHris(emp.npp)}
                                  disabled={isImportingThis}
                                  className="px-3 py-1 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold text-[11px] rounded-lg transition-all shadow-md flex items-center gap-1 disabled:opacity-50"
                                >
                                  {isImportingThis ? (
                                    <RefreshCw size={12} className="animate-spin" />
                                  ) : (
                                    <UserPlus size={12} />
                                  )}
                                  <span>Sinkronkan</span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 bg-[#101624] border-t border-gray-800 flex justify-end">
              <button
                onClick={() => setShowHrisModal(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg transition-colors"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 3: UBAH ROLE PENGGUNA                                               */}
      {/* ========================================================================= */}
      {showRoleModal && selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0B0F19] border border-cyan-800/60 rounded-2xl w-full max-w-md shadow-2xl p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3">
              <div className="flex items-center gap-2">
                <Shield size={18} className="text-cyan-400" />
                <h3 className="font-bold text-white text-sm">Ubah Hak Akses Role</h3>
              </div>
              <button onClick={() => setShowRoleModal(false)} className="text-gray-500 hover:text-gray-300">
                <X size={18} />
              </button>
            </div>

            <div className="bg-[#121826] p-3 rounded-xl border border-gray-800 text-xs space-y-1">
              <div className="text-gray-400">Pengguna: <span className="text-white font-semibold">{selectedUser.fullname}</span></div>
              <div className="text-gray-400">NPP / ID: <span className="text-cyan-300 font-mono">{selectedUser.npp}</span></div>
              <div className="text-gray-400">Role Saat Ini: <span className="text-amber-400 font-bold">{selectedUser.role}</span></div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-2">
                Pilih Role Baru:
              </label>
              <div className="space-y-2">
                {[
                  { key: 'USER', label: 'USER (Pengguna Biasa)', desc: 'Akses chat standar, mode RAG, dan asisten.' },
                  { key: 'TRAINER', label: 'TRAINER (Knowledge & Tuning)', desc: 'Dapat menambahkan dokumen, fine-tuning prompt, dan evaluasi QA.' },
                  { key: 'ADMIN', label: 'ADMIN (Administrator)', desc: 'Akses penuh ke dashboard analytics, audit logs, dan manajemen pengguna.' },
                  { key: 'SUPERADMIN', label: 'SUPERADMIN', desc: 'Hak akses tingkat tertinggi tanpa batasan.' }
                ].map((r) => (
                  <label
                    key={r.key}
                    className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                      targetRole === r.key 
                        ? 'bg-cyan-950/40 border-cyan-600 text-cyan-200' 
                        : 'bg-[#101624] border-gray-800 text-gray-400 hover:border-gray-700'
                    }`}
                  >
                    <input
                      type="radio"
                      name="roleOption"
                      value={r.key}
                      checked={targetRole === r.key}
                      onChange={(e) => setTargetRole(e.target.value)}
                      className="mt-0.5 text-cyan-500 focus:ring-cyan-500"
                    />
                    <div>
                      <span className="font-semibold text-xs text-white block">{r.label}</span>
                      <span className="text-[11px] text-gray-500 block mt-0.5">{r.desc}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-gray-800 flex justify-end gap-3">
              <button
                onClick={() => setShowRoleModal(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg transition-colors"
              >
                Batal
              </button>
              <button
                onClick={handleUpdateRole}
                disabled={isUpdatingRole}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs rounded-lg transition-all disabled:opacity-50"
              >
                {isUpdatingRole ? 'Menyimpan...' : 'Perbarui Role'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 4: RESET PASSWORD AKUN                                              */}
      {/* ========================================================================= */}
      {showPasswordModal && selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0B0F19] border border-amber-800/60 rounded-2xl w-full max-w-md shadow-2xl p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3">
              <div className="flex items-center gap-2">
                <Key size={18} className="text-amber-400" />
                <h3 className="font-bold text-white text-sm">Reset Password Pengguna</h3>
              </div>
              <button onClick={() => setShowPasswordModal(false)} className="text-gray-500 hover:text-gray-300">
                <X size={18} />
              </button>
            </div>

            <div className="bg-[#121826] p-3 rounded-xl border border-gray-800 text-xs space-y-1">
              <div className="text-gray-400">Pengguna: <span className="text-white font-semibold">{selectedUser.fullname}</span></div>
              <div className="text-gray-400">NPP / ID: <span className="text-cyan-300 font-mono">{selectedUser.npp}</span></div>
              <div className="text-gray-400">Tipe: <span className="text-purple-300 font-semibold">{selectedUser.account_type}</span></div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                Password Baru:
              </label>
              <div className="relative">
                <input
                  type={showNewPassword ? 'text' : 'password'}
                  required
                  minLength={6}
                  placeholder="Masukkan password baru minimal 6 karakter..."
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-[#121826] border border-gray-700 rounded-lg pl-3 pr-10 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                >
                  {showNewPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <span className="text-[10px] text-gray-500 mt-1 block">
                Reset password akan menghapus sesi login aktif pengguna sehingga harus login ulang dengan password ini.
              </span>
            </div>

            <div className="pt-3 border-t border-gray-800 flex justify-end gap-3">
              <button
                onClick={() => setShowPasswordModal(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg transition-colors"
              >
                Batal
              </button>
              <button
                onClick={handleResetPassword}
                disabled={isResettingPassword}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs rounded-lg transition-all disabled:opacity-50"
              >
                {isResettingPassword ? 'Mereset...' : 'Reset Password'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 5: KONFIRMASI HAPUS PENGGUNA                                        */}
      {/* ========================================================================= */}
      {showDeleteModal && selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#0B0F19] border border-red-800/60 rounded-2xl w-full max-w-md shadow-2xl p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3">
              <div className="flex items-center gap-2 text-red-400">
                <AlertCircle size={18} />
                <h3 className="font-bold text-white text-sm">Hapus Pengguna dari CAKRA</h3>
              </div>
              <button onClick={() => setShowDeleteModal(false)} className="text-gray-500 hover:text-gray-300">
                <X size={18} />
              </button>
            </div>

            <div className="text-xs text-gray-300 space-y-2">
              <p>
                Apakah Anda yakin ingin menghapus akun pengguna{' '}
                <strong className="text-white">{selectedUser.fullname}</strong> ({selectedUser.npp})?
              </p>
              <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-xl text-[11px] text-red-300 space-y-1">
                <span className="font-bold block">Catatan Integritas Data:</span>
                <p>• Akun dan seluruh sesi aktif akan dihapus dari sistem CAKRA (<span className="font-mono">ragdb</span>).</p>
                <p>• Jika pengguna adalah karyawan resmi Pindad, data di <span className="font-mono">HRIS DB</span> <strong>TETAP AMAN</strong> dan tidak tersentuh.</p>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-800 flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg transition-colors"
              >
                Batal
              </button>
              <button
                onClick={handleDeleteUser}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-semibold text-xs rounded-lg transition-all disabled:opacity-50"
              >
                {isDeleting ? 'Menghapus...' : 'Ya, Hapus Akun'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default UserManagementTab;
