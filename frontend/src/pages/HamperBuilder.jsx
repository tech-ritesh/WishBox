import { useEffect, useState } from 'react';
import { Plus, Minus, X } from 'lucide-react';
import { productsApi, hampersApi } from '../api/client';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { inr } from '../utils/format';

export default function HamperBuilder() {
  const { add } = useCart();
  const { user } = useAuth();
  const [products, setProducts] = useState([]);
  const [picked, setPicked] = useState({}); // id -> {product, qty}
  const [name, setName] = useState('My Hamper');
  const [message, setMessage] = useState('');
  const [saved, setSaved] = useState('');

  useEffect(() => { productsApi.list({ limit: 50 }).then((r) => setProducts(r.data.items)); }, []);

  const addItem = (p) => setPicked((s) => ({ ...s, [p.id]: { product: p, qty: (s[p.id]?.qty || 0) + 1 } }));
  const decItem = (id) => setPicked((s) => {
    const qty = (s[id]?.qty || 0) - 1;
    if (qty <= 0) { const n = { ...s }; delete n[id]; return n; }
    return { ...s, [id]: { ...s[id], qty } };
  });

  const items = Object.values(picked);
  const total = items.reduce((sum, i) => sum + Number(i.product.discount_price ?? i.product.price) * i.qty, 0);

  const saveHamper = async () => {
    if (!user) { window.location.href = '/login'; return; }
    await hampersApi.create({
      name, gift_message: message,
      items: items.map((i) => ({ product_id: i.product.id, quantity: i.qty })),
    });
    setSaved('Hamper saved to your account!');
  };

  const addAllToCart = async () => {
    if (!user) { window.location.href = '/login'; return; }
    for (const i of items) await add(i.product.id, i.qty);
    setSaved('Added all items to cart!');
  };

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="md:col-span-2">
        <h1 className="text-2xl font-bold">🎀 Smart Hamper Builder</h1>
        <p className="text-slate-500">Pick items to compose your perfect hamper.</p>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {products.map((p) => (
            <div key={p.id} className="card p-3">
              <div className="flex h-20 items-center justify-center rounded-lg bg-brand-50 text-3xl">🎁</div>
              <p className="mt-2 line-clamp-1 text-sm font-medium">{p.name}</p>
              <p className="text-sm text-slate-500">{inr(p.discount_price ?? p.price)}</p>
              <button onClick={() => addItem(p)} className="btn-primary mt-2 w-full text-sm py-1"><Plus size={14} /> Add</button>
            </div>
          ))}
        </div>
      </div>

      <div className="card h-fit p-5">
        <input value={name} onChange={(e) => setName(e.target.value)} className="input font-bold" />
        <div className="mt-3 space-y-2">
          {items.length === 0 && <p className="text-sm text-slate-400">No items yet. Add from the left.</p>}
          {items.map((i) => (
            <div key={i.product.id} className="flex items-center gap-2 text-sm">
              <span className="flex-1 line-clamp-1">{i.product.name}</span>
              <button onClick={() => decItem(i.product.id)} className="rounded border px-1"><Minus size={12} /></button>
              <span>{i.qty}</span>
              <button onClick={() => addItem(i.product)} className="rounded border px-1"><Plus size={12} /></button>
            </div>
          ))}
        </div>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Gift message…" className="input mt-3" rows={2} />
        <div className="mt-3 flex justify-between border-t pt-2 font-bold"><span>Total</span><span>{inr(total)}</span></div>
        {saved && <p className="mt-2 text-sm text-green-600">{saved}</p>}
        <button onClick={addAllToCart} disabled={items.length === 0} className="btn-primary mt-3 w-full">Add all to cart</button>
        <button onClick={saveHamper} disabled={items.length === 0} className="btn-ghost mt-2 w-full">Save hamper</button>
      </div>
    </div>
  );
}
