"use client";

import { create } from "zustand";
import { api, setToken } from "@/lib/api";

interface Me {
  id: string;
  email: string;
  full_name: string | null;
  onboarding_completed: boolean;
  is_demo: boolean;
  is_admin: boolean;
}

interface AuthState {
  user: Me | null;
  loading: boolean;
  hydrate: () => Promise<void>;
  login: (email: string, password: string) => Promise<Me>;
  register: (email: string, password: string, fullName?: string) => Promise<Me>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,

  hydrate: async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("lingoadapt_token") : null;
    if (!token) {
      set({ loading: false });
      return;
    }
    try {
      const me = await api.get<Me>("/api/v1/auth/me");
      set({ user: me, loading: false });
    } catch {
      setToken(null);
      set({ user: null, loading: false });
    }
  },

  login: async (email, password) => {
    const res = await api.post<{ access_token: string; user_id: string; onboarding_completed: boolean }>(
      "/api/v1/auth/login",
      { email, password }
    );
    setToken(res.access_token);
    const me = await api.get<Me>("/api/v1/auth/me");
    set({ user: me });
    return me;
  },

  register: async (email, password, fullName) => {
    const res = await api.post<{ access_token: string; user_id: string; onboarding_completed: boolean }>(
      "/api/v1/auth/register",
      { email, password, full_name: fullName }
    );
    setToken(res.access_token);
    const me = await api.get<Me>("/api/v1/auth/me");
    set({ user: me });
    return me;
  },

  logout: () => {
    setToken(null);
    set({ user: null });
  },
}));
