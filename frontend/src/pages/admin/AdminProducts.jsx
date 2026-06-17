import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, AlertTriangle, Pencil, X, Sparkles } from 'lucide-react';
import { adminApi, productsApi, categoriesApi } from '../../api/client';
import { inr } from '../../utils/format';
import { Spinner } from '../../components/Layout';

const EMPTY = { name: '', description: '', price: '', discount_price: '', stock: 10, tags: '', is_quick_delivery: false, is_customizable: false };
const EMPTY_SEL = { parent: '', sub: '', leaf: '' };

// Flatten the category tree → { id: {name, path} } for table display.
function flatten(tree) {
  const map = {};
  const walk = (node, ancestors) => {
    const path = [...ancestors, node.name];
    map[node.id] = { name: node.name, path: path.join(' › ') };
    (node.children || []).forEach((c) => walk(c, path));
  };
  tree.forEach((r) => walk(r, []));
  return map;
}

// Return the ancestor id chain [parentId, subId, leafId] for a category id.
function findChain(tree, id) {
  let result = [];
  const dfs = (node, path) => {
    const next = [...path, node.id];
    if (node.id === id) { result = next; return true; }
    return (node.children || []).some((c) => dfs(c, next));
  };
  tree.some((r) => dfs(r, []));
  return result;
}

export default function AdminProducts() {
  const [products, setProducts] = useState(null);
  const [tree, setTree] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [sel, setSel] = useState(EMPTY_SEL);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');

  const load = () => productsApi.list({ limit: 100 })
    .then((r) => setProducts(r.data.items))
    .catch(() => setProducts([]));
  useEffect(() => { load(); categoriesApi.tree().then((r) => setTree(r.data)).catch(() => {}); }, []);

  const flat = useMemo(() => flatten(tree), [tree]);

  const parentNode = tree.find((p) => String(p.id) === sel.parent);
  const subs = parentNode?.children || [];
  const subNode = subs.find((s) => String(s.id) === sel.sub);
  const leaves = subNode?.children || [];
  const resolvedCategoryId = sel.leaf || sel.sub || sel.parent;

  const resetForm = () => { setForm(EMPTY); setSel(EMPTY_SEL); setEditingId(null); setShowForm(false); setError(''); };

  const startCreate = () => { resetForm(); setShowForm(true); };

  const startEdit = (p) => {
    setForm({
      name: p.name, description: p.description || '', price: p.price,
      discount_price: p.discount_price ?? '', stock: p.stock, tags: '',
      is_quick_delivery: p.is_quick_delivery, is_customizable: p.is_customizable,
    });
    const chain = findChain(tree, p.category_id);
    setSel({ parent: String(chain[0] || ''), sub: String(chain[1] || ''), leaf: String(chain[2] || '') });
    setEditingId(p.id);
    setShowForm(true);
    setError('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!resolvedCategoryId) { setError('Please select a category (and sub-category if applicable)'); return; }
    const payload = {
      name: form.name, description: form.description,
      price: Number(form.price), discount_price: form.discount_price !== '' ? Number(form.discount_price) : null,
      stock: Number(form.stock), category_id: Number(resolvedCategoryId),
      is_quick_delivery: form.is_quick_delivery, is_customizable: form.is_customizable,
    };
    if (form.tags) payload.tags = form.tags.split(',').map((t) => t.trim());
    try {
      if (editingId) {
        await adminApi.updateProduct(editingId, payload);
      } else {
        await adminApi.createProduct({ ...payload, tags: form.tags ? form.tags.split(',').map((t) => t.trim()) : [] });
      }
      resetForm(); load();
    } catch (err) { setError(err.response?.data?.detail || 'Save failed'); }
  };

  const del = async (id) => { await adminApi.deleteProduct(id); load(); };

  if (!products) return <Spinner />;

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Products</h1>
        <button onClick={() => (showForm ? resetForm() : startCreate())} className="btn-primary">
          {showForm ? <><X size={16} /> Close</> : <><Plus size={16} /> New product</>}
        </button>
      </div>

      {showForm && (
        <form onSubmit={submit} className="card mt-4 grid grid-cols-2 gap-3 p-5">
          <div className="col-span-2 flex items-center justify-between">
            <h2 className="font-bold">{editingId ? `Edit product #${editingId}` : 'New product'}</h2>
            {editingId && <button type="button" onClick={resetForm} className="text-sm text-slate-500 hover:text-slate-700">Cancel edit</button>}
          </div>
          <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input col-span-2" />
          <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input col-span-2" rows={2} />
          <input type="number" required placeholder="Price" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="input" />
          <input type="number" placeholder="Discount price" value={form.discount_price} onChange={(e) => setForm({ ...form, discount_price: e.target.value })} className="input" />
          <input type="number" placeholder="Stock" value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} className="input" />
          <input placeholder={editingId ? 'Tags (leave blank to keep current)' : 'Tags (comma separated)'} value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} className="input" />

          <div className="col-span-2">
            <label className="mb-1 block text-xs font-semibold text-slate-500">Category &rarr; Sub-category &rarr; Item</label>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <select required value={sel.parent} onChange={(e) => setSel({ parent: e.target.value, sub: '', leaf: '' })} className="input">
                <option value="">Category…</option>
                {tree.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <select value={sel.sub} disabled={!parentNode} onChange={(e) => setSel({ ...sel, sub: e.target.value, leaf: '' })} className="input disabled:bg-slate-100">
                <option value="">{parentNode ? 'Sub-category…' : '—'}</option>
                {subs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <select value={sel.leaf} disabled={!subNode} onChange={(e) => setSel({ ...sel, leaf: e.target.value })} className="input disabled:bg-slate-100">
                <option value="">{subNode ? 'Item (optional)…' : '—'}</option>
                {leaves.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            {resolvedCategoryId && <p className="mt-1 text-xs text-brand-600">Assigning to: {flat[resolvedCategoryId]?.path}</p>}
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.is_quick_delivery} onChange={(e) => setForm({ ...form, is_quick_delivery: e.target.checked })} /> Quick delivery eligible
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.is_customizable} onChange={(e) => setForm({ ...form, is_customizable: e.target.checked })} /> Customizable (personalization)
          </label>
          {error && <p className="col-span-2 text-sm text-red-500">{error}</p>}
          <button className="btn-primary col-span-2">{editingId ? 'Save changes' : 'Create product'}</button>
        </form>
      )}

      <div className="card mt-4 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr><th className="p-3">Name</th><th className="p-3">Category (full path)</th><th className="p-3">Price</th><th className="p-3">Stock</th><th className="p-3">Custom</th><th className="p-3"></th></tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="p-3 font-medium">{p.name}</td>
                <td className="p-3 text-slate-500">
                  {flat[p.category_id] ? (
                    <>
                      <span className="text-xs text-slate-400">{flat[p.category_id].path.split(' › ').slice(0, -1).join(' › ')}</span>
                      <span className="block font-medium text-slate-700">{flat[p.category_id].name}</span>
                    </>
                  ) : '—'}
                </td>
                <td className="p-3">{inr(p.discount_price ?? p.price)}</td>
                <td className="p-3">
                  <span className={p.stock <= 5 ? 'flex items-center gap-1 text-amber-600' : ''}>
                    {p.stock <= 5 && <AlertTriangle size={14} />}{p.stock}
                  </span>
                </td>
                <td className="p-3">
                  {p.is_customizable
                    ? <span className="badge bg-brand-100 text-brand-700 inline-flex items-center gap-1"><Sparkles size={12} /> Yes</span>
                    : <span className="text-slate-300">—</span>}
                </td>
                <td className="p-3 text-right">
                  <div className="flex justify-end gap-3">
                    <button onClick={() => startEdit(p)} className="text-slate-500 hover:text-brand-600" title="Edit"><Pencil size={16} /></button>
                    <button onClick={() => del(p.id)} className="text-red-500" title="Delete"><Trash2 size={16} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
