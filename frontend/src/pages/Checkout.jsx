import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi, ordersApi, couponsApi } from '../api/client';
import { useCart } from '../context/CartContext';
import { inr } from '../utils/format';

const SLOTS = ['09:00-12:00', '12:00-15:00', '15:00-18:00', '18:00-21:00', 'midnight'];

export default function Checkout() {
  const { cart, refresh } = useCart();
  const navigate = useNavigate();
  const [addresses, setAddresses] = useState([]);
  const [addressId, setAddressId] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [newAddr, setNewAddr] = useState({ recipient_name: '', phone: '', address_line1: '', city: '', state: '', postal_code: '' });
  const [payment, setPayment] = useState('cod');
  const [coupon, setCoupon] = useState('');
  const [discount, setDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState('');
  const [isGift, setIsGift] = useState(false);
  const [giftMessage, setGiftMessage] = useState('');
  const [schedule, setSchedule] = useState({ date: '', slot: '' });
  const [error, setError] = useState('');
  const [placing, setPlacing] = useState(false);

  const loadAddresses = () => authApi.addresses().then((r) => {
    setAddresses(r.data);
    const def = r.data.find((a) => a.is_default) || r.data[0];
    if (def) setAddressId(def.id);
    setShowNew(r.data.length === 0);
  });
  useEffect(() => { loadAddresses(); }, []);

  const subtotal = Number(cart.subtotal);
  const shipping = (subtotal - discount) >= 999 ? 0 : (subtotal > 0 ? 49 : 0);
  const total = Math.max(subtotal - discount, 0) + shipping;

  const applyCoupon = async () => {
    try {
      const { data } = await couponsApi.validate(coupon, subtotal);
      setDiscount(Number(data.discount));
      setCouponMsg(data.message);
    } catch { setCouponMsg('Could not validate coupon'); }
  };

  const saveAddress = async (e) => {
    e.preventDefault();
    const { data } = await authApi.addAddress(newAddr);
    await loadAddresses();
    setAddressId(data.id);
    setShowNew(false);
  };

  const placeOrder = async () => {
    if (!addressId) { setError('Please select an address'); return; }
    setPlacing(true); setError('');
    try {
      const { data } = await ordersApi.create({
        address_id: addressId, payment_method: payment, coupon_code: coupon || null,
        is_gift: isGift, gift_message: giftMessage || null,
        scheduled_delivery_date: schedule.date || null, delivery_slot: schedule.slot || null,
      });
      await refresh();
      navigate(`/orders/${data.order_number}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Order failed');
      setPlacing(false);
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="md:col-span-2 space-y-5">
        <h1 className="text-2xl font-bold">Checkout</h1>

        <section className="card p-5">
          <h2 className="font-bold">Delivery address</h2>
          <div className="mt-3 space-y-2">
            {addresses.map((a) => (
              <label key={a.id} className={`flex cursor-pointer gap-3 rounded-lg border p-3 ${addressId === a.id ? 'border-brand-500 bg-brand-50' : 'border-slate-200'}`}>
                <input type="radio" checked={addressId === a.id} onChange={() => setAddressId(a.id)} />
                <span className="text-sm">{a.recipient_name}, {a.address_line1}, {a.city}, {a.state} - {a.postal_code} · {a.phone}</span>
              </label>
            ))}
          </div>
          <button onClick={() => setShowNew(!showNew)} className="mt-2 text-sm text-brand-600">+ Add new address</button>
          {showNew && (
            <form onSubmit={saveAddress} className="mt-3 grid grid-cols-2 gap-2">
              {[['recipient_name', 'Recipient name'], ['phone', 'Phone'], ['address_line1', 'Address'], ['city', 'City'], ['state', 'State'], ['postal_code', 'PIN code']].map(([k, label]) => (
                <input key={k} required placeholder={label} value={newAddr[k]}
                  onChange={(e) => setNewAddr({ ...newAddr, [k]: e.target.value })} className="input" />
              ))}
              <button className="btn-primary col-span-2">Save address</button>
            </form>
          )}
        </section>

        <section className="card p-5">
          <h2 className="font-bold">Gifting</h2>
          <label className="mt-2 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isGift} onChange={(e) => setIsGift(e.target.checked)} /> This is a gift
          </label>
          {isGift && (
            <textarea value={giftMessage} onChange={(e) => setGiftMessage(e.target.value)}
              placeholder="Your personal gift message…" className="input mt-2" rows={2} />
          )}
        </section>

        <section className="card p-5">
          <h2 className="font-bold">Schedule delivery</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <input type="date" value={schedule.date} onChange={(e) => setSchedule({ ...schedule, date: e.target.value })} className="input max-w-[180px]" />
            <select value={schedule.slot} onChange={(e) => setSchedule({ ...schedule, slot: e.target.value })} className="input max-w-[180px]">
              <option value="">Any time slot</option>
              {SLOTS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </section>

        <section className="card p-5">
          <h2 className="font-bold">Payment</h2>
          <div className="mt-2 flex gap-3">
            {[['cod', 'Cash on Delivery'], ['card', 'Card (mock)'], ['upi', 'UPI (mock)']].map(([v, label]) => (
              <label key={v} className={`btn ${payment === v ? 'btn-primary' : 'btn-ghost'} text-sm`}>
                <input type="radio" className="hidden" checked={payment === v} onChange={() => setPayment(v)} /> {label}
              </label>
            ))}
          </div>
        </section>
      </div>

      <div className="card h-fit p-5">
        <h2 className="font-bold">Order summary</h2>
        <div className="mt-3 flex gap-2">
          <input value={coupon} onChange={(e) => setCoupon(e.target.value.toUpperCase())} placeholder="Coupon code" className="input" />
          <button onClick={applyCoupon} className="btn-ghost text-sm">Apply</button>
        </div>
        {couponMsg && <p className="mt-1 text-xs text-brand-600">{couponMsg}</p>}
        <div className="mt-4 space-y-1 text-sm">
          <div className="flex justify-between"><span>Subtotal</span><span>{inr(subtotal)}</span></div>
          <div className="flex justify-between text-green-600"><span>Discount</span><span>-{inr(discount)}</span></div>
          <div className="flex justify-between"><span>Shipping</span><span>{shipping === 0 ? 'FREE' : inr(shipping)}</span></div>
          <div className="mt-2 flex justify-between border-t pt-2 font-bold"><span>Total</span><span>{inr(total)}</span></div>
        </div>
        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
        <button onClick={placeOrder} disabled={placing} className="btn-primary mt-4 w-full">
          {placing ? 'Placing…' : 'Place order'}
        </button>
      </div>
    </div>
  );
}
