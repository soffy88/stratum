import { create } from "zustand";
import { apiClient, AuthRequiredError } from "@/lib/api-client";
import type { UserPublic, LoginResponse } from "@/lib/auth";

interface AuthState {
  user: UserPublic | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadCurrentUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,

  login: async (emailOrUsername, password) => {
    const data = await apiClient.post<LoginResponse>("/api/auth/login", {
      email_or_username: emailOrUsername,
      password,
    });
    apiClient.setAccessToken(data.access_token);
    set({ user: data.user });
  },

  register: async (email, username, password) => {
    await apiClient.post("/api/auth/register", { email, username, password });
  },

  logout: async () => {
    await apiClient.post("/api/auth/logout", {}).catch(() => {});
    apiClient.setAccessToken(null);
    set({ user: null });
  },

  loadCurrentUser: async () => {
    try {
      const user = await apiClient.get<UserPublic>("/api/auth/me");
      set({ user, isLoading: false });
    } catch (e) {
      if (e instanceof AuthRequiredError) {
        set({ user: null, isLoading: false });
      } else {
        set({ isLoading: false });
      }
    }
  },
}));
