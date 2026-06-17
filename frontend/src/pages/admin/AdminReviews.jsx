import { useEffect, useState } from 'react';
import { adminApi } from '../../api/client';

export default function AdminReviews() {
  const [reviews, setReviews] = useState([]);
  const load = () => adminApi.reviews().then((r) => setReviews(r.data));
  useEffect(() => { load(); }, []);

  const moderate = async (id, status) => { await adminApi.moderateReview(id, status); load(); };

  return (
    <div>
      <h1 className="text-2xl font-bold">Review moderation</h1>
      <div className="mt-4 space-y-3">
        {reviews.length === 0 && <p className="text-slate-500">No reviews.</p>}
        {reviews.map((r) => (
          <div key={r.id} className="card p-4 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{r.user_name} · {'★'.repeat(r.rating)}</span>
              <span className={`badge ${r.status === 'approved' ? 'bg-green-100 text-green-700' : r.status === 'rejected' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{r.status}</span>
            </div>
            <p className="mt-1 text-slate-600">{r.comment}</p>
            {r.image_url && <img src={r.image_url} alt="" className="mt-2 h-20 w-20 rounded object-cover" />}
            <div className="mt-2 flex gap-2">
              {r.status !== 'approved' && <button onClick={() => moderate(r.id, 'approved')} className="btn-ghost text-xs">Approve</button>}
              {r.status !== 'rejected' && <button onClick={() => moderate(r.id, 'rejected')} className="btn-ghost text-xs">Reject</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
