import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { supportApi } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Support() {
  const { user } = useAuth();
  const [faqs, setFaqs] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [form, setForm] = useState({ subject: '', body: '' });
  const [reply, setReply] = useState({});

  const loadTickets = () => { if (user) supportApi.myTickets().then((r) => setTickets(r.data)); };
  useEffect(() => { supportApi.faqs().then((r) => setFaqs(r.data)); loadTickets(); }, [user]);

  const openTicket = async (e) => {
    e.preventDefault();
    if (!form.subject || !form.body) return;
    await supportApi.openTicket(form);
    setForm({ subject: '', body: '' });
    loadTickets();
  };
  const sendReply = async (id) => {
    if (!reply[id]?.trim()) return;
    await supportApi.reply(id, reply[id]);
    setReply({ ...reply, [id]: '' });
    loadTickets();
  };

  const grouped = faqs.reduce((acc, f) => { (acc[f.category] ||= []).push(f); return acc; }, {});

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold">Help & Support</h1>

      <section className="mt-5">
        <h2 className="mb-2 text-lg font-bold">Frequently asked questions</h2>
        {faqs.length === 0 && <p className="text-slate-400">No FAQs yet.</p>}
        {Object.entries(grouped).map(([cat, items]) => (
          <div key={cat} className="mb-4">
            <h3 className="text-sm font-semibold text-slate-500">{cat}</h3>
            <div className="mt-1 space-y-2">
              {items.map((f) => (
                <details key={f.id} className="card p-3">
                  <summary className="cursor-pointer font-medium">{f.question}</summary>
                  <p className="mt-2 text-sm text-slate-600">{f.answer}</p>
                </details>
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-lg font-bold">Contact support</h2>
        {!user ? (
          <p className="text-sm text-slate-500">Please <Link to="/login" className="text-brand-600">log in</Link> to open a support ticket.</p>
        ) : (
          <>
            <form onSubmit={openTicket} className="card space-y-2 p-4">
              <input required placeholder="Subject" value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })} className="input" />
              <textarea required placeholder="How can we help?" value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })} className="input" rows={3} />
              <button className="btn-primary">Submit ticket</button>
            </form>

            <div className="mt-4 space-y-3">
              {tickets.map((t) => (
                <div key={t.id} className="card p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{t.subject}</span>
                    <span className="badge bg-slate-100">{t.status}</span>
                  </div>
                  <div className="mt-2 space-y-1">
                    {t.messages.map((m) => (
                      <p key={m.id} className={`text-sm ${m.is_staff ? 'text-brand-700' : 'text-slate-600'}`}>
                        <b>{m.is_staff ? 'WishBox' : 'You'}:</b> {m.body}
                      </p>
                    ))}
                  </div>
                  {t.status !== 'closed' && (
                    <div className="mt-2 flex gap-2">
                      <input value={reply[t.id] || ''} onChange={(e) => setReply({ ...reply, [t.id]: e.target.value })}
                        placeholder="Reply…" className="input text-sm" />
                      <button onClick={() => sendReply(t.id)} className="btn-ghost text-sm">Send</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
