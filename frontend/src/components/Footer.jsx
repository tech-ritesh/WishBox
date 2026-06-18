import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-8 text-sm text-slate-500">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="font-semibold text-brand-700">🎁 WishBox</p>
          <p>Local-first gifting platform · successor to Celebration Box</p>
          <div className="flex gap-4">
            <Link to="/support" className="hover:text-brand-600">Help &amp; Support</Link>
            <Link to="/shop" className="hover:text-brand-600">Shop</Link>
            <a href="/showcase.html" className="hover:text-brand-600">Showcase</a>
          </div>
          <p>© {new Date().getFullYear()} WishBox</p>
        </div>
      </div>
    </footer>
  );
}
