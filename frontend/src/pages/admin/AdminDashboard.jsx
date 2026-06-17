import { useEffect, useState } from 'react';
import { IndianRupee, ShoppingBag, Package, Users, AlertTriangle } from 'lucide-react';
import { adminApi } from '../../api/client';
import { inr, STATUS_COLORS, prettyStatus } from '../../utils/format';
import { Spinner } from '../../components/Layout';

const TONES = {
  brand: 'bg-brand-100 text-brand-600',
  amber: 'bg-amber-100 text-amber-600',
};

function Stat({ icon: Icon, label, value, tone = 'brand' }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <div className={`rounded-lg p-2 ${TONES[tone]}`}><Icon /></div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-xl font-bold">{value}</p>
      </div>
    </div>
  );
}

function Bars({ data, fmt = (v) => v }) {
  const max = Math.max(...Object.values(data), 1);
  const entries = Object.entries(data);
  if (entries.length === 0) return <p className="text-sm text-slate-400">No data yet.</p>;
  return (
    <div className="space-y-2">
      {entries.map(([k, v]) => (
        <div key={k}>
          <div className="flex justify-between text-xs text-slate-500"><span>{k}</span><span>{fmt(v)}</span></div>
          <div className="h-2 rounded bg-slate-100"><div className="h-2 rounded bg-brand-500" style={{ width: `${(v / max) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  useEffect(() => { adminApi.analytics().then((r) => setData(r.data)); }, []);
  if (!data) return <Spinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat icon={IndianRupee} label="Revenue" value={inr(data.total_revenue)} />
        <Stat icon={ShoppingBag} label="Orders" value={data.total_orders} />
        <Stat icon={Package} label="Products" value={data.total_products} />
        <Stat icon={Users} label="Customers" value={data.total_users} />
        <Stat icon={AlertTriangle} label="Low stock" value={data.low_stock_count} tone="amber" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="mb-3 font-bold">Sales by category</h2>
          <Bars data={data.sales_by_category} fmt={inr} />
        </section>
        <section className="card p-5">
          <h2 className="mb-3 font-bold">Monthly sales</h2>
          <Bars data={data.monthly_sales} fmt={inr} />
        </section>
        <section className="card p-5">
          <h2 className="mb-3 font-bold">Orders by status</h2>
          <Bars data={data.orders_by_status} />
        </section>
        <section className="card p-5">
          <h2 className="mb-3 font-bold">Recent orders</h2>
          <div className="space-y-2">
            {data.recent_orders.map((o) => (
              <div key={o.id} className="flex items-center justify-between text-sm">
                <span>{o.order_number}</span>
                <span className={`badge ${STATUS_COLORS[o.status]}`}>{prettyStatus(o.status)}</span>
                <span className="font-semibold">{inr(o.total_amount)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
