export type MemoryCategory =
  | "identity"
  | "preference"
  | "goal"
  | "project"
  | "relationship"
  | "emotional"
  | "behavior";

export interface Memory {
  id: string;
  category: MemoryCategory;
  text: string;
  importance?: number;
  created_at?: string;
  createdAt?: string;
  updated_at?: string;
  updatedAt?: string;
  timestamp?: string | number;
}

export interface MemoryTransaction {
  id: string;
  type?: string;
  action?: string;
  memoryId?: string;
  text?: string;
  category?: MemoryCategory;
  data?: any;
  timestamp?: number;
}
