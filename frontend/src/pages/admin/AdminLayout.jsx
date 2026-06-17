import { NavLink, Outlet, Link } from 'react-router-dom';
import { LayoutDashboard, Package, ShoppingBag, Ticket, Gift, LogOut, RotateCcw, Mail, Star } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const links = [
  ['/admin', 'Dashboard', LayoutDashboard],
  ['/admin/products', 'Products', Package],
  ['/admin/orders', 'Orders', ShoppingBag],
  ['/admin/coupons', 'Coupons', Ticket],
  ['/admin/returns', 'Returns', RotateCcw],
  ['/admin/reviews', 'Reviews', Star],
  ['/admin/outbox', 'Outbox', Mail],
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen bg-slate-100">
      <aside className="flex w-60 flex-col border-r border-slate-200 bg-white p-4">
        <Link to="/" className="flex items-center gap-2 text-lg font-extrabold text-brand-700"><Gift /> WishBox</Link>
        <p className="mt-1 text-xs text-slate-400">Admin · {user?.full_name}</p>
        <nav className="mt-6 flex-1 space-y-1">
          {links.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === '/admin'}
              className={({ isActive }) => `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </nav>
        <button onClick={logout} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"><LogOut size={16} /> Logout</button>
      </aside>
      <main className="flex-1 overflow-auto p-6"><Outlet /></main>
    </div>
  );
}
