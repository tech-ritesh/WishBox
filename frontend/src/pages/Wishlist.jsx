import { useEffect, useState } from 'react';
import { wishlistApi } from '../api/client';
import ProductCard from '../components/ProductCard';
import { Spinner } from '../components/Layout';

export default function Wishlist() {
  const [items, setItems] = useState(null);
  useEffect(() => { wishlistApi.list().then((r) => setItems(r.data)); }, []);
  if (!items) return <Spinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold">My Wishlist</h1>
      {items.length === 0 ? <p className="mt-6 text-slate-400">Your wishlist is empty.</p> : (
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((w) => <ProductCard key={w.id} product={w.product} />)}
        </div>
      )}
    </div>
  );
}
