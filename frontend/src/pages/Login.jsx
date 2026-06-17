import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const me = await login(email, password);
      navigate(['admin', 'staff'].includes(me.role) ? '/admin' : '/');
    } catch (err) { setError(err.response?.data?.detail || 'Login failed'); }
  };

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-2xl font-bold">Welcome back</h1>
      <form onSubmit={submit} className="card mt-4 space-y-3 p-6">
        <input type="email" required placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="input" />
        <input type="password" required placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} className="input" />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="btn-primary w-full">Sign in</button>
        <p className="text-center text-sm"><Link to="/forgot-password" className="text-brand-600">Forgot password?</Link></p>
        <p className="text-center text-sm text-slate-500">No account? <Link to="/register" className="text-brand-600">Register</Link></p>
        <p className="rounded bg-slate-50 p-2 text-center text-xs text-slate-400">Demo: customer@wishbox.com / customer123</p>
      </form>
    </div>
  );
}
