import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, Calendar, Package, Heart } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { remindersApi, notificationsApi } from '../api/client';

export default function Account() {
  const { user } = useAuth();
  const [reminders, setReminders] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [form, setForm] = useState({ title: '', occasion: '', recipient_name: '', reminder_date: '' });

  const load = () => {
    remindersApi.list().then((r) => setReminders(r.data));
    notificationsApi.list().then((r) => setNotifications(r.data));
  };
  useEffect(() => { load(); }, []);

  const addReminder = async (e) => {
    e.preventDefault();
    await remindersApi.create(form);
    setForm({ title: '', occasion: '', recipient_name: '', reminder_date: '' });
    load();
  };

  return (
    <div>
      <h1 className="text-2xl font-bold">Hi, {user.full_name} 👋</h1>
      <div className="mt-4 flex flex-wrap gap-3">
        <Link to="/orders" className="btn-ghost"><Package size={16} /> My orders</Link>
        <Link to="/wishlist" className="btn-ghost"><Heart size={16} /> Wishlist</Link>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <section className="card p-5">
          <h2 className="flex items-center gap-2 font-bold"><Calendar size={18} /> Celebration reminders</h2>
          <form onSubmit={addReminder} className="mt-3 grid grid-cols-2 gap-2">
            <input required placeholder="Title (e.g. Mom's Birthday)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input col-span-2" />
            <input placeholder="Occasion" value={form.occasion} onChange={(e) => setForm({ ...form, occasion: e.target.value })} className="input" />
            <input type="date" required value={form.reminder_date} onChange={(e) => setForm({ ...form, reminder_date: e.target.value })} className="input" />
            <button className="btn-primary col-span-2">Add reminder</button>
          </form>
          <ul className="mt-3 space-y-2">
            {reminders.map((r) => (
              <li key={r.id} className="flex items-center justify-between rounded-lg bg-slate-50 p-2 text-sm">
                <span>{r.title} {r.occasion && `· ${r.occasion}`}</span>
                <span className="text-slate-500">{r.reminder_date}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-5">
          <h2 className="flex items-center gap-2 font-bold"><Bell size={18} /> Notifications</h2>
          <ul className="mt-3 space-y-2">
            {notifications.length === 0 && <li className="text-sm text-slate-400">Nothing yet.</li>}
            {notifications.map((n) => (
              <li key={n.id} className={`rounded-lg p-2 text-sm ${n.is_read ? 'bg-slate-50' : 'bg-brand-50'}`}>
                <p className="font-medium">{n.title}</p>
                <p className="text-slate-500">{n.body}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
