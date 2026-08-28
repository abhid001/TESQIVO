import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { http, ApiError } from "../api/client";
import type { Me } from "../api/types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthState>(null as unknown as AuthState);
export const useAuth = () => useContext(Ctx);

/** The current user's role in a project, or "system_admin", or null. */
export function useRole(projectId: string | undefined): string | null {
  const { me } = useAuth();
  if (!me || !projectId) return null;
  if (me.is_system_admin) return "system_admin";
  return me.memberships.find((m) => m.project_id === projectId)?.role ?? null;
}

export function canManageProject(role: string | null): boolean {
  return role === "system_admin" || role === "project_admin";
}
export function canAuthor(role: string | null): boolean {
  return role === "system_admin" || role === "project_admin" || role === "test_manager";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      setMe(await http.get<Me>("/auth/me"));
    } catch (e) {
      if (e instanceof ApiError && e.body.status === 401) setMe(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const login = async (username: string, password: string) => {
    const m = await http.post<Me>("/auth/session", { username, password });
    setMe(m);
  };

  const logout = async () => {
    await http.del("/auth/session");
    setMe(null);
  };

  return (
    <Ctx.Provider value={{ me, loading, login, logout, refresh }}>{children}</Ctx.Provider>
  );
}
