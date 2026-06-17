import { useEffect, useState } from 'react';
import { adminApi } from '../../api/client';
import { inr, STATUS_COLORS, prettyStatus } from '../../utils/format';
import { Spinner } from '../../components/Layout';

const STATUSES = ['pending', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered', 'cancelled', 'refunded'];

export default function AdminOrders() {
  const [orders, setOrders] = useState(null);
  const load = () => adminApi.orders().then((r) => setOrders(r.data));
  useEffect(() => { load(); }, []);

  const update = async (id, field, value) => {
    await adminApi.updateOrder(id, { [field]: value });
    load();
  };

  if (!orders) return <Spinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold">Orders</h1>
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr><th className="p-3">Order</th><th className="p-3">Customer</th><th className="p-3">Total</th><th className="p-3">Payment</th><th className="p-3">Status</th></tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-t border-slate-100">
                <td className="p-3 font-medium">{o.order_number}<div className="text-xs text-slate-400">{new Date(o.created_at).toLocaleDateString()}</div></td>
                <td className="p-3">{o.recipient_name}</td>
                <td className="p-3">{inr(o.total_amount)}</td>
                <td className="p-3"><span className="badge bg-slate-100 text-slate-600">{o.payment_status}</span></td>
                <td className="p-3">
                  <select value={o.status} onChange={(e) => update(o.id, 'status', e.target.value)}
                    className={`rounded-lg border-0 px-2 py-1 text-xs font-semibold ${STATUS_COLORS[o.status]}`}>
                    {STATUSES.map((s) => <option key={s} value={s}>{prettyStatus(s)}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
