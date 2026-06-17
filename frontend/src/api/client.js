import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Attach access token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('wb_access');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401 (once)
let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    const refresh = localStorage.getItem('wb_refresh');
    if (error.response?.status === 401 && refresh && !original._retried) {
      original._retried = true;
      try {
        refreshing = refreshing || axios.post('/api/v1/auth/refresh', { refresh_token: refresh });
        const { data } = await refreshing;
        refreshing = null;
        localStorage.setItem('wb_access', data.access_token);
        localStorage.setItem('wb_refresh', data.refresh_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch (e) {
        refreshing = null;
        localStorage.clear();
      }
    }
    return Promise.reject(error);
  }
);

export default api;

export const authApi = {
  register: (d) => api.post('/auth/register', d),
  login: (d) => api.post('/auth/login-json', d),
  profile: () => api.get('/auth/profile'),
  updateProfile: (d) => api.put('/auth/profile', d),
  addresses: () => api.get('/auth/addresses'),
  addAddress: (d) => api.post('/auth/addresses', d),
  deleteAddress: (id) => api.delete(`/auth/addresses/${id}`),
};
export const productsApi = {
  list: (params) => api.get('/products', { params }),
  detail: (slug) => api.get(`/products/${slug}`),
  quickDelivery: () => api.get('/products/quick-delivery'),
};
export const categoriesApi = {
  list: () => api.get('/categories'),
  tree: () => api.get('/categories/tree'),
};
export const cartApi = {
  get: () => api.get('/cart'),
  add: (d) => api.post('/cart', d),
  update: (id, d) => api.put(`/cart/${id}`, d),
  remove: (id) => api.delete(`/cart/${id}`),
  clear: () => api.delete('/cart'),
};
export const ordersApi = {
  create: (d) => api.post('/orders', d),
  list: () => api.get('/orders'),
  get: (num) => api.get(`/orders/${num}`),
};
export const couponsApi = { validate: (code, subtotal) => api.post('/coupons/validate', { code, subtotal }) };
export const paymentsApi = {
  config: () => api.get('/payments/config'),
  create: (orderNumber) => api.post('/payments/create', { order_number: orderNumber }),
  verify: (d) => api.post('/payments/verify', d),
};
export const reviewsApi = {
  list: (pid) => api.get(`/reviews/${pid}`),
  create: (d) => api.post('/reviews', d),
};
export const wishlistApi = {
  list: () => api.get('/wishlist'),
  add: (pid) => api.post(`/wishlist/${pid}`),
  remove: (pid) => api.delete(`/wishlist/${pid}`),
};
export const remindersApi = {
  list: () => api.get('/reminders'),
  create: (d) => api.post('/reminders', d),
  remove: (id) => api.delete(`/reminders/${id}`),
};
export const notificationsApi = {
  list: () => api.get('/notifications'),
  read: (id) => api.post(`/notifications/${id}/read`),
};
export const hampersApi = {
  templates: () => api.get('/hampers/templates'),
  mine: () => api.get('/hampers'),
  create: (d) => api.post('/hampers', d),
};
export const recommendationsApi = { smart: (d) => api.post('/recommendations/smart', d) };
export const adminApi = {
  analytics: () => api.get('/admin/analytics'),
  customers: () => api.get('/admin/customers'),
  orders: () => api.get('/admin/orders'),
  updateOrder: (id, d) => api.put(`/admin/orders/${id}`, d),
  createProduct: (d) => api.post('/admin/products', d),
  updateProduct: (id, d) => api.put(`/admin/products/${id}`, d),
  deleteProduct: (id) => api.delete(`/admin/products/${id}`),
  coupons: () => api.get('/admin/coupons'),
  createCoupon: (d) => api.post('/admin/coupons', d),
  deleteCoupon: (id) => api.delete(`/admin/coupons/${id}`),
  vendors: () => api.get('/admin/vendors'),
  lowStock: () => api.get('/admin/inventory/low-stock'),
};
