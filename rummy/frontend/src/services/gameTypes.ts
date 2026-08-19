export interface PlayerState {
  id: string;
  name: string;
  seat: number;
  chips: number;
  status: string;
  deal_points: number;
  total_score: number;
  eliminated: boolean;
  hand_count: number;
}

export interface TableState {
  table_id: string;
  phase: string;
  deal_number: number;
  num_deals: number;
  pool_limit: number | null;
  turn: string | null;
  wild_joker: string | null;
  wild_rank: number | null;
  top_discard: string | null;
  stock_count: number;
  discard_count: number;
  winner_id: string | null;
  players: PlayerState[];
}

export type ServerMessage =
  | { type: "state"; state: TableState }
  | { type: "hand"; cards: string[] }
  | { type: "event"; event: string; [k: string]: unknown }
  | { type: "error"; message: string };

export interface ClientAction {
  action: "join" | "start" | "draw" | "discard" | "declare" | "drop" | "sync";
  source?: "stock" | "discard";
  card?: string;
  groups?: string[][];
  // Injected automatically by useGameSocket's send() — set it yourself here, it'll
  // be overwritten.
  action_id?: string;
}
