import { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { categoriesApi, productsApi } from '../api/client';
import ProductCard from '../components/ProductCard';
import { Spinner } from '../components/Layout';

// Flatten the tree into lookup maps with parent pointers.
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

export default function CategoryLanding() {
  const { slug } = useParams();
  const [tree, setTree] = useState([]);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const limit = 12;
  const [offset, setOffset] = useState(0);

  useEffect(() => { categoriesApi.tree().then((r) => setTree(r.data)).catch(() => {}); }, []);
  useEffect(() => { setOffset(0); }, [slug]);

  useEffect(() => {
    setLoading(true);
    productsApi.list({ category: slug, limit, offset }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [slug, offset]);

  const { bySlug, parentOf } = useMemo(() => indexTree(tree), [tree]);
  const node = bySlug[slug];
  // Section root = the top-level parent of the current node (so the sidebar stays stable).
  let sectionRoot = node;
  while (sectionRoot && parentOf[sectionRoot.slug]) sectionRoot = parentOf[sectionRoot.slug];

  const pages = Math.ceil(data.total / limit);
  const currentPage = Math.floor(offset / limit);

  return (
    <div>
      <nav className="mb-3 text-sm text-slate-500">
        <Link to="/" className="hover:text-brand-600">Home</Link>
        {sectionRoot && <> / <Link to={`/category/${sectionRoot.slug}`} className="hover:text-brand-600">{sectionRoot.name}</Link></>}
        {node && node.slug !== sectionRoot?.slug && <> / <span className="text-slate-700">{node.name}</span></>}
      </nav>

      <h1 className="text-2xl font-bold">{node ? node.name : 'Category'}</h1>
      {node?.description && <p className="text-slate-500">{node.description}</p>}

      <div className="mt-4 grid gap-6 md:grid-cols-[240px_1fr]">
        {/* Sub-category sidebar */}
        <aside className="hidden md:block">
          {sectionRoot?.children?.length > 0 && (
            <div className="card p-4">
              {sectionRoot.children.map((sub) => (
                <div key={sub.id} className="mb-3">
                  <Link to={`/category/${sub.slug}`}
                    className={`block text-sm font-semibold ${slug === sub.slug ? 'text-brand-600' : 'text-slate-800'} hover:text-brand-600`}>
                    {sub.name}
                  </Link>
                  <ul className="mt-1 space-y-0.5">
                    {(sub.children || []).map((leaf) => (
                      <li key={leaf.id}>
                        <Link to={`/category/${leaf.slug}`}
                          className={`text-xs hover:text-brand-600 ${slug === leaf.slug ? 'text-brand-600 font-medium' : 'text-slate-500'}`}>
                          {leaf.name}
                          {leaf.is_badge_new && <span className="badge ml-1 bg-emerald-100 text-emerald-700">New</span>}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Product grid */}
        <div>
          {loading ? <Spinner /> : data.items.length === 0 ? (
            <p className="py-20 text-center text-slate-400">No products in this category yet.</p>
          ) : (
            <>
              <p className="mb-3 text-sm text-slate-500">{data.total} products</p>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
                {data.items.map((p) => <ProductCard key={p.id} product={p} />)}
              </div>
              {pages > 1 && (
                <div className="mt-6 flex justify-center gap-2">
                  {Array.from({ length: pages }).map((_, i) => (
                    <button key={i} onClick={() => setOffset(i * limit)}
                      className={`h-9 w-9 rounded-lg text-sm ${i === currentPage ? 'bg-brand-600 text-white' : 'border border-slate-300'}`}>
                      {i + 1}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
