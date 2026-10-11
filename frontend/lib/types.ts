export type Source = {
  id: string;
  name: string;
  source_type: "postgresql" | "mongodb" | "spreadsheet" | "google_ads" | string;
  origin: "sample" | "external" | "upload" | string;
  enabled: boolean;
  status: "unknown" | "healthy" | "error" | string;
  status_message: string | null;
  last_checked_at: string | null;
  has_secret: boolean;
  config: Record<string, string | number | boolean | null>;
  created_at: string;
  updated_at: string;
};

export type ColumnInfo = {
  name: string;
  data_type: string;
  nullable: boolean | null;
};

export type CatalogObject = {
  schema_name: string | null;
  name: string;
  kind: string;
  row_count: number | null;
  note: string | null;
  columns: ColumnInfo[];
};

export type Sample = {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
};

export type ColumnProfile = {
  name: string;
  suggested_name: string;
  inferred_type: string;
  missing: number;
  nullable: boolean;
};

export type Profile = {
  row_count: number;
  column_count: number;
  duplicate_rows: number;
  columns: ColumnProfile[];
  preview: Record<string, unknown>[];
  suggested_ddl: string;
  sheet_name: string | null;
  table_name: string;
  note: string;
};

export type Mapping = {
  id: string;
  left_source_name: string;
  left_object: string;
  left_field: string;
  right_source_name: string;
  right_object: string;
  right_field: string;
  description: string;
};

export type Activity = {
  id: string;
  source_id: string | null;
  source_name: string | null;
  action: string;
  status: string;
  detail: string;
  created_at: string;
};

export type Dashboard = {
  counts: { total: number; healthy: number; enabled: number; attention: number };
  sources: Source[];
  activity: Activity[];
  mappings: Mapping[];
};

export type Meta = {
  app_name: string;
  version: string;
  phase: string;
  seed_demo_data: boolean;
  openai_configured: boolean;
  upload_limit_mb: number;
  supported_sources: string[];
  embedding_model: string;
  openai_model: string;
};

export type TestResult = {
  ok: boolean;
  message: string;
  source: Source;
};

export type ColumnTransform = {
  name: string;
  suggested_name: string;
  inferred_type: "text" | "bigint" | "numeric" | "boolean" | "date" | "timestamp";
  include: boolean;
};

export type PreviewTransform = {
  profile: Profile;
  row_count: number;
  dropped_duplicates: number;
  dropped_empty_rows: number;
};

export type ImportResult = {
  source: Source;
  destination_source: Source;
  object_name: string;
  row_count: number;
  message: string;
};

export type ChartSpec = {
  type: "bar" | "line" | "pie";
  category: string;
  value: string;
  title: string;
};

export type ReportSection = {
  title: string;
  body: string;
  columns: string[];
  rows: Record<string, unknown>[];
  chart: ChartSpec | null;
  sql?: string | null;
};

export type ReportDocument = {
  title: string;
  summary: string;
  generated_at: string;
  sections: ReportSection[];
  sources_used: string[];
};

export type AskResult = {
  answer: string;
  points: string[];
  sources_used: string[];
  query: string | null;
  columns: string[];
  rows: Record<string, unknown>[];
  chart: ChartSpec | null;
  status: "ok" | "needs_clarification" | "error";
  note: string | null;
  tools_used: string[];
  report?: ReportDocument | null;
  steps: AgentStep[];
  options: string[];
  assumptions: string[];
  planner: string | null;
  truncated: boolean;
};

export type AgentStep = {
  name: string;
  detail: string;
  status: "ok" | "error";
};

export type LinkSuggestion = {
  left_source_id: string;
  left_source_name: string;
  left_object: string;
  left_field: string;
  right_source_id: string;
  right_source_name: string;
  right_object: string;
  right_field: string;
  overlap: number;
  shared_values: number;
  examples: string[];
};

export type Suggestions = {
  questions: string[];
  generated_by: string;
  tables: { table: string; source: string; object: string; rows: number }[];
};

export type McpTool = {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
};

export type McpServer = {
  name: string;
  transport: string;
  enabled: boolean;
  data_origin?: string | null;
  tools?: string[] | null;
  command?: string[] | null;
  note?: string | null;
};

export type McpRegistry = {
  servers: McpServer[];
  tools: McpTool[];
};

export type Catalog = {
  objects: CatalogObject[];
};
