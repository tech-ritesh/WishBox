// Display currency is selectable; prices are stored/charged in INR and converted
// for display only. The active currency is held module-side so the widely-used
// inr() helper needs no call-site changes.
let _currency = (() => {
  try { return JSON.parse(localStorage.getItem('wb_currency')) || { code: 'INR', symbol: '₹', rate: 1 }; }
  catch { return { code: 'INR', symbol: '₹', rate: 1 }; }
})();

export const setCurrency = (c) => {
  _currency = c;
  try { localStorage.setItem('wb_currency', JSON.stringify(c)); } catch { /* ignore */ }
};
export const getCurrency = () => _currency;

export const inr = (v) => {
  const amount = Number(v || 0) * (_currency.rate || 1);
  if (_currency.code === 'INR') {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
  }
  return `${_currency.symbol}${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

export const STATUS_COLORS = {
  pending: 'bg-amber-100 text-amber-700',
  confirmed: 'bg-blue-100 text-blue-700',
  packed: 'bg-indigo-100 text-indigo-700',
  shipped: 'bg-purple-100 text-purple-700',
  out_for_delivery: 'bg-cyan-100 text-cyan-700',
  delivered: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
  refunded: 'bg-slate-200 text-slate-700',
};

export const prettyStatus = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
