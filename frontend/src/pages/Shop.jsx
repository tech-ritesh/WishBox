import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { productsApi, categoriesApi } from '../api/client';
import ProductCard from '../components/ProductCard';
import { Spinner } from '../components/Layout';

function indexTree(tree) {
  const bySlug = {};
  const parentOf = {};
  const walk = (node, parent) => {
    bySlug[node.slug] = node;
    if (parent) parentOf[node.slug] = parent;
    (node.children || []).forEach((c) => walk(c, node));
  };
  tree.forEach((r) => walk(r, null));
  return { bySlug, parentOf };
}

export default function Shop() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState({ items: [], total: 0 });
  const [tree, setTree] = useState([]);
  const [loading, setLoading] = useState(true);
  const limit = 12;
  const offset = Number(params.get('offset') || 0);

  const q = params.get('q') || '';
  const category = params.get('category') || '';
  const sort = params.get('sort') || '';

  useEffect(() => { categoriesApi.tree().then((r) => setTree(r.data)).catch(() => {}); }, []);

  useEffect(() => {
    setLoading(true);
    const query = { limit, offset };
    if (q) query.q = q;
    if (category) query.category = category;
    if (sort) query.sort = sort;
    productsApi.list(query).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [q, category, sort, offset]);

  const { bySlug, parentOf } = useMemo(() => indexTree(tree), [tree]);
  // Resolve the active top-level parent from whatever category slug is selected.
  let root = bySlug[category];
  while (root && parentOf[root.slug]) root = parentOf[root.slug];
  const rootSlug = root?.slug || '';

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    next.delete('offset');
    setParams(next);
  };

  const pages = Math.ceil(data.total / limit);
  const currentPage = Math.floor(offset / limit);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">Shop</h1>
        <input defaultValue={q} onKeyDown={(e) => e.key === 'Enter' && setParam('q', e.target.value)}
          placeholder="Search gifts…" className="input max-w-xs" />

        {/* Parent category */}
        <select value={rootSlug} onChange={(e) => setParam('category', e.target.value)} className="input max-w-[170px]">
          <option value="">All categories</option>
          {tree.map((p) => <option key={p.id} value={p.slug}>{p.name}</option>)}
        </select>

        {/* Sub-category (children + leaves of the active parent) */}
        {root?.children?.length > 0 && (
          <select value={bySlug[category] && category !== rootSlug ? category : ''}
            onChange={(e) => setParam('category', e.target.value || rootSlug)} className="input max-w-[200px]">
            <option value="">All {root.name}</option>
            {root.children.map((sub) => (
              <optgroup key={sub.id} label={sub.name}>
                <option value={sub.slug}>{sub.name} (all)</option>
                {(sub.children || []).map((leaf) => (
                  <option key={leaf.id} value={leaf.slug}>— {leaf.name}</option>
                ))}
              </optgroup>
            ))}
          </select>
        )}

        <select value={sort} onChange={(e) => setParam('sort', e.target.value)} className="input max-w-[160px]">
          <option value="">Sort: Featured</option>
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
          <option value="rating">Top rated</option>
          <option value="newest">Newest</option>
        </select>
        <span className="ml-auto text-sm text-slate-500">{data.total} results</span>
      </div>

      {loading ? <Spinner /> : data.items.length === 0 ? (
        <p className="py-20 text-center text-slate-400">No products found.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {data.items.map((p) => <ProductCard key={p.id} product={p} />)}
        </div>
      )}

      {pages > 1 && (
        <div className="mt-6 flex justify-center gap-2">
          {Array.from({ length: pages }).map((_, i) => (
            <button key={i} onClick={() => setParam('offset', i * limit)}
              className={`h-9 w-9 rounded-lg text-sm ${i === currentPage ? 'bg-brand-600 text-white' : 'border border-slate-300'}`}>
              {i + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
