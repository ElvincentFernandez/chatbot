"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { 
  ShieldAlert, 
  ArrowLeft, 
  UserPlus, 
  Users, 
  Trash2, 
  UploadCloud, 
  CheckCircle,
  Database,
  Sparkles,
  LayoutDashboard
} from "lucide-react";

interface User {
  id: number;
  username: string;
  password: string;
  token: string;
  role: string;
}

export default function AdminDashboard() {
  const [role, setRole] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const router = useRouter();

  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    const storedRole = localStorage.getItem("role");

    if (!storedToken || (storedRole !== "admin" && storedRole !== "superadmin")) {
      router.push("/");
    } else {
      setRole(storedRole);
      if (storedRole === "superadmin") {
        fetchUsers();
      }
    }
  }, [router]);

  const fetchUsers = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;

    setIsLoadingUsers(true);
    try {
      const res = await fetch("http://localhost:8000/api/admin/users", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      } else {
        console.error("Gagal mengambil data user");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingUsers(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setErrorMsg("");
    try {
      const res = await fetch("http://localhost:8000/api/admin/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword.trim(),
          role: newRole
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal membuat user.");
      }

      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
      fetchUsers();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleDeleteUser = async (userId: number) => {
    const token = localStorage.getItem("token");
    if (!token) return;

    if (confirm("Apakah Anda yakin ingin menghapus user ini?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/admin/users/${userId}`, {
          method: "DELETE",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (res.ok) {
          fetchUsers();
        } else {
          alert("Gagal menghapus user");
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setIsUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal upload PDF.");
      }

      setUploadStatus(`Sukses membaca '${file.name}' dan dimasukkan ke ChromaDB!`);
    } catch (err: any) {
      setUploadStatus(`Error: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-6xl mx-auto">
        
        {/* Top bar */}
        <div className="flex items-center justify-between mb-8 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => router.push("/")}
              className="p-2 bg-slate-900 rounded-lg hover:bg-slate-800 border border-slate-800 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent flex items-center gap-2">
                <LayoutDashboard className="w-6 h-6 text-indigo-400" />
                Admin Dashboard
              </h1>
              <p className="text-xs text-slate-400">
                Kelola basis pengetahuan RAG dan token akses user
              </p>
            </div>
          </div>
          <div className="text-xs px-3.5 py-1.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 font-bold capitalize">
            Role: {role}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Box 1: Knowledge Base Upload (For Admin & Superadmin) */}
          <div className="lg:col-span-1 bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-200 mb-2 flex items-center gap-2">
                <Database className="w-5 h-5 text-indigo-400" />
                RAG Document Upload
              </h2>
              <p className="text-xs text-slate-400 mb-6">
                Unggah file PDF baru ke dalam database ChromaDB untuk menambah basis pengetahuan Chatbot.
              </p>

              <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-700 hover:border-purple-500 rounded-xl p-8 cursor-pointer transition-colors bg-slate-950/40 group">
                <UploadCloud className="w-12 h-12 text-slate-500 group-hover:text-purple-400 transition-colors mb-3" />
                <span className="text-sm font-semibold text-slate-300">Pilih File PDF</span>
                <span className="text-xs text-slate-500 mt-1">Hanya format .pdf</span>
                <input 
                  type="file" 
                  accept=".pdf" 
                  className="hidden" 
                  onChange={handleFileUpload}
                  disabled={isUploading}
                />
              </label>

              {isUploading && (
                <div className="mt-4 flex items-center gap-3 p-3 bg-purple-950/20 border border-purple-500/20 rounded-xl text-purple-300 text-sm">
                  <span className="w-4 h-4 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
                  <span>Sedang memproses PDF & membuat Embeddings...</span>
                </div>
              )}

              {uploadStatus && (
                <div className={`mt-4 p-3 rounded-xl border text-sm flex gap-2 items-start ${
                  uploadStatus.startsWith("Error") 
                    ? "bg-red-500/10 border-red-500/20 text-red-300" 
                    : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                }`}>
                  {uploadStatus.startsWith("Error") ? (
                    <ShieldAlert className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  )}
                  <span>{uploadStatus}</span>
                </div>
              )}
            </div>

            <div className="mt-6 pt-6 border-t border-slate-800 text-xs text-slate-500">
              💡 **ChromaDB** akan otomatis melakukan ekstraksi halaman, memotong teks (chunking), dan membuat embedding yang dapat digunakan instan oleh model AI.
            </div>
          </div>

          {/* Box 2 & 3: User Password Management (For Superadmin Only) */}
          <div className="lg:col-span-2 space-y-6">
            
            {role !== "superadmin" ? (
              <div className="bg-slate-900/40 border border-slate-800 p-8 rounded-2xl flex flex-col items-center justify-center text-center h-full min-h-[300px]">
                <ShieldAlert className="w-12 h-12 text-slate-600 mb-3" />
                <h3 className="font-bold text-slate-400">User Management Terkunci</h3>
                <p className="text-xs text-slate-500 max-w-sm mt-1">
                  Hanya akun dengan role **Superadmin** (`super123`) yang dapat menambah, menghapus, atau mengelola akun user.
                </p>
              </div>
            ) : (
              <>
                {/* Form Tambah User */}
                <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                  <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                    <UserPlus className="w-5 h-5 text-purple-400" />
                    Tambah Akun Pengguna Baru
                  </h2>

                  <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div className="md:col-span-1">
                      <label className="block text-xs text-slate-400 mb-2 uppercase font-semibold">Username</label>
                      <input 
                        type="text"
                        placeholder="Username"
                        value={newUsername}
                        onChange={(e) => setNewUsername(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500"
                        required
                      />
                    </div>
                    <div className="md:col-span-1">
                      <label className="block text-xs text-slate-400 mb-2 uppercase font-semibold">Password</label>
                      <input 
                        type="text"
                        placeholder="Password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500"
                        required
                      />
                    </div>
                    <div className="md:col-span-1">
                      <label className="block text-xs text-slate-400 mb-2 uppercase font-semibold">Role</label>
                      <select
                        value={newRole}
                        onChange={(e) => setNewRole(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-purple-500"
                      >
                        <option value="user">User (Chat Only)</option>
                        <option value="admin">Admin (Chat + Upload PDF)</option>
                        <option value="superadmin">Superadmin (All Access)</option>
                      </select>
                    </div>
                    <div className="md:col-span-1">
                      <button
                        type="submit"
                        className="w-full py-2 bg-purple-500 hover:bg-purple-600 text-white font-semibold rounded-lg transition-colors shadow-lg shadow-purple-500/10 flex items-center justify-center gap-2"
                      >
                        <Sparkles className="w-4 h-4" />
                        Tambah
                      </button>
                    </div>
                  </form>

                  {errorMsg && (
                    <p className="text-red-400 text-xs mt-3 flex items-center gap-1.5">
                      <ShieldAlert className="w-4 h-4" /> {errorMsg}
                    </p>
                  )}
                </div>

                {/* Tabel User */}
                <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                  <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                    <Users className="w-5 h-5 text-indigo-400" />
                    Daftar Akun Pengguna
                  </h2>

                  {isLoadingUsers ? (
                    <div className="py-12 flex justify-center">
                      <span className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400">
                            <th className="py-3 px-4 font-semibold">Username</th>
                            <th className="py-3 px-4 font-semibold">Password</th>
                            <th className="py-3 px-4 font-semibold">API Token</th>
                            <th className="py-3 px-4 font-semibold">Role</th>
                            <th className="py-3 px-4 font-semibold text-right">Aksi</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/40">
                          {users.map((u) => (
                            <tr key={u.id} className="hover:bg-slate-900/30 transition-colors">
                              <td className="py-3.5 px-4 font-medium text-slate-200">{u.username}</td>
                              <td className="py-3.5 px-4 text-slate-300">{u.password}</td>
                              <td className="py-3.5 px-4 font-mono text-xs text-slate-400 truncate max-w-[150px]">{u.token}</td>
                              <td className="py-3.5 px-4">
                                <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                                  u.role === "superadmin" 
                                    ? "bg-red-500/10 text-red-400 border-red-500/20" 
                                    : u.role === "admin" 
                                      ? "bg-purple-500/10 text-purple-400 border-purple-500/20"
                                      : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                                }`}>
                                  {u.role}
                                </span>
                              </td>
                              <td className="py-3.5 px-4 text-right">
                                {u.username !== "superadmin" ? (
                                  <button
                                    onClick={() => handleDeleteUser(u.id)}
                                    className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                    title="Hapus User"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                ) : (
                                  <span className="text-xs text-slate-600 italic px-2">Protected</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            )}

          </div>

        </div>

      </div>
    </div>
  );
}
