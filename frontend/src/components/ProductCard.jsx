import { Link } from 'react-router-dom';
import { Heart, ShoppingCart, Star } from 'lucide-react';
import { inr } from '../utils/format';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { wishlistApi } from '../api/client';

export default function ProductCard({ product }) {
  const { add } = useCart();
  const { user } = useAuth();
  const hasDiscount = product.discount_price != null;

  return (
    <div className="card group overflow-hidden">
      <Link to={`/product/${product.slug}`} className="block">
        <div className="relative aspect-square bg-gradient-to-br from-brand-50 to-pink-50 flex items-center justify-center text-5xl">
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} className="h-full w-full object-cover" />
          ) : ('🎁')}
          {hasDiscount && <span className="badge bg-red-500 text-white absolute top-2 left-2">SALE</span>}
          {product.is_quick_delivery && <span className="badge bg-emerald-500 text-white absolute top-2 right-2">⚡ Fast</span>}
          {product.is_customizable && <span className="badge bg-brand-600 text-white absolute bottom-2 left-2">✨ Customizable</span>}
        </div>
      </Link>
      <div className="p-3">
        <Link to={`/product/${product.slug}`}>
          <h3 className="font-semibold text-slate-800 line-clamp-1 hover:text-brand-600">{product.name}</h3>
        </Link>
        <div className="mt-1 flex items-center gap-1 text-sm text-amber-500">
          <Star size={14} fill="currentColor" /> {Number(product.rating_avg || 0).toFixed(1)}
          <span className="text-slate-400">({product.rating_count})</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="font-bold text-slate-900">{inr(product.discount_price ?? product.price)}</span>
          {hasDiscount && <span className="text-sm text-slate-400 line-through">{inr(product.price)}</span>}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            disabled={product.stock <= 0}
            onClick={() => user ? add(product.id) : (window.location.href = '/login')}
            className="btn-primary flex-1 text-sm py-1.5"
          >
            <ShoppingCart size={16} /> {product.stock > 0 ? 'Add' : 'Sold out'}
          </button>
          {user && (
            <button onClick={() => wishlistApi.add(product.id)} className="btn-ghost px-2 py-1.5" title="Wishlist">
              <Heart size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
