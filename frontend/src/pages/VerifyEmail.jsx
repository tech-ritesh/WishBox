import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/client';

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [state, setState] = useState('working'); // working | ok | error

  useEffect(() => {
    if (!token) { setState('error'); return; }
    authApi.confirmVerifyEmail(token).then(() => setState('ok')).catch(() => setState('error'));
  }, [token]);

  return (
    <div className="mx-auto max-w-md text-center">
      <h1 className="text-2xl font-bold">Email verification</h1>
      <div className="card mt-4 p-6">
        {state === 'working' && <p>Verifying…</p>}
        {state === 'ok' && <p className="text-green-600">✓ Your email is verified. Thank you!</p>}
        {state === 'error' && <p className="text-red-500">This link is invalid or has expired.</p>}
        <Link to="/account" className="btn-ghost mt-4 inline-block text-sm">Go to account</Link>
      </div>
    </div>
  );
}
