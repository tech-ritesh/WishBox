import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Gift, ShoppingCart, User, LayoutDashboard, Sparkles, Heart, LogOut, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { categoriesApi, storefrontApi } from '../api/client';
import { getCurrency, setCurrency } from '../utils/format';
import SearchBox from './SearchBox';

export default function Navbar() {
  const { user, logout, isStaff } = useAuth();
  const { cart } = useCart();
  const navigate = useNavigate();
  const [tree, setTree] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [currencies, setCurrencies] = useState([]);
  const [cur, setCur] = useState(getCurrency().code);

  useEffect(() => { categoriesApi.tree().then((r) => setTree(r.data)).catch(() => {}); }, []);
  useEffect(() => { storefrontApi.currencies().then((r) => setCurrencies(r.data.rates)).catch(() => {}); }, []);

  const onCurrency = (code) => {
    const c = currencies.find((x) => x.code === code);
    if (c) { setCurrency(c); setCur(code); window.location.reload(); }
  };

  const openParent = tree.find((p) => p.id === openId);

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <Link to="/" className="flex items-center gap-2 text-xl font-extrabold text-brand-700">
          <Gift /> WishBox
        </Link>
        <div className="hidden md:flex items-center gap-4 text-sm font-medium text-slate-600">
          {tree.map((p) => (
            <button key={p.id} onMouseEnter={() => setOpenId(p.id)} onClick={() => navigate(`/category/${p.slug}`)}
              className={`flex items-center gap-1 py-1 hover:text-brand-600 ${openId === p.id ? 'text-brand-600' : ''}`}>
              {p.name} <ChevronDown size={13} />
            </button>
          ))}
          <Link to="/hamper-builder" onMouseEnter={() => setOpenId(null)} className="hover:text-brand-600">Build a Hamper</Link>
          <Link to="/gift-finder" onMouseEnter={() => setOpenId(null)} className="flex items-center gap-1 hover:text-brand-600"><Sparkles size={15} /> Gift Finder</Link>
          {/* Static premium showcase page (full-page nav, shares the same auth token) */}
          <a href="/showcase.html" onMouseEnter={() => setOpenId(null)} className="flex items-center gap-1 hover:text-brand-600">
            Showcase <span className="badge bg-brand-100 text-brand-700">New</span>
          </a>
        </div>
        <div className="ml-auto" />
        <SearchBox />
        <div className="flex items-center gap-3" onMouseEnter={() => setOpenId(null)}>
          {currencies.length > 0 && (
            <select value={cur} onChange={(e) => onCurrency(e.target.value)}
              className="hidden rounded border border-slate-200 px-1 py-1 text-xs sm:block" title="Currency">
              {currencies.map((c) => <option key={c.code} value={c.code}>{c.code}</option>)}
            </select>
          )}
          <Link to="/cart" className="relative">
            <ShoppingCart className="text-slate-700" />
            {cart.item_count > 0 && <span className="absolute -right-2 -top-2 badge bg-brand-600 text-white">{cart.item_count}</span>}
          </Link>
          {user ? (
            <>
              <Link to="/wishlist" title="Wishlist"><Heart className="text-slate-700" /></Link>
              {isStaff && <Link to="/admin" title="Admin"><LayoutDashboard className="text-slate-700" /></Link>}
              <Link to="/account" title="Account"><User className="text-slate-700" /></Link>
              <button onClick={() => { logout(); navigate('/'); }} title="Logout"><LogOut className="text-slate-700" /></button>
            </>
          ) : (
            <Link to="/login" className="btn-primary text-sm py-1.5">Sign in</Link>
          )}
        </div>
      </nav>

      {/* Mega-menu panel */}
      {openParent && openParent.children?.length > 0 && (
        <div className="hidden md:block border-t border-slate-100 bg-white shadow-lg" onMouseLeave={() => setOpenId(null)}>
          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-x-6 gap-y-4 px-4 py-5 lg:grid-cols-4">
            {openParent.children.map((sub) => (
              <div key={sub.id}>
                <Link to={`/category/${sub.slug}`} onClick={() => setOpenId(null)}
                  className="text-sm font-bold text-slate-800 hover:text-brand-600">{sub.name}</Link>
                <ul className="mt-1 space-y-0.5">
                  {(sub.children || []).slice(0, 6).map((leaf) => (
                    <li key={leaf.id}>
                      <Link to={`/category/${leaf.slug}`} onClick={() => setOpenId(null)}
                        className="text-xs text-slate-500 hover:text-brand-600">
                        {leaf.name}
                        {leaf.is_badge_new && <span className="badge ml-1 bg-emerald-100 text-emerald-700">New</span>}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </header>
  );
}
