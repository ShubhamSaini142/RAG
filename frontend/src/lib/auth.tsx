"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  api,
  clearToken,
  getToken,
  registerUnauthorizedHandler,
  setToken,
} from "./api";
import type { Me, Org, Role } from "./types";

const ORG_KEY = "rag_org_id";

type AuthContextValue = {
  loading: boolean;
  me: Me | null;
  activeOrg: Org | null;
  role: Role | null;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    name?: string;
    org_name?: string;
  }) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [loading, setLoading] = React.useState(true);
  const [me, setMe] = React.useState<Me | null>(null);
  const [orgId, setOrgId] = React.useState<string | null>(null);

  const loadMe = React.useCallback(async () => {
    const data = await api.me();
    setMe(data);
    return data;
  }, []);

  const logout = React.useCallback(() => {
    clearToken();
    localStorage.removeItem(ORG_KEY);
    setMe(null);
    setOrgId(null);
    router.replace("/login");
  }, [router]);

  // Boot: if we have a token, resolve the current user; otherwise stay logged out.
  React.useEffect(() => {
    registerUnauthorizedHandler(() => {
      setMe(null);
      setOrgId(null);
      router.replace("/login");
    });

    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    setOrgId(localStorage.getItem(ORG_KEY));
    loadMe()
      .catch(() => {
        clearToken();
        localStorage.removeItem(ORG_KEY);
      })
      .finally(() => setLoading(false));

    return () => registerUnauthorizedHandler(null);
  }, [loadMe, router]);

  const finishAuth = React.useCallback(
    async (token: string, org: string) => {
      setToken(token);
      localStorage.setItem(ORG_KEY, org);
      setOrgId(org);
      await loadMe();
    },
    [loadMe],
  );

  const login = React.useCallback(
    async (email: string, password: string) => {
      const res = await api.login({ email, password });
      await finishAuth(res.access_token, res.org_id);
    },
    [finishAuth],
  );

  const register = React.useCallback(
    async (input: { email: string; password: string; name?: string; org_name?: string }) => {
      const res = await api.register(input);
      await finishAuth(res.access_token, res.org_id);
    },
    [finishAuth],
  );

  const activeOrg =
    me?.orgs.find((o) => o.id === orgId) ?? me?.orgs[0] ?? null;
  const role = activeOrg?.role ?? null;
  const isAdmin = role === "owner" || role === "admin";

  const value: AuthContextValue = {
    loading,
    me,
    activeOrg,
    role,
    isAdmin,
    login,
    register,
    logout,
    refresh: async () => {
      await loadMe();
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
