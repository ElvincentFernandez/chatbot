"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { 
  ShieldAlert, 
  ArrowLeft, 
  Users, 
  Trash2, 
  Sparkles, 
  LayoutDashboard,
  Building2,
  Lock,
  Eye,
  EyeOff,
  Pencil,
  Plus,
  Database,
  UploadCloud,
  CheckCircle,
  Calendar,
  FileText
} from "lucide-react";
import { ForceChangePassword } from "@/components/force-change-password";

interface User {
  id: number;
  username: string;
  password: string;
  token: string;
  role: string;
  client_id: number | null;
  client_name: string | null;
  client_type: string | null;
  email: string | null;
  password_changed: number;
  is_active?: number;
  last_login?: string;
  client_api_key?: string;
}

interface Client {
  id: number;
  name: string;
  type: string;
  api_key?: string;
}

interface Document {
  id: number;
  client_id: number;
  filename: string;
  doc_type: string;
  upload_date: string;
}

export default function AdminDashboard() {
  const [role, setRole] = useState<string | null>(null);
  const [currentUsername, setCurrentUsername] = useState<string>("");
  const [userClientId, setUserClientId] = useState<number | null>(null);
  const [userClientName, setUserClientName] = useState<string | null>(null);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  
  const [clients, setClients] = useState<Client[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  
  // Form states
  const [usernameInput, setUsernameInput] = useState("");
  const [instansiNameInput, setInstansiNameInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [clientTypeInput, setClientTypeInput] = useState("Campus");
  const [showPassword, setShowPassword] = useState(false);
  
  // Edit mode states
  const [isEditMode, setIsEditMode] = useState(false);
  const [editUserId, setEditUserId] = useState<number | null>(null);
  
  const [errorMsg, setErrorMsg] = useState("");
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    const storedRole = localStorage.getItem("role");
    const uname = localStorage.getItem("username") || "Admin";
    const uClientId = localStorage.getItem("client_id");
    const uClientName = localStorage.getItem("client_name");
    const pwChanged = localStorage.getItem("password_changed");

    if (!token || (storedRole !== "admin" && storedRole !== "admin_client")) {
      router.push("/");
      return;
    }

    setRole(storedRole);
    setCurrentUsername(uname);
    
    if (storedRole === "admin_client" && pwChanged === "0") {
      setMustChangePassword(true);
    }

    if (uClientId) {
      const cid = parseInt(uClientId);
      setUserClientId(cid);
      setUserClientName(uClientName);
      
      if (storedRole === "admin_client") {
        fetchDocuments(token, cid);
      }
    }

    // Initial fetch
    fetchClients(token);
    if (storedRole === "admin") {
      fetchUsers(token);
    }
  }, [router]);

  const fetchClients = async (token: string) => {
    try {
      const res = await fetch("http://localhost:8000/api/clients", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchUsers = async (token: string) => {
    setIsLoadingUsers(true);
    try {
      const res = await fetch("http://localhost:8000/api/admin/users", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingUsers(false);
    }
  };

  const fetchDocuments = async (token: string, clientId: number) => {
    setIsLoadingDocs(true);
    try {
      const res = await fetch(`http://localhost:8000/api/documents/${clientId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  // Client Instansi CRUD
  const handleCreateClientInstansi = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameInput.trim() || !instansiNameInput.trim() || !emailInput.trim() || !passwordInput.trim()) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setErrorMsg("");
    try {
      const res = await fetch("http://localhost:8000/api/admin/client-instansi", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          username: usernameInput.trim(),
          instansi_name: instansiNameInput.trim(),
          email: emailInput.trim(),
          password: passwordInput.trim(),
          client_type: clientTypeInput
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal membuat client instansi.");
      }

      setUsernameInput("");
      setInstansiNameInput("");
      setEmailInput("");
      setPasswordInput("");
      setClientTypeInput("Campus");
      fetchUsers(token);
      fetchClients(token);
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleUpdateClientInstansi = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editUserId || !usernameInput.trim() || !instansiNameInput.trim()) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setErrorMsg("");
    try {
      const res = await fetch(`http://localhost:8000/api/admin/client-instansi/${editUserId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          username: usernameInput.trim(),
          instansi_name: instansiNameInput.trim(),
          client_type: clientTypeInput,
          password: passwordInput.trim() || null
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal memperbarui client instansi.");
      }

      setUsernameInput("");
      setInstansiNameInput("");
      setEmailInput("");
      setPasswordInput("");
      setClientTypeInput("Campus");
      setIsEditMode(false);
      setEditUserId(null);
      fetchUsers(token);
      fetchClients(token);
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleDeleteClientInstansi = async (userId: number, clientId: number | null) => {
    const token = localStorage.getItem("token");
    if (!token) return;

    if (confirm("Menghapus akun pengguna juga akan menghapus client instansi yang terikat beserta seluruh data riwayatnya. Yakin?")) {
      try {
        if (clientId) {
          const resClient = await fetch(`http://localhost:8000/api/clients/${clientId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
          });
          if (!resClient.ok) {
            console.error("Gagal menghapus instansi client.");
          }
        }

        const resUser = await fetch(`http://localhost:8000/api/admin/users/${userId}`, {
          method: "DELETE",
          headers: { "Authorization": `Bearer ${token}` }
        });

        if (resUser.ok) {
          fetchUsers(token);
          fetchClients(token);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleGenerateApiKey = async (clientId: number) => {
    const token = localStorage.getItem("token");
    if (!token) return;

    if (confirm("Apakah Anda yakin ingin me-reset API Key instansi ini? Widget lama tidak akan bisa diakses sampai API Key diperbarui di website client.")) {
      try {
        const res = await fetch(`http://localhost:8000/api/admin/clients/${clientId}/generate-api-key`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          if (role === "admin") {
            fetchUsers(token);
          }
          fetchClients(token);
        } else {
          const err = await res.json();
          alert(err.detail || "Gagal generate API Key.");
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !userClientId) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setIsUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`http://localhost:8000/api/upload?client_id=${userClientId}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal upload PDF.");
      }

      setUploadStatus(`Sukses membaca '${file.name}' dan dimasukkan ke ChromaDB!`);
      fetchDocuments(token, userClientId);
    } catch (err: any) {
      setUploadStatus(`Error: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: number) => {
    const token = localStorage.getItem("token");
    if (!token || !userClientId) return;

    if (confirm("Apakah Anda yakin ingin menghapus dokumen RAG ini?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/documents/${docId}`, {
          method: "DELETE",
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          fetchDocuments(token, userClientId);
        } else {
          const err = await res.json();
          alert(err.detail || "Gagal menghapus dokumen.");
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const startEdit = (user: User) => {
    setIsEditMode(true);
    setEditUserId(user.id);
    setUsernameInput(user.username);
    setInstansiNameInput(user.client_name || "");
    setClientTypeInput(user.client_type || "Campus");
    setEmailInput(user.email || "");
    setPasswordInput("");
    setErrorMsg("");
  };

  const cancelEdit = () => {
    setIsEditMode(false);
    setEditUserId(null);
    setUsernameInput("");
    setInstansiNameInput("");
    setEmailInput("");
    setPasswordInput("");
    setClientTypeInput("Campus");
    setErrorMsg("");
  };

  const clientUsers = users.filter(u => u.role === "admin_client");

  if (mustChangePassword) {
    return <ForceChangePassword onSuccess={() => setMustChangePassword(false)} />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header Dashboard */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-900 pb-6">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => router.push("/")}
              className="p-2 bg-slate-900 rounded-lg hover:bg-slate-800 border border-slate-800 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent flex items-center gap-2">
                <LayoutDashboard className="w-6 h-6 text-indigo-400" />
                RAGChat Admin Dashboard
              </h1>
              <p className="text-xs text-slate-400">
                {role === "admin_client" 
                  ? `Panel unggah berkas pengetahuan RAG untuk instansi ${userClientName}`
                  : "Kelola data client instansi, akun pengguna, dan konfigurasi sistem"
                }
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-xs px-3.5 py-1.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 font-bold capitalize">
              Role: {role === "admin_client" ? `Admin - ${userClientName}` : role}
            </div>
            <div className="text-xs text-slate-400">
              Hi, <span className="font-semibold text-slate-200">{currentUsername}</span>
            </div>
          </div>
        </div>

        {role === "admin_client" ? (
          /* ========================================== */
          /* RAG LAYOUT (FOR ADMIN CLIENT)              */
          /* ========================================== */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* COLUMN 1: Upload Data RAG */}
            <div className="lg:col-span-1">
              <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl space-y-4">
                <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                  <Database className="w-5 h-5 text-purple-400" />
                  Upload Data RAG
                </h2>
                <p className="text-xs text-slate-400">
                  Unggah file PDF saja untuk basis pengetahuan client. Data akan otomatis di-vektorisasi per client.
                </p>

                {/* Target Client Input (Disabled/Read-only) */}
                <div>
                  <div className="w-full px-3 py-2.5 bg-indigo-950/20 border border-indigo-500/20 rounded-lg text-indigo-300 text-xs font-semibold">
                    Target: {userClientName}
                  </div>
                </div>

                {/* Accepted format badge */}
                <div className="rounded-lg border border-purple-500/20 bg-purple-500/10 px-3 py-2 text-xs text-purple-200">
                  Format yang diterima: <span className="font-semibold">PDF</span>
                </div>

                {/* File Dropzone */}
                <label className={`flex flex-col items-center justify-center border-2 border-dashed border-slate-700 hover:border-purple-500 rounded-xl p-8 cursor-pointer transition-colors bg-slate-950/40 group ${isUploading ? "pointer-events-none opacity-40" : ""}`}>
                  <UploadCloud className="w-10 h-10 text-slate-500 group-hover:text-purple-400 transition-colors mb-2 animate-bounce" />
                  <span className="text-xs font-semibold text-slate-300">Pilih File PDF</span>
                  <input
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={handleFileUpload}
                    disabled={isUploading}
                  />
                </label>

                {/* Upload Status */}
                {isUploading && (
                  <div className="flex items-center gap-3 p-3 bg-purple-950/20 border border-purple-500/20 rounded-xl text-purple-300 text-xs">
                    <span className="w-4 h-4 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
                    <span>Sedang memproses &amp; mengekstrak data...</span>
                  </div>
                )}

                {uploadStatus && (
                  <div className={`p-3 rounded-xl border text-xs flex gap-2 items-start ${
                    uploadStatus.startsWith("Error") 
                      ? "bg-red-500/10 border-red-500/20 text-red-300" 
                      : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                  }`}>
                    {uploadStatus.startsWith("Error") ? (
                      <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                    ) : (
                      <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    )}
                    <span>{uploadStatus}</span>
                  </div>
                )}
              </div>

              {/* Card API Key & Simulator */}
              <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl space-y-4 mt-6">
                <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-indigo-400" />
                  Konfigurasi Widget & API Key
                </h2>
                <p className="text-xs text-slate-400">
                  Gunakan API Key ini untuk menghubungkan widget chatbot live di website Anda.
                </p>

                {(() => {
                  const currentClientData = clients.find(c => c.id === userClientId);
                  if (!currentClientData) return <p className="text-xs text-slate-500 italic">Memuat data instansi...</p>;
                  
                  return (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">API Key Anda</label>
                        <code className="block bg-slate-950 px-3 py-2 rounded-lg text-purple-400 border border-slate-800 select-all font-mono text-xs truncate w-full">
                          {currentClientData.api_key || "Belum di-generate"}
                        </code>
                      </div>

                      <div className="flex flex-wrap gap-2 pt-2">
                        <button
                          onClick={() => {
                            if (currentClientData.api_key) {
                              navigator.clipboard.writeText(currentClientData.api_key);
                              alert("API Key disalin ke clipboard!");
                            }
                          }}
                          className="flex-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold transition-all text-center"
                        >
                          Salin Key
                        </button>
                        
                        <button
                          onClick={() => handleGenerateApiKey(userClientId!)}
                          className="flex-1 px-3 py-2 bg-purple-600/10 hover:bg-purple-600/20 text-purple-400 border border-purple-500/20 rounded-lg text-xs font-bold transition-all text-center"
                        >
                          Reset Key
                        </button>
                      </div>

                      <div className="border-t border-slate-800/80 pt-4">
                        <a
                          href={`/livechat?api_key=${currentClientData.api_key}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block w-full py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white font-bold text-xs rounded-xl transition-all text-center shadow-lg shadow-indigo-500/10"
                        >
                          Uji di Simulator Livechat 🚀
                        </a>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* COLUMN 2 & 3: Informasi Data RAG Table */}
            <div className="lg:col-span-2">
              <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl space-y-4">
                <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-400" />
                  Informasi Data RAG
                </h2>

                {isLoadingDocs ? (
                  <div className="py-12 flex justify-center">
                    <span className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                  </div>
                ) : documents.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 text-xs">
                          <th className="py-3 px-4 font-semibold">Tipe</th>
                          <th className="py-3 px-4 font-semibold">Nama File</th>
                          <th className="py-3 px-4 font-semibold">Tanggal Upload</th>
                          <th className="py-3 px-4 font-semibold text-right">Aksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40 text-xs">
                        {documents.map((d) => (
                          <tr key={d.id} className="hover:bg-slate-900/30 transition-colors">
                            <td className="py-3 px-4">
                              <span className="flex items-center gap-1.5">
                                <FileText className="w-4 h-4 text-red-500" />
                                <span className="font-bold text-slate-300">{d.doc_type}</span>
                              </span>
                            </td>
                            <td className="py-3 px-4 font-medium text-slate-200 max-w-[240px] truncate" title={d.filename}>
                              {d.filename}
                            </td>
                            <td className="py-3 px-4 text-slate-400">
                              <span className="flex items-center gap-1.5">
                                <Calendar className="w-3.5 h-3.5 text-slate-500" />
                                {d.upload_date}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <button
                                onClick={() => handleDeleteDocument(d.id)}
                                className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                title="Hapus Dokumen RAG"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="py-12 text-center text-slate-500 italic text-sm">
                    Belum ada dokumen RAG terdaftar. Silakan unggah file PDF baru di sebelah kiri.
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* ========================================== */
          /* ADMIN LAYOUT (CLIENT INSTANSI MANAGEMENT)  */
          /* ========================================== */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* COLUMN 1: Form (Tambah / Edit Client Instansi) */}
            <div className="lg:col-span-1">
              {isEditMode ? (
                /* EDIT CLIENT INSTANSI */
                <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl space-y-4">
                  <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <button 
                      type="button"
                      onClick={cancelEdit}
                      className="p-1 hover:bg-slate-800 rounded transition-colors mr-1"
                      title="Kembali ke Tambah Client"
                    >
                      <ArrowLeft className="w-4 h-4 text-slate-400 hover:text-slate-200" />
                    </button>
                    <Building2 className="w-5 h-5 text-purple-400" />
                    Edit Client Instansi
                  </h2>
                  <form onSubmit={handleUpdateClientInstansi} className="space-y-4">
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Nama Instansi</label>
                      <input 
                        type="text" 
                        placeholder="Universitas Gunadarma" 
                        value={instansiNameInput}
                        onChange={(e) => setInstansiNameInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Username</label>
                      <input 
                        type="text" 
                        placeholder="Masukkan nama lengkap.." 
                        value={usernameInput}
                        onChange={(e) => setUsernameInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Pilih Jenis Client</label>
                      <select
                        value={clientTypeInput}
                        onChange={(e) => setClientTypeInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-purple-500 text-sm"
                      >
                        <option value="Campus">Campus</option>
                        <option value="Bank">Bank</option>
                        <option value="General">General</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Masukan password</label>
                      <div className="relative">
                        <input 
                          type={showPassword ? "text" : "password"} 
                          placeholder="Masukkan password anda.." 
                          value={passwordInput}
                          onChange={(e) => setPasswordInput(e.target.value)}
                          className="w-full pl-3 pr-10 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
                        >
                          {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                      <p className="text-[10px] text-slate-500 mt-1">Kosongkan jika tidak ingin mengubah password.</p>
                    </div>
                    
                    {errorMsg && (
                      <p className="text-red-400 text-xs mt-2">{errorMsg}</p>
                    )}

                    <div className="flex gap-3 pt-2">
                      <button 
                        type="submit" 
                        className="flex-1 py-2.5 bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white font-semibold rounded-lg text-xs transition-all flex items-center justify-center gap-1.5"
                      >
                        Simpan Perubahan
                      </button>
                      <button 
                        type="button" 
                        onClick={cancelEdit}
                        className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg text-xs transition-colors"
                      >
                        Batal
                      </button>
                    </div>
                  </form>
                </div>
              ) : (
                /* TAMBAH CLIENT INSTANSI */
                <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl space-y-4">
                  <h2 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-indigo-400" />
                    Tambah Client Instansi
                  </h2>
                  <form onSubmit={handleCreateClientInstansi} className="space-y-4">
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Username</label>
                      <input 
                        type="text" 
                        placeholder="Masukkan nama lengkap.." 
                        value={usernameInput}
                        onChange={(e) => setUsernameInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Nama Instansi</label>
                      <input 
                        type="text" 
                        placeholder="Masukkan nama instansi..." 
                        value={instansiNameInput}
                        onChange={(e) => setInstansiNameInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Email Aktif</label>
                      <input 
                        type="email" 
                        placeholder="Masukkan email anda.." 
                        value={emailInput}
                        onChange={(e) => setEmailInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Password</label>
                      <div className="relative">
                        <input 
                          type={showPassword ? "text" : "password"} 
                          placeholder="Masukkan password" 
                          value={passwordInput}
                          onChange={(e) => setPasswordInput(e.target.value)}
                          className="w-full pl-3 pr-10 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-sm"
                          required
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
                        >
                          {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Pilih Jenis Client</label>
                      <select
                        value={clientTypeInput}
                        onChange={(e) => setClientTypeInput(e.target.value)}
                        className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500 text-sm"
                      >
                        <option value="" disabled>Jenis client</option>
                        <option value="Campus">Campus</option>
                        <option value="Bank">Bank</option>
                        <option value="General">General</option>
                      </select>
                    </div>

                    {errorMsg && (
                      <p className="text-red-400 text-xs mt-2">{errorMsg}</p>
                    )}

                    <button 
                      type="submit" 
                      className="w-full py-2.5 bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white font-semibold rounded-lg text-xs transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-purple-500/20"
                    >
                      Buat akun
                    </button>
                  </form>
                </div>
              )}
            </div>

            {/* COLUMN 2 & 3: Daftar Akun Pengguna */}
            <div className="lg:col-span-2 space-y-6">
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
                        <tr className="border-b border-slate-800 text-slate-400 text-xs">
                          <th className="py-3 px-4 font-semibold">Nama</th>
                          <th className="py-3 px-4 font-semibold">Email</th>
                          <th className="py-3 px-4 font-semibold">Instansi</th>
                          <th className="py-3 px-4 font-semibold">Jenis</th>
                          <th className="py-3 px-4 font-semibold">Status</th>
                          <th className="py-3 px-4 font-semibold text-right">Aksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40 text-xs">
                        {clientUsers.map((u) => (
                          <tr key={u.id} className="hover:bg-slate-900/30 transition-colors">
                            <td className="py-3 px-4 font-medium text-slate-200">{u.username}</td>
                            <td className="py-3 px-4 text-slate-400">{u.email || "-"}</td>
                            <td className="py-3 px-4">
                              {u.client_name ? (
                                <span className="text-slate-300 font-semibold">{u.client_name}</span>
                              ) : (
                                <span className="text-slate-500 italic">Tidak Ada</span>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <span className="text-slate-400">{u.client_type || "-"}</span>
                            </td>
                            <td className="py-3 px-4">
                              {u.is_active === 0 ? (
                                <span className="text-red-400 font-medium bg-red-500/10 px-2 py-0.5 rounded-full border border-red-500/20 text-[10px]">Inactive</span>
                              ) : (
                                <span className="text-emerald-400 font-medium bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 text-[10px]">Active</span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              <div className="flex justify-end gap-1.5">
                                <button
                                  onClick={() => startEdit(u)}
                                  className="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded transition-colors"
                                  title="Edit Client Instansi"
                                >
                                  <Pencil className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteClientInstansi(u.id, u.client_id)}
                                  className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                  title="Hapus Client Instansi"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {clientUsers.length === 0 && (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 italic">
                              Belum ada akun pengguna terdaftar.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                    
                    {/* Pagination Footer */}
                    <div className="flex items-center justify-between border-t border-slate-800/60 mt-4 pt-4 text-[10px] text-slate-400">
                      <div>
                        Menampilkan 1 hingga {clientUsers.length} dari {clientUsers.length} entri
                      </div>
                      <div className="flex items-center gap-1">
                        <button disabled className="px-3 py-1 bg-slate-900 border border-slate-800 rounded opacity-50 cursor-not-allowed">
                          Sebelum
                        </button>
                        <button className="px-3 py-1 bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 rounded font-bold">
                          1
                        </button>
                        <button disabled className="px-3 py-1 bg-slate-900 border border-slate-800 rounded opacity-50 cursor-not-allowed">
                          Selanjutnya
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
