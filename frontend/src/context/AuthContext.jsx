import { createContext, useContext, useEffect, useState } from 'react';
import { authApi } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (localStorage.getItem('wb_access')) {
      authApi.profile().then((r) => setUser(r.data)).catch(() => localStorage.clear()).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const persist = (data) => {
    localStorage.setItem('wb_access', data.access_token);
    localStorage.setItem('wb_refresh', data.refresh_token);
    localStorage.setItem('wb_role', data.role);
  };

  const login = async (email, password) => {
    const { data } = await authApi.login({ email, password });
    persist(data);
    const me = await authApi.profile();
    setUser(me.data);
    return me.data;
  };

  const register = async (payload) => {
    const { data } = await authApi.register(payload);
    persist(data);
    const me = await authApi.profile();
    setUser(me.data);
    return me.data;
  };

  const logout = () => {
    localStorage.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAdmin: user?.role === 'admin', isStaff: ['admin', 'staff'].includes(user?.role) }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
