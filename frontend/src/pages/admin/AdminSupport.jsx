import { useEffect, useState } from 'react';
import { adminApi, supportApi } from '../../api/client';

export default function AdminSupport() {
  const [tickets, setTickets] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [reply, setReply] = useState({});
  const [faqForm, setFaqForm] = useState({ question: '', answer: '', category: 'General' });

  const load = () => {
    adminApi.tickets().then((r) => setTickets(r.data));
    supportApi.faqs().then((r) => setFaqs(r.data));
  };
  useEffect(() => { load(); }, []);

  const sendReply = async (id) => {
    if (!reply[id]?.trim()) return;
    await adminApi.replyTicket(id, reply[id]);
    setReply({ ...reply, [id]: '' }); load();
  };
  const setStatus = async (id, status) => { await adminApi.updateTicket(id, status); load(); };
  const addFaq = async (e) => {
    e.preventDefault();
    await adminApi.createFaq(faqForm);
    setFaqForm({ question: '', answer: '', category: 'General' }); load();
  };
  const delFaq = async (id) => { await adminApi.deleteFaq(id); load(); };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Support tickets</h1>
        <div className="mt-4 space-y-3">
          {tickets.length === 0 && <p className="text-slate-500">No tickets.</p>}
          {tickets.map((t) => (
            <div key={t.id} className="card p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-semibold">#{t.id} {t.subject}</span>
                <select value={t.status} onChange={(e) => setStatus(t.id, e.target.value)} className="input max-w-[140px] text-xs">
                  {['open', 'pending', 'resolved', 'closed'].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="mt-2 space-y-1">
                {t.messages.map((m) => (
                  <p key={m.id} className={m.is_staff ? 'text-brand-700' : 'text-slate-600'}>
                    <b>{m.is_staff ? 'Staff' : 'Customer'}:</b> {m.body}
                  </p>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <input value={reply[t.id] || ''} onChange={(e) => setReply({ ...reply, [t.id]: e.target.value })}
                  placeholder="Reply to customer…" className="input text-sm" />
                <button onClick={() => sendReply(t.id)} className="btn-primary text-sm">Reply</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-xl font-bold">FAQ management</h2>
        <form onSubmit={addFaq} className="card mt-3 grid gap-2 p-4 md:grid-cols-2">
          <input required placeholder="Question" value={faqForm.question}
            onChange={(e) => setFaqForm({ ...faqForm, question: e.target.value })} className="input md:col-span-2" />
          <textarea required placeholder="Answer" value={faqForm.answer}
            onChange={(e) => setFaqForm({ ...faqForm, answer: e.target.value })} className="input md:col-span-2" rows={2} />
          <input placeholder="Category" value={faqForm.category}
            onChange={(e) => setFaqForm({ ...faqForm, category: e.target.value })} className="input" />
          <button className="btn-primary">Add FAQ</button>
        </form>
        <div className="mt-3 space-y-2">
          {faqs.map((f) => (
            <div key={f.id} className="card flex items-center justify-between p-3 text-sm">
              <span>{f.question} <span className="text-slate-400">· {f.category}</span></span>
              <button onClick={() => delFaq(f.id)} className="text-red-500 text-xs">Delete</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
