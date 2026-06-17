import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { productsApi } from '../api/client';

export default function SearchBox() {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [sug, setSug] = useState({ products: [], categories: [] });
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);

  // Debounced autocomplete
  useEffect(() => {
    if (q.trim().length < 2) { setSug({ products: [], categories: [] }); return; }
    const t = setTimeout(() => {
      productsApi.autocomplete(q.trim())
        .then((r) => { setSug(r.data); setOpen(true); })
        .catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const go = (path) => { setOpen(false); setQ(''); navigate(path); };
  const submit = (e) => {
    e.preventDefault();
    if (q.trim()) go(`/shop?q=${encodeURIComponent(q.trim())}`);
  };

  const hasResults = sug.products.length > 0 || sug.categories.length > 0;

  return (
    <div ref={boxRef} className="relative hidden flex-1 max-w-xs lg:block">
      <form onSubmit={submit}>
        <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => hasResults && setOpen(true)}
          placeholder="Search gifts…" className="input w-full pl-9 py-1.5 text-sm" />
      </form>
      {open && hasResults && (
        <div className="absolute left-0 right-0 z-50 mt-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          {sug.products.map((p) => (
            <button key={`p-${p.slug}`} onClick={() => go(`/product/${p.slug}`)}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50">{p.name}</button>
          ))}
          {sug.categories.length > 0 && (
            <div className="border-t border-slate-100">
              {sug.categories.map((c) => (
                <button key={`c-${c.slug}`} onClick={() => go(`/category/${c.slug}`)}
                  className="block w-full px-3 py-2 text-left text-xs text-slate-500 hover:bg-slate-50">
                  in <b>{c.name}</b>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
