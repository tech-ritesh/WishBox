import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/client';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const navigate = useNavigate();
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr('');
    try {
      const { data } = await authApi.resetPassword(token, pw);
      setMsg(data.detail);
      setTimeout(() => navigate('/login'), 1500);
    } catch (e2) {
      setErr(e2.response?.data?.detail || 'Could not reset password');
    } finally { setBusy(false); }
  };

  if (!token) return <p className="text-center text-slate-500">Missing reset token.</p>;

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-bold">Set a new password</h1>
      <form onSubmit={submit} className="card mt-4 space-y-3 p-5">
        <input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)}
          placeholder="New password (min 8 chars)" className="input" />
        {err && <p className="text-sm text-red-500">{err}</p>}
        {msg && <p className="text-sm text-green-600">{msg}</p>}
        <button disabled={busy} className="btn-primary w-full">{busy ? 'Saving…' : 'Update password'}</button>
        <Link to="/login" className="block text-center text-sm text-brand-600">Back to login</Link>
      </form>
    </div>
  );
}
