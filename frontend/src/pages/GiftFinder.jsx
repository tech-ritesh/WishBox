import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { recommendationsApi } from '../api/client';
import ProductCard from '../components/ProductCard';

export default function GiftFinder() {
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({ occasion: '', relationship: '', emotion: '', budget: '' });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const search = async () => {
    setLoading(true);
    try {
      const { data } = await recommendationsApi.smart({
        message: message || null,
        occasion: form.occasion || null,
        relationship: form.relationship || null,
        emotion: form.emotion || null,
        budget: form.budget ? Number(form.budget) : null,
      });
      setResult(data);
    } finally { setLoading(false); }
  };

  return (
    <div>
      <h1 className="flex items-center gap-2 text-2xl font-bold"><Sparkles className="text-brand-600" /> Gift Finder</h1>
      <p className="text-slate-500">Describe who it's for, or use the filters. Our local engine curates matches.</p>

      <div className="card mt-4 space-y-3 p-5">
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={2} className="input"
          placeholder="e.g. Romantic anniversary gift for my wife under 2000" />
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <input placeholder="Occasion" value={form.occasion} onChange={(e) => setForm({ ...form, occasion: e.target.value })} className="input" />
          <input placeholder="Relationship" value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} className="input" />
          <input placeholder="Emotion" value={form.emotion} onChange={(e) => setForm({ ...form, emotion: e.target.value })} className="input" />
          <input type="number" placeholder="Budget ₹" value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} className="input" />
        </div>
        <button onClick={search} disabled={loading} className="btn-primary">{loading ? 'Thinking…' : 'Find gifts'}</button>
      </div>

      {result && (
        <div className="mt-6">
          <div className="card mb-4 bg-brand-50 p-4">
            <p className="text-slate-700">{result.assistant_message}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {result.insight_tags.map((t) => <span key={t} className="badge bg-white text-brand-700">{t}</span>)}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {result.products.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        </div>
      )}
    </div>
  );
}
