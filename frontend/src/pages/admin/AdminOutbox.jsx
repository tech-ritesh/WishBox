import { useEffect, useState } from 'react';
import { adminApi } from '../../api/client';

export default function AdminOutbox() {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = () => adminApi.outbox().then((r) => setMessages(r.data));
  useEffect(() => { load(); }, []);

  const runTick = async () => {
    setBusy(true);
    try { await adminApi.runWorkerTick(); await load(); } finally { setBusy(false); }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Outbox (email / SMS)</h1>
        <button onClick={runTick} disabled={busy} className="btn-primary text-sm">
          {busy ? 'Running…' : 'Run worker tick'}
        </button>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Offline mode prints messages to the backend console and marks them sent. Add SMTP/Twilio creds to send for real.
      </p>
      <div className="mt-4 space-y-2">
        {messages.length === 0 && <p className="text-slate-500">Outbox is empty.</p>}
        {messages.map((m) => (
          <div key={m.id} className="card p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">{m.channel} → {m.to_address}</span>
              <span className={`badge ${m.status === 'sent' ? 'bg-green-100 text-green-700' : m.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{m.status}</span>
            </div>
            {m.subject && <p className="text-slate-700">{m.subject}</p>}
            <p className="whitespace-pre-wrap text-xs text-slate-500">{m.body}</p>
            {m.error && <p className="text-xs text-red-500">Error: {m.error}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
