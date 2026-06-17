import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { cartApi } from '../api/client';
import { useAuth } from './AuthContext';

const CartContext = createContext(null);
const GUEST_KEY = 'wb_guest_cart';

const emptyCart = { items: [], subtotal: 0, item_count: 0 };

// --- Guest (anonymous) cart, persisted in localStorage ----------------------
function loadGuest() {
  try { return JSON.parse(localStorage.getItem(GUEST_KEY)) || []; } catch { return []; }
}
function saveGuest(rows) { localStorage.setItem(GUEST_KEY, JSON.stringify(rows)); }

function guestSummary(rows) {
  const items = rows.map((r, i) => ({
    id: r.key || `g${i}`,
    product_id: r.product.id,
    variant_id: r.variant?.id ?? null,
    quantity: r.quantity,
    customization_details: r.customization_details || null,
    product: r.product,
    variant: r.variant || null,
  }));
  const subtotal = rows.reduce((s, r) => {
    const base = Number(r.product.discount_price ?? r.product.price);
    const delta = r.variant ? Number(r.variant.price_delta) : 0;
    return s + (base + delta) * r.quantity;
  }, 0);
  return { items, subtotal, item_count: rows.reduce((s, r) => s + r.quantity, 0) };
}

export function CartProvider({ children }) {
  const { user } = useAuth();
  const [cart, setCart] = useState(emptyCart);

  const refreshGuest = useCallback(() => setCart(guestSummary(loadGuest())), []);

  const refresh = useCallback(async () => {
    if (!user) { refreshGuest(); return; }
    try {
      const { data } = await cartApi.get();
      setCart(data);
    } catch { /* ignore */ }
  }, [user, refreshGuest]);

  // On login, merge any guest cart into the server cart, then clear it.
  useEffect(() => {
    (async () => {
      if (user) {
        const rows = loadGuest();
        if (rows.length) {
          for (const r of rows) {
            try {
              await cartApi.add({
                product_id: r.product.id, variant_id: r.variant?.id ?? null,
                quantity: r.quantity, customization_details: r.customization_details || null,
              });
            } catch { /* skip unavailable */ }
          }
          localStorage.removeItem(GUEST_KEY);
        }
      }
      refresh();
    })();
  }, [user, refresh]);

  // add(product, quantity, customization, variant) — product is the full object.
  const add = async (product, quantity = 1, customization = null, variant = null) => {
    const productId = typeof product === 'object' ? product.id : product;
    const variantId = variant?.id ?? null;
    if (user) {
      const { data } = await cartApi.add({
        product_id: productId, variant_id: variantId, quantity, customization_details: customization,
      });
      setCart(data);
      return;
    }
    // Guest: store in localStorage (needs the product snapshot)
    const rows = loadGuest();
    const key = `${productId}:${variantId ?? ''}`;
    const existing = rows.find((r) => r.key === key && !customization);
    if (existing) existing.quantity += quantity;
    else rows.push({ key, product, variant: variant || null, quantity, customization_details: customization });
    saveGuest(rows);
    refreshGuest();
  };

  const update = async (id, quantity) => {
    if (user) { const { data } = await cartApi.update(id, { quantity }); setCart(data); return; }
    const rows = loadGuest().map((r) => (r.key === id ? { ...r, quantity } : r));
    saveGuest(rows); refreshGuest();
  };
  const remove = async (id) => {
    if (user) { const { data } = await cartApi.remove(id); setCart(data); return; }
    saveGuest(loadGuest().filter((r) => r.key !== id)); refreshGuest();
  };
  const clear = async () => {
    if (user) { await cartApi.clear(); refresh(); return; }
    localStorage.removeItem(GUEST_KEY); refreshGuest();
  };

  return (
    <CartContext.Provider value={{ cart, add, update, remove, clear, refresh, isGuest: !user }}>
      {children}
    </CartContext.Provider>
  );
}

export const useCart = () => useContext(CartContext);
