import { create } from "zustand";
import { setAccessToken } from "../services/api";

interface AuthState {
  token: string | null;
  username: string | null;
  setAuth: (token: string, username: string) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  username: null,
  setAuth: (token, username) => {
    setAccessToken(token);
    set({ token, username });
  },
  logout: () => {
    setAccessToken(null);
    set({ token: null, username: null });
  },
}));
