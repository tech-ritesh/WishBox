import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ordersApi } from '../api/client';
import { inr, STATUS_COLORS, prettyStatus } from '../utils/format';
import { Spinner } from '../components/Layout';

export default function Orders() {
  const [orders, setOrders] = useState(null);
  useEffect(() => { ordersApi.list().then((r) => setOrders(r.data)); }, []);
  if (!orders) return <Spinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold">My Orders</h1>
      {orders.length === 0 ? <p className="mt-6 text-slate-400">No orders yet.</p> : (
        <div className="mt-4 space-y-3">
          {orders.map((o) => (
            <Link key={o.id} to={`/orders/${o.order_number}`} className="card flex items-center justify-between p-4 hover:border-brand-300">
              <div>
                <p className="font-semibold">{o.order_number}</p>
                <p className="text-sm text-slate-500">{new Date(o.created_at).toLocaleDateString()} · {o.items.length} item(s)</p>
              </div>
              <div className="text-right">
                <span className={`badge ${STATUS_COLORS[o.status]}`}>{prettyStatus(o.status)}</span>
                <p className="mt-1 font-bold">{inr(o.total_amount)}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
