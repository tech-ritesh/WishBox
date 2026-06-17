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
  const [invoice, setInvoice] = useState(null);
  const [shipment, setShipment] = useState(null);
  const [returns, setReturns] = useState([]);
  const [showReturn, setShowReturn] = useState(false);
  const [returnForm, setReturnForm] = useState({ kind: 'return', reason: '', items: {} });
  const [returnMsg, setReturnMsg] = useState('');

  const loadOrder = () => ordersApi.get(orderNumber).then((r) => setOrder(r.data));
  useEffect(() => {
    loadOrder();
    ordersApi.shipment(orderNumber).then((r) => setShipment(r.data)).catch(() => {});
    ordersApi.listReturns(orderNumber).then((r) => setReturns(r.data)).catch(() => {});
  }, [orderNumber]);
  const loadInvoice = () => ordersApi.invoice(orderNumber).then((r) => setInvoice(r.data));
  if (!order) return <Spinner />;

  const submitReturn = async (e) => {
    e.preventDefault();
    setReturnMsg('');
    const items = Object.entries(returnForm.items)
      .filter(([, q]) => Number(q) > 0)
      .map(([order_item_id, q]) => ({ order_item_id: Number(order_item_id), quantity: Number(q) }));
    if (!items.length) { setReturnMsg('Select at least one item and quantity.'); return; }
    try {
      await ordersApi.requestReturn(orderNumber, { kind: returnForm.kind, reason: returnForm.reason, items });
      const r = await ordersApi.listReturns(orderNumber);
      setReturns(r.data); setShowReturn(false);
    } catch (err) { setReturnMsg(err.response?.data?.detail || 'Could not submit request'); }
  };

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
          {shipment && (
            <div className="mt-3 border-t pt-3 text-sm">
              <p className="text-slate-600">{shipment.carrier} · <b>{shipment.tracking_number}</b> · {prettyStatus(shipment.status)}
                {shipment.estimated_delivery && <> · ETA {shipment.estimated_delivery}</>}</p>
              {shipment.events?.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-slate-500">
                  {shipment.events.map((e) => (
                    <li key={e.id}>{new Date(e.created_at).toLocaleString()} — {prettyStatus(e.status)}{e.location ? ` @ ${e.location}` : ''}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {(order.status === 'delivered' || returns.length > 0) && (
        <div className="card mt-4 p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-bold">Returns & exchanges</h2>
            {order.status === 'delivered' && returns.every((r) => ['rejected', 'completed'].includes(r.status)) && (
              <button onClick={() => setShowReturn(!showReturn)} className="btn-ghost text-sm">Request return/exchange</button>
            )}
          </div>
          {returns.map((r) => (
            <div key={r.id} className="mt-2 rounded-lg border border-slate-200 p-3 text-sm">
              <div className="flex justify-between"><span>#{r.id} · {r.kind}</span><span className="badge bg-slate-100">{prettyStatus(r.status)}</span></div>
              <p className="text-slate-500">Reason: {r.reason}{Number(r.refund_amount) > 0 && <> · Refund {inr(r.refund_amount)}</>}</p>
              {r.resolution_note && <p className="text-xs text-slate-400">Note: {r.resolution_note}</p>}
            </div>
          ))}
          {showReturn && (
            <form onSubmit={submitReturn} className="mt-3 space-y-2 border-t pt-3 text-sm">
              <div className="flex gap-3">
                {['return', 'exchange'].map((k) => (
                  <label key={k} className={`btn ${returnForm.kind === k ? 'btn-primary' : 'btn-ghost'} text-sm`}>
                    <input type="radio" className="hidden" checked={returnForm.kind === k}
                      onChange={() => setReturnForm({ ...returnForm, kind: k })} /> {k}
                  </label>
                ))}
              </div>
              <input required placeholder="Reason (e.g. damaged, wrong item)" value={returnForm.reason}
                onChange={(e) => setReturnForm({ ...returnForm, reason: e.target.value })} className="input" />
              <div className="space-y-1">
                {order.items.map((it) => (
                  <div key={it.id} className="flex items-center justify-between gap-2">
                    <span>{it.product_name} (max {it.quantity})</span>
                    <input type="number" min={0} max={it.quantity} placeholder="0" className="input max-w-[80px]"
                      value={returnForm.items[it.id] || ''}
                      onChange={(e) => setReturnForm({ ...returnForm, items: { ...returnForm.items, [it.id]: e.target.value } })} />
                  </div>
                ))}
              </div>
              {returnMsg && <p className="text-red-500">{returnMsg}</p>}
              <button className="btn-primary">Submit request</button>
            </form>
          )}
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

      <div className="card mt-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-bold">Tax invoice (GST)</h2>
          <div className="flex gap-2">
            {!invoice && <button onClick={loadInvoice} className="btn-ghost text-sm">View invoice</button>}
            {invoice && <button onClick={() => window.print()} className="btn-ghost text-sm">Print</button>}
          </div>
        </div>
        {invoice && (
          <div className="mt-3 text-sm">
            <div className="flex flex-wrap justify-between text-slate-500">
              <span>Invoice <b>{invoice.invoice_number}</b></span>
              <span>Seller GSTIN: {invoice.seller_gstin}</span>
              <span>Place of supply: {invoice.place_of_supply}</span>
            </div>
            <div className="mt-3 space-y-1 border-t pt-2">
              <div className="flex justify-between"><span>Taxable value</span><span>{inr(invoice.taxable_value)}</span></div>
              {Number(invoice.cgst) > 0 && <div className="flex justify-between"><span>CGST ({Number(invoice.gst_percent) / 2}%)</span><span>{inr(invoice.cgst)}</span></div>}
              {Number(invoice.sgst) > 0 && <div className="flex justify-between"><span>SGST ({Number(invoice.gst_percent) / 2}%)</span><span>{inr(invoice.sgst)}</span></div>}
              {Number(invoice.igst) > 0 && <div className="flex justify-between"><span>IGST ({Number(invoice.gst_percent)}%)</span><span>{inr(invoice.igst)}</span></div>}
              {Number(invoice.discount_amount) > 0 && <div className="flex justify-between text-green-600"><span>Discount</span><span>-{inr(invoice.discount_amount)}</span></div>}
              <div className="flex justify-between"><span>Shipping</span><span>{Number(invoice.shipping_fee) === 0 ? 'FREE' : inr(invoice.shipping_fee)}</span></div>
              <div className="flex justify-between border-t pt-1 font-bold"><span>Total (incl. GST)</span><span>{inr(invoice.total_amount)}</span></div>
            </div>
            <p className="mt-2 text-xs text-slate-400">Prices are GST-inclusive; tax shown is the GST component of the goods value.</p>
          </div>
        )}
      </div>
    </div>
  );
}
