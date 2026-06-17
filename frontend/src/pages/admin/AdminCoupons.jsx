import { useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { adminApi } from '../../api/client';
import { inr } from '../../utils/format';
import { Spinner } from '../../components/Layout';

const EMPTY = { code: '', description: '', discount_type: 'percentage', discount_value: '', max_discount: '', min_order_value: '', per_user_limit: '' };

export default function AdminCoupons() {
  const [coupons, setCoupons] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');

  const load = () => adminApi.coupons().then((r) => setCoupons(r.data));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await adminApi.createCoupon({
        code: form.code.toUpperCase(), description: form.description,
        discount_type: form.discount_type, discount_value: Number(form.discount_value),
        max_discount: form.max_discount ? Number(form.max_discount) : null,
        min_order_value: form.min_order_value ? Number(form.min_order_value) : 0,
        per_user_limit: form.per_user_limit ? Number(form.per_user_limit) : null,
      });
      setForm(EMPTY); load();
    } catch (err) { setError(err.response?.data?.detail || 'Failed'); }
  };

  if (!coupons) return <Spinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold">Coupons</h1>
      <form onSubmit={create} className="card mt-4 grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
        <input required placeholder="CODE" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="input" />
        <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })} className="input">
          <option value="percentage">Percentage</option>
          <option value="flat">Flat ₹</option>
        </select>
        <input type="number" required placeholder="Value" value={form.discount_value} onChange={(e) => setForm({ ...form, discount_value: e.target.value })} className="input" />
        <input type="number" placeholder="Max discount" value={form.max_discount} onChange={(e) => setForm({ ...form, max_discount: e.target.value })} className="input" />
        <input type="number" placeholder="Min order value" value={form.min_order_value} onChange={(e) => setForm({ ...form, min_order_value: e.target.value })} className="input" />
        <input type="number" placeholder="Per-user limit" value={form.per_user_limit} onChange={(e) => setForm({ ...form, per_user_limit: e.target.value })} className="input" />
        <input placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input md:col-span-2" />
        {error && <p className="col-span-full text-sm text-red-500">{error}</p>}
        <button className="btn-primary col-span-full md:col-auto"><Plus size={16} /> Add</button>
      </form>

      <div className="card mt-4 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr><th className="p-3">Code</th><th className="p-3">Discount</th><th className="p-3">Min order</th><th className="p-3">Used</th><th className="p-3"></th></tr>
          </thead>
          <tbody>
            {coupons.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="p-3 font-medium">{c.code}<div className="text-xs text-slate-400">{c.description}</div></td>
                <td className="p-3">{c.discount_type === 'flat' ? inr(c.discount_value) : `${c.discount_value}%`}</td>
                <td className="p-3">{inr(c.min_order_value)}</td>
                <td className="p-3">{c.times_used}{c.usage_limit ? `/${c.usage_limit}` : ''}</td>
                <td className="p-3 text-right"><button onClick={async () => { await adminApi.deleteCoupon(c.id); load(); }} className="text-red-500"><Trash2 size={16} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
