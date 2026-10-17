import { createContext, useContext, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../api/client";
import type { Me } from "../api/types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

async function fetchMe(): Promise<Me | null> {
  try {
    return await api<Me>("/me");
  } catch (e) {
    // DRF SessionAuthentication отвечает 403 без сессии
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return null;
    throw e;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: 5 * 60_000 });
  // Данные предыдущего пользователя не должны остаться в кэше после смены сессии.
  const dropUserData = () => qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });

  const value: AuthState = {
    me: data ?? null,
    loading: isLoading,
    async login(username, password) {
      const me = await api<Me>("/auth/login", { method: "POST", body: { username, password } });
      dropUserData();
      qc.setQueryData(["me"], me);
    },
    async logout() {
      await api("/auth/logout", { method: "POST" });
      dropUserData();
      qc.setQueryData(["me"], null);
    },
    can: (permission) => !!data?.permissions.includes(permission),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
