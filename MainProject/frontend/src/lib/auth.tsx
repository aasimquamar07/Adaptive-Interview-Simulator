import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { Meta, User } from "./types";

interface AuthCtx {
  user: User | null;
  meta: Meta | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.get()) { setUser(null); return; }
    try { setUser(await api<User>("/auth/me")); } catch { logout(); }
  }, [logout]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    Promise.all([
      api<Meta>("/meta").then(setMeta).catch(() => setMeta(null)),
      refreshUser(),
    ]).finally(() => setLoading(false));
  }, [logout, refreshUser]);

  const finish = (r: { token: string; user: User }) => { tokenStore.set(r.token); setUser(r.user); };
  const login = async (email: string, password: string) =>
    finish(await api("/auth/login", { method: "POST", json: { email, password } }));
  const signup = async (email: string, password: string, full_name: string) =>
    finish(await api("/auth/signup", { method: "POST", json: { email, password, full_name } }));

  return <Ctx.Provider value={{ user, meta, loading, login, signup, logout, refreshUser }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
