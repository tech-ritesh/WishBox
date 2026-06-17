import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Star, ShoppingCart, Heart, Truck, Sparkles } from 'lucide-react';
import { productsApi, reviewsApi, wishlistApi, discoveryApi } from '../api/client';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { inr } from '../utils/format';
import { Spinner } from '../components/Layout';
import ProductCard from '../components/ProductCard';

export default function ProductDetails() {
  const { slug } = useParams();
  const { add } = useCart();
  const { user } = useAuth();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [related, setRelated] = useState([]);
  const [qty, setQty] = useState(1);
  const [variant, setVariant] = useState(null);
  const [msg, setMsg] = useState('');
  const [notifyMsg, setNotifyMsg] = useState('');
  const [personalMsg, setPersonalMsg] = useState('');
  const [form, setForm] = useState({ rating: 5, comment: '' });

  useEffect(() => {
    productsApi.detail(slug).then((r) => {
      setProduct(r.data);
      reviewsApi.list(r.data.id).then((rv) => setReviews(rv.data));
      if (user) discoveryApi.recordView(r.data.id).catch(() => {});
    });
    productsApi.related(slug).then((r) => setRelated(r.data)).catch(() => {});
  }, [slug, user]);

  if (!product) return <Spinner />;

  const notifyMe = async () => {
    if (!user) { window.location.href = '/login'; return; }
    try { await discoveryApi.notifyMe(product.id); setNotifyMsg("We'll email you when it's back in stock."); }
    catch (e) { setNotifyMsg(e.response?.data?.detail || 'Could not subscribe'); }
  };

  const submitReview = async (e) => {
    e.preventDefault();
    try {
      await reviewsApi.create({ product_id: product.id, ...form });
      const rv = await reviewsApi.list(product.id);
      setReviews(rv.data);
      setForm({ rating: 5, comment: '' });
    } catch (err) { setMsg(err.response?.data?.detail || 'Could not submit review'); }
  };

  return (
    <div>
      <div className="grid gap-8 md:grid-cols-2">
        <div className="card flex aspect-square items-center justify-center bg-gradient-to-br from-brand-50 to-pink-50 text-8xl">
          {product.image_url ? <img src={product.image_url} alt={product.name} className="h-full w-full object-cover rounded-xl" /> : '🎁'}
        </div>
        <div>
          <Link to={`/shop?category=${product.category.slug}`} className="text-sm text-brand-600">{product.category.name}</Link>
          <h1 className="mt-1 text-3xl font-bold">{product.name}</h1>
          <div className="mt-2 flex items-center gap-1 text-amber-500">
            <Star size={16} fill="currentColor" /> {Number(product.rating_avg).toFixed(1)}
            <span className="text-slate-400">· {product.rating_count} reviews</span>
          </div>
          {(() => {
            const base = Number(product.discount_price ?? product.price);
            const delta = variant ? Number(variant.price_delta) : 0;
            return (
              <div className="mt-4 flex items-center gap-3">
                <span className="text-3xl font-bold">{inr(base + delta)}</span>
                {product.discount_price != null && <span className="text-lg text-slate-400 line-through">{inr(product.price)}</span>}
              </div>
            );
          })()}
          {product.variants?.length > 0 && (
            <div className="mt-4">
              <label className="text-sm font-semibold">Choose an option</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {product.variants.filter((v) => v.is_active).map((v) => (
                  <button key={v.id} onClick={() => setVariant(v)} disabled={v.stock <= 0}
                    className={`btn text-sm ${variant?.id === v.id ? 'btn-primary' : 'btn-ghost'} ${v.stock <= 0 ? 'opacity-40' : ''}`}>
                    {v.name}{Number(v.price_delta) ? ` (+${inr(v.price_delta)})` : ''}{v.stock <= 0 ? ' — out' : ''}
                  </button>
                ))}
              </div>
            </div>
          )}
          <p className="mt-4 text-slate-600">{product.description}</p>

          <div className="mt-3 flex flex-wrap gap-2">
            {product.tags.map((t) => <span key={t.id} className="badge bg-brand-100 text-brand-700">{t.name}</span>)}
          </div>

          {product.is_quick_delivery && (
            <p className="mt-3 flex items-center gap-2 text-sm text-emerald-600"><Truck size={16} /> Express delivery available</p>
          )}
          {product.is_customizable && (
            <p className="mt-2 flex items-center gap-2 text-sm font-medium text-brand-700">
              <Sparkles size={16} /> Customizable — personalize this gift
            </p>
          )}
          {(() => {
            const hasVariants = product.variants?.length > 0;
            const eff = hasVariants ? (variant ? variant.stock : null) : product.stock;
            const label = hasVariants && variant === null ? 'Select an option above'
              : eff > 0 ? `${eff} in stock` : 'Out of stock';
            return <p className="mt-2 text-sm text-slate-500">{label}</p>;
          })()}
          {(product.variants?.length > 0 ? (variant && variant.stock <= 0) : product.stock <= 0) && (
            <div className="mt-2">
              <button onClick={notifyMe} className="btn-ghost text-sm">🔔 Notify me when available</button>
              {notifyMsg && <p className="mt-1 text-xs text-brand-600">{notifyMsg}</p>}
            </div>
          )}

          {product.is_customizable && (
            <div className="mt-4 rounded-lg border border-brand-200 bg-brand-50 p-3">
              <label className="text-sm font-semibold text-brand-700">Add a personal message</label>
              <textarea value={personalMsg} onChange={(e) => setPersonalMsg(e.target.value)} rows={2}
                placeholder="e.g. Happy Birthday! Wishing you all the best…" className="input mt-1 bg-white" />
              <p className="mt-1 text-xs text-slate-500">This note is attached to your item and carried into your order.</p>
            </div>
          )}

          {(() => {
            const hasVariants = product.variants?.length > 0;
            const effStock = hasVariants ? (variant ? variant.stock : 0) : product.stock;
            const needsVariant = hasVariants && variant === null;
            return (
              <div className="mt-5 flex items-center gap-3">
                <input type="number" min={1} max={effStock} value={qty}
                  onChange={(e) => setQty(Math.max(1, Number(e.target.value)))} className="input w-20" />
                <button disabled={effStock <= 0 || needsVariant}
                  onClick={() => {
                    if (!user) { window.location.href = '/login'; return; }
                    const customization = product.is_customizable && personalMsg.trim() ? { message: personalMsg.trim() } : null;
                    add(product.id, qty, customization, variant?.id ?? null);
                  }}
                  className="btn-primary flex-1">
                  <ShoppingCart size={18} /> {needsVariant ? 'Select an option' : 'Add to cart'}
                </button>
                {user && <button onClick={() => wishlistApi.add(product.id)} className="btn-ghost"><Heart size={18} /></button>}
              </div>
            );
          })()}
        </div>
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-bold">Reviews</h2>
        {user && (
          <form onSubmit={submitReview} className="card mb-4 space-y-2 p-4">
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button type="button" key={n} onClick={() => setForm({ ...form, rating: n })}>
                  <Star size={22} className={n <= form.rating ? 'text-amber-500' : 'text-slate-300'} fill="currentColor" />
                </button>
              ))}
            </div>
            <textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })}
              placeholder="Share your experience…" className="input" rows={2} />
            {msg && <p className="text-sm text-red-500">{msg}</p>}
            <button className="btn-primary">Submit review</button>
          </form>
        )}
        <div className="space-y-3">
          {reviews.length === 0 && <p className="text-slate-400">No reviews yet.</p>}
          {reviews.map((r) => (
            <div key={r.id} className="card p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">{r.user_name}</span>
                <span className="flex text-amber-500">{Array.from({ length: r.rating }).map((_, i) => <Star key={i} size={14} fill="currentColor" />)}</span>
              </div>
              {r.verified_purchase && <span className="badge bg-green-100 text-green-700 mt-1">Verified purchase</span>}
              <p className="mt-1 text-slate-600">{r.comment}</p>
            </div>
          ))}
        </div>
      </section>

      {related.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-xl font-bold">You may also like</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {related.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        </section>
      )}
    </div>
  );
}
