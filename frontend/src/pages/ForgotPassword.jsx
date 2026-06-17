import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/client';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await authApi.forgotPassword(email); } finally { setSent(true); setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-bold">Forgot password</h1>
      {sent ? (
        <div className="card mt-4 p-5 text-sm">
          <p>If an account exists for <b>{email}</b>, we've sent a reset link.</p>
          <p className="mt-2 text-slate-500">
            In local/offline mode the link is printed to the backend console and visible
            in <b>Admin → Outbox</b>. Open it to set a new password.
          </p>
          <Link to="/login" className="btn-ghost mt-3 inline-block text-sm">Back to login</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="card mt-4 space-y-3 p-5">
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="Your account email" className="input" />
          <button disabled={busy} className="btn-primary w-full">{busy ? 'Sending…' : 'Send reset link'}</button>
          <Link to="/login" className="block text-center text-sm text-brand-600">Back to login</Link>
        </form>
      )}
    </div>
  );
}
