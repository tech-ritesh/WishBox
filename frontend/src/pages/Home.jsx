import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Truck, Gift, ShieldCheck } from 'lucide-react';
import { productsApi, categoriesApi } from '../api/client';
import ProductCard from '../components/ProductCard';
import { Spinner } from '../components/Layout';

export default function Home() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([productsApi.list({ sort: 'rating', limit: 8 }), categoriesApi.tree()])
      .then(([p, c]) => { setProducts(p.data.items); setCategories(c.data); })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <section className="rounded-2xl bg-gradient-to-br from-brand-600 to-pink-500 p-10 text-white">
        <h1 className="text-4xl font-extrabold">Gifts that say it perfectly 🎁</h1>
        <p className="mt-3 max-w-xl text-brand-50">
          Curated hampers and personalized gifts for every occasion. Build your own hamper,
          schedule delivery, and let our gift finder do the thinking.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/shop" className="btn bg-white text-brand-700 hover:bg-brand-50">Shop now</Link>
          <Link to="/gift-finder" className="btn border border-white/60 text-white hover:bg-white/10">
            <Sparkles size={18} /> Find a gift
          </Link>
        </div>
      </section>

      <section className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[[Truck, 'Scheduled & express delivery'], [Gift, 'Smart hamper builder'],
          [Sparkles, 'AI-style gift finder'], [ShieldCheck, 'Secure local checkout']].map(([Icon, label]) => (
          <div key={label} className="card flex items-center gap-3 p-4">
            <Icon className="text-brand-600" />
            <span className="text-sm font-medium">{label}</span>
          </div>
        ))}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-xl font-bold">Shop by occasion</h2>
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <Link key={c.id} to={`/category/${c.slug}`} className="btn-ghost text-sm">{c.name}</Link>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-xl font-bold">Top rated</h2>
        {loading ? <Spinner /> : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {products.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        )}
      </section>
    </div>
  );
}
