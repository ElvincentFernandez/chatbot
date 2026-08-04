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
  LayoutDashboard,
  Building2,
  School,
  Landmark,
  FileText,
  Plus,
  Calendar
} from "lucide-react";

interface User {
  id: number;
  username: string;
  password: string;
  token: string;
  role: string;
  client_id: number | null;
  client_name: string | null;
}

interface Client {
  id: number;
  name: string;
  type: string;
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
  const [userClientId, setUserClientId] = useState<number | null>(null);
  const [userClientName, setUserClientName] = useState<string | null>(null);
  
  const [clients, setClients] = useState<Client[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  
  // Scopes and selection
  const [selectedClientId, setSelectedClientId] = useState<number | string>("");
  
  // Client Form state
  const [newClientName, setNewClientName] = useState("");
  const [newClientType, setNewClientType] = useState("Perbankan");
  
  // User Form state
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [newUserClientId, setNewUserClientId] = useState<number | string>("");

  // Document Upload state
  const [selectedDocType] = useState("PDF");
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [clientErrorMsg, setClientErrorMsg] = useState("");

  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [isLoadingClients, setIsLoadingClients] = useState(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);

  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    const storedRole = localStorage.getItem("role");
    const uClientId = localStorage.getItem("client_id");
    const uClientName = localStorage.getItem("client_name");

    if (!token || (storedRole !== "admin" && storedRole !== "superadmin" && storedRole !== "admin_client")) {
      router.push("/");
      return;
    }

    setRole(storedRole);
    if (uClientId) {
      const cid = parseInt(uClientId);
      setUserClientId(cid);
      setUserClientName(uClientName);
      setSelectedClientId(cid); // Locked to client
    }

    // Initial fetches
    fetchClients(token);
    if (storedRole === "superadmin" || storedRole === "admin") {
      fetchUsers(token);
    }
  }, [router]);

  // Fetch docs when client selection changes
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token && selectedClientId) {
      fetchDocuments(token, parseInt(selectedClientId.toString()));
    } else {
      setDocuments([]);
    }
  }, [selectedClientId]);

  const fetchClients = async (token: string) => {
    setIsLoadingClients(true);
    try {
      const res = await fetch("http://localhost:8000/api/clients", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
        // Default select first client for superadmin
        if (!userClientId && data.length > 0 && !selectedClientId) {
          setSelectedClientId(data[0].id);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingClients(false);
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

  // Client CRUD
  const handleCreateClient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClientName.trim()) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setClientErrorMsg("");
    try {
      const res = await fetch("http://localhost:8000/api/clients", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          name: newClientName.trim(),
          type: newClientType
        })
      });

      if (!res.ok) {
        const err = await res.json();
        let errMsg = "Gagal membuat client.";
        if (Array.isArray(err.detail)) {
          errMsg = err.detail.map((e: any) => `${e.loc.join(".")}: ${e.msg}`).join(", ");
        } else if (typeof err.detail === "string") {
          errMsg = err.detail;
        }
        throw new Error(errMsg);
      }

      setNewClientName("");
      fetchClients(token);
    } catch (err: any) {
      setClientErrorMsg(err.message);
    }
  };

  const handleDeleteClient = async (clientId: number) => {
    const token = localStorage.getItem("token");
    if (!token) return;

    if (confirm("Menghapus client akan menghapus semua user terikat, sesi chat, dan database vektor client ini. Yakin?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/clients/${clientId}`, {
          method: "DELETE",
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          fetchClients(token);
          if (storedRole === "superadmin" || storedRole === "admin") {
            fetchUsers(token);
          }
          if (selectedClientId === clientId) {
            setSelectedClientId("");
          }
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  // User CRUD
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setErrorMsg("");
    const clientIdParam = newUserClientId === "" ? null : parseInt(newUserClientId.toString());

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
          role: newRole,
          client_id: clientIdParam
        })
      });

      if (!res.ok) {
        const err = await res.json();
        let errMsg = "Gagal membuat user.";
        if (Array.isArray(err.detail)) {
          errMsg = err.detail.map((e: any) => `${e.loc.join(".")}: ${e.msg}`).join(", ");
        } else if (typeof err.detail === "string") {
          errMsg = err.detail;
        }
        throw new Error(errMsg);
      }

      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
      setNewUserClientId("");
      fetchUsers(token);
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
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          fetchUsers(token);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  // Document management (Upload / Delete)
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedClientId) return;

    const token = localStorage.getItem("token");
    if (!token) return;

    setIsUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`http://localhost:8000/api/upload?client_id=${selectedClientId}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal upload PDF.");
      }

      setUploadStatus(`Sukses membaca '${file.name}' dan dimasukkan ke ChromaDB!`);
      fetchDocuments(token, parseInt(selectedClientId.toString()));
    } catch (err: any) {
      setUploadStatus(`Error: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: number) => {
    const token = localStorage.getItem("token");
    if (!token || !selectedClientId) return;

    if (confirm("Apakah Anda yakin ingin menghapus dokumen ini dari RAG?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/documents/${docId}`, {
          method: "DELETE",
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          fetchDocuments(token, parseInt(selectedClientId.toString()));
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const getClientIcon = (type: string) => {
    switch (type) {
      case "Perbankan": return <Landmark className="w-4 h-4 text-indigo-400" />;
      case "Kampus": return <School className="w-4 h-4 text-purple-400" />;
      default: return <Building2 className="w-4 h-4 text-cyan-400" />;
    }
  };

  const getDocIcon = (type: string) => {
    return <FileText className="w-5 h-5 text-red-400" />;
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
                Kelola data client, dokumen RAG (PDF/Gambar/Video), dan akun user
              </p>
            </div>
          </div>
          <div className="text-xs px-3.5 py-1.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 font-bold capitalize">
            Role: {role === "admin_client" ? `Admin - ${userClientName}` : role}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* COLUMN 1: Client & RAG Document Upload */}
          <div className="space-y-6 lg:col-span-1">
            
            {/* 1.1 Client Management (Superadmin Only) */}
            {(role === "superadmin" || role === "admin") && (
              <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-indigo-400" />
                  Tambah Client Instansi
                </h2>
                <form onSubmit={handleCreateClient} className="space-y-3">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Nama Client</label>
                    <input 
                      type="text" 
                      placeholder="cth: BANK DKI, Gunadarma" 
                      value={newClientName}
                      onChange={(e) => setNewClientName(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-sm"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Jenis Client</label>
                    <select
                      value={newClientType}
                      onChange={(e) => setNewClientType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-indigo-500 text-sm"
                    >
                      <option value="Perbankan">Perbankan</option>
                      <option value="Kampus">Kampus</option>
                      <option value="Umum">Umum</option>
                    </select>
                  </div>
                  <button 
                    type="submit" 
                    className="w-full py-2 bg-indigo-500 hover:bg-indigo-600 text-white font-semibold rounded-lg text-sm transition-colors flex items-center justify-center gap-1"
                  >
                    <Plus className="w-4 h-4" /> Tambah Client
                  </button>
                  {clientErrorMsg && (
                    <p className="text-red-400 text-xs mt-2">{clientErrorMsg}</p>
                  )}
                </form>
              </div>
            )}

            {/* 1.2 RAG Document Upload (All Admins) */}
            <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
              <h2 className="text-lg font-bold text-slate-200 mb-2 flex items-center gap-2">
                <Database className="w-5 h-5 text-purple-400" />
                Upload Data RAG
              </h2>
              <p className="text-xs text-slate-400 mb-4">
                Unggah file PDF saja untuk basis pengetahuan client. Data akan otomatis di-vektorisasi per client.
              </p>

              {/* Client Selector (Only if Global Admin) */}
              {!userClientId ? (
                <div className="mb-4">
                  <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Pilih Client Target</label>
                  <select
                    value={selectedClientId}
                    onChange={(e) => setSelectedClientId(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-purple-500 text-sm"
                  >
                    <option value="" disabled>-- Pilih Client --</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>{c.name} ({c.type})</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="mb-4 px-3 py-2 bg-indigo-950/20 border border-indigo-500/20 rounded-lg text-xs text-indigo-300">
                  Target: <strong>{userClientName}</strong>
                </div>
              )}

              <div className="mb-4 rounded-lg border border-purple-500/20 bg-purple-500/10 px-3 py-2 text-xs text-purple-200">
                Format yang diterima: <span className="font-semibold">PDF</span>
              </div>

              <label className={`flex flex-col items-center justify-center border-2 border-dashed border-slate-700 hover:border-purple-500 rounded-xl p-6 cursor-pointer transition-colors bg-slate-950/40 group ${!selectedClientId ? "pointer-events-none opacity-40" : ""}`}>
                <UploadCloud className="w-10 h-10 text-slate-500 group-hover:text-purple-400 transition-colors mb-2" />
                <span className="text-xs font-semibold text-slate-300">Pilih File PDF</span>
                <input
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={handleFileUpload}
                  disabled={isUploading || !selectedClientId}
                />
              </label>

              {isUploading && (
                <div className="mt-4 flex items-center gap-3 p-3 bg-purple-950/20 border border-purple-500/20 rounded-xl text-purple-300 text-xs">
                  <span className="w-4 h-4 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
                  <span>Sedang memproses & mengekstrak data...</span>
                </div>
              )}

              {uploadStatus && (
                <div className={`mt-4 p-3 rounded-xl border text-xs flex gap-2 items-start ${
                  uploadStatus.startsWith("Error") 
                    ? "bg-red-500/10 border-red-500/20 text-red-300" 
                    : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                }`}>
                  {uploadStatus.startsWith("Error") ? (
                    <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  )}
                  <span>{uploadStatus}</span>
                </div>
              )}
            </div>

          </div>

          {/* COLUMN 2 & 3: Database Tables & Details */}
          <div className="lg:col-span-2 space-y-6">

            {/* 2.1 RAG Documents List (Informasi Data) */}
            <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
              <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                Informasi Data RAG
              </h2>

              {!selectedClientId ? (
                <p className="text-sm text-slate-500 italic py-6 text-center">Silakan pilih client untuk melihat daftar data RAG.</p>
              ) : isLoadingDocs ? (
                <div className="py-12 flex justify-center">
                  <span className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                </div>
              ) : documents.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-xs">
                        <th className="py-2.5 px-4 font-semibold">Tipe</th>
                        <th className="py-2.5 px-4 font-semibold">Nama File</th>
                        <th className="py-2.5 px-4 font-semibold">Tanggal Upload</th>
                        <th className="py-2.5 px-4 font-semibold text-right">Aksi</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/40">
                      {documents.map((d) => (
                        <tr key={d.id} className="hover:bg-slate-900/30 transition-colors text-xs">
                          <td className="py-3 px-4">
                            <span className="flex items-center gap-1.5">
                              {getDocIcon(d.doc_type)}
                              <span className="font-bold text-slate-300">{d.doc_type}</span>
                            </span>
                          </td>
                          <td className="py-3 px-4 font-medium text-slate-200 max-w-[200px] truncate" title={d.filename}>{d.filename}</td>
                          <td className="py-3 px-4 text-slate-400 flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5 text-slate-500" />
                            {d.upload_date}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={() => handleDeleteDocument(d.id)}
                              className="p-1 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                              title="Hapus Dokumen RAG"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-500 italic py-6 text-center">Belum ada data RAG yang diunggah untuk client ini.</p>
              )}
            </div>

            {/* 2.2 Client List (Superadmin/Admin Only) */}
            {(role === "superadmin" || role === "admin") && (
              <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-indigo-400" />
                  Daftar Client Instansi
                </h2>
                {isLoadingClients ? (
                  <div className="py-8 flex justify-center">
                    <span className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {clients.map((c) => (
                      <div key={c.id} className="p-4 bg-slate-950/60 border border-slate-850 rounded-xl flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-slate-900 rounded-lg">
                            {getClientIcon(c.type)}
                          </div>
                          <div>
                            <h4 className="font-bold text-slate-200 text-sm">{c.name}</h4>
                            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">{c.type}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteClient(c.id)}
                          className="p-1 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 2.3 User Token / Account Management (Superadmin Only) */}
            {(role === "superadmin" || role === "admin") && (
              <>
                {/* Form Tambah User */}
                <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                  <h2 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                    <UserPlus className="w-5 h-5 text-purple-400" />
                    Tambah Akun Pengguna Baru
                  </h2>

                  <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1 uppercase font-semibold">Username</label>
                      <input 
                        type="text"
                        placeholder="Username"
                        value={newUsername}
                        onChange={(e) => setNewUsername(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1 uppercase font-semibold">Password</label>
                      <input 
                        type="text"
                        placeholder="Password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1 uppercase font-semibold">Role</label>
                      <select
                        value={newRole}
                        onChange={(e) => setNewRole(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-purple-500 text-sm"
                      >
                        <option value="user">User (Chat Only)</option>
                        <option value="admin">Admin (Global)</option>
                        <option value="admin_client">Admin Client (Local)</option>
                        <option value="superadmin">Superadmin</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1 uppercase font-semibold">Client</label>
                      <select
                        value={newUserClientId}
                        onChange={(e) => setNewUserClientId(e.target.value)}
                        disabled={newRole !== "admin_client" && newRole !== "user"}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-purple-500 text-sm disabled:opacity-40"
                      >
                        <option value="">Global / Tanpa Client</option>
                        {clients.map(c => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <button
                        type="submit"
                        className="w-full py-2 bg-purple-500 hover:bg-purple-600 text-white font-semibold rounded-lg transition-colors shadow-lg text-sm flex items-center justify-center gap-1"
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
                          <tr className="border-b border-slate-800 text-slate-400 text-xs">
                            <th className="py-3 px-4 font-semibold">Username</th>
                            <th className="py-3 px-4 font-semibold">Password</th>
                            <th className="py-3 px-4 font-semibold">Client Terikat</th>
                            <th className="py-3 px-4 font-semibold">Role</th>
                            <th className="py-3 px-4 font-semibold text-right">Aksi</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/40 text-xs">
                          {users.map((u) => (
                            <tr key={u.id} className="hover:bg-slate-900/30 transition-colors">
                              <td className="py-3 px-4 font-medium text-slate-200">{u.username}</td>
                              <td className="py-3 px-4 text-slate-400">{u.password}</td>
                              <td className="py-3 px-4">
                                {u.client_name ? (
                                  <span className="text-indigo-400 font-semibold">{u.client_name}</span>
                                ) : (
                                  <span className="text-slate-500 italic">Global / Tidak Ada</span>
                                )}
                              </td>
                              <td className="py-3 px-4">
                                <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-semibold border ${
                                  u.role === "superadmin" 
                                    ? "bg-red-500/10 text-red-400 border-red-500/20" 
                                    : u.role === "admin" 
                                      ? "bg-purple-500/10 text-purple-400 border-purple-500/20"
                                      : u.role === "admin_client"
                                        ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                                        : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                                }`}>
                                  {u.role}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-right">
                                {u.username !== "superadmin" && u.username !== "admin" ? (
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
