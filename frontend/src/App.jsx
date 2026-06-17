import { Routes, Route } from 'react-router-dom';
import { PublicLayout, RequireAuth, RequireStaff } from './components/Layout';
import Home from './pages/Home';
import Shop from './pages/Shop';
import CategoryLanding from './pages/CategoryLanding';
import ProductDetails from './pages/ProductDetails';
import Cart from './pages/Cart';
import Checkout from './pages/Checkout';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import VerifyEmail from './pages/VerifyEmail';
import Account from './pages/Account';
import Orders from './pages/Orders';
import OrderTracking from './pages/OrderTracking';
import Wishlist from './pages/Wishlist';
import GiftFinder from './pages/GiftFinder';
import HamperBuilder from './pages/HamperBuilder';
import AdminLayout from './pages/admin/AdminLayout';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminProducts from './pages/admin/AdminProducts';
import AdminOrders from './pages/admin/AdminOrders';
import AdminCoupons from './pages/admin/AdminCoupons';

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/shop" element={<Shop />} />
        <Route path="/category/:slug" element={<CategoryLanding />} />
        <Route path="/product/:slug" element={<ProductDetails />} />
        <Route path="/cart" element={<Cart />} />
        <Route path="/gift-finder" element={<GiftFinder />} />
        <Route path="/hamper-builder" element={<HamperBuilder />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/checkout" element={<RequireAuth><Checkout /></RequireAuth>} />
        <Route path="/account" element={<RequireAuth><Account /></RequireAuth>} />
        <Route path="/orders" element={<RequireAuth><Orders /></RequireAuth>} />
        <Route path="/orders/:orderNumber" element={<RequireAuth><OrderTracking /></RequireAuth>} />
        <Route path="/wishlist" element={<RequireAuth><Wishlist /></RequireAuth>} />
      </Route>
      <Route path="/admin" element={<RequireStaff><AdminLayout /></RequireStaff>}>
        <Route index element={<AdminDashboard />} />
        <Route path="products" element={<AdminProducts />} />
        <Route path="orders" element={<AdminOrders />} />
        <Route path="coupons" element={<AdminCoupons />} />
      </Route>
      <Route path="*" element={<PublicLayout />} />
    </Routes>
  );
}
