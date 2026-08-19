import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export const api = axios.create({ baseURL: API_BASE });

// Attach the bearer token from localStorage-free in-memory store.
let accessToken: string | null = null;
export function setAccessToken(token: string | null) {
  accessToken = token;
}
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// ---- typed API surface ---------------------------------------------------------------
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export interface Wallet {
  real_paise: number;
  bonus_paise: number;
  virtual_chips: number;
}
export interface Transaction {
  id: string;
  txn_type: string;
  kind: string;
  amount_paise: number;
  balance_after: number;
  reference: string;
  created_at: string;
}
export interface Withdrawal {
  id: string;
  amount_paise: number;
  status: string;
  payout_reference: string;
  created_at: string;
}
export interface DepositOrder {
  deposit_id: string;
  razorpay_order_id: string;
  razorpay_key_id: string;
  amount_paise: number;
  currency: string;
}
export interface Table {
  id: string;
  name: string;
  mode: string;
  status: string;
  max_players: number;
  num_deals: number;
  entry_fee_paise: number;
  pool_limit: number | null;
  turn_seconds: number;
  online_players: number;
  is_private: boolean;
  join_code: string | null;
}

export const AuthApi = {
  register: (email: string, username: string, password: string, is18: boolean) =>
    api.post("/auth/register", { email, username, password, is_18_plus: is18 }),
  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
};

export const WalletApi = {
  get: () => api.get<Wallet>("/wallet").then((r) => r.data),
  transactions: () => api.get<Transaction[]>("/wallet/transactions").then((r) => r.data),
  withdrawals: () => api.get<Withdrawal[]>("/wallet/withdrawals").then((r) => r.data),
  withdraw: (amount_paise: number) =>
    api.post<Withdrawal>("/wallet/withdraw", { amount_paise }).then((r) => r.data),
};

export const PaymentsApi = {
  deposit: (amount_paise: number) =>
    api.post<DepositOrder>("/payments/deposit", { amount_paise }).then((r) => r.data),
};

export const TableApi = {
  list: () => api.get<Table[]>("/tables").then((r) => r.data),
  get: (id: string) => api.get<Table>(`/tables/${id}`).then((r) => r.data),
  getByCode: (code: string) => api.get<Table>(`/tables/code/${code}`).then((r) => r.data),
  create: (body: Partial<Table>) => api.post<Table>("/tables", body).then((r) => r.data),
};
