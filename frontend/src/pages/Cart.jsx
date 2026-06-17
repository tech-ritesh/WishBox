import { Link, useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { inr } from '../utils/format';

export default function Cart() {
  const { cart, update, remove } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!user) return <p className="py-20 text-center">Please <Link to="/login" className="text-brand-600">sign in</Link> to view your cart.</p>;
  if (cart.items.length === 0) return (
    <div className="py-20 text-center text-slate-500">
      <p className="text-5xl">🛒</p>
      <p className="mt-3">Your cart is empty.</p>
      <Link to="/shop" className="btn-primary mt-4 inline-flex">Browse gifts</Link>
    </div>
  );

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="md:col-span-2 space-y-3">
        <h1 className="text-2xl font-bold">Your Cart</h1>
        {cart.items.map((item) => (
          <div key={item.id} className="card flex items-center gap-4 p-3">
            <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-brand-50 text-2xl">🎁</div>
            <div className="flex-1">
              <Link to={`/product/${item.product.slug}`} className="font-medium hover:text-brand-600">{item.product.name}</Link>
              <p className="text-sm text-slate-500">{inr(item.product.discount_price ?? item.product.price)}</p>
              {item.customization_details?.message && (
                <p className="text-xs text-brand-600">✨ “{item.customization_details.message}”</p>
              )}
            </div>
            <input type="number" min={1} value={item.quantity}
              onChange={(e) => update(item.id, Math.max(1, Number(e.target.value)))} className="input w-16" />
            <button onClick={() => remove(item.id)} className="text-red-500"><Trash2 size={18} /></button>
          </div>
        ))}
      </div>
      <div className="card h-fit p-5">
        <h2 className="font-bold">Summary</h2>
        <div className="mt-3 flex justify-between text-sm"><span>Subtotal ({cart.item_count} items)</span><span>{inr(cart.subtotal)}</span></div>
        <p className="mt-1 text-xs text-slate-400">Shipping & coupons applied at checkout</p>
        <button onClick={() => navigate('/checkout')} className="btn-primary mt-4 w-full">Proceed to checkout</button>
      </div>
    </div>
  );
}
