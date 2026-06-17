import { useEffect, useRef, useState } from 'react';
import { adminApi } from '../../api/client';

export default function AdminContent() {
  const [banners, setBanners] = useState([]);
  const [logs, setLogs] = useState([]);
  const [form, setForm] = useState({ title: '', subtitle: '', link: '/shop', cta_text: 'Shop now' });
  const [importMsg, setImportMsg] = useState('');
  const fileRef = useRef(null);

  const load = () => {
    adminApi.banners().then((r) => setBanners(r.data));
    adminApi.auditLogs().then((r) => setLogs(r.data));
  };
  useEffect(() => { load(); }, []);

  const addBanner = async (e) => {
    e.preventDefault();
    await adminApi.createBanner(form);
    setForm({ title: '', subtitle: '', link: '/shop', cta_text: 'Shop now' });
    load();
  };
  const delBanner = async (id) => { await adminApi.deleteBanner(id); load(); };

  const doImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) { setImportMsg('Choose a CSV file first.'); return; }
    const fd = new FormData(); fd.append('file', file);
    try {
      const { data } = await adminApi.bulkImport(fd);
      setImportMsg(`Imported ${data.created} products${data.errors.length ? `, ${data.errors.length} errors` : ''}.`);
    } catch (e) { setImportMsg(e.response?.data?.detail || 'Import failed'); }
  };

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Content & Tools</h1>

      <section>
        <h2 className="font-bold">Homepage banners</h2>
        <form onSubmit={addBanner} className="card mt-2 grid gap-2 p-4 md:grid-cols-2">
          <input required placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" />
          <input placeholder="Subtitle" value={form.subtitle} onChange={(e) => setForm({ ...form, subtitle: e.target.value })} className="input" />
          <input placeholder="Link (e.g. /shop)" value={form.link} onChange={(e) => setForm({ ...form, link: e.target.value })} className="input" />
          <input placeholder="CTA text" value={form.cta_text} onChange={(e) => setForm({ ...form, cta_text: e.target.value })} className="input" />
          <button className="btn-primary md:col-span-2">Add banner</button>
        </form>
        <div className="mt-2 space-y-2">
          {banners.map((b) => (
            <div key={b.id} className="card flex items-center justify-between p-3 text-sm">
              <span>{b.title} <span className="text-slate-400">→ {b.link}</span></span>
              <button onClick={() => delBanner(b.id)} className="text-red-500 text-xs">Delete</button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-bold">Bulk product import (CSV)</h2>
        <p className="text-sm text-slate-500">Columns: name, price, stock, category_id[, description, sku, discount_price, type]</p>
        <div className="mt-2 flex items-center gap-2">
          <input ref={fileRef} type="file" accept=".csv" className="text-sm" />
          <button onClick={doImport} className="btn-primary text-sm">Import</button>
          <a href="/api/v1/admin/reports/sales.csv" className="btn-ghost text-sm">Download sales report</a>
        </div>
        {importMsg && <p className="mt-1 text-sm text-brand-600">{importMsg}</p>}
      </section>

      <section>
        <h2 className="font-bold">Audit log</h2>
        <div className="mt-2 space-y-1 text-xs text-slate-500">
          {logs.length === 0 && <p className="text-slate-400">No audit entries yet.</p>}
          {logs.map((l) => (
            <div key={l.id} className="rounded bg-slate-50 p-2">
              <b>{l.action}</b> · {l.entity}#{l.entity_id} · {new Date(l.created_at).toLocaleString()}
              {l.detail && <span className="text-slate-400"> · {JSON.stringify(l.detail)}</span>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
