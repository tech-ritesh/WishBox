import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { CheckCircle2, Circle, Gift } from 'lucide-react';
import { ordersApi } from '../api/client';
import { inr, STATUS_COLORS, prettyStatus } from '../utils/format';
import { Spinner } from '../components/Layout';

const FLOW = ['pending', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered'];

export default function OrderTracking() {
  const { orderNumber } = useParams();
  const [order, setOrder] = useState(null);
  useEffect(() => { ordersApi.get(orderNumber).then((r) => setOrder(r.data)); }, [orderNumber]);
  if (!order) return <Spinner />;

  const reached = FLOW.indexOf(order.status);

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/orders" className="text-sm text-brand-600">← All orders</Link>
      <div className="mt-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{order.order_number}</h1>
        <span className={`badge ${STATUS_COLORS[order.status]}`}>{prettyStatus(order.status)}</span>
      </div>

      {order.status !== 'cancelled' && (
        <div className="card mt-4 p-5">
          <h2 className="mb-4 font-bold">Tracking</h2>
          <div className="flex justify-between">
            {FLOW.map((s, i) => (
              <div key={s} className="flex flex-1 flex-col items-center text-center">
                {i <= reached ? <CheckCircle2 className="text-brand-600" /> : <Circle className="text-slate-300" />}
                <span className="mt-1 text-[11px] text-slate-500">{prettyStatus(s)}</span>
              </div>
            ))}
          </div>
          {order.tracking_code && <p className="mt-3 text-sm text-slate-500">Tracking code: <b>{order.tracking_code}</b></p>}
          {order.scheduled_delivery_date && <p className="text-sm text-slate-500">Scheduled: {order.scheduled_delivery_date} {order.delivery_slot}</p>}
        </div>
      )}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="card p-5">
          <h2 className="mb-2 font-bold">Items</h2>
          {order.items.map((it) => (
            <div key={it.id} className="py-1 text-sm">
              <div className="flex justify-between">
                <span>{it.product_name} × {it.quantity}</span>
                <span>{inr(Number(it.unit_price) * it.quantity)}</span>
              </div>
              {it.customization_details?.message && (
                <p className="text-xs text-brand-600">✨ “{it.customization_details.message}”</p>
              )}
            </div>
          ))}
          <div className="mt-2 space-y-1 border-t pt-2 text-sm">
            <div className="flex justify-between"><span>Subtotal</span><span>{inr(order.subtotal)}</span></div>
            <div className="flex justify-between text-green-600"><span>Discount</span><span>-{inr(order.discount_amount)}</span></div>
            <div className="flex justify-between"><span>Shipping</span><span>{Number(order.shipping_fee) === 0 ? 'FREE' : inr(order.shipping_fee)}</span></div>
            <div className="flex justify-between font-bold"><span>Total</span><span>{inr(order.total_amount)}</span></div>
          </div>
        </div>
        <div className="card p-5">
          <h2 className="mb-2 font-bold">Delivery</h2>
          <p className="text-sm text-slate-600">{order.recipient_name}<br />{order.ship_address_line1}<br />{order.ship_city}, {order.ship_state} - {order.ship_postal_code}<br />{order.recipient_phone}</p>
          {order.is_gift && (
            <p className="mt-3 flex items-start gap-2 rounded-lg bg-pink-50 p-2 text-sm text-pink-700">
              <Gift size={16} /> {order.gift_message || 'Gift wrapped'}
            </p>
          )}
          <h3 className="mt-4 mb-1 text-sm font-semibold">History</h3>
          <ul className="space-y-1 text-xs text-slate-500">
            {order.history.map((h) => (
              <li key={h.id}>{new Date(h.created_at).toLocaleString()} — {prettyStatus(h.status)} {h.note && `(${h.note})`}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
