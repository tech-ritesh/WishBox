import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { cartApi } from '../api/client';
import { useAuth } from './AuthContext';

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const { user } = useAuth();
  const [cart, setCart] = useState({ items: [], subtotal: 0, item_count: 0 });

  const refresh = useCallback(async () => {
    if (!user) {
      setCart({ items: [], subtotal: 0, item_count: 0 });
      return;
    }
    try {
      const { data } = await cartApi.get();
      setCart(data);
    } catch { /* ignore */ }
  }, [user]);

  useEffect(() => { refresh(); }, [refresh]);

  const add = async (productId, quantity = 1, customization = null, variantId = null) => {
    const { data } = await cartApi.add({
      product_id: productId, variant_id: variantId, quantity, customization_details: customization,
    });
    setCart(data);
  };
  const update = async (id, quantity) => { const { data } = await cartApi.update(id, { quantity }); setCart(data); };
  const remove = async (id) => { const { data } = await cartApi.remove(id); setCart(data); };
  const clear = async () => { await cartApi.clear(); refresh(); };

  return (
    <CartContext.Provider value={{ cart, add, update, remove, clear, refresh }}>
      {children}
    </CartContext.Provider>
  );
}

export const useCart = () => useContext(CartContext);
