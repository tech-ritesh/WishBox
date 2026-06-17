import { useEffect, useState } from 'react';
import { adminApi } from '../../api/client';
import { inr } from '../../utils/format';

const NEXT = {
  requested: ['approved', 'rejected'],
  approved: ['picked_up', 'rejected'],
  picked_up: ['refunded', 'completed'],
  refunded: ['completed'],
};

export default function AdminReturns() {
  const [returns, setReturns] = useState([]);
  const load = () => adminApi.returns().then((r) => setReturns(r.data));
  useEffect(() => { load(); }, []);

  const act = async (id, status) => {
    const note = window.prompt(`Note for marking this ${status}? (optional)`) || undefined;
    await adminApi.updateReturn(id, { status, resolution_note: note });
    load();
  };

  return (
    <div>
      <h1 className="text-2xl font-bold">Returns & exchanges</h1>
      <div className="mt-4 space-y-3">
        {returns.length === 0 && <p className="text-slate-500">No return requests yet.</p>}
        {returns.map((r) => (
          <div key={r.id} className="card p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">#{r.id} · Order {r.order_id} · {r.kind}</span>
              <span className="badge bg-slate-100">{r.status}</span>
            </div>
            <p className="mt-1 text-slate-500">Reason: {r.reason} · {r.items.length} item(s)
              {Number(r.refund_amount) > 0 && <> · Refund {inr(r.refund_amount)}</>}</p>
            {r.resolution_note && <p className="text-xs text-slate-400">Note: {r.resolution_note}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              {(NEXT[r.status] || []).map((s) => (
                <button key={s} onClick={() => act(r.id, s)} className="btn-ghost text-xs">Mark {s}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
