import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authApi, ordersApi, couponsApi, paymentsApi, walletApi } from '../api/client';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { inr } from '../utils/format';

const SLOTS = ['09:00-12:00', '12:00-15:00', '15:00-18:00', '18:00-21:00', 'midnight'];

export default function Checkout() {
  const { cart, refresh, clear } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [addresses, setAddresses] = useState([]);
  const [addressId, setAddressId] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [newAddr, setNewAddr] = useState({ recipient_name: '', phone: '', address_line1: '', city: '', state: '', postal_code: '' });
  const [guest, setGuest] = useState({ email: '', full_name: '' });
  const [payment, setPayment] = useState('cod');
  const [coupon, setCoupon] = useState('');
  const [discount, setDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState('');
  const [isGift, setIsGift] = useState(false);
  const [giftMessage, setGiftMessage] = useState('');
  const [schedule, setSchedule] = useState({ date: '', slot: '' });
  const [error, setError] = useState('');
  const [placing, setPlacing] = useState(false);
  const [placedNumber, setPlacedNumber] = useState('');
  const [walletBalance, setWalletBalance] = useState(0);
  const [useWallet, setUseWallet] = useState(false);

  useEffect(() => { if (user) walletApi.get().then((r) => setWalletBalance(Number(r.data.balance))).catch(() => {}); }, [user]);

  const loadAddresses = () => authApi.addresses().then((r) => {
    setAddresses(r.data);
    const def = r.data.find((a) => a.is_default) || r.data[0];
    if (def) setAddressId(def.id);
    setShowNew(r.data.length === 0);
  });
  useEffect(() => { if (user) loadAddresses(); }, [user]);

  const subtotal = Number(cart.subtotal);
  const afterDiscount = Math.max(subtotal - discount, 0);
  const walletRedeem = useWallet ? Math.min(walletBalance, afterDiscount) : 0;
  const afterWallet = Math.max(afterDiscount - walletRedeem, 0);
  const shipping = afterWallet >= 999 ? 0 : (subtotal > 0 ? 49 : 0);
  const total = afterWallet + shipping;

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

  const loadRazorpay = () => new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });

  // Runs the online gateway for an already-created (pending) order.
  const payOnline = async (orderNumber) => {
    const { data: pay } = await paymentsApi.create(orderNumber);
    if (pay.provider === 'mock') {
      // Local mock gateway: it handed us a valid payment_id + signature.
      await paymentsApi.verify({
        provider_order_id: pay.provider_order_id,
        provider_payment_id: pay.mock.payment_id,
        provider_signature: pay.mock.signature,
      });
      return;
    }
    // Real Razorpay checkout
    const ok = await loadRazorpay();
    if (!ok) throw new Error('Could not load payment gateway');
    await new Promise((resolve, reject) => {
      const rzp = new window.Razorpay({
        key: pay.key_id,
        amount: pay.amount,
        currency: pay.currency,
        name: 'WishBox',
        order_id: pay.provider_order_id,
        handler: async (resp) => {
          try {
            await paymentsApi.verify({
              provider_order_id: resp.razorpay_order_id,
              provider_payment_id: resp.razorpay_payment_id,
              provider_signature: resp.razorpay_signature,
            });
            resolve();
          } catch (e) { reject(e); }
        },
        modal: { ondismiss: () => reject(new Error('Payment cancelled')) },
      });
      rzp.open();
    });
  };

  const placeGuestOrder = async () => {
    if (!guest.email || !guest.full_name) { setError('Please enter your name and email'); return; }
    const a = newAddr;
    if (!a.address_line1 || !a.city || !a.state || !a.postal_code) { setError('Please complete the delivery address'); return; }
    setPlacing(true); setError('');
    try {
      const { data } = await ordersApi.createGuest({
        email: guest.email, full_name: guest.full_name, phone: a.phone || null,
        recipient_name: a.recipient_name || guest.full_name,
        address_line1: a.address_line1, city: a.city, state: a.state, postal_code: a.postal_code,
        payment_method: 'cod', coupon_code: coupon || null,
        is_gift: isGift, gift_message: giftMessage || null,
        scheduled_delivery_date: schedule.date || null, delivery_slot: schedule.slot || null,
        items: cart.items.map((i) => ({
          product_id: i.product_id, variant_id: i.variant_id ?? null,
          quantity: i.quantity, customization_details: i.customization_details || null,
        })),
      });
      await clear();
      setPlacedNumber(data.order_number);
    } catch (err) {
      setError(err.response?.data?.detail || 'Order failed');
      setPlacing(false);
    }
  };

  const placeOrder = async () => {
    if (!user) return placeGuestOrder();
    if (!addressId) { setError('Please select an address'); return; }
    setPlacing(true); setError('');
    try {
      const { data } = await ordersApi.create({
        address_id: addressId, payment_method: payment, coupon_code: coupon || null,
        wallet_redeem: walletRedeem || 0,
        is_gift: isGift, gift_message: giftMessage || null,
        scheduled_delivery_date: schedule.date || null, delivery_slot: schedule.slot || null,
      });
      if (payment !== 'cod') {
        await payOnline(data.order_number);  // confirms the order on success
      }
      await refresh();
      navigate(`/orders/${data.order_number}`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Order failed');
      setPlacing(false);
    }
  };

  if (placedNumber) {
    return (
      <div className="mx-auto max-w-lg text-center">
        <div className="card p-8">
          <p className="text-5xl">🎉</p>
          <h1 className="mt-3 text-2xl font-bold">Order placed!</h1>
          <p className="mt-2 text-slate-600">Your order number is <b>{placedNumber}</b>. A confirmation has been sent to <b>{guest.email}</b>.</p>
          <p className="mt-3 text-sm text-slate-500">Want to track it? <Link to="/register" className="text-brand-600">Create an account</Link> with this email to see your order history.</p>
          <Link to="/shop" className="btn-primary mt-5 inline-block">Continue shopping</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="md:col-span-2 space-y-5">
        <h1 className="text-2xl font-bold">Checkout</h1>

        {!user && (
          <section className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-bold">Contact</h2>
              <span className="text-sm text-slate-500">Have an account? <Link to="/login" className="text-brand-600">Log in</Link></span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <input required placeholder="Full name" value={guest.full_name}
                onChange={(e) => setGuest({ ...guest, full_name: e.target.value })} className="input" />
              <input required type="email" placeholder="Email" value={guest.email}
                onChange={(e) => setGuest({ ...guest, email: e.target.value })} className="input" />
            </div>
          </section>
        )}

        <section className="card p-5">
          <h2 className="font-bold">Delivery address</h2>
          {user ? (
            <>
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
            </>
          ) : (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {[['recipient_name', 'Recipient name'], ['phone', 'Phone'], ['address_line1', 'Address'], ['city', 'City'], ['state', 'State'], ['postal_code', 'PIN code']].map(([k, label]) => (
                <input key={k} placeholder={label} value={newAddr[k]}
                  onChange={(e) => setNewAddr({ ...newAddr, [k]: e.target.value })} className="input" />
              ))}
            </div>
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
          {user ? (
            <div className="mt-2 flex gap-3">
              {[['cod', 'Cash on Delivery'], ['card', 'Card (mock)'], ['upi', 'UPI (mock)']].map(([v, label]) => (
                <label key={v} className={`btn ${payment === v ? 'btn-primary' : 'btn-ghost'} text-sm`}>
                  <input type="radio" className="hidden" checked={payment === v} onChange={() => setPayment(v)} /> {label}
                </label>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Cash on Delivery. <Link to="/login" className="text-brand-600">Log in</Link> to pay online (card / UPI).</p>
          )}
        </section>
      </div>

      <div className="card h-fit p-5">
        <h2 className="font-bold">Order summary</h2>
        <div className="mt-3 flex gap-2">
          <input value={coupon} onChange={(e) => setCoupon(e.target.value.toUpperCase())} placeholder="Coupon code" className="input" />
          <button onClick={applyCoupon} className="btn-ghost text-sm">Apply</button>
        </div>
        {couponMsg && <p className="mt-1 text-xs text-brand-600">{couponMsg}</p>}
        {user && walletBalance > 0 && (
          <label className="mt-3 flex items-center gap-2 rounded-lg bg-brand-50 p-2 text-sm">
            <input type="checkbox" checked={useWallet} onChange={(e) => setUseWallet(e.target.checked)} />
            Use wallet credit ({inr(walletBalance)} available)
          </label>
        )}
        <div className="mt-4 space-y-1 text-sm">
          <div className="flex justify-between"><span>Subtotal</span><span>{inr(subtotal)}</span></div>
          <div className="flex justify-between text-green-600"><span>Discount</span><span>-{inr(discount)}</span></div>
          {walletRedeem > 0 && <div className="flex justify-between text-green-600"><span>Wallet credit</span><span>-{inr(walletRedeem)}</span></div>}
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
