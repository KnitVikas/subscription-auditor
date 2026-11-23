export interface Subscription {
  id: string;
  merchant_name: string;
  category: string | null;
  logo_url: string | null;
  amount: string;
  currency: string;
  cadence: string;
  next_renewal_at: string | null;
  status: string;
  confidence_score: string;
  flags: string[];
}

export interface CancelGuide {
  merchant_key: string;
  name: string;
  url: string;
  difficulty: string;
  steps: string[];
  known: boolean;
}

export interface Totals {
  monthly: string;
  yearly: string;
  currency: string;
  count: number;
}

export interface SubscriptionList {
  totals: Totals;
  subscriptions: Subscription[];
}

export interface Charge {
  occurred_at: string;
  amount: string;
}

export interface Transaction {
  id: string;
  source: string;
  raw_merchant: string;
  amount: string;
  currency: string;
  occurred_at: string;
}

export interface Connection {
  id: string;
  type: string;
  status: string;
  last_synced_at: string | null;
  sync_status: string;
  sync_total: number;
  sync_done: number;
  sync_error: string | null;
  sync_days: number | null;
}

export interface ConnectionList {
  connections: Connection[];
}

export interface TransactionList {
  transactions: Transaction[];
}

export interface SubscriptionDetail extends Subscription {
  first_seen_at: string | null;
  last_charge_at: string | null;
  history: Charge[];
}

export interface Alert {
  id: string;
  subscription_id: string | null;
  category: string | null;
  type: string;
  scheduled_for: string;
  sent_at: string | null;
  channel: string;
}

export interface AlertList {
  alerts: Alert[];
}

export interface AlertSettings {
  renewal_lead_days: number;
  digest_enabled: boolean;
  trial_alerts: boolean;
  price_hike_alerts: boolean;
  budget_alerts: boolean;
}

export interface AlertRun {
  reminders: number;
  price_hikes: number;
  digests: number;
  budget_overages: number;
  email_configured: boolean;
  email_detail: string;
}

export interface EmailStatus {
  provider_configured: boolean;
  from_email: string;
  from_domain: string;
  deliverable: boolean;
  detail: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface CategorySpend {
  category: string;
  monthly: string;
  share: number;
}

export interface MonthSpend {
  month: string;
  total: string;
}

export interface Insights {
  currency: string;
  monthly_total: string;
  by_category: CategorySpend[];
  by_month: MonthSpend[];
  trend_pct: number | null;
}

export interface Budget {
  id: string;
  category: string;
  monthly_limit: string;
  currency: string;
  spent: string;
  status: string;
}

export interface BudgetList {
  budgets: Budget[];
}
