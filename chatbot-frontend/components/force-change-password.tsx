"use client";

import { useState, useEffect } from "react";
import { Lock, Eye, EyeOff, ShieldCheck, CheckCircle2, Circle, ArrowLeft } from "lucide-react";

interface ForceChangePasswordProps {
  onSuccess: () => void;
}

export function ForceChangePassword({ onSuccess }: ForceChangePasswordProps) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Validation States
  const isMinLength = newPassword.length >= 8;
  const hasUppercase = /[A-Z]/.test(newPassword);
  const hasNumber = /[0-9]/.test(newPassword);
  const hasSpecialChar = /[!@#$%^&*]/.test(newPassword);
  const isMatch = newPassword === confirmPassword && newPassword.length > 0;

  const isValid = isMinLength && hasUppercase && hasNumber && hasSpecialChar && isMatch;

  // Calculate strength percentage
  const getStrengthPercent = () => {
    let met = 0;
    if (isMinLength) met++;
    if (hasUppercase) met++;
    if (hasNumber) met++;
    if (hasSpecialChar) met++;
    return (met / 4) * 100;
  };

  const getStrengthText = () => {
    const pct = getStrengthPercent();
    if (pct <= 25) return { text: "Weak", color: "text-red-400", barColor: "bg-red-500" };
    if (pct <= 75) return { text: "Medium", color: "text-amber-400", barColor: "bg-amber-500" };
    return { text: "Strong", color: "text-emerald-400", barColor: "bg-emerald-500" };
  };

  const strength = getStrengthText();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    setIsLoading(true);
    setError("");

    const token = localStorage.getItem("token");
    if (!token) {
      setError("Sesi kadaluarsa. Silakan login kembali.");
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("http://localhost:8000/api/auth/change-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          new_password: newPassword,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Gagal mengubah password.");
      }

      localStorage.setItem("password_changed", "1");
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Terjadi kesalahan.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    localStorage.removeItem("password_changed");
    localStorage.removeItem("client_id");
    localStorage.removeItem("client_name");
    window.location.href = "/login";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl relative overflow-hidden">
        
        {/* Back arrow button at top-left */}
        <button 
          onClick={handleLogout}
          className="absolute top-6 left-6 p-2 bg-slate-950/60 hover:bg-slate-800 rounded-lg border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors z-20"
          title="Kembali ke Login"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        {/* Glow effect */}
        <div className="absolute -top-10 -left-10 w-40 h-40 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl" />

        <div className="text-center mb-6 relative z-10">
          <div className="inline-flex p-3 rounded-full bg-slate-950 border border-slate-800 mb-4 text-purple-400">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Atur Kata Sandi Baru
          </h1>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            Silakan buat kata sandi yang kuat untuk mengamankan akun Anda. Hal ini diperlukan untuk login pertama kali.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 relative z-10">
          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
              Password baru <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <input
                type={showNewPassword ? "text" : "password"}
                placeholder="Masukan password baru"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full pl-3 pr-10 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-purple-500 text-sm"
                required
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
              >
                {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Strength Bar */}
          {newPassword.length > 0 && (
            <div className="space-y-1.5">
              <div className="h-1.5 w-full bg-slate-950 rounded-full overflow-hidden">
                <div className={`h-full transition-all duration-300 ${strength.barColor}`} style={{ width: `${getStrengthPercent()}%` }} />
              </div>
              <span className={`text-[10px] font-semibold ${strength.color}`}>
                {strength.text} <span className="text-slate-500 font-normal">(Harus memenuhi persyaratan di bawah ini)</span>
              </span>
            </div>
          )}

          {/* Requirements Checkbox */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 space-y-2">
            <h3 className="text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
              Persyaratan Kata Sandi
            </h3>
            <ul className="space-y-1.5 text-[11px] text-slate-400">
              <li className="flex items-center gap-2">
                {isMinLength ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Circle className="w-3.5 h-3.5 text-slate-600" />}
                <span className={isMinLength ? "text-slate-300" : ""}>Minimal 8 karakter</span>
              </li>
              <li className="flex items-center gap-2">
                {hasUppercase ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Circle className="w-3.5 h-3.5 text-slate-600" />}
                <span className={hasUppercase ? "text-slate-300" : ""}>Satu huruf kapital</span>
              </li>
              <li className="flex items-center gap-2">
                {hasNumber ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Circle className="w-3.5 h-3.5 text-slate-600" />}
                <span className={hasNumber ? "text-slate-300" : ""}>Satu angka</span>
              </li>
              <li className="flex items-center gap-2">
                {hasSpecialChar ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Circle className="w-3.5 h-3.5 text-slate-600" />}
                <span className={hasSpecialChar ? "text-slate-300" : ""}>Satu karakter khusus (!@#$%^&*)</span>
              </li>
            </ul>
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
              Masukan password baru kembali <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <input
                type={showConfirmPassword ? "text" : "password"}
                placeholder="Masukan password anda kembali"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full pl-3 pr-10 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-purple-500 text-sm"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
              >
                {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {confirmPassword.length > 0 && !isMatch && (
              <p className="text-[10px] text-red-400 mt-1">Konfirmasi password tidak cocok.</p>
            )}
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2.5 rounded-xl text-center">{error}</p>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={!isValid || isLoading}
              className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold text-xs hover:from-purple-500 hover:to-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                "Update Password"
              )}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs transition-colors"
            >
              Batal
            </button>
          </div>
        </form>

        <div className="mt-6 pt-4 border-t border-slate-800/80 text-center relative z-10">
          <p className="text-[9px] uppercase tracking-widest text-slate-500 font-bold flex items-center justify-center gap-1">
            <Lock className="w-3 h-3 text-purple-500/60" />
            End-to-End Encrypted
          </p>
        </div>
      </div>
    </div>
  );
}
