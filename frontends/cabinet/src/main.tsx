import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { initAnalytics, trackAnalyticsEvent, trackPageView } from "./analytics";
import {
  Activity,
  ArrowLeft,
  ArrowLeftRight,
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  CreditCard,
  Database,
  Eye,
  GitBranch,
  Globe,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  PauseCircle,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Send,
  Server,
  Shield,
  ShieldOff,
  Trash2,
  User,
  UserCircle2,
  Users,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./base44-theme.css";
import "./styles.css";

type Lang = "ru" | "en";
type BusinessRole = "CLIENT" | "EMPLOYEE";
type SystemRole = "STUDENT";

type LoginResult = {
  access_token: string;
  refresh_token: string;
  business_role?: BusinessRole | null;
};

type StudentDocsTicketResult = {
  docs_url: string;
};

type AllureOpenUrlResult = {
  url: string;
  mode: "report" | "job";
};

type Profile = {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  system_role: SystemRole;
  business_role?: BusinessRole | null;
  permissions: string[];
};

type IdentityAccess = {
  id: string;
  service_name: string;
  principal: string;
  status: string;
};

type IdentityPayload = {
  identity: {
    id: string;
    status: string;
    username: string;
    system_role: string;
  };
  accesses: IdentityAccess[];
};

type Account = {
  id: string;
  account_number: string;
  currency: string;
  type: string;
  status: string;
  balance: string;
  available_balance: string;
};

type Ticket = {
  id: string;
  subject: string;
  description: string;
  status: string;
  priority: string;
  category: string;
  employee_id_nullable?: string | null;
  created_at?: string;
};

type Transfer = {
  id: string;
  source_account_id: string;
  target_account_id: string;
  amount: string;
  currency: string;
  exchange_rate?: string | number;
  status: string;
  description?: string;
  created_at?: string;
};

type ExchangeRate = {
  base_currency: string;
  quote_currency: string;
  rub_amount: number;
  direct_rate: number;
  inverse_rate: number;
  set_by_user_id?: string | null;
  updated_at?: string;
};

type Client = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  external_client_code: string;
  status: string;
  created_at?: string;
  updated_at?: string;
};

type StudentEvent = {
  id: string;
  topic: string;
  event_type: string;
  entity_type?: string | null;
  entity_id?: string | null;
  occurred_at: string;
  payload: Record<string, unknown>;
};

type Employee = {
  id: string;
  uuid?: string;
  email: string;
  username: string;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  status: string;
  is_active?: boolean;
  is_blocked?: boolean;
  created_at?: string;
  updated_at?: string;
  last_login_at?: string;
  clients_count?: number;
  tickets_count?: number;
};

type StudentDashboardPayload = {
  employees_total: number;
  employees_active: number;
  employees_blocked: number;
  clients_total: number;
  accounts_total: number;
  tickets_total: number;
  transfers_total: number;
  series: Array<{
    day: string;
    employees: number;
    clients: number;
    accounts: number;
    tickets: number;
  }>;
};

type StudentEntitiesGenerateResult = {
  run_id: string;
  cleaned_employees: number;
  cleaned_clients: number;
  cleaned_accounts: number;
  cleaned_tickets: number;
  cleaned_messages: number;
  cleaned_users: number;
  cleaned_identities: number;
  cleaned_identity_accesses: number;
  created_employees: number;
  created_clients: number;
  created_accounts: number;
  created_tickets: number;
  created_messages: number;
  employee_ids: string[];
  client_ids: string[];
};

type ToolMeta = {
  title: string;
  url?: string;
  hint: string;
};

type ToolPracticeTask = {
  id: number;
  goal: string;
  preconditions: string;
  steps: string[];
  expected: string;
  where: string;
};

type ToolCodeExample = {
  title: string;
  language: string;
  code: string;
};

type ToolGuide = {
  summary: string[];
  connection: string[];
  auth: string[];
  isolation: string[];
  practice: ToolPracticeTask[];
  examples?: ToolCodeExample[];
};

type ToolService = "GRAFANA" | "JENKINS" | "ALLURE" | "GRAPHQL" | "GRPC" | "KAFKA" | "POSTGRES" | "REDIS" | "REST_API" | "KIBANA" | "JAEGER";
type ToolSlug = "jenkins" | "allure" | "postgresql" | "rest-api" | "redis" | "kafka";

type AppRoute =
  | { route: "login" }
  | {
      route: "student";
      section: "dashboard" | "employees" | "employee-profile" | "employee-workspace" | "clients" | "client-profile" | "tools" | "tool-detail";
      employeeId?: string;
      clientId?: string;
      toolSlug?: ToolSlug;
    };

const HOST = window.location.hostname || "127.0.0.1";
const PROTOCOL = window.location.protocol === "https:" ? "https:" : "http:";
const LOCAL_HOSTS = new Set(["127.0.0.1", "0.0.0.0"]);
const KNOWN_APP_PREFIXES = ["student.", "api.", "grafana.", "jenkins.", "kibana.", "kafka.", "jaeger."] as const;

function isIpAddress(host: string): boolean {
  return /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host);
}

function isLocalAddress(host: string): boolean {
  return LOCAL_HOSTS.has(host) || host.endsWith(".local") || isIpAddress(host);
}

function stripKnownAppPrefix(host: string): string {
  for (const prefix of KNOWN_APP_PREFIXES) {
    if (host.startsWith(prefix)) {
      return host.slice(prefix.length);
    }
  }
  return host;
}

const BASE_HOST = stripKnownAppPrefix(HOST);

function appOrigin(target: "portal" | "student" | "api" | "grafana" | "jenkins" | "kibana" | "kafka" | "jaeger"): string {
  if (isLocalAddress(HOST)) {
    const portMap = {
      portal: "5173",
      student: "5174",
      api: "8080",
      grafana: "3000",
      jenkins: "8086",
      kibana: "5601",
      kafka: "8085",
      jaeger: "16686",
    } satisfies Record<typeof target, string>;
    return `${PROTOCOL}//${HOST}:${portMap[target]}`;
  }
  if (target === "portal") {
    return `${PROTOCOL}//${BASE_HOST}`;
  }
  return `${PROTOCOL}//${target}.${BASE_HOST}`;
}

const API = appOrigin("api");
const STUDENT_SESSION_KEY = "bank_student_session_v1";
const API_TIMEOUT_MS = 15000;
const TRAINING_STUDENT_LOGIN = "student@easyitlab.tech";
const TRAINING_STUDENT_PASSWORD = "student123";
const ALLOWED_TOOL_SERVICES = new Set<ToolService>(["JENKINS", "ALLURE", "POSTGRES", "REST_API", "REDIS", "KAFKA"]);

const TOOL_MAP: Record<ToolService, ToolMeta> = {
  REST_API: {
    title: "REST API / Swagger",
    url: `${appOrigin("api")}/students/docs`,
    hint: "API-шлюз. Вход по вашей почте и паролю.",
  },
  GRAPHQL: {
    title: "GraphQL",
    url: `${appOrigin("api")}/graphql`,
    hint: "GraphQL endpoint стенда.",
  },
  GRPC: {
    title: "gRPC Service",
    hint: `grpc://${HOST}:50051 (grpcurl/Postman)`,
  },
  KAFKA: {
    title: "Kafka",
    hint: `Kafka broker: ${HOST}:9092 (или kafka:9092 в docker-сети).`,
  },
  KIBANA: {
    title: "Kibana",
    url: appOrigin("kibana"),
    hint: "Логи и аудит действий.",
  },
  GRAFANA: {
    title: "Grafana",
    url: appOrigin("grafana"),
    hint: "Метрики и дашборды.",
  },
  JENKINS: {
    title: "Jenkins",
    url: `${appOrigin("jenkins")}/?locale=en`,
    hint: "CI/CD и учебные job. Вход под учетной записью студента.",
  },
  ALLURE: {
    title: "Allure",
    url: `${appOrigin("jenkins")}/?locale=en`,
    hint: "Automated test reports in Jenkins.",
  },
  POSTGRES: {
    title: "PostgreSQL",
    hint: `postgresql://${HOST}:5432 (${TRAINING_STUDENT_LOGIN})`,
  },
  REDIS: {
    title: "Redis",
    hint: `redis://${HOST}:6379`,
  },
  JAEGER: {
    title: "Jaeger Tracing",
    hint: appOrigin("jaeger"),
  },
};

const STUDENT_TOOL_MENU_ORDER: ToolService[] = ["JENKINS", "ALLURE", "POSTGRES", "REST_API", "REDIS", "KAFKA"];
const TOOL_SLUG_BY_SERVICE: Record<ToolService, ToolSlug | null> = {
  GRAFANA: null,
  JENKINS: "jenkins",
  ALLURE: "allure",
  GRAPHQL: null,
  GRPC: null,
  KAFKA: "kafka",
  POSTGRES: "postgresql",
  REDIS: "redis",
  REST_API: "rest-api",
  KIBANA: null,
  JAEGER: null,
};
const TOOL_SERVICE_BY_SLUG: Record<ToolSlug, ToolService> = {
  jenkins: "JENKINS",
  allure: "ALLURE",
  postgresql: "POSTGRES",
  redis: "REDIS",
  kafka: "KAFKA",
  "rest-api": "REST_API",
};
const TOOL_ICON_BY_SERVICE: Record<ToolService, React.ComponentType<{ className?: string }>> = {
  GRAFANA: BarChart3,
  JENKINS: Building2,
  ALLURE: CheckCircle2,
  GRAPHQL: GitBranch,
  GRPC: Radio,
  KAFKA: Activity,
  POSTGRES: Database,
  REDIS: Server,
  REST_API: Globe,
  KIBANA: Search,
  JAEGER: ArrowLeftRight,
};

const EMPLOYEE_TICKET_STATUSES = ["IN_REVIEW", "WAITING_FOR_CLIENT", "WAITING_FOR_EMPLOYEE", "RESOLVED", "REJECTED", "CLOSED"];

const CLIENT_STATUS_ACTIONS: Record<string, Array<{ endpoint: string; label: string }>> = {
  ACTIVE: [
    { endpoint: "suspend", label: "Suspend" },
    { endpoint: "block", label: "Block" },
  ],
  SUSPENDED: [
    { endpoint: "activate", label: "Activate" },
    { endpoint: "block", label: "Block" },
  ],
  BLOCKED: [
    { endpoint: "activate", label: "Activate" },
    { endpoint: "suspend", label: "Suspend" },
  ],
  PENDING_VERIFICATION: [
    { endpoint: "activate", label: "Activate" },
    { endpoint: "block", label: "Block" },
  ],
  NEW: [
    { endpoint: "activate", label: "Activate" },
    { endpoint: "block", label: "Block" },
  ],
};

function parseApiError(text: string, fallbackStatus: number): string {
  if (!text) {
    return `HTTP ${fallbackStatus}`;
  }
  try {
    const parsed = JSON.parse(text) as { error?: { code?: string; message?: string } };
    if (parsed?.error?.message) {
      return parsed.error.message;
    }
    if (parsed?.error?.code) {
      return parsed.error.code;
    }
  } catch {
    // keep raw text
  }
  return text;
}

async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      signal: options.signal || controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timeout");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }

  const text = await response.text();
  if (!response.ok) {
    throw new Error(parseApiError(text, response.status));
  }
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}

function parseRoute(hash: string): AppRoute {
  const rawWithQuery = hash.replace(/^#/, "").trim();
  const raw = rawWithQuery.split("?")[0];
  if (!raw || raw === "/login") {
    return { route: "login" };
  }
  if (!raw.startsWith("/student")) {
    return { route: "login" };
  }

  const segments = raw.split("/").filter(Boolean);
  const section = segments[1];
  if (!section) {
    return { route: "student", section: "dashboard" };
  }
  if (section === "clients") {
    if (segments[2]) {
      return { route: "student", section: "client-profile", clientId: decodeURIComponent(segments[2]) };
    }
    return { route: "student", section: "clients" };
  }
  if (section === "employees") {
    if (segments[2] && segments[3] === "workspace") {
      return { route: "student", section: "employee-workspace", employeeId: decodeURIComponent(segments[2]) };
    }
    if (segments[2]) {
      return { route: "student", section: "employee-profile", employeeId: decodeURIComponent(segments[2]) };
    }
    return { route: "student", section: "employees" };
  }
  if (section === "tools") {
    const slug = segments[2] as ToolSlug | undefined;
    if (slug && slug in TOOL_SERVICE_BY_SLUG) {
      return { route: "student", section: "tool-detail", toolSlug: slug };
    }
    return { route: "student", section: "tools" };
  }
  if (section === "dashboard") {
    return { route: "student", section: "dashboard" };
  }
  return { route: "student", section: "dashboard" };
}

function setHash(path: string): void {
  window.location.hash = path;
}

type StoredStudentSession = {
  refresh_token: string;
  username: string;
};

function loadStoredStudentSession(): StoredStudentSession | null {
  try {
    const raw = window.localStorage.getItem(STUDENT_SESSION_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<StoredStudentSession>;
    if (!parsed.refresh_token || !parsed.username) {
      return null;
    }
    return { refresh_token: parsed.refresh_token, username: parsed.username };
  } catch {
    return null;
  }
}

function storeStudentSession(refreshToken: string, username: string): void {
  window.localStorage.setItem(STUDENT_SESSION_KEY, JSON.stringify({ refresh_token: refreshToken, username }));
}

function clearStoredStudentSession(): void {
  window.localStorage.removeItem(STUDENT_SESSION_KEY);
}

function formatDate(value?: string): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function formatMoney(value: string | number, currency: string): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return `${value} ${currency}`;
  }
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: currency || "RUB",
    maximumFractionDigits: 2,
  }).format(numeric);
}

function statusClass(status?: string): string {
  const value = (status || "").toUpperCase();
  if (["ACTIVE", "COMPLETED", "SUCCESS", "RESOLVED"].includes(value)) return "bg-green-100 text-green-700 border-green-200";
  if (["BLOCKED", "FAILED", "REJECTED", "CLOSED"].includes(value)) return "bg-red-100 text-red-700 border-red-200";
  if (["SUSPENDED", "NEW", "IN_REVIEW", "WAITING_FOR_CLIENT", "WAITING_FOR_EMPLOYEE", "PENDING", "PROCESSING"].includes(value)) {
    return "bg-amber-100 text-amber-700 border-amber-200";
  }
  return "bg-muted text-muted-foreground border-border";
}

function statusLabel(value: string, lang: Lang): string {
  const key = value.toUpperCase();
  const ru: Record<string, string> = {
    ACTIVE: "Активен",
    BLOCKED: "Заблокирован",
    SUSPENDED: "Приостановлен",
    PENDING_VERIFICATION: "На проверке",
    NEW: "Новый",
    IN_REVIEW: "На рассмотрении",
    WAITING_FOR_CLIENT: "Ожидание клиента",
    WAITING_FOR_EMPLOYEE: "Ожидание сотрудника",
    RESOLVED: "Решен",
    REJECTED: "Отклонен",
    CLOSED: "Закрыт",
    COMPLETED: "Завершен",
    FAILED: "Ошибка",
    REVOKED: "Отозван",
    SKIPPED: "Пропущен",
  };
  if (lang === "ru") {
    return ru[key] || value;
  }
  return value;
}

function StatusBadge({ value, lang = "en" }: { value?: string; lang?: Lang }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusClass(value)}`}>
      {value ? statusLabel(value, lang) : "-"}
    </span>
  );
}

function cx(...parts: Array<string | false | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function App() {
  const [routeHash, setRouteHash] = useState(window.location.hash || "#/login");
  const route = useMemo(() => parseRoute(routeHash), [routeHash]);

  const [lang, setLang] = useState<Lang>("en");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessionBootstrapped, setSessionBootstrapped] = useState(false);
  const [sessionRestoring, setSessionRestoring] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [token, setToken] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [identity, setIdentity] = useState<IdentityPayload | null>(null);
  const [events, setEvents] = useState<StudentEvent[]>([]);
  const [dashboard, setDashboard] = useState<StudentDashboardPayload | null>(null);

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeProfile, setEmployeeProfile] = useState<Employee | null>(null);
  const [employeeProfileClients, setEmployeeProfileClients] = useState<Client[]>([]);
  const [employeeProfileTickets, setEmployeeProfileTickets] = useState<Ticket[]>([]);
  const [employeeAuditRows, setEmployeeAuditRows] = useState<Array<Record<string, unknown>>>([]);
  const [employeeExchangeRates, setEmployeeExchangeRates] = useState<ExchangeRate[]>([]);
  const [employeeProfileTab, setEmployeeProfileTab] = useState<"overview" | "tickets" | "analytics" | "audit">("overview");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeStatusFilter, setEmployeeStatusFilter] = useState("");
  const [employeeSortField, setEmployeeSortField] = useState<"name" | "status" | "updated_at" | "email">("updated_at");
  const [employeeSortDir, setEmployeeSortDir] = useState<"asc" | "desc">("desc");
  const [employeesPage, setEmployeesPage] = useState(1);

  const [employeeCreateOpen, setEmployeeCreateOpen] = useState(false);
  const [employeeCreateFullName, setEmployeeCreateFullName] = useState("");
  const [employeeCreateEmail, setEmployeeCreateEmail] = useState("");
  const [employeeCreatePassword, setEmployeeCreatePassword] = useState("");

  const [employeeEditOpen, setEmployeeEditOpen] = useState(false);
  const [employeeEditFullName, setEmployeeEditFullName] = useState("");
  const [employeeEditEmail, setEmployeeEditEmail] = useState("");

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [newOwnAccountCurrency, setNewOwnAccountCurrency] = useState("RUB");
  const [newOwnAccountType, setNewOwnAccountType] = useState("CURRENT");
  const [openOwnAccountForm, setOpenOwnAccountForm] = useState(false);
  const [ownTopUpAccountId, setOwnTopUpAccountId] = useState("");
  const [ownTopUpAmount, setOwnTopUpAmount] = useState("1000");
  const [transferSourceId, setTransferSourceId] = useState("");
  const [transferTargetId, setTransferTargetId] = useState("");
  const [transferAmount, setTransferAmount] = useState("1000");
  const [transferDescription, setTransferDescription] = useState("Перевод в учебном контуре");
  const [createTicketModalOpen, setCreateTicketModalOpen] = useState(false);
  const [ticketCategory, setTicketCategory] = useState("OTHER");
  const [ticketSubject, setTicketSubject] = useState("Вопрос по переводу");
  const [ticketDescription, setTicketDescription] = useState("Нужна проверка операции");
  const [expandedTicketId, setExpandedTicketId] = useState("");
  const [selectedOwnTicketId, setSelectedOwnTicketId] = useState("");
  const [ownTicketMessage, setOwnTicketMessage] = useState("Уточните детали по обращению");

  const [clients, setClients] = useState<Client[]>([]);
  const [clientStats, setClientStats] = useState<Record<string, { accounts: number; tickets: number }>>({});

  const [clientProfile, setClientProfile] = useState<Client | null>(null);
  const [clientProfileAccounts, setClientProfileAccounts] = useState<Account[]>([]);
  const [clientProfileTransfers, setClientProfileTransfers] = useState<Transfer[]>([]);
  const [clientProfileTickets, setClientProfileTickets] = useState<Ticket[]>([]);
  const [clientProfileTab, setClientProfileTab] = useState<"overview" | "accounts" | "transfers" | "tickets" | "analytics" | "audit">("overview");
  const [clientTransferSourceId, setClientTransferSourceId] = useState("");
  const [clientTransferTargetId, setClientTransferTargetId] = useState("");
  const [clientTransferAmount, setClientTransferAmount] = useState("1000");
  const [clientTransferDescription, setClientTransferDescription] = useState("Перевод между счетами клиента");
  const [clientTopUpAccountId, setClientTopUpAccountId] = useState("");
  const [clientTopUpAmount, setClientTopUpAmount] = useState("1000");
  const [selectedEmployeeTicketId, setSelectedEmployeeTicketId] = useState("");
  const [employeeTicketStatus, setEmployeeTicketStatus] = useState("IN_REVIEW");
  const [employeeTicketMessage, setEmployeeTicketMessage] = useState("Статус обновлен, проверяем детали.");

  const [notice, setNotice] = useState("");
  const [toolRouteDenied, setToolRouteDenied] = useState("");
  const [busy, setBusy] = useState(false);

  const [clientSearch, setClientSearch] = useState("");
  const [clientStatusFilter, setClientStatusFilter] = useState("");
  const [clientSortField, setClientSortField] = useState<"name" | "status" | "updated_at" | "email">("updated_at");
  const [clientSortDir, setClientSortDir] = useState<"asc" | "desc">("desc");
  const [clientsPage, setClientsPage] = useState(1);

  const [clientCreateOpen, setClientCreateOpen] = useState(false);
  const [generateEntitiesConfirmOpen, setGenerateEntitiesConfirmOpen] = useState(false);
  const [clientCreateStudentUsername, setClientCreateStudentUsername] = useState("");
  const [clientCreateEmployeeId, setClientCreateEmployeeId] = useState("");
  const [clientCreateFirstName, setClientCreateFirstName] = useState("Иван");
  const [clientCreateLastName, setClientCreateLastName] = useState("Иванов");
  const [clientCreatePhone, setClientCreatePhone] = useState("+79990000000");
  const [clientCreateEmail, setClientCreateEmail] = useState("ivanov.client@demobank.local");

  const [openAccountModal, setOpenAccountModal] = useState(false);
  const [newClientAccountCurrency, setNewClientAccountCurrency] = useState("RUB");
  const [newClientAccountType, setNewClientAccountType] = useState("CURRENT");

  const isAuthenticated = Boolean(token && profile);
  const t = (ru: string, en: string): string => (lang === "ru" ? ru : en);
  const toolHint = (serviceName: string, fallback: string): string => {
    const service = serviceName as ToolService;
    if (service === "JENKINS") {
      return t("CI/CD и учебные job. Логин и пароль как в кабинете студента.", "CI/CD and training jobs. Use the same login and password as in the student cabinet.");
    }
    if (service === "ALLURE") {
      return t("Отчеты автотестов Allure в Jenkins.", "Allure automated test reports in Jenkins.");
    }
    if (service === "POSTGRES") {
      return t(`Подключение: postgresql://${HOST}:5432 (${TRAINING_STUDENT_LOGIN} / ${TRAINING_STUDENT_PASSWORD}).`, `Connection: postgresql://${HOST}:5432 (${TRAINING_STUDENT_LOGIN} / ${TRAINING_STUDENT_PASSWORD}).`);
    }
    if (service === "REST_API") {
      return t("Swagger/OpenAPI для студента. Реальные вызовы выполняйте через Postman или curl.", "Student Swagger/OpenAPI. Run real requests via Postman or curl.");
    }
    if (service === "REDIS") {
      return t(`Redis: ${HOST}:6379. Учетка: ${TRAINING_STUDENT_LOGIN} / ${TRAINING_STUDENT_PASSWORD}.`, `Redis: ${HOST}:6379. Credentials: ${TRAINING_STUDENT_LOGIN} / ${TRAINING_STUDENT_PASSWORD}.`);
    }
    if (service === "KAFKA") {
      return t(`Kafka broker: ${HOST}:9092 (или kafka:9092 внутри docker-compose).`, `Kafka broker: ${HOST}:9092 (or kafka:9092 inside docker-compose).`);
    }
    return fallback;
  };
  const renderDeveloperFooter = (className = "") => (
    <div className={cx("rounded-2xl border border-border/70 bg-white/70 px-4 py-3 text-xs text-muted-foreground space-y-1.5", className)}>
      <p>{t("Разработчик Николаев Даниил", "Developed by Daniil Nikolaev")}</p>
      <p>
        {t(
          "Облачная версия платформы для QA, backend и DevOps практики со всеми 10 инструментами - ",
          "Cloud version of the platform for QA, backend, and DevOps practice with all 10 tools - "
        )}
        <a className="font-medium text-primary hover:underline break-all" href="https://bank.easyitlab.tech/" target="_blank" rel="noreferrer">
          bank.easyitlab.tech
        </a>
      </p>
      <p>
        {t("Связь по почте ", "Contact via email ")}
        <a className="font-medium text-primary hover:underline" href="mailto:easyitwithdaniil@gmail.com">
          easyitwithdaniil@gmail.com
        </a>
        {t(" или телеграм ", " or Telegram ")}
        <a className="font-medium text-primary hover:underline" href="https://t.me/danilfg" target="_blank" rel="noreferrer">
          @danilfg
        </a>
      </p>
      <p>
        {t("Присоединяйся к сообществу: ", "Join the community: ")}
        <a
          className="font-medium text-primary hover:underline break-all"
          href="https://chat.easyitlab.tech/signup_user_complete/?id=xx9z9sjt9bfy9y8t7eokdzgdac"
          target="_blank"
          rel="noreferrer"
        >
          chat.easyitlab.tech
        </a>
      </p>
    </div>
  );

  const availableTools = useMemo(() => {
    if (!identity) {
      return [] as Array<IdentityAccess & { tool: ToolMeta }>;
    }
    return identity.accesses
      .filter((access) => ALLOWED_TOOL_SERVICES.has(access.service_name as ToolService))
      .map((access) => {
        const serviceName = access.service_name as ToolService;
        const tool = TOOL_MAP[serviceName] || {
          title: access.service_name,
          hint: t("Сервис без web-интерфейса", "Service without web UI"),
        };
        return { ...access, tool };
      })
      .sort((a, b) => a.service_name.localeCompare(b.service_name));
  }, [identity]);

  const activeToolsByService = useMemo(() => {
    const map = new Map<ToolService, IdentityAccess & { tool: ToolMeta }>();
    availableTools.forEach((access) => {
      const key = access.service_name as ToolService;
      if (access.status === "ACTIVE") {
        map.set(key, access);
      }
    });
    return map;
  }, [availableTools]);

  const menuTools = useMemo(() => {
    return STUDENT_TOOL_MENU_ORDER.flatMap((service) => {
      const access = activeToolsByService.get(service);
      const slug = TOOL_SLUG_BY_SERVICE[service];
      if (!access || !slug) {
        return [];
      }
      return [{ service, slug, access }];
    });
  }, [activeToolsByService]);

  const resolveToolOpenUrl = (service: ToolService): string | undefined => {
    const baseUrl = TOOL_MAP[service]?.url;
    if (!baseUrl) {
      return undefined;
    }
    return baseUrl;
  };

  async function openTool(service: ToolService): Promise<void> {
    const baseUrl = resolveToolOpenUrl(service);
    if (!baseUrl) {
      return;
    }
    if (service === "ALLURE") {
      if (!token) {
        window.open(baseUrl, "_blank", "noopener,noreferrer");
        return;
      }
      try {
        const payload = await api<AllureOpenUrlResult>("/students/allure/open-url", {}, token);
        if (payload.mode === "job") {
          setNotice(
            t(
              "Allure отчет пока недоступен. Открыта Jenkins job для запуска build.",
              "Allure report is not available yet. Opened Jenkins job so you can run a build."
            )
          );
          const separator = payload.url.includes("?") ? "&" : "?";
          window.open(`${payload.url}${separator}locale=en`, "_blank", "noopener,noreferrer");
          return;
        }
        window.open(payload.url, "_blank", "noopener,noreferrer");
        return;
      } catch {
        window.open(baseUrl, "_blank", "noopener,noreferrer");
        return;
      }
    }
    if (service !== "REST_API") {
      window.open(baseUrl, "_blank", "noopener,noreferrer");
      return;
    }
    if (!token) {
      setNotice("Сначала войдите в кабинет студента.");
      return;
    }
    try {
      const payload = await api<StudentDocsTicketResult>("/students/docs-ticket", { method: "POST" }, token);
      window.open(`${API}${payload.docs_url}`, "_blank", "noopener,noreferrer");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }

  const employeesFilteredSorted = useMemo(() => {
    const query = employeeSearch.trim().toLowerCase();
    const rows = employees.filter((employee) => {
      if (employeeStatusFilter && employee.status !== employeeStatusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      const fullName = (employee.full_name || `${employee.first_name || ""} ${employee.last_name || ""}`.trim() || "").toLowerCase();
      return fullName.includes(query) || employee.email.toLowerCase().includes(query) || (employee.id || "").toLowerCase().includes(query);
    });
    return rows.sort((left, right) => {
      const direction = employeeSortDir === "asc" ? 1 : -1;
      const leftName = (left.full_name || `${left.first_name || ""} ${left.last_name || ""}`.trim() || left.email).toLowerCase();
      const rightName = (right.full_name || `${right.first_name || ""} ${right.last_name || ""}`.trim() || right.email).toLowerCase();
      if (employeeSortField === "name") {
        return leftName.localeCompare(rightName) * direction;
      }
      if (employeeSortField === "email") {
        return left.email.localeCompare(right.email) * direction;
      }
      if (employeeSortField === "status") {
        return left.status.localeCompare(right.status) * direction;
      }
      return String(left.updated_at || left.created_at || "").localeCompare(String(right.updated_at || right.created_at || "")) * direction;
    });
  }, [employees, employeeSearch, employeeStatusFilter, employeeSortDir, employeeSortField]);

  const clientsFilteredSorted = useMemo(() => {
    const query = clientSearch.trim().toLowerCase();
    const rows = clients.filter((client) => {
      if (clientStatusFilter && client.status !== clientStatusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      const fullName = `${client.first_name} ${client.last_name}`.toLowerCase();
      return (
        fullName.includes(query) ||
        client.email.toLowerCase().includes(query) ||
        client.external_client_code.toLowerCase().includes(query) ||
        String((client as Record<string, unknown>).employee_name || "").toLowerCase().includes(query)
      );
    });

    return rows.sort((left, right) => {
      const direction = clientSortDir === "asc" ? 1 : -1;
      const leftName = `${left.first_name} ${left.last_name}`;
      const rightName = `${right.first_name} ${right.last_name}`;

      if (clientSortField === "name") {
        return leftName.localeCompare(rightName) * direction;
      }
      if (clientSortField === "email") {
        return left.email.localeCompare(right.email) * direction;
      }
      if (clientSortField === "status") {
        return left.status.localeCompare(right.status) * direction;
      }
      return String(left.updated_at || "").localeCompare(String(right.updated_at || "")) * direction;
    });
  }, [clients, clientSearch, clientStatusFilter, clientSortField, clientSortDir]);

  const pageSize = 10;
  const employeesTotalPages = Math.max(1, Math.ceil(employeesFilteredSorted.length / pageSize));
  const employeesPageRows = employeesFilteredSorted.slice((employeesPage - 1) * pageSize, employeesPage * pageSize);
  const clientsTotalPages = Math.max(1, Math.ceil(clientsFilteredSorted.length / pageSize));
  const clientsPageRows = clientsFilteredSorted.slice((clientsPage - 1) * pageSize, clientsPage * pageSize);

  const topClients = useMemo(() => {
    return clients
      .map((client) => {
        const stats = clientStats[client.id] || { accounts: 0, tickets: 0 };
        return {
          ...client,
          accountCount: stats.accounts,
          ticketCount: stats.tickets,
          activityScore: stats.accounts + stats.tickets,
        };
      })
      .sort((a, b) => b.activityScore - a.activityScore)
      .slice(0, 5);
  }, [clients, clientStats]);

  const recentClients = useMemo(() => {
    return [...clients]
      .sort((a, b) => String(b.updated_at || b.created_at || "").localeCompare(String(a.updated_at || a.created_at || "")))
      .slice(0, 8);
  }, [clients]);

  const topEmployees = useMemo(() => {
    return [...employees]
      .sort((a, b) => (b.clients_count || 0) + (b.tickets_count || 0) - ((a.clients_count || 0) + (a.tickets_count || 0)))
      .slice(0, 5);
  }, [employees]);

  const statusDistribution = useMemo(() => {
    const countMap = new Map<string, number>();
    clients.forEach((client) => {
      countMap.set(client.status, (countMap.get(client.status) || 0) + 1);
    });
    const palette: Record<string, string> = {
      ACTIVE: "#22c55e",
      BLOCKED: "#ef4444",
      SUSPENDED: "#f59e0b",
      PENDING_VERIFICATION: "#3b82f6",
      NEW: "#8b5cf6",
    };
    return Array.from(countMap.entries()).map(([name, value]) => ({ name, value, color: palette[name] || "#64748b" }));
  }, [clients]);

  const activityData = useMemo(() => {
    if (dashboard?.series?.length) {
      return dashboard.series.map((row) => ({
        date: new Date(`${row.day}T00:00:00Z`).toLocaleDateString("ru-RU", { day: "2-digit", month: "short" }),
        employees: row.employees,
        clients: row.clients,
      }));
    }
    return [];
  }, [dashboard]);

  const dashboardKpis = useMemo(() => {
    return [
      { label: t("Всего сотрудников", "Total Employees"), value: dashboard?.employees_total || employees.length, color: "bg-blue-50 text-blue-600", icon: Users },
      { label: t("Активных сотрудников", "Active Employees"), value: dashboard?.employees_active || employees.filter((item) => item.status === "ACTIVE").length, color: "bg-green-50 text-green-600", icon: CheckCircle2 },
      { label: t("Заблокированных сотрудников", "Blocked Employees"), value: dashboard?.employees_blocked || employees.filter((item) => item.status === "BLOCKED").length, color: "bg-red-50 text-red-600", icon: ShieldOff },
      { label: t("Всего клиентов", "Total Clients"), value: dashboard?.clients_total || clients.length, color: "bg-indigo-50 text-indigo-600", icon: UserCircle2 },
      { label: t("Всего счетов", "Total Accounts"), value: dashboard?.accounts_total || 0, color: "bg-violet-50 text-violet-600", icon: CreditCard },
      { label: t("Всего тикетов", "Total Tickets"), value: dashboard?.tickets_total || 0, color: "bg-pink-50 text-pink-600", icon: MessageSquare },
      { label: t("Всего переводов", "Total Transfers"), value: dashboard?.transfers_total || 0, color: "bg-amber-50 text-amber-600", icon: ArrowLeftRight },
      { label: t("Доступов активных", "Active Accesses"), value: availableTools.filter((item) => item.status === "ACTIVE").length, color: "bg-green-50 text-green-600", icon: CheckCircle2 },
      { label: t("Логи аудита", "Audit Events"), value: events.length, color: "bg-amber-50 text-amber-600", icon: Bell },
    ];
  }, [dashboard, employees, clients, availableTools, events.length, t]);

  const clientAuditRows = useMemo(() => {
    if (!clientProfile) {
      return [];
    }
    const related = new Set<string>([
      clientProfile.id,
      ...clientProfileAccounts.map((item) => item.id),
      ...clientProfileTickets.map((item) => item.id),
      ...clientProfileTransfers.map((item) => item.id),
    ]);
    return events
      .filter((event) => {
        if (event.entity_id && related.has(event.entity_id)) {
          return true;
        }
        const payloadClientId = typeof event.payload.client_id === "string" ? event.payload.client_id : "";
        return payloadClientId === clientProfile.id;
      })
      .slice(0, 50);
  }, [clientProfile, clientProfileAccounts, clientProfileTickets, clientProfileTransfers, events]);

  const selectedEmployeeTicket = useMemo(() => {
    return clientProfileTickets.find((ticket) => ticket.id === selectedEmployeeTicketId) || null;
  }, [clientProfileTickets, selectedEmployeeTicketId]);

  useEffect(() => {
    initAnalytics("student-cabinet");
  }, []);

  useEffect(() => {
    trackPageView(`${window.location.pathname}${routeHash || "#/login"}`, "EasyBank Student Cabinet");
  }, [routeHash]);

  useEffect(() => {
    if (!window.location.hash) {
      setHash("/login");
    }
    const onHashChange = () => setRouteHash(window.location.hash || "#/login");
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    const stored = loadStoredStudentSession();
    if (stored) {
      setRefreshToken(stored.refresh_token);
      setUsername(stored.username);
    }
    setSessionBootstrapped(true);
  }, []);

  useEffect(() => {
    if (!sessionBootstrapped || token || profile || !refreshToken) {
      return;
    }
    void refreshSession();
  }, [sessionBootstrapped, token, profile, refreshToken]);

  useEffect(() => {
    if (!isAuthenticated || !profile) {
      return;
    }
    if (route.route !== "student") {
      setHash("/student/dashboard");
    }
  }, [isAuthenticated, profile, route]);

  useEffect(() => {
    if (clientsPage > clientsTotalPages) {
      setClientsPage(clientsTotalPages);
    }
  }, [clientsPage, clientsTotalPages]);

  useEffect(() => {
    if (employeesPage > employeesTotalPages) {
      setEmployeesPage(employeesTotalPages);
    }
  }, [employeesPage, employeesTotalPages]);

  useEffect(() => {
    if (!token || clientsPageRows.length === 0) {
      return;
    }
    void loadClientStats(
      token,
      clientsPageRows.map((item) => item.id)
    ).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : String(error));
    });
  }, [token, clientsPageRows]);

  async function loadProfile(activeToken: string): Promise<Profile> {
    const me = await api<Profile>("/auth/me", {}, activeToken);
    setProfile(me);
    return me;
  }

  async function loadIdentity(activeToken: string): Promise<void> {
    const payload = await api<IdentityPayload>("/students/me/identity", {}, activeToken);
    setIdentity(payload);
  }

  async function loadEvents(activeToken: string): Promise<void> {
    const rows = await api<StudentEvent[]>("/students/me/events?limit=200", {}, activeToken);
    setEvents(rows);
  }

  async function loadClientStats(activeToken: string, clientIds: string[]): Promise<void> {
    const missing = clientIds.filter((id) => !(id in clientStats));
    if (missing.length === 0) {
      return;
    }
    const entries = await Promise.all(
      missing.map(async (clientId) => {
        const [accs, tks] = await Promise.all([
          api<Account[]>(`/students/clients/${clientId}/accounts`, {}, activeToken),
          api<Ticket[]>(`/students/clients/${clientId}/tickets`, {}, activeToken),
        ]);
        return [clientId, { accounts: accs.length, tickets: tks.length }] as const;
      })
    );
    setClientStats((prev) => ({
      ...prev,
      ...Object.fromEntries(entries),
    }));
  }

  async function loadDashboard(activeToken: string): Promise<void> {
    const payload = await api<StudentDashboardPayload>("/students/dashboard", {}, activeToken);
    setDashboard(payload);
  }

  async function loadEmployees(activeToken: string): Promise<void> {
    const rows = await api<Employee[]>("/students/employees", {}, activeToken);
    setEmployees(rows);
  }

  async function loadClients(activeToken: string): Promise<void> {
    const rows = await api<Client[]>("/students/clients", {}, activeToken);
    setClients(rows);
    await loadClientStats(
      activeToken,
      rows
        .slice(0, 20)
        .map((item) => item.id)
    );
  }

  async function loadClientWorkspace(activeToken: string): Promise<void> {
    const [nextAccounts, nextTransfers, nextTickets] = await Promise.all([
      api<Account[]>("/clients/me/accounts", {}, activeToken),
      api<Transfer[]>("/clients/me/transfers", {}, activeToken),
      api<Ticket[]>("/clients/me/tickets", {}, activeToken),
    ]);
    const activeAccounts = nextAccounts.filter((item) => item.status === "ACTIVE");
    setAccounts(nextAccounts);
    setTransfers(nextTransfers);
    setTickets(nextTickets);

    if (nextAccounts.length > 0) {
      if (!activeAccounts.some((item) => item.id === ownTopUpAccountId)) {
        setOwnTopUpAccountId(activeAccounts[0]?.id || "");
      }
      if (!activeAccounts.some((item) => item.id === transferSourceId)) {
        setTransferSourceId(activeAccounts[0]?.id || "");
      }
      if (!nextAccounts.some((item) => item.id === transferTargetId)) {
        const fallbackTarget = nextAccounts[1]?.id || "";
        setTransferTargetId(fallbackTarget);
      }
    } else {
      setOwnTopUpAccountId("");
      setTransferSourceId("");
      setTransferTargetId("");
    }

    if (nextTickets.length > 0 && !nextTickets.some((item) => item.id === selectedOwnTicketId)) {
      setSelectedOwnTicketId(nextTickets[0].id);
    }
  }

  async function loadEmployeeProfile(activeToken: string, employeeId: string): Promise<void> {
    const [employee, employeeClients, employeeTickets, employeeAudit, rates] = await Promise.all([
      api<Employee>(`/students/employees/${employeeId}`, {}, activeToken),
      api<Client[]>(`/students/employees/${employeeId}/clients`, {}, activeToken),
      api<Ticket[]>(`/students/employees/${employeeId}/tickets`, {}, activeToken),
      api<Array<Record<string, unknown>>>(`/students/employees/${employeeId}/audit?limit=200`, {}, activeToken),
      api<ExchangeRate[]>(`/students/employees/${employeeId}/exchange-rates`, {}, activeToken),
    ]);
    setEmployeeProfile(employee);
    setEmployeeProfileClients(employeeClients);
    setEmployeeProfileTickets(employeeTickets);
    setEmployeeAuditRows(employeeAudit);
    setEmployeeExchangeRates(rates);
  }

  async function loadStudentClientProfile(activeToken: string, clientId: string): Promise<void> {
    const [client, clientAccounts, clientTransfers, clientTickets] = await Promise.all([
      api<Client>(`/students/clients/${clientId}`, {}, activeToken),
      api<Account[]>(`/students/clients/${clientId}/accounts`, {}, activeToken),
      api<Transfer[]>(`/students/clients/${clientId}/transfers`, {}, activeToken),
      api<Ticket[]>(`/students/clients/${clientId}/tickets`, {}, activeToken),
    ]);
    setClientProfile(client);
    setClientProfileAccounts(clientAccounts);
    setClientProfileTransfers(clientTransfers);
    setClientProfileTickets(clientTickets);

    const activeClientAccounts = clientAccounts.filter((item) => item.status === "ACTIVE");
    if (activeClientAccounts.length > 0) {
      setClientTopUpAccountId((prev) => (activeClientAccounts.some((item) => item.id === prev) ? prev : activeClientAccounts[0].id));
      setClientTransferSourceId((prev) => (activeClientAccounts.some((item) => item.id === prev) ? prev : activeClientAccounts[0].id));
      setClientTransferTargetId((prev) => {
        if (activeClientAccounts.length < 2) {
          return "";
        }
        const currentValid = activeClientAccounts.some((item) => item.id === prev && item.id !== (clientTransferSourceId || activeClientAccounts[0].id));
        if (currentValid) {
          return prev;
        }
        const fallbackSource = activeClientAccounts.some((item) => item.id === clientTransferSourceId) ? clientTransferSourceId : activeClientAccounts[0].id;
        return activeClientAccounts.find((item) => item.id !== fallbackSource)?.id || "";
      });
    } else {
      setClientTopUpAccountId("");
      setClientTransferSourceId("");
      setClientTransferTargetId("");
    }

    if (clientTickets.length > 0) {
      setSelectedEmployeeTicketId((prev) => (clientTickets.some((item) => item.id === prev) ? prev : clientTickets[0].id));
      setEmployeeTicketStatus(clientTickets[0].status);
    } else {
      setSelectedEmployeeTicketId("");
    }

    setClientStats((prev) => ({
      ...prev,
      [clientId]: { accounts: clientAccounts.length, tickets: clientTickets.length },
    }));
  }

  async function hydrateWorkspace(activeToken: string): Promise<void> {
    const tasks = await Promise.allSettled([
      loadIdentity(activeToken),
      loadEvents(activeToken),
      loadDashboard(activeToken),
      loadEmployees(activeToken),
      loadClients(activeToken),
    ]);
    const firstFailure = tasks.find((task): task is PromiseRejectedResult => task.status === "rejected");
    if (firstFailure) {
      const message = firstFailure.reason instanceof Error ? firstFailure.reason.message : String(firstFailure.reason);
      setNotice(message);
    }
  }

  useEffect(() => {
    if (!token || route.route !== "student" || route.section !== "client-profile" || !route.clientId) {
      return;
    }
    void loadStudentClientProfile(token, route.clientId).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : String(error));
    });
  }, [token, route]);

  useEffect(() => {
    if (
      !token ||
      route.route !== "student" ||
      (route.section !== "employee-profile" && route.section !== "employee-workspace") ||
      !route.employeeId
    ) {
      return;
    }
    void loadEmployeeProfile(token, route.employeeId).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : String(error));
    });
  }, [token, route]);

  function clearState(): void {
    setToken("");
    setRefreshToken("");
    setSessionRestoring(false);
    clearStoredStudentSession();
    setProfile(null);
    setIdentity(null);
    setEvents([]);
    setDashboard(null);
    setEmployees([]);
    setEmployeeProfile(null);
    setEmployeeProfileClients([]);
    setEmployeeProfileTickets([]);
    setEmployeeAuditRows([]);
    setAccounts([]);
    setTransfers([]);
    setTickets([]);
    setClients([]);
    setClientStats({});
    setClientProfile(null);
    setClientProfileAccounts([]);
    setClientProfileTransfers([]);
    setClientProfileTickets([]);
    setSelectedEmployeeTicketId("");
  }

  function isStudentCabinetAccessError(message: string): boolean {
    const normalized = message.toUpperCase();
    return normalized.includes("STUDENT_OWNER_REQUIRED") || normalized.includes("STUDENT OWNER ACCESS REQUIRED");
  }

  async function loginWithCredentials(): Promise<void> {
    if (!username || !password) {
      setNotice("Укажите логин и пароль.");
      return;
    }

    setBusy(true);
    setNotice("");
    try {
      const payload = await api<LoginResult>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: username, password }),
      });

      const me = await loadProfile(payload.access_token);
      setToken(payload.access_token);
      setRefreshToken(payload.refresh_token);
      storeStudentSession(payload.refresh_token, me.email);
      setHash("/student/dashboard");
      trackAnalyticsEvent("login_success", {
        app_name: "student-cabinet",
        system_role: me.system_role,
        business_role: me.business_role || "",
        username: me.username,
      });
      void hydrateWorkspace(payload.access_token);
      setNotice(`Вход выполнен: ${me.full_name || me.email}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (isStudentCabinetAccessError(message)) {
        clearState();
        setHash("/login");
        setNotice("Вход в кабинет студента разрешен только для учетной записи студента.");
      } else {
        setNotice(message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function refreshSession(options: { interactive?: boolean } = {}): Promise<void> {
    if (!refreshToken) {
      return;
    }
    const interactive = Boolean(options.interactive);
    setSessionRestoring(true);
    if (interactive) {
      setBusy(true);
    }
    setNotice("");
    try {
      const payload = await api<LoginResult>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const me = await loadProfile(payload.access_token);
      setToken(payload.access_token);
      setRefreshToken(payload.refresh_token);
      storeStudentSession(payload.refresh_token, me.email);
      void hydrateWorkspace(payload.access_token);
      setNotice("Сессия обновлена.");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (isStudentCabinetAccessError(message)) {
        clearState();
        setHash("/login");
        setNotice("Вход в кабинет студента разрешен только для учетной записи студента.");
      } else {
        setNotice(message);
      }
    } finally {
      setSessionRestoring(false);
      if (interactive) {
        setBusy(false);
      }
    }
  }

  function logout(): void {
    trackAnalyticsEvent("logout", {
      app_name: "student-cabinet",
      system_role: profile?.system_role || "STUDENT",
      business_role: profile?.business_role || "",
    });
    clearState();
    setHash("/login");
    setNotice("");
  }

  function openGenerateEntitiesConfirm(): void {
    setGenerateEntitiesConfirmOpen(true);
  }

  async function generateStudentEntities(): Promise<void> {
    if (!token) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const result = await api<StudentEntitiesGenerateResult>(
        "/students/entities/generate",
        {
          method: "POST",
          body: JSON.stringify({ confirm_cleanup: true }),
        },
        token
      );
      await Promise.all([loadEmployees(token), loadClients(token), loadDashboard(token), loadEvents(token)]);
      if (route.route === "student" && (route.section === "employee-profile" || route.section === "employee-workspace")) {
        setHash("/student/employees");
      }
      if (route.route === "student" && route.section === "client-profile") {
        setHash("/student/clients");
      }
      setGenerateEntitiesConfirmOpen(false);
      setNotice(
        t(
          `Готово: создано ${result.created_employees} сотрудников, ${result.created_clients} клиентов, ${result.created_accounts} счетов, ${result.created_tickets} тикетов, ${result.created_messages} сообщений.`,
          `Done: created ${result.created_employees} employees, ${result.created_clients} clients, ${result.created_accounts} accounts, ${result.created_tickets} tickets, ${result.created_messages} messages.`
        )
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createEmployeeUser(): Promise<void> {
    if (!token) {
      return;
    }
    if (!employeeCreateFullName.trim() || !employeeCreateEmail.trim()) {
      setNotice("Заполните ФИО и email сотрудника.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const created = await api<Employee & { generated_password?: string }>(
        "/students/employees",
        {
          method: "POST",
          body: JSON.stringify({
            full_name: employeeCreateFullName,
            email: employeeCreateEmail,
            password: employeeCreatePassword || undefined,
          }),
        },
        token
      );
      await Promise.all([loadEmployees(token), loadDashboard(token), loadEvents(token)]);
      setEmployeeCreateOpen(false);
      setEmployeeCreateFullName("");
      setEmployeeCreateEmail("");
      setEmployeeCreatePassword("");
      setHash(`/student/employees/${encodeURIComponent(created.id)}`);
      setNotice(created.generated_password ? `Сотрудник создан. Сгенерированный пароль: ${created.generated_password}` : "Сотрудник создан.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createEmployeeClient(): Promise<void> {
    if (!token) {
      return;
    }
    if (employees.length === 0) {
      setNotice("Сначала создайте сотрудника.");
      return;
    }

    const preferredEmployeeId =
      (route.route === "student" && (route.section === "employee-workspace" || route.section === "employee-profile") && route.employeeId) ||
      clientCreateEmployeeId ||
      employees[0]?.id;
    if (!preferredEmployeeId) {
      setNotice("Сначала создайте сотрудника.");
      return;
    }
    if (!clientCreateFirstName.trim() || !clientCreateLastName.trim() || !clientCreateEmail.trim()) {
      setNotice("Заполните имя, фамилию и email клиента.");
      return;
    }

    setBusy(true);
    setNotice("");
    try {
      const created = await api<Client & { generated_password?: string }>(
        `/students/employees/${encodeURIComponent(preferredEmployeeId)}/clients`,
        {
          method: "POST",
          body: JSON.stringify({
            student_username: (clientCreateStudentUsername || clientCreateEmail).trim().toLowerCase(),
            first_name: clientCreateFirstName.trim(),
            last_name: clientCreateLastName.trim(),
            phone: clientCreatePhone.trim() || "+79990000000",
            email: clientCreateEmail.trim().toLowerCase(),
          }),
        },
        token
      );
      await Promise.all([loadClients(token), loadDashboard(token), loadEvents(token)]);
      if (route.route === "student" && (route.section === "employee-workspace" || route.section === "employee-profile")) {
        await loadEmployeeProfile(token, preferredEmployeeId);
      }
      setClientCreateOpen(false);
      setClientCreateStudentUsername("");
      setClientCreateFirstName("Иван");
      setClientCreateLastName("Иванов");
      setClientCreatePhone("+79990000000");
      setClientCreateEmail("ivanov.client@demobank.local");
      setHash(`/student/clients/${encodeURIComponent(created.id)}`);
      setNotice(created.generated_password ? `Клиент создан. Сгенерированный пароль: ${created.generated_password}` : "Клиент создан.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  function openClientCreateModal(employeeId?: string): void {
    if (employees.length === 0) {
      setNotice("Сначала создайте сотрудника.");
      return;
    }
    const fallback = employeeId || employees[0]?.id || "";
    setClientCreateEmployeeId(fallback);
    setClientCreateOpen(true);
  }

  function openEmployeeEditForm(employee: Employee): void {
    const fullName = employee.full_name || `${employee.first_name || ""} ${employee.last_name || ""}`.trim();
    setEmployeeEditFullName(fullName);
    setEmployeeEditEmail(employee.email);
    setEmployeeEditOpen(true);
  }

  async function updateEmployeeUser(): Promise<void> {
    if (!token || !employeeProfile) {
      return;
    }
    if (!employeeEditFullName.trim() || !employeeEditEmail.trim()) {
      setNotice("Заполните ФИО и email.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/students/employees/${employeeProfile.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ full_name: employeeEditFullName, email: employeeEditEmail }),
        },
        token
      );
      await Promise.all([loadEmployees(token), loadDashboard(token), loadEvents(token), loadEmployeeProfile(token, employeeProfile.id)]);
      setEmployeeEditOpen(false);
      setNotice("Сотрудник обновлен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function changeEmployeeStatus(employeeId: string, blocked: boolean): Promise<void> {
    if (!token) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const endpoint = blocked ? "unblock" : "block";
      await api(`/students/employees/${employeeId}/${endpoint}`, { method: "PATCH" }, token);
      await Promise.all([loadEmployees(token), loadDashboard(token), loadEvents(token)]);
      if (route.route === "student" && route.section === "employee-profile" && route.employeeId === employeeId) {
        await loadEmployeeProfile(token, employeeId);
      }
      setNotice(blocked ? "Сотрудник разблокирован." : "Сотрудник заблокирован.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function deleteEmployeeUser(employeeId: string): Promise<void> {
    if (!token) {
      return;
    }
    if (!window.confirm("Удалить сотрудника и связанные данные клиентов безвозвратно?")) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/employees/${employeeId}`, { method: "DELETE" }, token);
      await Promise.all([loadEmployees(token), loadDashboard(token), loadClients(token), loadEvents(token)]);
      if (route.route === "student" && route.section === "employee-profile" && route.employeeId === employeeId) {
        setHash("/student/employees");
      }
      setNotice("Сотрудник удален.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function changeEmployeeClientStatus(clientId: string, endpoint: string): Promise<void> {
    if (!token) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/clients/${clientId}/${endpoint}`, { method: "PATCH" }, token);
      await Promise.all([loadClients(token), loadDashboard(token), loadEvents(token)]);
      if (route.route === "student" && route.section === "client-profile" && route.clientId === clientId) {
        await loadStudentClientProfile(token, clientId);
      }
      setNotice("Статус клиента обновлен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function deleteEmployeeClient(clientId: string): Promise<void> {
    if (!token) {
      return;
    }
    if (!window.confirm("Удалить клиента и все связанные сущности безвозвратно?")) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/clients/${clientId}?force=true`, { method: "DELETE" }, token);
      await Promise.all([loadClients(token), loadDashboard(token), loadEvents(token)]);
      if (route.route === "student" && route.section === "client-profile" && route.clientId === clientId) {
        setHash("/student/clients");
      }
      setNotice("Клиент удален.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function openAccountForClient(): Promise<void> {
    if (!token || !clientProfile) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/students/clients/${clientProfile.id}/accounts`,
        {
          method: "POST",
          body: JSON.stringify({ currency: newClientAccountCurrency, type: newClientAccountType }),
        },
        token
      );
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadEvents(token), loadDashboard(token), loadClients(token)]);
      setOpenAccountModal(false);
      setNotice("Счет для клиента открыт.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function changeEmployeeAccountStatus(accountId: string, endpoint: "block" | "unblock" | "close"): Promise<void> {
    if (!token || !clientProfile) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/accounts/${accountId}/${endpoint}`, { method: "PATCH" }, token);
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadEvents(token), loadDashboard(token)]);
      setNotice("Статус счета обновлен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function deleteEmployeeAccount(accountId: string): Promise<void> {
    if (!token || !clientProfile) {
      return;
    }
    if (!window.confirm("Удалить счет безвозвратно?")) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/accounts/${accountId}`, { method: "DELETE" }, token);
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadEvents(token), loadDashboard(token)]);
      setNotice("Счет удален.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function assignEmployeeTicket(): Promise<void> {
    if (!token || !selectedEmployeeTicketId || !clientProfile) {
      return;
    }
    const employeeId = String((clientProfile as Record<string, unknown>).employee_id || "");
    if (!employeeId) {
      setNotice("Не найден ответственный сотрудник для клиента.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/employees/${employeeId}/tickets/${selectedEmployeeTicketId}/assign`, { method: "PATCH" }, token);
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadEvents(token), loadEmployeeProfile(token, employeeId)]);
      setNotice("Тикет назначен на вас.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateEmployeeTicketStatus(ticketId: string, status: string): Promise<void> {
    if (!token || !clientProfile) {
      return;
    }
    const employeeId = String((clientProfile as Record<string, unknown>).employee_id || "");
    if (!employeeId) {
      setNotice("Не найден ответственный сотрудник для клиента.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/students/employees/${employeeId}/tickets/${ticketId}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
        },
        token
      );
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadEvents(token), loadEmployeeProfile(token, employeeId)]);
      setNotice("Статус тикета обновлен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function sendEmployeeTicketMessage(): Promise<void> {
    if (!token || !selectedEmployeeTicketId || !employeeTicketMessage.trim() || !clientProfile) {
      return;
    }
    const employeeId = String((clientProfile as Record<string, unknown>).employee_id || "");
    if (!employeeId) {
      setNotice("Не найден ответственный сотрудник для клиента.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/students/employees/${employeeId}/tickets/${selectedEmployeeTicketId}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ message: employeeTicketMessage }),
        },
        token
      );
      await Promise.all([loadEvents(token), loadStudentClientProfile(token, clientProfile.id), loadEmployeeProfile(token, employeeId)]);
      setNotice("Сообщение в тикет отправлено.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function assignManagedTicket(employeeId: string, ticketId: string): Promise<void> {
    if (!token) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(`/students/employees/${employeeId}/tickets/${ticketId}/assign`, { method: "PATCH" }, token);
      await Promise.all([loadEmployeeProfile(token, employeeId), loadEvents(token)]);
      setNotice("Тикет назначен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateManagedTicketStatus(employeeId: string, ticketId: string, status: string): Promise<void> {
    if (!token) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/students/employees/${employeeId}/tickets/${ticketId}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
        },
        token
      );
      await Promise.all([loadEmployeeProfile(token, employeeId), loadEvents(token)]);
      setNotice("Статус тикета обновлен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createOwnAccount(): Promise<void> {
    if (!token) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api<Account>(
        "/clients/me/accounts",
        {
          method: "POST",
          body: JSON.stringify({ currency: newOwnAccountCurrency, type: newOwnAccountType }),
        },
        token
      );
      await Promise.all([loadClientWorkspace(token), loadEvents(token)]);
      setOpenOwnAccountForm(false);
      setNotice("Счет создан.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function closeOwnAccount(accountId: string, hardDelete: boolean): Promise<void> {
    if (!token || !accountId) {
      return;
    }
    if (hardDelete && !window.confirm("Удалить счет безвозвратно?")) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const endpoint = hardDelete ? `/clients/me/accounts/${accountId}/hard-delete` : `/clients/me/accounts/${accountId}`;
      await api(endpoint, { method: "DELETE" }, token);
      await Promise.all([loadClientWorkspace(token), loadEvents(token)]);
      setNotice(hardDelete ? "Счет удален безвозвратно." : "Счет закрыт.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createOwnTransfer(): Promise<void> {
    if (!token) {
      return;
    }
    if (!transferSourceId || !transferTargetId || !transferAmount) {
      setNotice("Укажите источник, получателя и сумму перевода.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const source = accounts.find((item) => item.id === transferSourceId);
      await api(
        "/clients/me/transfers",
        {
          method: "POST",
          body: JSON.stringify({
            source_account_id: transferSourceId,
            target_account_id: transferTargetId,
            amount: Number(transferAmount),
            currency: source?.currency || "RUB",
            description: transferDescription,
            idempotency_key: `cabinet-ui-${Date.now()}`,
          }),
        },
        token
      );
      await Promise.all([loadClientWorkspace(token), loadEvents(token)]);
      setNotice("Перевод отправлен.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createOwnCashTopUp(): Promise<void> {
    if (!token) {
      return;
    }
    if (!ownTopUpAccountId || !ownTopUpAmount) {
      setNotice("Выберите счет и сумму для пополнения.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        "/clients/me/transfers/top-up",
        {
          method: "POST",
          body: JSON.stringify({
            account_id: ownTopUpAccountId,
            amount: Number(ownTopUpAmount),
            idempotency_key: `cabinet-top-up-${Date.now()}`,
          }),
        },
        token
      );
      await Promise.all([loadClientWorkspace(token), loadEvents(token)]);
      setNotice("Наличные зачислены на счет клиента.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createManagedClientCashTopUp(): Promise<void> {
    if (!token || !clientProfile) {
      return;
    }
    if (!clientTopUpAccountId || !clientTopUpAmount) {
      setNotice("Выберите счет клиента и сумму пополнения.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/students/clients/${clientProfile.id}/transfers/top-up`,
        {
          method: "POST",
          body: JSON.stringify({
            account_id: clientTopUpAccountId,
            amount: Number(clientTopUpAmount),
            idempotency_key: `student-client-top-up-${Date.now()}`,
          }),
        },
        token
      );
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadClients(token), loadDashboard(token), loadEvents(token)]);
      setNotice("Счет клиента пополнен наличными.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createManagedClientTransfer(): Promise<void> {
    if (!token || !clientProfile) {
      return;
    }
    if (!clientTransferSourceId || !clientTransferTargetId || !clientTransferAmount) {
      setNotice("Выберите счета клиента и сумму перевода.");
      return;
    }
    if (clientTransferSourceId === clientTransferTargetId) {
      setNotice("Счет списания и счет зачисления должны отличаться.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const source = clientProfileAccounts.find((item) => item.id === clientTransferSourceId);
      const target = clientProfileAccounts.find((item) => item.id === clientTransferTargetId);
      await api(
        `/students/clients/${clientProfile.id}/transfers/self`,
        {
          method: "POST",
          body: JSON.stringify({
            source_account_id: clientTransferSourceId,
            target_account_id: clientTransferTargetId,
            amount: Number(clientTransferAmount),
            currency: source?.currency || "RUB",
            description: clientTransferDescription,
            idempotency_key: `student-client-transfer-${Date.now()}`,
          }),
        },
        token
      );
      await Promise.all([loadStudentClientProfile(token, clientProfile.id), loadClients(token), loadDashboard(token), loadEvents(token)]);
      setNotice(
        source && target && source.currency !== target.currency
          ? `Перевод выполнен с конвертацией ${source.currency} -> ${target.currency}.`
          : "Перевод между счетами клиента выполнен."
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateEmployeeExchangeRate(quoteCurrency: string, rubAmount: number): Promise<void> {
    if (!token || !employeeProfile) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const updated = await api<ExchangeRate>(
        `/students/employees/${employeeProfile.id}/exchange-rates/${quoteCurrency}`,
        {
          method: "PUT",
          body: JSON.stringify({ rub_amount: rubAmount }),
        },
        token
      );
      setEmployeeExchangeRates((prev) => {
        const rest = prev.filter((item) => item.quote_currency !== updated.quote_currency);
        return [...rest, updated].sort((a, b) => a.quote_currency.localeCompare(b.quote_currency));
      });
      setNotice(`Курс RUB/${quoteCurrency} обновлен.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function createOwnTicket(): Promise<void> {
    if (!token || !ticketSubject.trim() || !ticketDescription.trim()) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const created = await api<Ticket>(
        "/clients/me/tickets",
        {
          method: "POST",
          body: JSON.stringify({
            subject: ticketSubject,
            description: ticketDescription,
            priority: "MEDIUM",
            category: ticketCategory,
          }),
        },
        token
      );
      await Promise.all([loadClientWorkspace(token), loadEvents(token)]);
      setSelectedOwnTicketId(created.id);
      setCreateTicketModalOpen(false);
      setNotice("Обращение создано.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function sendOwnTicketMessage(): Promise<void> {
    if (!token || !selectedOwnTicketId || !ownTicketMessage.trim()) {
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/clients/me/tickets/${selectedOwnTicketId}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ message: ownTicketMessage }),
        },
        token
      );
      await loadEvents(token);
      setNotice("Сообщение по обращению отправлено.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  const selectedToolService = useMemo<ToolService | null>(() => {
    if (route.route !== "student" || route.section !== "tool-detail" || !route.toolSlug) {
      return null;
    }
    return TOOL_SERVICE_BY_SLUG[route.toolSlug];
  }, [route]);

  const selectedToolAccess = useMemo(() => {
    if (!selectedToolService) {
      return null;
    }
    return activeToolsByService.get(selectedToolService) || null;
  }, [selectedToolService, activeToolsByService]);

  useEffect(() => {
    if (!token || !selectedToolService) {
      setToolRouteDenied("");
      return;
    }
    let cancelled = false;
    void api(`/students/tools/${selectedToolService}`, {}, token)
      .then(() => {
        if (!cancelled) {
          setToolRouteDenied("");
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setToolRouteDenied(error instanceof Error ? error.message : String(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, selectedToolService]);

  const createPractice = (...tasks: Omit<ToolPracticeTask, "id">[]): ToolPracticeTask[] =>
    tasks.map((task, index) => ({ id: index + 1, ...task }));

  const buildGenericToolPractice = (
    toolTitle: string,
    studentFilterHint: string,
    createdEntity: string,
    uiCheckPoint: string,
    technicalCheckPoint: string
  ): ToolPracticeTask[] =>
    createPractice(
      {
        goal: `Проверить доступ и базовое подключение к ${toolTitle}.`,
        preconditions: "У студента включен доступ к инструменту, студент авторизован в кабинете.",
        steps: [
          "Откройте инструмент из левого меню.",
          "Войдите под email и паролем студента.",
          `Проверьте, что доступны только ваши данные (${studentFilterHint}).`,
        ],
        expected: "Инструмент открывается без ошибок, данные других студентов не видны.",
        where: `Кабинет студента -> ${toolTitle} и сам инструмент.`,
      },
      {
        goal: "Найти собственные сущности по фильтру.",
        preconditions: "Есть минимум один сотрудник или клиент в вашем контуре.",
        steps: [
          "Примените фильтр по student_id/email/owner.",
          "Откройте найденные записи.",
          "Убедитесь, что чужие записи не отображаются.",
        ],
        expected: "Отображаются только ваши записи в пределах student scope.",
        where: technicalCheckPoint,
      },
      {
        goal: `Создать тестовый объект (${createdEntity}) и зафиксировать результат.`,
        preconditions: "Есть права на создание или запись в рамках инструмента.",
        steps: [
          `Создайте ${createdEntity} в инструменте или через связанный API.`,
          "Сохраните изменения.",
          "Проверьте, что объект связан с вашим контуром.",
        ],
        expected: "Новый объект создан и доступен только вашему студенту.",
        where: `${uiCheckPoint}; ${technicalCheckPoint}.`,
      },
      {
        goal: "Проверить, что изменения видны в UI кабинета.",
        preconditions: "Создан тестовый объект из предыдущего шага.",
        steps: [
          "Вернитесь в кабинет студента.",
          "Откройте соответствующую страницу (Сотрудники, Клиенты, Тикеты или Дашборд).",
          "Проверьте, что данные синхронизировались.",
        ],
        expected: "Изменения отображаются в UI кабинета без ручной правки базы.",
        where: uiCheckPoint,
      },
      {
        goal: "Проверить аудит и телеметрию по выполненному действию.",
        preconditions: "Выполнено хотя бы одно изменение данных.",
        steps: [
          "Откройте раздел Аудит в кабинете студента.",
          "Найдите событие по времени и типу операции.",
          "Сверьте actor и entity_id.",
        ],
        expected: "Событие в аудите содержит вашего пользователя и корректный объект.",
        where: "Кабинет студента -> Аудит / события.",
      },
      {
        goal: "Обновить ранее созданный объект.",
        preconditions: "Тестовый объект существует.",
        steps: [
          "Измените одно поле объекта.",
          "Сохраните изменения.",
          "Обновите страницу и проверьте, что значение сохранилось.",
        ],
        expected: "Обновление успешно применено и видно в интерфейсе.",
        where: `${uiCheckPoint}; ${technicalCheckPoint}.`,
      },
      {
        goal: "Проверить ограничение доступа к чужим данным.",
        preconditions: "Известен идентификатор чужой сущности или чужой namespace.",
        steps: [
          "Попробуйте запросить объект другого студента по прямому id/ключу.",
          "Попробуйте открыть чужой URL напрямую.",
          "Проверьте код ответа и текст ошибки.",
        ],
        expected: "Система возвращает 403/404 и не раскрывает содержимое чужих данных.",
        where: technicalCheckPoint,
      },
      {
        goal: "Сделать выгрузку или скрин результата.",
        preconditions: "Есть данные по вашему контуру.",
        steps: [
          "Выполните экспорт (CSV/JSON), если инструмент поддерживает экспорт.",
          "Если экспорта нет, сделайте скрин ключевых экранов.",
          "Сохраните артефакт для отчета.",
        ],
        expected: "Есть подтверждение результата в виде выгрузки или скрина.",
        where: `Инструмент ${toolTitle}.`,
      },
      {
        goal: "Удалить тестовый объект и проверить очистку.",
        preconditions: "Тестовый объект существует и доступен к удалению.",
        steps: [
          "Удалите тестовый объект.",
          "Обновите экран списка.",
          "Проверьте, что объект исчез в UI и в техническом инструменте.",
        ],
        expected: "Объект удален, следов в списках активных сущностей нет.",
        where: `${uiCheckPoint}; ${technicalCheckPoint}.`,
      },
      {
        goal: "Сравнить результат через второй канал доступа.",
        preconditions: "Есть доступ к API или другому инструменту из меню.",
        steps: [
          "Повторите один сценарий через альтернативный интерфейс (например, API вместо UI).",
          "Сравните итоговые данные.",
          "Подтвердите идентичность результатов.",
        ],
        expected: "Данные согласованы между UI, API и инструментом мониторинга.",
        where: `${technicalCheckPoint}; ${uiCheckPoint}.`,
      }
    );

  const buildToolPractice = (service: ToolService): ToolPracticeTask[] => {
    if (service === "GRAFANA") {
      return buildGenericToolPractice("Grafana", "по папке/дашбордам студента", "личный дашборд", "Дашборд студента", "Grafana -> Dashboards / Explore");
    }
    if (service === "JENKINS") {
      return createPractice(
        {
          goal: t("Открыть Jenkins и проверить доступ к job.", "Open Jenkins and verify access to the job."),
          preconditions: t("У студента активирован доступ JENKINS.", "Student has active JENKINS access."),
          steps: [
            t("Откройте раздел Jenkins в меню.", "Open Jenkins in the left menu."),
            t("Нажмите 'Открыть инструмент'.", "Click 'Open tool'."),
            t("Убедитесь, что открывается Jenkins UI.", "Verify Jenkins UI opens successfully."),
          ],
          expected: t("Jenkins открывается без ошибок.", "Jenkins opens without errors."),
          where: t("Кабинет студента -> Jenkins.", "Student cabinet -> Jenkins."),
        },
        {
          goal: t("Запустить job из кабинета.", "Run a job from the cabinet."),
          preconditions: t("Открыт раздел Jenkins.", "Jenkins section is open."),
          steps: [
            t("Нажмите кнопку запуска job.", "Click the run job button."),
            t("Дождитесь завершения запуска.", "Wait for run completion."),
            t("Проверьте новую строку в таблице запусков.", "Verify a new row appears in runs table."),
          ],
          expected: t("Появился build со статусом и ссылками.", "A build appears with status and links."),
          where: t("Кабинет студента -> Jenkins.", "Student cabinet -> Jenkins."),
        },
        {
          goal: t("Проверить Console output.", "Check Console output."),
          preconditions: t("Есть хотя бы один запуск.", "At least one run exists."),
          steps: [
            t("Откройте ссылку Console у последнего запуска.", "Open Console link for the latest run."),
            t("Проверьте, что лог содержит шаги запуска.", "Verify the log contains execution steps."),
            t("Сверьте номер build с таблицей.", "Compare build number with the runs table."),
          ],
          expected: t("Console лог доступен и читаемый.", "Console log is accessible and readable."),
          where: "Jenkins build console",
        },
        {
          goal: t("Проверить Allure report.", "Verify the Allure report."),
          preconditions: t("Есть хотя бы один запуск.", "At least one run exists."),
          steps: [
            t("Откройте ссылку Allure у последнего запуска.", "Open the Allure link for the latest run."),
            t("Проверьте overview и список тестов.", "Check overview and test list."),
            t("Сверьте статус отчета со статусом build.", "Compare report status with build status."),
          ],
          expected: t("Отчет открывается и соответствует запуску.", "Report opens and matches the run."),
          where: "Jenkins build -> Allure",
        },
        {
          goal: t("Изменить шаги job.", "Modify job steps."),
          preconditions: t("Есть доступ к конфигурации job.", "Job configuration is available."),
          steps: [
            t("Откройте Configure.", "Open Configure."),
            t("Добавьте новый shell-step или stage.", "Add a new shell step or stage."),
            t("Сохраните изменения и повторно запустите job.", "Save changes and rerun the job."),
          ],
          expected: t("Новый шаг сохраняется и выполняется.", "New step is saved and executed."),
          where: "Jenkins -> Configure / Build history",
        },
        {
          goal: t("Проверить негативный сценарий.", "Check a negative scenario."),
          preconditions: t("Можно редактировать job.", "Job is editable."),
          steps: [
            t("Добавьте команду, завершающуюся ошибкой.", "Add a command that fails."),
            t("Запустите job.", "Run the job."),
            t("Проверьте статус FAILED и текст ошибки.", "Verify FAILED status and error output."),
          ],
          expected: t("Build завершается в FAILED с диагностикой в логе.", "Build fails with diagnostics in logs."),
          where: "Jenkins -> Build history / Console",
        },
        {
          goal: t("Вернуть job в рабочее состояние.", "Restore job to a green state."),
          preconditions: t("Есть неуспешный запуск.", "There is a failed run."),
          steps: [
            t("Исправьте ошибочный шаг.", "Fix the failing step."),
            t("Сохраните конфигурацию и перезапустите job.", "Save configuration and rerun job."),
            t("Проверьте статус SUCCESS.", "Verify SUCCESS status."),
          ],
          expected: t("Job снова выполняется успешно.", "Job succeeds again."),
          where: "Jenkins -> Configure / Build history",
        },
        {
          goal: t("Проверить retention отчетов (10).", "Verify report retention (10)."),
          preconditions: t("Можно запускать job многократно.", "Job can be executed multiple times."),
          steps: [
            t("Сделайте 11+ запусков подряд.", "Run the job 11+ times."),
            t("Обновите историю запусков.", "Refresh run history."),
            t("Проверьте, что видны только последние 10 отчетов.", "Verify only the latest 10 reports remain."),
          ],
          expected: t("Сохраняются только последние 10 отчетов.", "Only last 10 reports are retained."),
          where: t("Кабинет студента -> Jenkins.", "Student cabinet -> Jenkins."),
        },
        {
          goal: t("Проверить аудит запуска Jenkins.", "Verify Jenkins run audit event."),
          preconditions: t("Сделан запуск job.", "A Jenkins run has been executed."),
          steps: [
            t("Откройте события в кабинете студента.", "Open events in student cabinet."),
            t("Найдите событие jenkins.job.run.", "Find jenkins.job.run event."),
            t("Сверьте build number и actor.", "Check build number and actor values."),
          ],
          expected: t("Событие корректно отражает выполненный запуск.", "Event correctly reflects executed run."),
          where: t("Кабинет студента -> События.", "Student cabinet -> Events."),
        },
        {
          goal: t("Подготовить pipeline для автотестов.", "Prepare pipeline for automated tests."),
          preconditions: t("Базовый запуск работает.", "Baseline run works."),
          steps: [
            t("Разбейте pipeline на checkout/test/report.", "Split pipeline into checkout/test/report stages."),
            t("Добавьте читаемые лог-сообщения.", "Add readable log messages."),
            t("Запустите pipeline и сохраните ссылки на Console/Allure.", "Run pipeline and save Console/Allure links."),
          ],
          expected: t("Pipeline готов к дальнейшему расширению.", "Pipeline is ready for further extension."),
          where: "Jenkins",
        }
      );
    }
    if (service === "ALLURE") {
      return createPractice(
        {
          goal: t("Создать минимальный автотест с Allure.", "Create a minimal automated test with Allure."),
          preconditions: t("Доступен Python-проект с pytest.", "A Python project with pytest is available."),
          steps: [
            t("Добавьте зависимость allure-pytest.", "Add allure-pytest dependency."),
            t("Напишите тест с одним assert.", "Write a test with one assert."),
            t("Запустите тесты с --alluredir=allure-results.", "Run tests with --alluredir=allure-results."),
          ],
          expected: t("Файлы результатов Allure созданы.", "Allure result files are generated."),
          where: t("Локальный репозиторий и Jenkins artifacts.", "Local repository and Jenkins artifacts."),
        },
        {
          goal: t("Добавить заголовок и описание теста.", "Add test title and description."),
          preconditions: t("Подключен allure-pytest.", "allure-pytest is installed."),
          steps: [
            t("Используйте @allure.title.", "Use @allure.title."),
            t("Используйте @allure.description.", "Use @allure.description."),
            t("Перезапустите тесты и проверьте отчет.", "Rerun tests and verify report."),
          ],
          expected: t("В отчете отображаются title и description.", "Report shows title and description."),
          where: "Allure report",
        },
        {
          goal: t("Добавить шаги выполнения.", "Add execution steps."),
          preconditions: t("Есть рабочий тест.", "A working test exists."),
          steps: [
            t("Оберните действия в allure.step().", "Wrap actions in allure.step()."),
            t("Сгруппируйте шаги по логике сценария.", "Group steps by scenario flow."),
            t("Проверьте отображение step tree.", "Check step tree in report."),
          ],
          expected: t("Шаги читабельно отображаются в отчете.", "Steps are clearly displayed in report."),
          where: "Allure report -> test details",
        },
        {
          goal: t("Добавить параметризацию теста.", "Add test parametrization."),
          preconditions: t("Есть базовый сценарий.", "A baseline test exists."),
          steps: [
            t("Используйте pytest.mark.parametrize.", "Use pytest.mark.parametrize."),
            t("Добавьте 3 входных набора данных.", "Add 3 input datasets."),
            t("Проверьте раздельные кейсы в отчете.", "Verify separate cases in report."),
          ],
          expected: t("Параметризованные кейсы видны отдельно.", "Parametrized cases are listed separately."),
          where: "Allure report -> test list",
        },
        {
          goal: t("Прикрепить текстовый артефакт.", "Attach a text artifact."),
          preconditions: t("Тест успешно выполняется.", "Test runs successfully."),
          steps: [
            t("Соберите диагностический текст.", "Prepare a diagnostics text."),
            t("Добавьте allure.attach(..., attachment_type=TEXT).", "Add allure.attach(..., attachment_type=TEXT)."),
            t("Проверьте attachment в отчете.", "Verify attachment in report."),
          ],
          expected: t("Текстовый attachment доступен в карточке теста.", "Text attachment is available in test card."),
          where: "Allure report -> attachments",
        },
        {
          goal: t("Прикрепить JSON-ответ API.", "Attach an API JSON response."),
          preconditions: t("Есть тест с API-вызовом.", "A test with API call exists."),
          steps: [
            t("Сохраните JSON-ответ в строку.", "Serialize API response to string."),
            t("Прикрепите JSON как attachment.", "Attach JSON as an attachment."),
            t("Проверьте форматирование в отчете.", "Check rendering in report."),
          ],
          expected: t("JSON доступен для разбора в отчете.", "JSON is available for analysis in report."),
          where: "Allure report -> attachments",
        },
        {
          goal: t("Сделать один тест падающим.", "Create one intentionally failing test."),
          preconditions: t("В проекте есть минимум 3 теста.", "Project has at least 3 tests."),
          steps: [
            t("Добавьте контролируемую ошибку assert.", "Add a controlled assert failure."),
            t("Запустите пакет тестов.", "Run the test suite."),
            t("Проверьте failed статус в отчете.", "Verify failed status in report."),
          ],
          expected: t("В отчете отображается failed кейс и трассировка.", "Report shows failed case and stack trace."),
          where: "Allure report -> failed tests",
        },
        {
          goal: t("Добавить маркировку severity и tags.", "Add severity and tags."),
          preconditions: t("Подключен allure-pytest.", "allure-pytest is available."),
          steps: [
            t("Добавьте @allure.severity и @allure.tag.", "Add @allure.severity and @allure.tag."),
            t("Разметьте минимум 3 теста.", "Label at least 3 tests."),
            t("Проверьте фильтрацию по тегам.", "Verify filtering by tags."),
          ],
          expected: t("Severity и tags видны в отчетах.", "Severity and tags are visible in report."),
          where: "Allure report filters",
        },
        {
          goal: t("Запустить тесты через Jenkins job.", "Run tests via Jenkins job."),
          preconditions: t("Открыта job training-github-allure.", "training-github-allure job is open."),
          steps: [
            t("Передайте параметры GITHUB_URL и GITHUB_BRANCH.", "Set GITHUB_URL and GITHUB_BRANCH parameters."),
            t("Запустите build.", "Start build."),
            t("Откройте archived allure-report.", "Open archived allure-report."),
          ],
          expected: t("Отчет сформирован и доступен в артефактах.", "Report is generated and available in artifacts."),
          where: "Jenkins -> training-github-allure -> build artifacts",
        },
        {
          goal: t("Собрать шаблон для будущих автотестов.", "Build a reusable template for future tests."),
          preconditions: t("Есть рабочий отчет Allure.", "A working Allure report exists."),
          steps: [
            t("Вынесите повторяющиеся шаги в helper-функции.", "Move repeated steps to helper functions."),
            t("Добавьте единый стиль именования тестов.", "Add unified test naming style."),
            t("Проверьте читаемость итогового отчета.", "Verify final report readability."),
          ],
          expected: t("Получен шаблон автотестов с чистым Allure-репортингом.", "You get a reusable test template with clean Allure reporting."),
          where: "Repository + Allure report",
        }
      );
    }
    if (service === "GRAPHQL") {
      return buildGenericToolPractice("GraphQL", "по полю owner/student_id", "запрос или мутацию", "Сотрудники / Клиенты в кабинете", "Postman или GraphQL endpoint");
    }
    if (service === "GRPC") {
      return buildGenericToolPractice("gRPC Service", "по контексту JWT", "RPC-вызов на создание сущности", "Сотрудники / Клиенты в кабинете", "Postman gRPC или grpcurl");
    }
    if (service === "KAFKA") {
      return createPractice(
        {
          goal: t("Подключиться к Kafka broker.", "Connect to the Kafka broker."),
          preconditions: t("Kafka контейнер запущен.", "Kafka container is running."),
          steps: [
            t("Откройте Conduktor Desktop.", "Open Conduktor Desktop."),
            t(`Укажите bootstrap server: ${HOST}:9092.`, `Set bootstrap server: ${HOST}:9092.`),
            t("Проверьте, что соединение установлено.", "Verify the connection is established."),
          ],
          expected: t("Подключение к Kafka успешно.", "Kafka connection is successful."),
          where: "Conduktor Desktop",
        },
        {
          goal: t("Проверить список топиков.", "Check the topic list."),
          preconditions: t("Подключение к Kafka активно.", "Kafka connection is active."),
          steps: [
            t("Откройте раздел Topics.", "Open the Topics section."),
            t("Проверьте наличие тестового топика.", "Verify a test topic exists."),
            t("При необходимости создайте новый топик.", "Create a new topic if needed."),
          ],
          expected: t("Топики отображаются корректно.", "Topics are displayed correctly."),
          where: "Conduktor Desktop",
        },
        {
          goal: t("Отправить тестовое сообщение producer-ом.", "Send a test message with a producer."),
          preconditions: t("Есть доступный топик.", "An accessible topic exists."),
          steps: [
            t("Создайте сообщение с JSON payload.", "Create a message with JSON payload."),
            t("Отправьте сообщение в выбранный топик.", "Send the message to the selected topic."),
            t("Проверьте успешную отправку.", "Verify successful publish."),
          ],
          expected: t("Сообщение записано в топик.", "The message is written to the topic."),
          where: "Conduktor Producer",
        },
        {
          goal: t("Прочитать сообщение consumer-ом.", "Read a message with a consumer."),
          preconditions: t("В топике есть хотя бы одно сообщение.", "At least one message is present in the topic."),
          steps: [
            t("Откройте просмотр сообщений топика.", "Open topic message viewer."),
            t("Запустите чтение с latest offset.", "Start reading from latest offset."),
            t("Проверьте содержимое payload.", "Verify payload content."),
          ],
          expected: t("Сообщение читается без ошибок.", "The message is consumed without errors."),
          where: "Conduktor Consumer",
        },
        {
          goal: t("Проверить ключ и заголовки сообщения.", "Validate message key and headers."),
          preconditions: t("Есть отправленное сообщение.", "There is a published message."),
          steps: [
            t("Откройте карточку сообщения.", "Open message details."),
            t("Проверьте key и headers.", "Check key and headers."),
            t("Сверьте значения с ожидаемыми.", "Compare values with expected ones."),
          ],
          expected: t("Key и headers заполнены корректно.", "Key and headers are set correctly."),
          where: "Conduktor message details",
        },
        {
          goal: t("Проверить повторную отправку нескольких сообщений.", "Verify batch publishing of multiple messages."),
          preconditions: t("Есть рабочий producer.", "Producer is operational."),
          steps: [
            t("Отправьте 5 сообщений подряд.", "Publish 5 messages in sequence."),
            t("Проверьте рост offset.", "Check offset growth."),
            t("Убедитесь, что все сообщения читаются.", "Ensure all messages are readable."),
          ],
          expected: t("Все отправленные сообщения доступны в топике.", "All published messages are available in the topic."),
          where: "Conduktor Topics",
        },
        {
          goal: t("Проверить Python producer/consumer.", "Validate Python producer/consumer."),
          preconditions: t("Установлен пакет kafka-python.", "kafka-python package is installed."),
          steps: [
            t("Запустите пример producer из раздела Examples.", "Run producer example from the Examples section."),
            t("Запустите consumer и прочитайте одно сообщение.", "Run consumer and read one message."),
            t("Проверьте вывод в консоли.", "Verify terminal output."),
          ],
          expected: t("Python код успешно отправляет и читает сообщение.", "Python code successfully publishes and consumes a message."),
          where: "Terminal + Python script",
        },
        {
          goal: t("Проверить поведение при несуществующем топике.", "Check behavior with a non-existing topic."),
          preconditions: t("Есть доступ к producer/consumer.", "Producer/consumer access is available."),
          steps: [
            t("Укажите несуществующий топик.", "Use a non-existing topic name."),
            t("Попробуйте отправить сообщение.", "Try publishing a message."),
            t("Проверьте ошибку и ее текст.", "Check error output and message."),
          ],
          expected: t("Получена ожидаемая ошибка конфигурации/топика.", "Expected topic/configuration error is returned."),
          where: "Conduktor or Python logs",
        },
        {
          goal: t("Проверить логи Kafka контейнера.", "Inspect Kafka container logs."),
          preconditions: t("Выполнены операции publish/consume.", "Publish/consume operations were executed."),
          steps: [
            t("Откройте логи kafka-контейнера.", "Open Kafka container logs."),
            t("Найдите записи о подключении клиента.", "Find client connection records."),
            t("Найдите записи по целевому топику.", "Find records for the target topic."),
          ],
          expected: t("Логи подтверждают операции с топиком.", "Logs confirm topic operations."),
          where: "docker logs kafka",
        },
        {
          goal: t("Подготовить минимальный Kafka чек-лист.", "Prepare a minimal Kafka checklist."),
          preconditions: t("Проверены connection, publish, consume.", "Connection, publish, and consume are verified."),
          steps: [
            t("Зафиксируйте bootstrap и имя топика.", "Document bootstrap and topic name."),
            t("Зафиксируйте команды/скрипты publish и consume.", "Document publish/consume commands or scripts."),
            t("Сохраните критерии успешной проверки.", "Save pass criteria."),
          ],
          expected: t("Готов практический чек-лист для повторной проверки Kafka.", "A practical checklist for repeat Kafka verification is ready."),
          where: "Project notes",
        }
      );
    }
    if (service === "POSTGRES") {
      return createPractice(
        {
          goal: t("Подключиться к PostgreSQL через DBeaver или psql.", "Connect to PostgreSQL using DBeaver or psql."),
          preconditions: t("Есть student credentials.", "Student credentials are available."),
          steps: [
            t("Откройте клиент базы данных.", "Open your DB client."),
            t("Укажите host, port, database, user, password.", "Set host, port, database, user, password."),
            t("Проверьте успешное подключение.", "Verify successful connection."),
          ],
          expected: t("Подключение установлено.", "Connection is established."),
          where: "DBeaver / psql",
        },
        {
          goal: t("Проверить список клиентов.", "Check the client list."),
          preconditions: t("Подключение к БД активно.", "Database connection is active."),
          steps: [
            t("Выполните SELECT для таблицы clients.", "Run SELECT query for clients table."),
            t("Отсортируйте по created_at DESC.", "Sort by created_at DESC."),
            t("Ограничьте выборку LIMIT 20.", "Limit output to 20 rows."),
          ],
          expected: t("Данные клиентов получены.", "Client data is returned."),
          where: "SQL editor",
        },
        {
          goal: t("Проверить список сотрудников.", "Check the employee list."),
          preconditions: t("Подключение к БД активно.", "Database connection is active."),
          steps: [
            t("Выполните SELECT для student_users.", "Run SELECT for student_users."),
            t("Отфильтруйте system_role='STUDENT'.", "Filter by system_role='STUDENT'."),
            t("Проверьте поля email/username/status.", "Verify email/username/status fields."),
          ],
          expected: t("Данные сотрудников доступны.", "Employee data is available."),
          where: "SQL editor",
        },
        {
          goal: t("Проверить связь clients -> accounts.", "Verify clients -> accounts relation."),
          preconditions: t("Есть записи клиентов и счетов.", "Clients and accounts records exist."),
          steps: [
            t("Сделайте JOIN clients и accounts.", "Run JOIN between clients and accounts."),
            t("Посчитайте количество счетов по client_id.", "Count accounts by client_id."),
            t("Сравните результат с UI кабинета.", "Compare with cabinet UI."),
          ],
          expected: t("Связи клиентов и счетов корректны.", "Client-account relations are correct."),
          where: "SQL editor + Student cabinet",
        },
        {
          goal: t("Проверить таблицу тикетов.", "Check support tickets table."),
          preconditions: t("В системе есть тикеты.", "There are tickets in the system."),
          steps: [
            t("Выполните SELECT из support_tickets.", "Run SELECT from support_tickets."),
            t("Проверьте статус и приоритет.", "Review status and priority fields."),
            t("Проверьте created_at/updated_at.", "Check created_at/updated_at."),
          ],
          expected: t("Тикеты читаются корректно.", "Tickets are returned correctly."),
          where: "SQL editor",
        },
        {
          goal: t("Сравнить данные API и БД.", "Compare API and DB results."),
          preconditions: t("Есть access token студента.", "Student access token is available."),
          steps: [
            t("Получите список клиентов через API.", "Fetch clients via API."),
            t("Получите тот же список SQL-запросом.", "Fetch the same list via SQL."),
            t("Сравните id/email/статусы.", "Compare id/email/status."),
          ],
          expected: t("API и БД возвращают согласованные данные.", "API and DB results are consistent."),
          where: "REST API + SQL editor",
        },
        {
          goal: t("Проверить сортировку и пагинацию SQL.", "Validate SQL sorting and pagination."),
          preconditions: t("Есть достаточно данных.", "Enough records exist."),
          steps: [
            t("Выполните запрос с ORDER BY и LIMIT.", "Run query with ORDER BY and LIMIT."),
            t("Добавьте OFFSET и проверьте следующую страницу.", "Add OFFSET and verify next page."),
            t("Убедитесь в стабильной сортировке.", "Verify stable ordering."),
          ],
          expected: t("Пагинация и сортировка работают предсказуемо.", "Pagination and sorting work predictably."),
          where: "SQL editor",
        },
        {
          goal: t("Проверить, что schema public доступна.", "Verify public schema access."),
          preconditions: t("Подключение от student account.", "Connected with student account."),
          steps: [
            t("Выполните SELECT current_schema().", "Run SELECT current_schema()."),
            t("Проверьте доступ к бизнес-таблицам.", "Check access to business tables."),
            t("Убедитесь, что запросы выполняются без ошибок прав.", "Ensure queries run without permission errors."),
          ],
          expected: t("Рабочая схема доступна для практики.", "Working schema is accessible for practice."),
          where: "SQL editor",
        },
        {
          goal: t("Экспортировать небольшой набор данных.", "Export a small dataset."),
          preconditions: t("Есть успешный SELECT.", "There is a successful SELECT query."),
          steps: [
            t("Сформируйте выборку LIMIT 20.", "Prepare query with LIMIT 20."),
            t("Экспортируйте результат в CSV.", "Export result to CSV."),
            t("Проверьте открытие файла.", "Verify file opens correctly."),
          ],
          expected: t("Экспорт выполнен без ошибок.", "Export completed without errors."),
          where: "DBeaver / psql output",
        },
        {
          goal: t("Подготовить SQL-шаблон для ежедневной проверки.", "Prepare a daily SQL check template."),
          preconditions: t("Есть рабочие запросы по clients/accounts/tickets.", "Working queries for clients/accounts/tickets exist."),
          steps: [
            t("Соберите 3-5 проверочных SELECT запросов.", "Collect 3-5 verification SELECT queries."),
            t("Добавьте комментарии по назначению запросов.", "Add comments with query purpose."),
            t("Проверьте выполнение шаблона целиком.", "Run the template end-to-end."),
          ],
          expected: t("Готов SQL-чеклист для регулярной валидации данных.", "A SQL checklist is ready for regular data validation."),
          where: "SQL editor",
        }
      );
    }
    if (service === "REDIS") {
      return createPractice(
        {
          goal: t("Подключиться к Redis через redis-cli.", "Connect to Redis with redis-cli."),
          preconditions: t("Redis контейнер запущен.", "Redis container is running."),
          steps: [
            t("Откройте терминал.", "Open terminal."),
            t(`Выполните: redis-cli -u redis://${HOST}:6379`, `Run: redis-cli -u redis://${HOST}:6379`),
            t("Проверьте ответ командой PING.", "Check connectivity with PING."),
          ],
          expected: t("Получен ответ PONG.", "PONG is returned."),
          where: "redis-cli",
        },
        {
          goal: t("Создать тестовые ключи строкового типа.", "Create test string keys."),
          preconditions: t("Есть подключение к Redis.", "Redis connection is established."),
          steps: [
            t("Выполните SET demo:status ok.", "Run SET demo:status ok."),
            t("Выполните SET demo:env local.", "Run SET demo:env local."),
            t("Проверьте значения через GET.", "Check values via GET."),
          ],
          expected: t("Ключи созданы и читаются без ошибок.", "Keys are created and readable."),
          where: "redis-cli / Redis Insight",
        },
        {
          goal: t("Проверить hash-структуру.", "Validate hash structure."),
          preconditions: t("Есть подключение к Redis.", "Redis connection is established."),
          steps: [
            t("Выполните HSET demo:user name Daniil role student.", "Run HSET demo:user name Daniil role student."),
            t("Выполните HGET demo:user name.", "Run HGET demo:user name."),
            t("Выполните HGETALL demo:user.", "Run HGETALL demo:user."),
          ],
          expected: t("Поля hash корректно сохраняются и читаются.", "Hash fields are stored and returned correctly."),
          where: "redis-cli / Redis Insight",
        },
        {
          goal: t("Проверить list-структуру.", "Validate list structure."),
          preconditions: t("Есть подключение к Redis.", "Redis connection is established."),
          steps: [
            t("Выполните LPUSH demo:queue task1 task2 task3.", "Run LPUSH demo:queue task1 task2 task3."),
            t("Выполните LRANGE demo:queue 0 -1.", "Run LRANGE demo:queue 0 -1."),
            t("Проверьте порядок элементов.", "Verify element order."),
          ],
          expected: t("Список доступен и возвращается в ожидаемом порядке.", "List is available and returned in expected order."),
          where: "redis-cli / Redis Insight",
        },
        {
          goal: t("Проверить TTL и срок жизни ключа.", "Validate TTL and key expiration."),
          preconditions: t("Есть тестовый ключ demo:ttl.", "There is a test key demo:ttl."),
          steps: [
            t("Выполните SET demo:ttl temp EX 120.", "Run SET demo:ttl temp EX 120."),
            t("Выполните TTL demo:ttl.", "Run TTL demo:ttl."),
            t("Проверьте, что TTL уменьшается со временем.", "Verify TTL decreases over time."),
          ],
          expected: t("Ключ имеет TTL и автоматически истекает.", "Key has TTL and expires automatically."),
          where: "redis-cli",
        },
        {
          goal: t("Обновить существующее значение.", "Update existing value."),
          preconditions: t("Есть ключ demo:status.", "Key demo:status exists."),
          steps: [
            t("Выполните SET demo:status updated.", "Run SET demo:status updated."),
            t("Выполните GET demo:status.", "Run GET demo:status."),
            t("Зафиксируйте новое значение.", "Capture updated value."),
          ],
          expected: t("Значение ключа обновлено.", "Key value is updated."),
          where: "redis-cli / Redis Insight",
        },
        {
          goal: t("Проверить поиск ключей по шаблону.", "Validate key search by pattern."),
          preconditions: t("Созданы ключи с префиксом demo:.", "Keys with demo: prefix are created."),
          steps: [
            t("Выполните SCAN 0 MATCH demo:* COUNT 100.", "Run SCAN 0 MATCH demo:* COUNT 100."),
            t("Проверьте, что возвращаются тестовые ключи.", "Verify test keys are returned."),
            t("Повторите SCAN до завершения курсора.", "Repeat SCAN until cursor is complete."),
          ],
          expected: t("Ключи по шаблону находятся корректно.", "Pattern-based key lookup works correctly."),
          where: "redis-cli",
        },
        {
          goal: t("Проверить удаление ключей.", "Validate key deletion."),
          preconditions: t("Есть ключ demo:env.", "Key demo:env exists."),
          steps: [
            t("Выполните DEL demo:env.", "Run DEL demo:env."),
            t("Проверьте через EXISTS demo:env.", "Check via EXISTS demo:env."),
            t("Убедитесь, что ключ удален.", "Ensure key is removed."),
          ],
          expected: t("Ключ удален и больше не доступен.", "Key is deleted and no longer available."),
          where: "redis-cli / Redis Insight",
        },
        {
          goal: t("Сравнить данные Redis Insight и redis-cli.", "Compare Redis Insight and redis-cli output."),
          preconditions: t("Установлен Redis Insight.", "Redis Insight is installed."),
          steps: [
            t("Откройте Redis Insight и подключитесь к localhost:6379.", "Open Redis Insight and connect to localhost:6379."),
            t("Найдите ключи demo:* в UI.", "Find demo:* keys in UI."),
            t("Сверьте значения с выводом redis-cli.", "Compare values with redis-cli output."),
          ],
          expected: t("Данные совпадают в UI и CLI.", "Data matches in UI and CLI."),
          where: "Redis Insight + redis-cli",
        },
        {
          goal: t("Очистить тестовые ключи после практики.", "Clean up test keys after practice."),
          preconditions: t("Есть созданные demo:* ключи.", "There are created demo:* keys."),
          steps: [
            t("Найдите ключи через SCAN 0 MATCH demo:* COUNT 100.", "Find keys via SCAN 0 MATCH demo:* COUNT 100."),
            t("Удалите найденные ключи через DEL.", "Delete found keys via DEL."),
            t("Повторно проверьте SCAN.", "Run SCAN again."),
          ],
          expected: t("Тестовые ключи удалены.", "Test keys are removed."),
          where: "redis-cli",
        }
      );
    }
    return createPractice(
      {
        goal: "Проверить доступ к документации REST API.",
        preconditions: "Студент авторизован, доступ REST API включен.",
        steps: [
          "Откройте пункт REST API / Swagger в меню.",
          "Проверьте, что документация открывается без 403.",
          "Проверьте, что доступна только student-группа методов.",
        ],
        expected: "Swagger доступен, только student-методы доступны.",
        where: "Кабинет студента -> REST API / Swagger.",
      },
      {
        goal: "Получить JWT access token по логину и паролю студента.",
        preconditions: "Известны email и пароль студента.",
        steps: [
          "Отправьте POST /auth/login с email и паролем.",
          "Сохраните access_token из ответа.",
          "Проверьте, что токен имеет роль STUDENT.",
        ],
        expected: "Получен валидный Bearer token.",
        where: "Postman/curl и endpoint авторизации.",
      },
      {
        goal: "Выполнить защищенный запрос с Bearer token.",
        preconditions: "Есть access_token.",
        steps: [
          "Добавьте заголовок Authorization: Bearer <token>.",
          "Вызовите /students/me или /students/dashboard.",
          "Проверьте, что ответ содержит ваши данные.",
        ],
        expected: "Запрос успешен (200), данные принадлежат текущему студенту.",
        where: "REST API endpoint и кабинет студента.",
      },
      {
        goal: "Проверить ограничение на чужие данные через REST.",
        preconditions: "Есть id сущности другого студента.",
        steps: [
          "Выполните запрос по чужому id.",
          "Проверьте HTTP код и тело ошибки.",
          "Убедитесь, что данные не раскрываются.",
        ],
        expected: "Система возвращает 403 или 404.",
        where: "REST API response.",
      },
      {
        goal: "Создать сотрудника через API и проверить в UI.",
        preconditions: "Есть access_token, валидационные поля заполнены.",
        steps: [
          "Выполните POST /students/employees.",
          "Откройте раздел Сотрудники в кабинете.",
          "Найдите созданного сотрудника.",
        ],
        expected: "Сотрудник создан и отображается в UI.",
        where: "REST API и кабинет студента -> Сотрудники.",
      },
      {
        goal: "Создать клиента через API и проверить привязку к сотруднику.",
        preconditions: "Существует сотрудник в вашем контуре.",
        steps: [
          "Выполните POST /students/employees/{employee_id}/clients.",
          "Проверьте карточку сотрудника.",
          "Проверьте карточку клиента.",
        ],
        expected: "Клиент создан и корректно привязан к сотруднику.",
        where: "Карточка сотрудника и карточка клиента в кабинете.",
      },
      {
        goal: "Обновить клиента через API и проверить аудит.",
        preconditions: "Клиент существует.",
        steps: [
          "Выполните PATCH/PUT для клиента.",
          "Откройте карточку клиента в UI.",
          "Проверьте событие в аудите.",
        ],
        expected: "Изменение применилось, событие аудита зафиксировано.",
        where: "REST API, UI клиента, аудит.",
      },
      {
        goal: "Создать и обработать тикет через API.",
        preconditions: "Есть клиент в вашем контуре.",
        steps: [
          "Создайте тикет через API.",
          "Откройте тикет в UI сотрудника/студента.",
          "Измените статус тикета.",
        ],
        expected: "Тикет проходит жизненный цикл и виден в интерфейсе.",
        where: "REST API и UI разделов Тикеты.",
      },
      {
        goal: "Проверить refresh token сценарий.",
        preconditions: "Есть refresh_token из /auth/login.",
        steps: [
          "Вызовите endpoint обновления токена.",
          "Получите новый access_token.",
          "Повторите защищенный запрос с новым токеном.",
        ],
        expected: "Старый токен можно заменить новым без повторного логина.",
        where: "Postman/curl и auth endpoints.",
      },
      {
        goal: "Подготовить мини-интеграционный сценарий.",
        preconditions: "Созданы минимум 1 сотрудник и 1 клиент.",
        steps: [
          "Через API создайте клиента и тикет.",
          "Через UI проверьте появление сущностей.",
          "Через аудит подтвердите все действия.",
        ],
        expected: "Полный цикл подтвержден в API, UI и аудите.",
        where: "REST API, кабинет студента, аудит.",
      }
    );
  };

  const getToolPurpose = (service: ToolService): string[] => {
    if (service === "JENKINS") {
      return [
        t("Jenkins нужен для CI/CD: запускать pipeline, автотесты и хранить историю сборок.", "Jenkins is used for CI/CD: running pipelines, automated tests, and build history."),
        t("Через Jenkins проверяется, что изменения в репозитории стабильно проходят тесты.", "Jenkins is used to verify repository changes consistently pass tests."),
      ];
    }
    if (service === "ALLURE") {
      return [
        t("Allure нужен для визуального анализа результатов автотестов: шаги, ошибки, вложения, тренды.", "Allure is used for visual analysis of automated test results: steps, failures, attachments, trends."),
        t("В проекте Allure дополняет Jenkins и ускоряет разбор причин падения тестов.", "In this project, Allure complements Jenkins and speeds up failure investigation."),
      ];
    }
    if (service === "POSTGRES") {
      return [
        t("PostgreSQL хранит основные бизнес-данные платформы: сотрудники, клиенты, счета, тикеты.", "PostgreSQL stores core platform business data: employees, clients, accounts, tickets."),
        t("Используется для проверки целостности данных и сверки API/UI с фактическими записями в БД.", "It is used to validate data integrity and compare API/UI behavior with actual DB records."),
      ];
    }
    if (service === "REST_API") {
      return [
        t("REST API — главный интерфейс интеграции: через него выполняются операции и автоматизация тестов.", "REST API is the main integration interface for operations and test automation."),
        t("Swagger в проекте нужен как справочник контрактов и схем запросов/ответов.", "Swagger is used as a contract and request/response schema reference."),
      ];
    }
    if (service === "REDIS") {
      return [
        t("Redis в проекте используется для кеша, быстрых временных данных и ускорения API-операций.", "Redis is used for cache, fast temporary data, and API acceleration."),
        t("Через Redis удобно проверять состояние ключей и влияние фоновых процессов.", "Redis helps validate key state and background process effects."),
      ];
    }
    if (service === "KAFKA") {
      return [
        t("Kafka используется для событийной интеграции между сервисами и асинхронной обработки действий.", "Kafka is used for event-driven integration between services and asynchronous processing."),
        t("В проекте Kafka используется как broker событий; проверка выполняется через CLI-клиенты и логи сервисов.", "In this project Kafka is used as an event broker; verification is done via CLI clients and service logs."),
      ];
    }
    return [
      t("Инструмент используется для инфраструктурной отладки и проверки интеграций.", "This tool is used for infrastructure debugging and integration validation."),
    ];
  };

  const getToolGuide = (service: ToolService): ToolGuide => {
    if (service === "GRAFANA") {
      return {
        summary: [
          "Grafana визуализирует метрики и события в виде дашбордов, панелей и алертов.",
          "Prometheus собирает метрики, Grafana читает их и показывает в наглядном виде.",
          "Для студента важен собственный скоуп: панели и фильтры должны быть привязаны к вашему student_id.",
        ],
        connection: [
          `URL: ${TOOL_MAP.GRAFANA.url || "-"}.`,
          "Войдите под email и паролем студента (единые учетные данные).",
          "Откройте папку или дашборд своего контура, примените переменную фильтра student_id.",
          "Если вход не проходит, проверьте, что доступ к инструменту включен для вашей учетной записи.",
        ],
        auth: [
          `Логин: ${profile?.email || "-"}.`,
          "Пароль: тот же, что у кабинета студента.",
          "Рекомендуемая роль: Viewer или ограниченный Editor только в личной папке.",
        ],
        isolation: [
          "Работайте только в личной папке дашбордов или в фильтрованном datasource.",
          "Не редактируйте глобальные dashboards без отдельного разрешения.",
          "Проверяйте, что запросы панели всегда содержат фильтр по student_id.",
        ],
        practice: buildToolPractice(service),
        examples: [
          {
            title: "Проверочный PromQL фильтр",
            language: "promql",
            code: "sum(rate(bank_student_events_total{student_id=\"$student_id\"}[5m]))",
          },
        ],
      };
    }
    if (service === "JENKINS") {
      return {
        summary: [
          t("Jenkins запускает automation job/pipeline и хранит историю запусков.", "Jenkins runs automation jobs/pipelines and stores build history."),
          t("Каждый build содержит статус, console logs, артефакты и ссылку на отчет.", "Each build includes status, console logs, artifacts, and report link."),
          t("Allure используется для визуализации результатов автотестов.", "Allure is used to visualize automated test results."),
          t("Для CI-практики рекомендуется хранить pipeline как код (Jenkinsfile).", "For CI practice, keep the pipeline as code (Jenkinsfile)."),
        ],
        connection: [
          t(`URL Jenkins: ${TOOL_MAP.JENKINS.url || "-"}.`, `Jenkins URL: ${TOOL_MAP.JENKINS.url || "-"}.`),
          t("Откройте Jenkins кнопкой 'Открыть инструмент'.", "Open Jenkins via the 'Open tool' button."),
          t(`Логин: ${TRAINING_STUDENT_LOGIN}, пароль: ${TRAINING_STUDENT_PASSWORD}.`, `Login: ${TRAINING_STUDENT_LOGIN}, password: ${TRAINING_STUDENT_PASSWORD}.`),
          t("Для запуска тестов из GitHub используйте job training-github-allure.", "Use training-github-allure job to run tests from GitHub."),
        ],
        auth: [],
        isolation: [],
        practice: buildToolPractice(service),
        examples: [
          {
            title: t("Пример Jenkinsfile (Pipeline)", "Jenkinsfile example (Pipeline)"),
            language: "groovy",
            code: `pipeline {\n  agent any\n  stages {\n    stage('Checkout') {\n      steps {\n        checkout scm\n      }\n    }\n    stage('Tests') {\n      steps {\n        sh 'pytest -q --alluredir=allure-results'\n      }\n    }\n    stage('Allure') {\n      steps {\n        sh 'allure generate allure-results -o allure-report --clean'\n      }\n    }\n  }\n}`,
          },
          {
            title: t("Пример shell step", "Shell step example"),
            language: "bash",
            code: "pytest -q --alluredir=allure-results",
          },
        ],
      };
    }
    if (service === "ALLURE") {
      return {
        summary: [
          t("Allure показывает результаты автотестов: passed/failed, шаги, вложения и историю.", "Allure shows automated test results: passed/failed, steps, attachments, and history."),
          t("Отчет формируется из папки allure-results и публикуется как HTML.", "The report is generated from allure-results and published as HTML."),
          t("В этом проекте отчеты создаются через Jenkins job training-github-allure.", "In this project, reports are generated via the Jenkins job training-github-allure."),
        ],
        connection: [
          t("Зайдите в Jenkins и нажмите возле запуска на allure отчет.", "Open Jenkins and click the Allure report link next to the run."),
        ],
        auth: [],
        isolation: [],
        practice: buildToolPractice(service),
        examples: [
          {
            title: t("Python + pytest + allure", "Python + pytest + allure"),
            language: "python",
            code: `import allure\n\n@allure.title(\"Client can be created\")\n@allure.severity(allure.severity_level.CRITICAL)\ndef test_create_client(api_client):\n    with allure.step(\"Create a client via API\"):\n        response = api_client.post(\"/students/clients\", json={\"first_name\": \"Jane\", \"last_name\": \"Doe\"})\n    allure.attach(response.text, name=\"api_response\", attachment_type=allure.attachment_type.JSON)\n    assert response.status_code == 200`,
          },
          {
            title: t("Команда запуска с отчетом", "Run command with report output"),
            language: "bash",
            code: "pytest -q --alluredir=allure-results && allure generate allure-results -o allure-report --clean",
          },
        ],
      };
    }
    if (service === "GRAPHQL") {
      return {
        summary: [
          "GraphQL позволяет запрашивать только нужные поля и объединять несколько сущностей в один запрос.",
          "Преимущество перед REST: меньше лишних полей и меньше round-trip запросов.",
          "Недостаток: сложнее кеширование и контроль тяжёлых запросов без ограничений depth/cost.",
        ],
        connection: [
          `Endpoint: ${TOOL_MAP.GRAPHQL.url || "-"}.`,
          "Откройте Postman или GraphQL-клиент.",
          "Метод: POST, Content-Type: application/json, Header Authorization: Bearer <token>.",
          "Перед вызовами получите JWT в /auth/login тем же email и паролем студента.",
        ],
        auth: [
          "Для запросов используйте только токен студента.",
          "Внутренние проверки ownership выполняются на backend и не зависят от UI.",
          "При отключенном доступе к GraphQL backend возвращает 403 Forbidden.",
        ],
        isolation: [
          "Query и mutation должны работать только с вашими сотрудниками, клиентами, счетами и тикетами.",
          "Попытка доступа к чужим id должна возвращать 403/404.",
          "Проверяйте наличие student_id в ответах и аудит-событиях.",
        ],
        practice: buildToolPractice(service),
        examples: [
          {
            title: "Пример query",
            language: "graphql",
            code: `query Employees {\n  studentEmployees {\n    id\n    fullName\n    email\n    status\n  }\n}`,
          },
          {
            title: "Пример mutation",
            language: "graphql",
            code: `mutation CreateEmployee {\n  createStudentEmployee(input: { fullName: "Тестовый Сотрудник", email: "employee.demo@bank.local" }) {\n    id\n    fullName\n    status\n  }\n}`,
          },
        ],
      };
    }
    if (service === "GRPC") {
      return {
        summary: [
          "gRPC использует Protocol Buffers для строгих контрактов между сервисами.",
          "Плюсы: высокая производительность, строгая типизация, двоичный протокол, потоковые вызовы.",
          "Минусы: сложнее ручная отладка, требуется proto-контракт и специализированные клиенты.",
        ],
        connection: [
          `Endpoint: ${TOOL_MAP.GRPC.hint}.`,
          "В Postman импортируйте соответствующий .proto файл.",
          "Выберите RPC-метод и добавьте metadata: Authorization=Bearer <token>.",
          "Проверьте, что в request передаются только id из вашего student scope.",
        ],
        auth: [
          "JWT токен должен быть получен в BANK через /auth/login.",
          "Токен пробрасывается в gRPC metadata и валидируется сервером.",
          "Без токена или с чужим токеном ожидается UNAUTHENTICATED/PERMISSION_DENIED.",
        ],
        isolation: [
          "RPC-методы обязаны фильтровать данные по student_id из токена.",
          "Даже при ручной подстановке чужого id сервер должен отклонять запрос.",
          "Аудит должен фиксировать RPC вызовы с вашим actor_id.",
        ],
        practice: buildToolPractice(service),
        examples: [
          {
            title: "Пример grpcurl запроса",
            language: "bash",
            code: `grpcurl -plaintext -H "Authorization: Bearer <token>" -d '{"employee_id":"emp-1001"}' ${HOST}:50051 bank.student.EmployeeService/GetEmployee`,
          },
        ],
      };
    }
    if (service === "KAFKA") {
      return {
        summary: [
          t("Kafka хранит события в топиках, а потребители читают их асинхронно.", "Kafka stores events in topics, and consumers process them asynchronously."),
          t("В текущем стенде web-интерфейс для Kafka не развернут.", "Kafka web UI is not deployed in the current setup."),
          t("Для практики используйте локальный broker и клиентские инструменты.", "Use the local broker and client tools for practice."),
        ],
        connection: [
          t("Используйте Conduktor Desktop для подключения к Kafka и просмотра топиков.", "Use Conduktor Desktop to connect to Kafka and inspect topics."),
          t(`Bootstrap для локальных клиентов: ${HOST}:9092.`, `Bootstrap for local clients: ${HOST}:9092.`),
          t("Bootstrap для клиентов внутри docker-compose: kafka:9092.", "Bootstrap for clients inside docker-compose: kafka:9092."),
          t("Для автоматизации используйте Python-библиотеку kafka-python (пример ниже).", "For automation use the kafka-python library (example below)."),
        ],
        auth: [],
        isolation: [],
        practice: buildToolPractice(service),
        examples: [
          {
            title: t("Python пример producer/consumer", "Python producer/consumer example"),
            language: "python",
            code: `from kafka import KafkaProducer, KafkaConsumer\nimport json\n\nBOOTSTRAP = "${HOST}:9092"\nTOPIC = "bank.student.events"\n\nproducer = KafkaProducer(\n    bootstrap_servers=BOOTSTRAP,\n    value_serializer=lambda value: json.dumps(value).encode("utf-8"),\n)\nproducer.send(TOPIC, {"event": "demo_event", "source": "training"})\nproducer.flush()\n\nconsumer = KafkaConsumer(\n    TOPIC,\n    bootstrap_servers=BOOTSTRAP,\n    auto_offset_reset="latest",\n    enable_auto_commit=True,\n    value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),\n)\n\nfor message in consumer:\n    print(message.value)\n    break`,
          },
        ],
      };
    }
    if (service === "POSTGRES") {
      return {
        summary: [
          t("PostgreSQL — основная транзакционная БД для сотрудников, клиентов, счетов и тикетов.", "PostgreSQL is the core transactional database for employees, clients, accounts, and tickets."),
          t("Используйте SQL-проверки, чтобы валидировать данные из UI и API.", "Use SQL checks to validate what you see in UI and API responses."),
          t("В student mode делайте упор на безопасные read-сценарии и проверочные запросы.", "In student mode, focus on safe read scenarios and verification queries."),
        ],
        connection: [
          t("Используйте DBeaver или psql.", "Use DBeaver or psql."),
          `Host: ${HOST}, port: 5432, database: demobank.`,
          t(`User: ${TRAINING_STUDENT_LOGIN}, password: ${TRAINING_STUDENT_PASSWORD}.`, `User: ${TRAINING_STUDENT_LOGIN}, password: ${TRAINING_STUDENT_PASSWORD}.`),
          t("Выполняйте SELECT-запросы для проверки сгенерированных сущностей и связей.", "Run SELECT queries to validate generated entities and links."),
        ],
        auth: [],
        isolation: [],
        practice: buildToolPractice(service),
        examples: [
          {
            title: t("Проверочный SQL", "Verification SQL"),
            language: "sql",
            code: "SELECT id, first_name, last_name, email FROM clients ORDER BY created_at DESC LIMIT 20;",
          },
        ],
      };
    }
    if (service === "REDIS") {
      return {
        summary: [
          t("Redis используется для кеша, сессий, counters и быстрых временных структур.", "Redis is used for cache, sessions, counters, and fast temporary structures."),
          t("Redis полезен для проверки фоновых операций и кэширования API.", "Redis is useful for validating background operations and API caching."),
        ],
        connection: [
          t("Установите Redis Insight или используйте redis-cli.", "Install Redis Insight or use redis-cli."),
          t(`Endpoint: redis://${HOST}:6379.`, `Endpoint: redis://${HOST}:6379.`),
          t(`Логин/пароль: ${TRAINING_STUDENT_LOGIN} / ${TRAINING_STUDENT_PASSWORD}.`, `Login/password: ${TRAINING_STUDENT_LOGIN} / ${TRAINING_STUDENT_PASSWORD}.`),
        ],
        auth: [],
        isolation: [],
        practice: buildToolPractice(service),
        examples: [
          {
            title: t("Проверка ключей (CMD и macOS/Ubuntu)", "Key check (CMD and macOS/Ubuntu)"),
            language: "bash",
            code: `# macOS / Ubuntu terminal\nredis-cli -u redis://${HOST}:6379 SCAN 0 MATCH demo:* COUNT 100\n\n:: Windows CMD\nredis-cli.exe -h ${HOST} -p 6379 SCAN 0 MATCH demo:* COUNT 100`,
          },
        ],
      };
    }
    return {
      summary: [
        t(
          "REST API — основной HTTP-интерфейс стенда для авторизации, чтения данных и создания сущностей студента.",
          "REST API is the main HTTP interface for authentication, reading data, and creating student entities."
        ),
        t(
          "Swagger здесь нужен как справочник по контрактам: какие есть методы, какие поля обязательны и какие ответы возвращаются.",
          "Swagger is used as a contract reference: available methods, required fields, and response formats."
        ),
        t(
          "Практические вызовы удобнее выполнять через Postman или curl, потому что они позволяют явно управлять токенами, окружениями и повторным запуском запросов.",
          "Practical calls are easier through Postman or curl because they give explicit control over tokens, environments, and repeated requests."
        ),
      ],
      connection: [
        t(`Swagger URL: ${TOOL_MAP.REST_API.url || "-"}.`, `Swagger URL: ${TOOL_MAP.REST_API.url || "-"}.`),
        t(`API base URL: ${API}.`, `API base URL: ${API}.`),
        t(
          "Скачайте Postman Desktop App с https://www.postman.com/downloads/ и установите обычным инсталлятором под вашу ОС.",
          "Download Postman Desktop App from https://www.postman.com/downloads/ and install it for your OS."
        ),
        t(
          "После установки создайте в Postman новый HTTP Request или Collection и задайте переменную base_url со значением API base URL.",
          "After installation, create a new HTTP Request or Collection in Postman and set `base_url` to the API base URL."
        ),
        t(
          "Для всех student-методов используйте Header Authorization: Bearer <access_token>; Content-Type: application/json.",
          "For all student methods use Authorization: Bearer <access_token> and Content-Type: application/json."
        ),
        t(
          "Swagger оставьте для чтения схемы, примеров полей и кодов ответов, а реальные вызовы запускайте из Postman/curl.",
          "Use Swagger for schemas and response codes, and execute real calls from Postman/curl."
        ),
      ],
      auth: [
        t(`Логин: ${TRAINING_STUDENT_LOGIN}.`, `Login: ${TRAINING_STUDENT_LOGIN}.`),
        t(`Пароль: ${TRAINING_STUDENT_PASSWORD}.`, `Password: ${TRAINING_STUDENT_PASSWORD}.`),
        t(
          "access_token — короткоживущий рабочий токен. Он нужен для всех обычных API-запросов в Authorization: Bearer <access_token>.",
          "access_token is a short-lived working token. Use it in Authorization: Bearer <access_token> for regular API requests."
        ),
        t(
          "refresh_token — токен продления сессии. Он не подставляется в обычные методы и нужен только для POST /auth/refresh, чтобы получить новую пару токенов без повторного логина.",
          "refresh_token is used only to renew the session via POST /auth/refresh and should not be sent to regular business endpoints."
        ),
        t(
          "Если access_token истек, не логиньтесь заново каждый раз: сначала вызывайте /auth/refresh с refresh_token, потом повторяйте рабочий запрос уже с новым access_token.",
          "If access_token is expired, call /auth/refresh with refresh_token first, then repeat the business request with a new access_token."
        ),
      ],
      isolation: [
        t(
          "Как подключить Postman: New -> HTTP Request, затем Method + URL, потом вкладка Headers и Body -> raw -> JSON.",
          "Postman quick setup: New -> HTTP Request, then Method + URL, then Headers and Body -> raw -> JSON."
        ),
        t(
          "Как хранить токены в Postman: создайте переменные access_token и refresh_token в Environment и подставляйте их как {{access_token}} и {{refresh_token}}.",
          "Store tokens in Postman Environment variables as {{access_token}} and {{refresh_token}}."
        ),
        t(
          "Как автоматизировать refresh: сначала сохраните refresh_token из /auth/login в Environment, затем отдельным запросом /auth/refresh обновляйте access_token перед серией вызовов.",
          "Automate refresh by saving refresh_token from /auth/login and updating access_token via /auth/refresh before request series."
        ),
        t(
          "Как читать Swagger: открывайте нужный метод, смотрите Request body schema, обязательные поля, примеры ответов и уже потом переносите запрос в Postman.",
          "Use Swagger by checking request schema, required fields, and response examples, then move calls to Postman."
        ),
      ],
      practice: buildToolPractice("REST_API"),
      examples: [
        {
          title: t("1) Логин и получение пары токенов", "1) Login and get token pair"),
          language: "bash",
          code: `curl -X POST '${API}/auth/login' \\\n  -H 'Content-Type: application/json' \\\n  -d '{\n    "email": "${TRAINING_STUDENT_LOGIN}",\n    "password": "${TRAINING_STUDENT_PASSWORD}"\n  }'`,
        },
        {
          title: t("2) Что делать с access_token", "2) Use access_token for business endpoints"),
          language: "bash",
          code: `curl -X GET '${API}/students/dashboard' \\\n  -H 'Authorization: Bearer <jwt_access_token>' \\\n  -H 'Content-Type: application/json'`,
        },
        {
          title: t("3) Создать сотрудника с access_token", "3) Create employee with access_token"),
          language: "bash",
          code: `curl -X POST '${API}/students/employees' \\\n  -H 'Authorization: Bearer <jwt_access_token>' \\\n  -H 'Content-Type: application/json' \\\n  -d '{\n    "email": "employee.demo@demobank.local",\n    "full_name": "Demo Employee"\n  }'`,
        },
        {
          title: t("4) Обновить access_token через refresh_token", "4) Refresh access_token with refresh_token"),
          language: "bash",
          code: `curl -X POST '${API}/auth/refresh' \\\n  -H 'Content-Type: application/json' \\\n  -d '{\n    "refresh_token": "<jwt_refresh_token>"\n  }'`,
        },
        {
          title: t("5) Использовать новый access_token после refresh", "5) Use new access_token after refresh"),
          language: "bash",
          code: `curl -X GET '${API}/students/employees' \\\n  -H 'Authorization: Bearer <new_jwt_access_token>' \\\n  -H 'Content-Type: application/json'`,
        },
        {
          title: t("Python: создать сотрудника через requests", "Python: create employee via requests"),
          language: "python",
          code: `import requests\n\nBASE_URL = "${API}"\nEMAIL = "${profile?.email || "student@example.com"}"\nPASSWORD = "<student_password>"\n\nlogin_response = requests.post(\n    f\"{BASE_URL}/auth/login\",\n    json={\"email\": EMAIL, \"password\": PASSWORD},\n    timeout=15,\n)\nlogin_response.raise_for_status()\ntokens = login_response.json()\naccess_token = tokens[\"access_token\"]\n\ncreate_employee_response = requests.post(\n    f\"{BASE_URL}/students/employees\",\n    headers={\n        \"Authorization\": f\"Bearer {access_token}\",\n        \"Content-Type\": \"application/json\",\n    },\n    json={\n        \"email\": \"employee.demo@demobank.local\",\n        \"full_name\": \"Demo Employee\",\n    },\n    timeout=15,\n)\ncreate_employee_response.raise_for_status()\nprint(create_employee_response.json())`,
        },
      ],
    };
  };

  const renderToolsPanel = () => (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-border p-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">{t("Доступы и инструменты", "Tools & Access")}</h3>
        <div className="space-y-2 text-xs text-muted-foreground mb-3">
          <div>{t("Логин:", "Login:")} <span className="font-mono text-foreground">{profile?.email || "-"}</span></div>
        </div>
        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
          {availableTools.map((access) => {
            const active = access.status === "ACTIVE";
            const openUrl = resolveToolOpenUrl(access.service_name as ToolService);
            return (
              <div key={access.id} className="rounded-xl border border-border p-3">
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="text-sm font-medium text-foreground">{access.tool.title}</div>
                  <StatusBadge value={access.status} lang={lang} />
                </div>
                <div className="text-xs text-muted-foreground mb-2">{toolHint(access.service_name, access.tool.hint)}</div>
                <div className="text-[11px] text-muted-foreground mb-2 font-mono break-all">{access.principal}</div>
                {active && openUrl ? (
                  <button
                    className="inline-flex items-center justify-center rounded-md border border-input px-2.5 py-1.5 text-xs font-medium hover:bg-accent"
                    onClick={() => void openTool(access.service_name as ToolService)}
                    type="button"
                  >
                    {t("Открыть", "Open")}
                  </button>
                ) : (
                  <button
                    className="inline-flex items-center justify-center rounded-md border border-input px-2.5 py-1.5 text-xs font-medium opacity-50"
                    disabled
                  >
                    {active ? t("Без web UI", "No web UI") : t("Доступ отозван", "Access revoked")}
                  </button>
                )}
              </div>
            );
          })}
          {availableTools.length === 0 && <div className="text-sm text-muted-foreground">{t("Доступы пока не загружены", "Access list is empty")}</div>}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-border p-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">{t("Последние события", "Latest Events")}</h3>
        <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
          {events.slice(0, 15).map((event) => (
            <div key={event.id} className="rounded-lg border border-border p-2.5">
              <div className="text-xs font-medium text-foreground">{event.event_type}</div>
              <div className="text-[11px] text-muted-foreground">{event.topic}</div>
              <div className="text-[11px] text-muted-foreground">{formatDate(event.occurred_at)}</div>
            </div>
          ))}
          {events.length === 0 && <div className="text-sm text-muted-foreground">{t("Нет событий", "No events")}</div>}
        </div>
      </div>
    </div>
  );

  const renderToolDetailPage = () => {
    if (!selectedToolService) {
      return <div className="bg-white rounded-2xl border border-border p-8 text-sm text-muted-foreground">Tool is not selected.</div>;
    }
    if (!identity && !toolRouteDenied) {
      return (
        <div className="bg-white rounded-2xl border border-border p-8 text-sm text-muted-foreground">
          {t("Загружаем доступы к инструментам...", "Loading tool access...")}
        </div>
      );
    }
    if (toolRouteDenied || !selectedToolAccess) {
      return (
        <div className="bg-white rounded-2xl border border-red-200 p-8 text-sm text-red-700">
          403 Forbidden: доступ к инструменту отключен. {toolRouteDenied || ""}
        </div>
      );
    }
    const guide = getToolGuide(selectedToolService);
    const purpose = getToolPurpose(selectedToolService);
    const meta = TOOL_MAP[selectedToolService];
    const openUrl = resolveToolOpenUrl(selectedToolService);
    const hideAuthAndIsolation =
      selectedToolService === "JENKINS" ||
      selectedToolService === "POSTGRES" ||
      selectedToolService === "ALLURE" ||
      selectedToolService === "REDIS" ||
      selectedToolService === "KAFKA";
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-foreground">{meta.title}</h1>
            <p className="text-sm text-muted-foreground">{t("Подробное описание и подключение", "Detailed description and connection guide")}</p>
          </div>
          {openUrl ? (
            <button
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
              onClick={() => void openTool(selectedToolService)}
              type="button"
            >
              {t("Открыть инструмент", "Open tool")}
            </button>
          ) : null}
        </div>

        <div className="bg-white rounded-2xl border border-border p-5 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">{t("Для чего инструмент в проекте", "Purpose in this project")}</h3>
          <div className="space-y-2">
            {purpose.map((line, index) => (
              <div key={`${meta.title}-purpose-${index}`} className="text-sm text-muted-foreground">
                {index + 1}. {line}
              </div>
            ))}
          </div>

          <h3 className="text-sm font-semibold text-foreground">{t("Описание", "Description")}</h3>
          <div className="space-y-2">
            {guide.summary.map((line, index) => (
              <div key={`${meta.title}-summary-${index}`} className="text-sm text-muted-foreground">
                {index + 1}. {line}
              </div>
            ))}
          </div>

          <h3 className="text-sm font-semibold text-foreground pt-1">{t("Подключение", "Connection")}</h3>
          <div className="space-y-2">
            {guide.connection.map((line, index) => (
              <div key={`${meta.title}-connection-${index}`} className="text-sm text-muted-foreground">
                {index + 1}. {line}
              </div>
            ))}
          </div>

          {!hideAuthAndIsolation && guide.auth.length > 0 && (
            <>
              <h3 className="text-sm font-semibold text-foreground pt-1">{t("Авторизация", "Authentication")}</h3>
              <div className="space-y-2">
                {guide.auth.map((line, index) => (
                  <div key={`${meta.title}-auth-${index}`} className="text-sm text-muted-foreground">
                    {index + 1}. {line}
                  </div>
                ))}
              </div>
            </>
          )}

          {!hideAuthAndIsolation && (
            <div className="text-sm text-muted-foreground">
              {t("Principal", "Principal")}: <span className="font-mono text-foreground break-all">{selectedToolAccess.principal}</span>
            </div>
          )}

          {!hideAuthAndIsolation && guide.isolation.length > 0 && (
            <>
              <h3 className="text-sm font-semibold text-foreground pt-1">
                {selectedToolService === "REST_API" ? t("Postman и работа с токенами", "Postman and tokens") : t("Изоляция и безопасность", "Isolation and security")}
              </h3>
              <div className="space-y-2">
                {guide.isolation.map((line, index) => (
                  <div key={`${meta.title}-isolation-${index}`} className="text-sm text-muted-foreground">
                    {index + 1}. {line}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {guide.examples && guide.examples.length > 0 && (
          <div className="bg-white rounded-2xl border border-border p-5">
            <h3 className="text-sm font-semibold text-foreground mb-3">{t("Примеры", "Examples")}</h3>
            <div className="space-y-3">
              {guide.examples.map((example, index) => (
                <div key={`${meta.title}-example-${index}`} className="rounded-xl border border-border p-3">
                  <div className="text-sm font-medium text-foreground mb-2">{example.title}</div>
                  <pre className="text-xs text-muted-foreground whitespace-pre-wrap overflow-x-auto">
                    <code>{example.code}</code>
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}

        {selectedToolService === "REDIS" && (
          <div className="bg-white rounded-2xl border border-border p-5 space-y-3">
            <h3 className="text-sm font-semibold text-foreground">{t("Перед практикой", "Before Practice")}</h3>
            <div className="text-sm text-muted-foreground">
              1. {t("Чтобы в Redis появились значения, создайте тестовые ключи через redis-cli:", "To get values in Redis, create test keys via redis-cli:")}
            </div>
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap overflow-x-auto">
              <code>{`# macOS / Ubuntu terminal
redis-cli -u redis://${HOST}:6379 SET demo:status ok
redis-cli -u redis://${HOST}:6379 HSET demo:user name Daniil role student

:: Windows CMD
redis-cli.exe -h ${HOST} -p 6379 SET demo:status ok
redis-cli.exe -h ${HOST} -p 6379 HSET demo:user name Daniil role student`}</code>
            </pre>
          </div>
        )}

        <div className="bg-white rounded-2xl border border-border p-5">
          <h3 className="text-sm font-semibold text-foreground mb-3">{t("Практика: 10 заданий", "Practice: 10 tasks")}</h3>
          <div className="space-y-3">
            {guide.practice.map((task) => (
              <div key={`${meta.title}-task-${task.id}`} className="rounded-xl border border-border p-4 space-y-2">
                <div className="text-sm font-semibold text-foreground">{t("Задание", "Task")} {task.id}</div>
                <div className="text-sm text-muted-foreground"><span className="font-medium text-foreground">{t("Цель:", "Goal:")}</span> {task.goal}</div>
                <div className="text-sm text-muted-foreground"><span className="font-medium text-foreground">{t("Предусловия:", "Preconditions:")}</span> {task.preconditions}</div>
                <div className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{t("Шаги:", "Steps:")}</span>
                  <div className="mt-1 space-y-1">
                    {task.steps.map((step, index) => (
                      <div key={`${meta.title}-task-${task.id}-step-${index}`} className="text-xs text-muted-foreground">
                        {index + 1}. {step}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="text-sm text-muted-foreground"><span className="font-medium text-foreground">{t("Ожидаемый результат:", "Expected result:")}</span> {task.expected}</div>
                <div className="text-sm text-muted-foreground"><span className="font-medium text-foreground">{t("Где увидеть результат:", "Where to verify:")}</span> {task.where}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderDashboard = () => (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">{t("Дашборд студента", "Student Dashboard")}</h1>
          <p className="text-sm text-muted-foreground">{t("Обзор сотрудников, клиентов и операций", "Overview of employees, clients and operations")}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {dashboardKpis.map((item, index) => (
          <div key={`${item.label}-${index}`} className="bg-white rounded-2xl border border-border p-5 flex items-start gap-4">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${item.color}`}>
              <item.icon className="w-5 h-5" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{item.value}</div>
              <div className="text-sm text-muted-foreground">{item.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-border p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-primary" />
            <h3 className="font-semibold text-sm text-foreground">{t("Динамика сотрудников и клиентов", "Employees and Clients Dynamics")}</h3>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={activityData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="employees" stroke="#6366f1" strokeWidth={2} dot={false} name={t("Сотрудники", "Employees")} />
              <Line type="monotone" dataKey="clients" stroke="#f59e0b" strokeWidth={2} dot={false} name={t("Клиенты", "Clients")} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-2xl border border-border p-5">
          <h3 className="font-semibold text-sm text-foreground mb-4">{t("Статусы клиентов", "Client Statuses")}</h3>
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={statusDistribution} cx="50%" cy="50%" innerRadius={40} outerRadius={62} paddingAngle={3} dataKey="value">
                {statusDistribution.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {statusDistribution.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: item.color }} />
                  {statusLabel(item.name, lang)}
                </span>
                <span className="font-medium">{item.value}</span>
              </div>
            ))}
            {statusDistribution.length === 0 && <div className="text-xs text-muted-foreground">{t("Нет данных", "No data")}</div>}
          </div>
        </div>
      </div>

      <>
          <div className="bg-white rounded-2xl border border-border p-5">
            <h3 className="font-semibold text-sm text-foreground mb-4">{t("Топ 5 клиентов по активности", "Top 5 Clients by Activity")}</h3>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={topClients.map((client) => ({ name: client.last_name, accounts: clientStats[client.id]?.accounts || 0, tickets: clientStats[client.id]?.tickets || 0 }))} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="accounts" fill="#6366f1" radius={[4, 4, 0, 0]} name={t("Счета", "Accounts")} />
                <Bar dataKey="tickets" fill="#f59e0b" radius={[4, 4, 0, 0]} name={t("Тикеты", "Tickets")} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-2xl border border-border overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <h3 className="font-semibold text-sm text-foreground">{t("Последние клиенты", "Recent Clients")}</h3>
              <button className="inline-flex items-center justify-center whitespace-nowrap rounded-md border border-input bg-background px-3 py-1 text-sm font-medium shadow-sm hover:bg-accent" onClick={() => setHash("/student/clients")}>
                {t("Все клиенты →", "All Clients →")}
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/30 border-b border-border">
                    {[t("ФИО", "Name"), "Email", t("Статус", "Status"), t("Счета", "Accounts"), t("Тикеты", "Tickets"), t("Последнее изменение", "Last Updated"), t("Действия", "Actions")].map((title) => (
                      <th key={title} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{title}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {recentClients.map((client) => (
                    <tr key={client.id} className="hover:bg-muted/10 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary/10 to-violet-100 flex items-center justify-center text-xs font-bold text-primary flex-shrink-0">
                            {client.first_name[0]}
                          </div>
                          <span className="font-medium whitespace-nowrap">{client.first_name} {client.last_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">{client.email}</td>
                      <td className="px-4 py-3"><StatusBadge value={client.status} lang={lang} /></td>
                      <td className="px-4 py-3 text-center font-semibold text-foreground">{clientStats[client.id]?.accounts || 0}</td>
                      <td className="px-4 py-3 text-center font-semibold text-foreground">{clientStats[client.id]?.tickets || 0}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{formatDate(client.updated_at)}</td>
                      <td className="px-4 py-3">
                        <button className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-xs h-7 px-2.5 hover:bg-accent gap-1.5" onClick={() => setHash(`/student/clients/${encodeURIComponent(client.id)}`)}>
                          <Eye className="w-3.5 h-3.5" />
                          {t("Открыть", "Open")}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {recentClients.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-10 text-center text-sm text-muted-foreground">{t("Клиенты не найдены", "No clients found")}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
      </>
    </div>
  );

  const renderEmployeesPage = () => {
    const toggleSort = (field: "name" | "status" | "updated_at" | "email") => {
      if (employeeSortField === field) {
        setEmployeeSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setEmployeeSortField(field);
        setEmployeeSortDir("asc");
      }
    };

    const sortIcon = (field: "name" | "status" | "updated_at" | "email") => {
      if (employeeSortField !== field) return <ChevronUp className="w-3 h-3 opacity-30" />;
      return employeeSortDir === "asc" ? <ChevronUp className="w-3 h-3 text-primary" /> : <ChevronDown className="w-3 h-3 text-primary" />;
    };

    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">{t("Сотрудники", "Employees")}</h1>
            <p className="text-sm text-muted-foreground">{employeesFilteredSorted.length} {t("записей", "records")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md border border-input bg-white px-4 py-2 text-sm font-medium shadow-sm hover:bg-accent disabled:opacity-50 gap-2"
              onClick={openGenerateEntitiesConfirm}
              disabled={busy}
            >
              <RefreshCw className={cx("w-4 h-4", busy ? "animate-spin" : "")} />
              {t("Сгенерировать сущности", "Generate entities")}
            </button>
            <button className="inline-flex items-center justify-center whitespace-nowrap rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-2" onClick={() => setEmployeeCreateOpen(true)}>
              <Plus className="w-4 h-4" />
              {t("Добавить сотрудника", "Add employee")}
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-border p-4 flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm pl-9" value={employeeSearch} onChange={(event) => { setEmployeeSearch(event.target.value); setEmployeesPage(1); }} placeholder={t("Поиск по ФИО, email, ID...", "Search by name, email, ID...")} />
          </div>
          <select className="px-3 py-2 text-sm border border-input rounded-lg bg-white" value={employeeStatusFilter} onChange={(event) => { setEmployeeStatusFilter(event.target.value); setEmployeesPage(1); }}>
            <option value="">{t("Все статусы", "All statuses")}</option>
            <option value="ACTIVE">{t("Активен", "Active")}</option>
            <option value="BLOCKED">{t("Заблокирован", "Blocked")}</option>
            <option value="INACTIVE">{t("Неактивен", "Inactive")}</option>
          </select>
        </div>

        <div className="bg-white rounded-2xl border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/30 border-b border-border">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("name")}>{t("ФИО", "Name")} {sortIcon("name")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("email")}>Email {sortIcon("email")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Клиенты", "Clients")}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Тикеты", "Tickets")}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("status")}>{t("Статус", "Status")} {sortIcon("status")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Действия", "Actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {employeesPageRows.map((employee) => (
                  <tr key={employee.id} className="hover:bg-muted/10 transition-colors">
                    <td className="px-4 py-3">
                      <button className="flex items-center gap-2.5 hover:opacity-90" onClick={() => setHash(`/student/employees/${encodeURIComponent(employee.id)}`)}>
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/10 to-violet-100 flex items-center justify-center text-xs font-bold text-primary">{(employee.full_name || employee.email)[0]}</div>
                        <span className="font-medium whitespace-nowrap">{employee.full_name || `${employee.first_name || ""} ${employee.last_name || ""}`.trim() || employee.email}</span>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{employee.email}</td>
                    <td className="px-4 py-3 text-center font-semibold">{employee.clients_count || 0}</td>
                    <td className="px-4 py-3 text-center font-semibold">{employee.tickets_count || 0}</td>
                    <td className="px-4 py-3"><StatusBadge value={employee.status} lang={lang} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted" onClick={() => setHash(`/student/employees/${encodeURIComponent(employee.id)}`)} title={t("Открыть", "Open")}><Eye className="w-3.5 h-3.5" /></button>
                        <button className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted" onClick={() => { setEmployeeProfile(employee); openEmployeeEditForm(employee); }} title={t("Редактировать", "Edit")}><UserCircle2 className="w-3.5 h-3.5" /></button>
                        <button className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-amber-600" onClick={() => void changeEmployeeStatus(employee.id, employee.status === "BLOCKED")} title={employee.status === "BLOCKED" ? t("Разблокировать", "Unblock") : t("Заблокировать", "Block")}><ShieldOff className="w-3.5 h-3.5" /></button>
                        <button className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-red-50 text-red-500" onClick={() => void deleteEmployeeUser(employee.id)} title={t("Удалить", "Delete")}><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                {employeesPageRows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-14 text-sm text-muted-foreground">{t("Сотрудники не найдены", "Employees not found")}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="px-5 py-3 border-t border-border flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{t(`Стр. ${employeesPage} из ${employeesTotalPages} · ${employeesFilteredSorted.length} записей`, `Page ${employeesPage} of ${employeesTotalPages} · ${employeesFilteredSorted.length} records`)}</span>
            <div className="flex gap-2">
              <button className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm disabled:opacity-50" onClick={() => setEmployeesPage((prev) => Math.max(1, prev - 1))} disabled={employeesPage === 1}>←</button>
              <button className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm disabled:opacity-50" onClick={() => setEmployeesPage((prev) => Math.min(employeesTotalPages, prev + 1))} disabled={employeesPage === employeesTotalPages}>→</button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderEmployeeProfilePage = () => {
    if (!employeeProfile) {
      return <div className="rounded-2xl border border-border bg-white p-8 text-center text-sm text-muted-foreground">{t("Сотрудник не найден", "Employee not found")}</div>;
    }

    const fullName = employeeProfile.full_name || `${employeeProfile.first_name || ""} ${employeeProfile.last_name || ""}`.trim() || employeeProfile.email;
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-80" onClick={() => setHash("/student/employees")}>
            <ArrowLeft className="w-4 h-4" />
            {t("Назад к сотрудникам", "Back to employees")}
          </button>
          <div className="flex items-center gap-2">
            <a
              className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm"
              href={`#/student/employees/${encodeURIComponent(employeeProfile.id)}/workspace`}
              target="_blank"
              rel="noreferrer"
            >
              {t("Зайти в кабинет сотрудника", "Open employee cabinet")}
            </a>
            <button className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm" onClick={() => openEmployeeEditForm(employeeProfile)}>{t("Редактировать", "Edit")}</button>
            <button className="inline-flex items-center justify-center rounded-md border border-amber-200 px-3 py-1.5 text-sm text-amber-700" onClick={() => void changeEmployeeStatus(employeeProfile.id, employeeProfile.status === "BLOCKED")}>{employeeProfile.status === "BLOCKED" ? t("Разблокировать", "Unblock") : t("Заблокировать", "Block")}</button>
            <button className="inline-flex items-center justify-center rounded-md bg-destructive px-3 py-1.5 text-sm text-destructive-foreground" onClick={() => void deleteEmployeeUser(employeeProfile.id)}>{t("Удалить", "Delete")}</button>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-border p-6">
          <div className="flex flex-wrap items-start gap-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-violet-200 flex items-center justify-center text-2xl font-bold text-primary flex-shrink-0">{fullName[0]}</div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-3 mb-1">
                <h2 className="text-xl font-bold text-foreground">{fullName}</h2>
                <StatusBadge value={employeeProfile.status} lang={lang} />
              </div>
              <div className="text-sm text-muted-foreground mb-3">{employeeProfile.email}</div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div><div className="text-xs text-muted-foreground">ID</div><div className="font-mono font-medium">{employeeProfile.id}</div></div>
                <div><div className="text-xs text-muted-foreground">{t("Клиенты", "Clients")}</div><div className="font-medium">{employeeProfile.clients_count || employeeProfileClients.length}</div></div>
                <div><div className="text-xs text-muted-foreground">{t("Тикеты", "Tickets")}</div><div className="font-medium">{employeeProfile.tickets_count || employeeProfileTickets.length}</div></div>
                <div><div className="text-xs text-muted-foreground">{t("Последний вход", "Last login")}</div><div className="font-medium">{formatDate(employeeProfile.last_login_at)}</div></div>
              </div>
            </div>
          </div>
        </div>

        <div className="inline-flex h-9 items-center justify-center rounded-lg p-1 text-muted-foreground bg-muted">
          {[
            { id: "overview", label: t("Обзор", "Overview") },
            { id: "tickets", label: t("Тикеты", "Tickets") },
            { id: "analytics", label: t("Аналитика", "Analytics") },
            { id: "audit", label: t("Аудит", "Audit") },
          ].map((item) => (
            <button key={item.id} onClick={() => setEmployeeProfileTab(item.id as typeof employeeProfileTab)} className={cx("inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all", employeeProfileTab === item.id ? "bg-background text-foreground shadow" : "")}>{item.label}</button>
          ))}
        </div>

        {employeeProfileTab === "overview" && (
          <div className="bg-white rounded-2xl border border-border overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <h3 className="font-semibold text-sm text-foreground">{t("Клиенты сотрудника", "Employee clients")}</h3>
            </div>
            <div className="divide-y divide-border">
              {employeeProfileClients.map((client) => (
                <button key={client.id} className="w-full text-left px-5 py-3 hover:bg-muted/20" onClick={() => setHash(`/student/clients/${encodeURIComponent(client.id)}`)}>
                  <div className="font-medium">{client.first_name} {client.last_name}</div>
                  <div className="text-xs text-muted-foreground">{client.email}</div>
                </button>
              ))}
              {employeeProfileClients.length === 0 && <div className="py-12 text-center text-sm text-muted-foreground">{t("Нет клиентов", "No clients")}</div>}
            </div>
          </div>
        )}

        {employeeProfileTab === "tickets" && (
          <div className="space-y-3">
            {employeeProfileTickets.map((ticket) => (
              <div key={ticket.id} className="bg-white rounded-2xl border border-border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-semibold">{ticket.subject}</div>
                    <div className="text-xs text-muted-foreground">{ticket.description}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge value={ticket.status} lang={lang} />
                    <button className="inline-flex items-center justify-center rounded-md border border-input px-2 py-1 text-xs" onClick={() => void assignManagedTicket(employeeProfile.id, ticket.id)}>{t("Назначить", "Assign")}</button>
                    <button className="inline-flex items-center justify-center rounded-md border border-input px-2 py-1 text-xs" onClick={() => void updateManagedTicketStatus(employeeProfile.id, ticket.id, "RESOLVED")}>{t("Решить", "Resolve")}</button>
                  </div>
                </div>
              </div>
            ))}
            {employeeProfileTickets.length === 0 && <div className="bg-white rounded-2xl border border-border py-12 text-center text-sm text-muted-foreground">{t("Нет тикетов", "No tickets")}</div>}
          </div>
        )}

        {employeeProfileTab === "analytics" && (
          <div className="bg-white rounded-2xl border border-border p-5">
            <h3 className="font-semibold text-sm text-foreground mb-4">{t("Нагрузка сотрудника", "Employee load")}</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={topEmployees.map((item) => ({ name: (item.full_name || item.email).split(" ")[0], clients: item.clients_count || 0, tickets: item.tickets_count || 0 }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="clients" fill="#6366f1" name={t("Клиенты", "Clients")} />
                <Bar dataKey="tickets" fill="#f59e0b" name={t("Тикеты", "Tickets")} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {employeeProfileTab === "audit" && (
          <div className="bg-white rounded-2xl border border-border overflow-hidden">
            <div className="divide-y divide-border">
              {employeeAuditRows.map((row, index) => (
                <div key={`${String(row.id || index)}`} className="px-5 py-3">
                  <div className="text-sm font-medium">{String(row.action || "-")}</div>
                  <div className="text-xs text-muted-foreground">{formatDate(String(row.created_at || ""))}</div>
                </div>
              ))}
              {employeeAuditRows.length === 0 && <div className="py-12 text-center text-sm text-muted-foreground">{t("Нет записей аудита", "No audit records")}</div>}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderEmployeeWorkspacePage = () => {
    if (!employeeProfile) {
      return <div className="rounded-2xl border border-border bg-white p-8 text-center text-sm text-muted-foreground">{t("Сотрудник не найден", "Employee not found")}</div>;
    }
    const fullName = employeeProfile.full_name || `${employeeProfile.first_name || ""} ${employeeProfile.last_name || ""}`.trim() || employeeProfile.email;
    const usdRate = employeeExchangeRates.find((item) => item.quote_currency === "USD");
    const eurRate = employeeExchangeRates.find((item) => item.quote_currency === "EUR");
    return (
      <div className="space-y-5">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-xl font-bold">{t("Кабинет сотрудника", "Employee Cabinet")}: {fullName}</h1>
          <div className="flex items-center gap-2">
            <button
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-1.5"
              onClick={() => openClientCreateModal(employeeProfile.id)}
            >
              <Plus className="w-3.5 h-3.5" />
              {t("Добавить клиента", "Add client")}
            </button>
            <button className="inline-flex items-center gap-2 text-sm font-medium hover:opacity-80" onClick={() => setHash(`/student/employees/${encodeURIComponent(employeeProfile.id)}`)}>
              <ArrowLeft className="w-4 h-4" />
              {t("Назад в карточку", "Back to profile")}
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-border p-5">
          <h3 className="font-semibold text-sm text-foreground mb-3">{t("Курсы конвертации", "Conversion rates")}</h3>
          <p className="text-sm text-muted-foreground mb-4">{t("Сотрудник задает, сколько рублей соответствует одной единице валюты. Эти курсы используются в переводах между счетами клиента.", "Employee sets how many rubles equal one unit of foreign currency. These rates are used for transfers between client accounts.")}</p>
          <div className="grid md:grid-cols-2 gap-3">
            {[
              {
                quote: "USD",
                title: "RUB / USD",
                hint: t("По умолчанию 100 RUB = 1 USD", "Default: 100 RUB = 1 USD"),
                value: usdRate?.rub_amount ?? 100,
              },
              {
                quote: "EUR",
                title: "RUB / EUR",
                hint: t("По умолчанию 120 RUB = 1 EUR", "Default: 120 RUB = 1 EUR"),
                value: eurRate?.rub_amount ?? 120,
              },
            ].map((item) => (
              <div key={item.quote} className="rounded-xl border border-border p-4 space-y-3">
                <div>
                  <div className="font-medium text-sm">{item.title}</div>
                  <div className="text-xs text-muted-foreground mt-1">{item.hint}</div>
                </div>
                <input
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  type="number"
                  min="0"
                  step="0.01"
                  value={String(employeeExchangeRates.find((rate) => rate.quote_currency === item.quote)?.rub_amount ?? item.value)}
                  onChange={(event) =>
                    setEmployeeExchangeRates((prev) =>
                      prev.some((rate) => rate.quote_currency === item.quote)
                        ? prev.map((rate) =>
                            rate.quote_currency === item.quote
                              ? { ...rate, rub_amount: Number(event.target.value || 0) }
                              : rate
                          )
                        : [
                            ...prev,
                            {
                              base_currency: "RUB",
                              quote_currency: item.quote,
                              rub_amount: Number(event.target.value || 0),
                              direct_rate: 0,
                              inverse_rate: 0,
                            },
                          ]
                    )
                  }
                />
                <button
                  className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => void updateEmployeeExchangeRate(item.quote, employeeExchangeRates.find((rate) => rate.quote_currency === item.quote)?.rub_amount ?? item.value)}
                  disabled={busy}
                >
                  {t("Сохранить курс", "Save rate")}
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-border p-5">
          <h3 className="font-semibold text-sm text-foreground mb-3">{t("Клиенты сотрудника", "Employee clients")} ({employeeProfileClients.length})</h3>
          <div className="divide-y divide-border">
            {employeeProfileClients.map((client) => (
              <button key={client.id} className="w-full text-left px-2 py-3 hover:bg-muted/20 rounded-md" onClick={() => setHash(`/student/clients/${encodeURIComponent(client.id)}`)}>
                <div className="font-medium text-sm">{client.first_name} {client.last_name}</div>
                <div className="text-xs text-muted-foreground">{client.email}</div>
              </button>
            ))}
            {employeeProfileClients.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">{t("Нет клиентов", "No clients")}</div>}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-border p-5">
          <h3 className="font-semibold text-sm text-foreground mb-3">{t("Тикеты клиентов сотрудника", "Employee client tickets")} ({employeeProfileTickets.length})</h3>
          <div className="space-y-2">
            {employeeProfileTickets.map((ticket) => (
              <div key={ticket.id} className="rounded-xl border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium text-sm">{ticket.subject}</div>
                  <StatusBadge value={ticket.status} lang={lang} />
                </div>
                <div className="text-xs text-muted-foreground mt-1">{ticket.description}</div>
              </div>
            ))}
            {employeeProfileTickets.length === 0 && <div className="py-8 text-sm text-muted-foreground">{t("Нет тикетов", "No tickets")}</div>}
          </div>
        </div>
      </div>
    );
  };

  const renderEmployeeClientsPage = () => {
    const toggleSort = (field: "name" | "status" | "updated_at" | "email") => {
      if (clientSortField === field) {
        setClientSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setClientSortField(field);
        setClientSortDir("asc");
      }
    };

    const sortIcon = (field: "name" | "status" | "updated_at" | "email") => {
      if (clientSortField !== field) return <ChevronUp className="w-3 h-3 opacity-30" />;
      return clientSortDir === "asc" ? <ChevronUp className="w-3 h-3 text-primary" /> : <ChevronDown className="w-3 h-3 text-primary" />;
    };

    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">{t("Мои клиенты", "My Clients")}</h1>
            <p className="text-sm text-muted-foreground">{clientsFilteredSorted.length} {t("клиентов", "clients")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md border border-input bg-white px-4 py-2 text-sm font-medium shadow-sm hover:bg-accent disabled:opacity-50 gap-2"
              onClick={openGenerateEntitiesConfirm}
              disabled={busy}
            >
              <RefreshCw className={cx("w-4 h-4", busy ? "animate-spin" : "")} />
              {t("Сгенерировать сущности", "Generate entities")}
            </button>
            <button
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-2"
              onClick={() => openClientCreateModal()}
            >
              <Plus className="w-4 h-4" />
              {t("Добавить клиента", "Add client")}
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-border p-4 flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={clientSearch}
              onChange={(event) => {
                setClientSearch(event.target.value);
                setClientsPage(1);
              }}
              placeholder={t("Поиск по имени, email, ID...", "Search by name, email, ID...")}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring pl-9"
            />
          </div>
          <select
            value={clientStatusFilter}
            onChange={(event) => {
              setClientStatusFilter(event.target.value);
              setClientsPage(1);
            }}
            className="px-3 py-2 text-sm border border-input rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">{t("Все статусы", "All statuses")}</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="BLOCKED">BLOCKED</option>
            <option value="SUSPENDED">SUSPENDED</option>
            <option value="PENDING_VERIFICATION">PENDING_VERIFICATION</option>
            <option value="NEW">NEW</option>
          </select>
        </div>

        <div className="bg-white rounded-2xl border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/30 border-b border-border">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("name")}>{t("ФИО", "Name")} {sortIcon("name")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("email")}>Email {sortIcon("email")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Код", "Code")}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("status")}>{t("Статус", "Status")} {sortIcon("status")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Счета", "Accounts")}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Тикеты", "Tickets")}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("updated_at")}>{t("Обновлён", "Updated")} {sortIcon("updated_at")}</button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{t("Действия", "Actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {clientsPageRows.map((client) => {
                  const actions = CLIENT_STATUS_ACTIONS[client.status] || CLIENT_STATUS_ACTIONS.ACTIVE;
                  const stats = clientStats[client.id] || { accounts: 0, tickets: 0 };
                  return (
                    <tr key={client.id} className="hover:bg-muted/10 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/10 to-violet-100 flex items-center justify-center text-xs font-bold text-primary flex-shrink-0">
                            {client.first_name[0]}
                          </div>
                          <div>
                            <div className="font-medium whitespace-nowrap">{client.first_name} {client.last_name}</div>
                            <div className="text-xs text-muted-foreground">{client.phone}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{client.email}</td>
                      <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{client.external_client_code}</td>
                      <td className="px-4 py-3"><StatusBadge value={client.status} lang={lang} /></td>
                      <td className="px-4 py-3 text-center font-semibold">{stats.accounts}</td>
                      <td className="px-4 py-3 text-center font-semibold">{stats.tickets}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{formatDate(client.updated_at || client.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 flex-wrap">
                          <button className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted" title={t("Открыть", "Open")} onClick={() => setHash(`/student/clients/${encodeURIComponent(client.id)}`)}>
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          {actions.map((action) => (
                            <button
                              key={`${client.id}-${action.endpoint}`}
                              className="inline-flex h-7 px-2 items-center justify-center rounded-md border border-input text-[11px] hover:bg-muted"
                              onClick={() => void changeEmployeeClientStatus(client.id, action.endpoint)}
                              disabled={busy}
                            >
                              {action.label}
                            </button>
                          ))}
                          <button className="inline-flex h-7 w-7 items-center justify-center rounded-md text-red-500 hover:bg-red-50" title={t("Удалить", "Delete")} onClick={() => void deleteEmployeeClient(client.id)}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {clientsPageRows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center py-14 text-sm text-muted-foreground">{t("Клиенты не найдены", "No clients found")}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="px-5 py-3 border-t border-border flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{t(`Стр. ${clientsPage} из ${clientsTotalPages} · ${clientsFilteredSorted.length} записей`, `Page ${clientsPage} of ${clientsTotalPages} · ${clientsFilteredSorted.length} records`)}</span>
            <div className="flex gap-2">
              <button className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm disabled:opacity-50" onClick={() => setClientsPage((prev) => Math.max(1, prev - 1))} disabled={clientsPage === 1}>←</button>
              <button className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm disabled:opacity-50" onClick={() => setClientsPage((prev) => Math.min(clientsTotalPages, prev + 1))} disabled={clientsPage === clientsTotalPages}>→</button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderClientProfilePage = () => {
    if (!clientProfile) {
      return (
        <div className="bg-white rounded-2xl border border-border p-12 text-center text-sm text-muted-foreground">
          {t("Клиент не найден", "Client not found")}
        </div>
      );
    }

    const statusActions = CLIENT_STATUS_ACTIONS[clientProfile.status] || [];
    const analyticsData = [
      { name: t("Всего счетов", "Total Accounts"), value: clientProfileAccounts.length },
      { name: t("Активных", "Active"), value: clientProfileAccounts.filter((item) => item.status === "ACTIVE").length },
      { name: t("Заблок.", "Blocked"), value: clientProfileAccounts.filter((item) => item.status === "BLOCKED").length },
      { name: t("Закрытых", "Closed"), value: clientProfileAccounts.filter((item) => item.status === "CLOSED").length },
      { name: t("Тикеты", "Tickets"), value: clientProfileTickets.length },
      { name: t("Решено", "Resolved"), value: clientProfileTickets.filter((item) => item.status === "RESOLVED").length },
    ];
    const activeClientProfileAccounts = clientProfileAccounts.filter((item) => item.status === "ACTIVE");

    return (
      <div className="space-y-5 max-w-5xl mx-auto">
        <div className="flex flex-wrap items-start gap-4">
          <button className="inline-flex items-center justify-center rounded-md px-3 py-1.5 text-sm hover:bg-muted gap-2" onClick={() => setHash("/student/clients")}>
            <ArrowLeft className="w-4 h-4" />
            {t("К списку", "Back to list")}
          </button>
        </div>

        <div className="bg-white rounded-2xl border border-border p-5 flex flex-wrap items-start gap-5">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/20 to-violet-200 flex items-center justify-center text-xl font-bold text-primary flex-shrink-0">
            {clientProfile.first_name[0]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3 mb-1">
              <h1 className="text-xl font-bold text-foreground">{clientProfile.first_name} {clientProfile.last_name}</h1>
              <StatusBadge value={clientProfile.status} lang={lang} />
            </div>
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mt-2">
              <span>{clientProfile.id}</span>
              <span>{clientProfile.email}</span>
              <span>{clientProfile.phone}</span>
              <span>{clientProfile.external_client_code}</span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {statusActions.map((action) => (
              <button
                key={`profile-${action.endpoint}`}
                className="inline-flex items-center justify-center rounded-md border border-input px-3 py-1.5 text-sm hover:bg-muted"
                onClick={() => void changeEmployeeClientStatus(clientProfile.id, action.endpoint)}
              >
                {action.label}
              </button>
            ))}
            <button className="inline-flex items-center justify-center rounded-md bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90 gap-1.5" onClick={() => void deleteEmployeeClient(clientProfile.id)}>
              <Trash2 className="w-3.5 h-3.5" />
              {t("Удалить", "Delete")}
            </button>
          </div>
        </div>

        <div className="flex gap-1 bg-muted/50 rounded-xl p-1 overflow-x-auto">
          {[
            { id: "overview", label: t("Обзор", "Overview") },
            { id: "accounts", label: t("Счета", "Accounts") },
            { id: "transfers", label: t("Переводы", "Transfers") },
            { id: "tickets", label: t("Тикеты", "Tickets") },
            { id: "analytics", label: t("Аналитика", "Analytics") },
            { id: "audit", label: t("Аудит", "Audit") },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setClientProfileTab(item.id as typeof clientProfileTab)}
              className={cx(
                "flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap flex-shrink-0",
                clientProfileTab === item.id ? "bg-white shadow text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {item.label}
            </button>
          ))}
        </div>

        {clientProfileTab === "overview" && (
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white rounded-2xl border border-border p-5 space-y-4">
              <h3 className="font-semibold text-sm">{t("Личные данные", "Personal Info")}</h3>
              {[
                [t("Имя", "First Name"), clientProfile.first_name],
                [t("Фамилия", "Last Name"), clientProfile.last_name],
                ["Email", clientProfile.email],
                [t("Телефон", "Phone"), clientProfile.phone],
                [t("Статус", "Status"), statusLabel(clientProfile.status, lang)],
                [t("Создан", "Created"), formatDate(clientProfile.created_at)],
                [t("Обновлён", "Updated"), formatDate(clientProfile.updated_at)],
              ].map(([key, value]) => (
                <div key={String(key)} className="flex justify-between items-center py-2 border-b border-border/50 last:border-0">
                  <span className="text-xs text-muted-foreground">{key}</span>
                  <span className="text-sm font-medium text-foreground">{value}</span>
                </div>
              ))}
            </div>
            <div className="bg-white rounded-2xl border border-border p-5 space-y-4">
              <h3 className="font-semibold text-sm">{t("Сводка", "Summary")}</h3>
              {[
                [t("Всего счетов", "Total Accounts"), clientProfileAccounts.length],
                [t("Активных счетов", "Active Accounts"), clientProfileAccounts.filter((item) => item.status === "ACTIVE").length],
                [t("Заблокированных счетов", "Blocked Accounts"), clientProfileAccounts.filter((item) => item.status === "BLOCKED").length],
                [t("Закрытых счетов", "Closed Accounts"), clientProfileAccounts.filter((item) => item.status === "CLOSED").length],
                [t("Всего тикетов", "Total Tickets"), clientProfileTickets.length],
                [t("Открытых тикетов", "Open Tickets"), clientProfileTickets.filter((item) => ["NEW", "IN_REVIEW", "WAITING_FOR_CLIENT", "WAITING_FOR_EMPLOYEE"].includes(item.status)).length],
              ].map(([key, value]) => (
                <div key={String(key)} className="flex justify-between items-center py-2 border-b border-border/50 last:border-0">
                  <span className="text-xs text-muted-foreground">{key}</span>
                  <span className="text-sm font-bold text-foreground">{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {clientProfileTab === "accounts" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{t("Счета клиента", "Client Accounts")} ({clientProfileAccounts.length})</h3>
              <button className="inline-flex items-center justify-center whitespace-nowrap rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-1.5" onClick={() => setOpenAccountModal(true)}>
                <Plus className="w-3.5 h-3.5" /> {t("Открыть счёт", "Open Account")}
              </button>
            </div>
            {clientProfileAccounts.length === 0 ? (
              <div className="bg-white rounded-2xl border border-border p-12 text-center text-sm text-muted-foreground">{t("Нет счетов", "No accounts")}</div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {clientProfileAccounts.map((account) => (
                  <div key={account.id} className="bg-white rounded-2xl border border-border p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="text-xs font-mono text-muted-foreground">{account.account_number}</div>
                        <div className="font-semibold mt-0.5">{formatMoney(account.balance, account.currency)}</div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <StatusBadge value={account.status} lang={lang} />
                        <StatusBadge value={account.type} lang={lang} />
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {account.status === "ACTIVE" && (
                        <button className="inline-flex items-center justify-center rounded-md border border-amber-200 px-2 py-1 text-xs text-amber-600 hover:bg-amber-50" onClick={() => void changeEmployeeAccountStatus(account.id, "block")}>
                          Block
                        </button>
                      )}
                      {account.status === "BLOCKED" && (
                        <button className="inline-flex items-center justify-center rounded-md border border-green-200 px-2 py-1 text-xs text-green-600 hover:bg-green-50" onClick={() => void changeEmployeeAccountStatus(account.id, "unblock")}>
                          Unblock
                        </button>
                      )}
                      {account.status !== "CLOSED" && (
                        <button className="inline-flex items-center justify-center rounded-md border border-input px-2 py-1 text-xs hover:bg-muted" onClick={() => void changeEmployeeAccountStatus(account.id, "close")}>
                          Close
                        </button>
                      )}
                      <button className="inline-flex items-center justify-center rounded-md border border-red-200 px-2 py-1 text-xs text-red-500 hover:bg-red-50" onClick={() => void deleteEmployeeAccount(account.id)}>
                        {t("Удалить", "Delete")}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {clientProfileTab === "transfers" && (
          <div className="space-y-4">
            <div className="bg-white rounded-2xl border border-border p-5">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h3 className="font-semibold text-sm text-foreground">{t("Перевод между счетами клиента", "Transfer between client accounts")}</h3>
                <span className="text-xs text-muted-foreground">{t("Конвертация применяется автоматически по курсам сотрудника", "Conversion is applied automatically using employee rates")}</span>
              </div>
              {activeClientProfileAccounts.length < 2 ? (
                <div className="text-sm text-muted-foreground">{t("Для перевода нужно минимум два активных счета клиента.", "At least two active client accounts are required for transfers.")}</div>
              ) : (
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">{t("Счет списания", "Source account")}</label>
                    <select
                      value={clientTransferSourceId}
                      onChange={(event) => {
                        const nextSource = event.target.value;
                        setClientTransferSourceId(nextSource);
                        if (nextSource === clientTransferTargetId) {
                          setClientTransferTargetId(activeClientProfileAccounts.find((item) => item.id !== nextSource)?.id || "");
                        }
                      }}
                      className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white"
                    >
                      {activeClientProfileAccounts.map((account) => (
                        <option key={account.id} value={account.id}>{account.account_number} - {formatMoney(account.balance, account.currency)}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">{t("Счет зачисления", "Target account")}</label>
                    <select value={clientTransferTargetId} onChange={(event) => setClientTransferTargetId(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                      <option value="">{t("Выберите счет", "Select account")}</option>
                      {activeClientProfileAccounts.filter((account) => account.id !== clientTransferSourceId).map((account) => (
                        <option key={account.id} value={account.id}>{account.account_number} - {formatMoney(account.balance, account.currency)}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">{t("Сумма", "Amount")}</label>
                    <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="number" min="0" step="0.01" value={clientTransferAmount} onChange={(event) => setClientTransferAmount(event.target.value)} placeholder="1000" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">{t("Описание", "Description")}</label>
                    <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={clientTransferDescription} onChange={(event) => setClientTransferDescription(event.target.value)} placeholder={t("Перевод между счетами клиента", "Transfer between client accounts")} />
                  </div>
                </div>
              )}
              <button className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-2 disabled:cursor-not-allowed disabled:opacity-50" onClick={() => void createManagedClientTransfer()} disabled={busy || activeClientProfileAccounts.length < 2}>
                <Send className="w-4 h-4" />
                {t("Выполнить перевод", "Create transfer")}
              </button>
            </div>

            <div className="bg-white rounded-2xl border border-border p-5">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h3 className="font-semibold text-sm text-foreground">{t("Пополнение наличными", "Cash top up")}</h3>
                <span className="text-xs text-muted-foreground">{t("Валюта берется из выбранного счета", "Currency is taken from the selected account")}</span>
              </div>
              {activeClientProfileAccounts.length === 0 ? (
                <div className="text-sm text-muted-foreground">{t("Сначала откройте активный счет клиенту.", "Open an active account for the client first.")}</div>
              ) : (
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">{t("Счет клиента", "Client account")}</label>
                    <select value={clientTopUpAccountId} onChange={(event) => setClientTopUpAccountId(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                      {activeClientProfileAccounts.map((account) => (
                        <option key={account.id} value={account.id}>{account.account_number} - {formatMoney(account.balance, account.currency)}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">{t("Сумма наличных", "Cash amount")}</label>
                    <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="number" min="0" step="0.01" value={clientTopUpAmount} onChange={(event) => setClientTopUpAmount(event.target.value)} placeholder="1000" />
                  </div>
                </div>
              )}
              <button className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-2 disabled:cursor-not-allowed disabled:opacity-50" onClick={() => void createManagedClientCashTopUp()} disabled={busy || activeClientProfileAccounts.length === 0}>
                <Plus className="w-4 h-4" />
                {t("Зачислить наличные", "Top up with cash")}
              </button>
            </div>

            <div className="bg-white rounded-2xl border border-border overflow-hidden">
              <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                <h3 className="font-semibold text-sm text-foreground">{t("Переводы клиента", "Client transfers")} ({clientProfileTransfers.length})</h3>
              </div>
              <div className="divide-y divide-border">
                {clientProfileTransfers.map((transfer) => (
                  <div key={transfer.id} className="px-5 py-3 flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">{transfer.description || t("Без описания", "No description")}</div>
                      <div className="text-xs text-muted-foreground font-mono">{transfer.source_account_id} → {transfer.target_account_id}</div>
                      <div className="text-xs text-muted-foreground">{formatDate(transfer.created_at)}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{formatMoney(transfer.amount, transfer.currency)}</div>
                      <StatusBadge value={transfer.status} lang={lang} />
                    </div>
                  </div>
                ))}
                {clientProfileTransfers.length === 0 && <div className="py-14 text-center text-sm text-muted-foreground">{t("Нет переводов", "No transfers")}</div>}
              </div>
            </div>
          </div>
        )}

        {clientProfileTab === "tickets" && (
          <div className="space-y-3">
            <h3 className="font-semibold">{t("Обращения", "Tickets")} ({clientProfileTickets.length})</h3>
            {clientProfileTickets.length === 0 ? (
              <div className="bg-white rounded-2xl border border-border p-12 text-center text-sm text-muted-foreground">{t("Нет обращений", "No tickets")}</div>
            ) : (
              clientProfileTickets.map((ticket) => (
                <div key={ticket.id} className="bg-white rounded-2xl border border-border p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-semibold text-sm">{ticket.subject}</span>
                        <StatusBadge value={ticket.status} lang={lang} />
                        <StatusBadge value={ticket.priority} lang={lang} />
                      </div>
                      <p className="text-xs text-muted-foreground">{ticket.description}</p>
                      <div className="flex gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                        <span>ID: {ticket.id}</span>
                        <span>{t("Назначен", "Assigned")}: {ticket.employee_id_nullable ? "YES" : t("не назначен", "unassigned")}</span>
                        <span>{formatDate(ticket.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {!ticket.employee_id_nullable && (
                        <button className="inline-flex items-center justify-center rounded-md border border-input px-2 py-1 text-xs hover:bg-muted" onClick={() => { setSelectedEmployeeTicketId(ticket.id); void assignEmployeeTicket(); }}>
                          {t("Назначить на себя", "Assign to me")}
                        </button>
                      )}
                      {EMPLOYEE_TICKET_STATUSES.filter((value) => value !== ticket.status).map((status) => (
                        <button key={`${ticket.id}-${status}`} className="inline-flex items-center justify-center rounded-md border border-input px-2 py-1 text-xs hover:bg-muted" onClick={() => void updateEmployeeTicketStatus(ticket.id, status)}>
                          → {status}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ))
            )}

            <div className="bg-white rounded-2xl border border-border p-4">
              <h4 className="text-sm font-semibold mb-3">{t("Сообщение в тикет", "Message to ticket")}</h4>
              <div className="grid sm:grid-cols-[200px_1fr_auto] gap-2">
                <select className="px-3 py-2 text-sm border border-input rounded-lg bg-white" value={selectedEmployeeTicketId} onChange={(event) => setSelectedEmployeeTicketId(event.target.value)}>
                  <option value="">{t("Выберите тикет", "Select ticket")}</option>
                  {clientProfileTickets.map((ticket) => (
                    <option key={ticket.id} value={ticket.id}>{ticket.subject}</option>
                  ))}
                </select>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={employeeTicketMessage} onChange={(event) => setEmployeeTicketMessage(event.target.value)} placeholder={t("Сообщение", "Message")} />
                <button className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90" onClick={() => void sendEmployeeTicketMessage()} disabled={!selectedEmployeeTicketId || busy}>
                  {t("Отправить", "Send")}
                </button>
              </div>
              {selectedEmployeeTicket && <div className="text-xs text-muted-foreground mt-2">{t("Текущий статус:", "Current status:")} <strong>{selectedEmployeeTicket.status}</strong></div>}
            </div>
          </div>
        )}

        {clientProfileTab === "analytics" && (
          <div className="bg-white rounded-2xl border border-border p-5">
            <h3 className="font-semibold text-sm mb-4">{t("Аналитика по клиенту", "Client Analytics")}</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={analyticsData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Bar dataKey="value" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4">
              {analyticsData.map((item) => (
                <div key={item.name} className="bg-muted/30 rounded-xl p-3 text-center">
                  <div className="text-2xl font-bold text-foreground">{item.value}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{item.name}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {clientProfileTab === "audit" && (
          <div className="bg-white rounded-2xl border border-border p-5">
            <h3 className="font-semibold text-sm mb-4">{t("История изменений", "Audit Timeline")}</h3>
            <div className="space-y-0">
              {clientAuditRows.map((entry, index) => (
                <div key={entry.id} className="flex gap-4 relative">
                  {index < clientAuditRows.length - 1 && <div className="absolute left-[19px] top-10 bottom-0 w-px bg-border" />}
                  <div className="w-10 h-10 rounded-full bg-primary/10 border-2 border-white ring-1 ring-border flex items-center justify-center flex-shrink-0 mt-1 z-10">
                    <Bell className="w-4 h-4 text-primary" />
                  </div>
                  <div className="flex-1 pb-6">
                    <div className="font-medium text-sm">{entry.event_type}</div>
                    <div className="flex gap-3 text-xs text-muted-foreground mt-0.5">
                      <span>{entry.topic}</span>
                      <span>{formatDate(entry.occurred_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
              {clientAuditRows.length === 0 && <div className="text-sm text-muted-foreground">{t("Нет записей аудита", "No audit records")}</div>}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderClientWorkspacePage = (activeTab: "accounts" | "transfers" | "tickets") => (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">{t("Клиентский кабинет", "Client Workspace")}</h1>
        <p className="text-sm text-muted-foreground">{t("Управление вашими счетами и обращениями", "Manage your accounts and requests")}</p>
      </div>

      <div className="flex gap-1 bg-muted/50 rounded-xl p-1">
        {[
          { id: "accounts", label: t("Мои счета", "My Accounts"), icon: CreditCard },
          { id: "transfers", label: t("Переводы", "Transfers"), icon: ArrowLeftRight },
          { id: "tickets", label: t("Обращения", "My Tickets"), icon: MessageSquare },
        ].map((item) => (
          <button
            key={item.id}
            onClick={() => setHash(`/student/${item.id}`)}
            className={cx(
              "flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all flex-1 justify-center",
              activeTab === item.id ? "bg-white shadow text-primary" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <item.icon className="w-3.5 h-3.5" />
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {activeTab === "accounts" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{t("Мои счета", "My Accounts")} ({accounts.length})</h2>
            <button className="inline-flex items-center justify-center whitespace-nowrap rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-1.5" onClick={() => setOpenOwnAccountForm((prev) => !prev)}>
              <Plus className="w-3.5 h-3.5" /> {t("Открыть счёт", "Open Account")}
            </button>
          </div>
          {openOwnAccountForm && (
            <div className="bg-white rounded-2xl border border-border p-4 flex flex-wrap gap-3 items-end">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">{t("Тип", "Type")}</label>
                <select value={newOwnAccountType} onChange={(event) => setNewOwnAccountType(event.target.value)} className="px-3 py-2 text-sm border border-input rounded-lg bg-white">
                  <option value="CURRENT">CURRENT</option>
                  <option value="SAVINGS">SAVINGS</option>
                  <option value="CARD_ACCOUNT">CARD_ACCOUNT</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">{t("Валюта", "Currency")}</label>
                <select value={newOwnAccountCurrency} onChange={(event) => setNewOwnAccountCurrency(event.target.value)} className="px-3 py-2 text-sm border border-input rounded-lg bg-white">
                  <option value="RUB">RUB</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
              <button className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90" onClick={() => void createOwnAccount()}>{t("Открыть", "Open")}</button>
              <button className="inline-flex items-center justify-center rounded-md border border-input px-3 py-2 text-sm" onClick={() => setOpenOwnAccountForm(false)}>{t("Отмена", "Cancel")}</button>
            </div>
          )}
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {accounts.length === 0 && <div className="col-span-3 bg-white rounded-2xl border border-border p-12 text-center text-sm text-muted-foreground">{t("Нет счетов", "No accounts")}</div>}
            {accounts.map((account) => (
              <div key={account.id} className="bg-white rounded-2xl border border-border p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="text-xs font-mono text-muted-foreground">{account.account_number}</div>
                    <div className="font-bold mt-1">{formatMoney(account.balance, account.currency)}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <StatusBadge value={account.status} lang={lang} />
                    <StatusBadge value={account.type} lang={lang} />
                  </div>
                </div>
                {account.status !== "CLOSED" && (
                  <div className="flex gap-1.5 mt-3">
                    <button className="inline-flex items-center justify-center rounded-md border border-input px-2 py-1 text-xs flex-1" onClick={() => void closeOwnAccount(account.id, false)}>
                      {t("Закрыть", "Close")}
                    </button>
                    <button className="inline-flex items-center justify-center rounded-md border border-red-200 px-2 py-1 text-xs text-red-500" onClick={() => void closeOwnAccount(account.id, true)}>
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "transfers" && (
        <div className="space-y-4">
          <h2 className="font-semibold">{t("Переводы", "Transfers")}</h2>
          <div className="bg-white rounded-2xl border border-border p-5">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h3 className="font-medium text-sm">{t("Пополнение наличными", "Cash top up")}</h3>
              <span className="text-xs text-muted-foreground">{t("Валюта определяется выбранным счетом", "Currency is defined by the selected account")}</span>
            </div>
            {accounts.length === 0 ? (
              <div className="text-sm text-muted-foreground">{t("Сначала откройте счет, затем пополните его наличными.", "Open an account first, then top it up with cash.")}</div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">{t("Счет для пополнения", "Account to top up")}</label>
                  <select value={ownTopUpAccountId} onChange={(event) => setOwnTopUpAccountId(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                    {accounts.filter((item) => item.status === "ACTIVE").map((account) => (
                      <option key={account.id} value={account.id}>{account.account_number} - {formatMoney(account.balance, account.currency)}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">{t("Сумма наличных", "Cash amount")}</label>
                  <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="number" min="0" step="0.01" value={ownTopUpAmount} onChange={(event) => setOwnTopUpAmount(event.target.value)} placeholder="1000" />
                </div>
              </div>
            )}
            <button className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-2 disabled:cursor-not-allowed disabled:opacity-50" onClick={() => void createOwnCashTopUp()} disabled={busy || accounts.filter((item) => item.status === "ACTIVE").length === 0}>
              <Plus className="w-4 h-4" />
              {t("Зачислить наличные", "Top up with cash")}
            </button>
          </div>

          <div className="bg-white rounded-2xl border border-border p-5">
            <h3 className="font-medium text-sm mb-4">{t("Новый перевод", "New Transfer")}</h3>
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">{t("Счёт отправителя", "Source Account")}</label>
                <select value={transferSourceId} onChange={(event) => setTransferSourceId(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                  {accounts.filter((item) => item.status === "ACTIVE").map((account) => (
                    <option key={account.id} value={account.id}>{account.account_number} — {formatMoney(account.balance, account.currency)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">{t("Счёт получателя", "Target Account")}</label>
                <select value={transferTargetId} onChange={(event) => setTransferTargetId(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                  <option value="">{t("Выберите счёт", "Select account")}</option>
                  {accounts.filter((item) => item.id !== transferSourceId).map((account) => (
                    <option key={account.id} value={account.id}>{account.account_number}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">{t("Сумма", "Amount")}</label>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="number" value={transferAmount} onChange={(event) => setTransferAmount(event.target.value)} placeholder="5000" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">{t("Описание", "Description")}</label>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={transferDescription} onChange={(event) => setTransferDescription(event.target.value)} placeholder={t("Перевод за услуги", "Payment for services")} />
              </div>
            </div>
            <button className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-2" onClick={() => void createOwnTransfer()}>
              <Send className="w-4 h-4" />
              {t("Выполнить перевод", "Create Transfer")}
            </button>
          </div>

          <div className="bg-white rounded-2xl border border-border overflow-hidden">
            <div className="px-5 py-3 border-b border-border">
              <h3 className="font-medium text-sm">{t("История переводов", "Transfer History")}</h3>
            </div>
            <div className="divide-y divide-border">
              {transfers.map((transfer) => (
                <div key={transfer.id} className="px-5 py-3 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">{transfer.description || t("Без описания", "No description")}</div>
                    <div className="text-xs text-muted-foreground font-mono mt-0.5">{transfer.source_account_id} → {transfer.target_account_id}</div>
                    <div className="text-xs text-muted-foreground">{formatDate(transfer.created_at)}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-foreground">{formatMoney(transfer.amount, transfer.currency)}</div>
                    <StatusBadge value={transfer.status} lang={lang} />
                  </div>
                </div>
              ))}
              {transfers.length === 0 && <div className="px-5 py-8 text-sm text-muted-foreground">{t("Переводы отсутствуют", "No transfers")}</div>}
            </div>
          </div>
        </div>
      )}

      {activeTab === "tickets" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{t("Мои обращения", "My Tickets")} ({tickets.length})</h2>
            <button className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 gap-1.5" onClick={() => setCreateTicketModalOpen(true)}>
              <Plus className="w-3.5 h-3.5" /> {t("Создать", "Create")}
            </button>
          </div>

          <div className="bg-white rounded-2xl border border-border p-4">
            <div className="grid sm:grid-cols-[220px_1fr_auto] gap-2">
              <select className="px-3 py-2 text-sm border border-input rounded-lg bg-white" value={selectedOwnTicketId} onChange={(event) => setSelectedOwnTicketId(event.target.value)}>
                <option value="">{t("Выберите обращение", "Select ticket")}</option>
                {tickets.map((ticket) => (
                  <option key={ticket.id} value={ticket.id}>{ticket.subject}</option>
                ))}
              </select>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={ownTicketMessage} onChange={(event) => setOwnTicketMessage(event.target.value)} placeholder={t("Сообщение в выбранный тикет", "Message to selected ticket")} />
              <button className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90" onClick={() => void sendOwnTicketMessage()} disabled={!selectedOwnTicketId || busy}>{t("Отправить", "Send")}</button>
            </div>
          </div>

          <div className="space-y-3">
            {tickets.length === 0 && <div className="bg-white rounded-2xl border border-border p-12 text-center text-sm text-muted-foreground">{t("Нет обращений", "No tickets")}</div>}
            {tickets.map((ticket) => (
              <div key={ticket.id} className="bg-white rounded-2xl border border-border overflow-hidden">
                <button className="w-full text-left px-5 py-4 flex items-center justify-between hover:bg-muted/10 transition-colors" onClick={() => setExpandedTicketId((prev) => (prev === ticket.id ? "" : ticket.id))}>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-medium text-sm">{ticket.subject}</span>
                    <StatusBadge value={ticket.status} lang={lang} />
                    <StatusBadge value={ticket.priority} lang={lang} />
                  </div>
                  {expandedTicketId === ticket.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {expandedTicketId === ticket.id && (
                  <div className="px-5 py-4 border-t border-border bg-muted/10">
                    <p className="text-sm text-muted-foreground mb-3">{ticket.description}</p>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span>ID: {ticket.id}</span>
                      <span>{formatDate(ticket.created_at)}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderGenerateEntitiesConfirmModal = () => {
    if (!generateEntitiesConfirmOpen) {
      return null;
    }
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/50" onClick={() => (busy ? null : setGenerateEntitiesConfirmOpen(false))} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 z-10">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-foreground">{t("Сгенерировать сущности", "Generate entities")}</h3>
            <button
              onClick={() => setGenerateEntitiesConfirmOpen(false)}
              className="p-1.5 hover:bg-muted rounded-lg disabled:opacity-50"
              disabled={busy}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="text-sm text-muted-foreground space-y-2">
            <p>{t("Будут удалены все текущие сотрудники, клиенты, счета, тикеты и сообщения вашего кабинета.", "All current employees, clients, accounts, tickets, and messages in your cabinet will be removed.")}</p>
            <p>{t("После очистки автоматически создастся новый тестовый набор данных.", "After cleanup, a new test data set will be generated automatically.")}</p>
          </div>
          <div className="flex gap-3 mt-5">
            <button
              className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium flex-1 disabled:opacity-50"
              onClick={() => setGenerateEntitiesConfirmOpen(false)}
              disabled={busy}
            >
              {t("Отмена", "Cancel")}
            </button>
            <button
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 flex-1 disabled:opacity-50 gap-2"
              onClick={() => void generateStudentEntities()}
              disabled={busy}
            >
              <RefreshCw className={cx("w-4 h-4", busy ? "animate-spin" : "")} />
              {busy ? t("Генерация...", "Generating...") : t("Подтвердить", "Confirm")}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderCreateClientModal = () => {
    if (!clientCreateOpen) {
      return null;
    }
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/50" onClick={() => setClientCreateOpen(false)} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 z-10">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-bold text-foreground">{t("Создать клиента", "Create Client")}</h3>
            <button onClick={() => setClientCreateOpen(false)} className="p-1.5 hover:bg-muted rounded-lg"><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">{t("Ответственный сотрудник", "Responsible employee")} *</label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={clientCreateEmployeeId}
                onChange={(event) => setClientCreateEmployeeId(event.target.value)}
              >
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.full_name || `${employee.first_name || ""} ${employee.last_name || ""}`.trim() || employee.email}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">{t("Имя", "First Name")} *</label>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={clientCreateFirstName} onChange={(event) => setClientCreateFirstName(event.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">{t("Фамилия", "Last Name")} *</label>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={clientCreateLastName} onChange={(event) => setClientCreateLastName(event.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">{t("Телефон", "Phone")}</label>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={clientCreatePhone} onChange={(event) => setClientCreatePhone(event.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
                <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={clientCreateEmail} onChange={(event) => setClientCreateEmail(event.target.value)} />
              </div>
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium flex-1" onClick={() => setClientCreateOpen(false)}>{t("Отмена", "Cancel")}</button>
            <button className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 flex-1" onClick={() => void createEmployeeClient()} disabled={busy || !clientCreateEmployeeId || !clientCreateFirstName || !clientCreateLastName || !clientCreateEmail}>{busy ? t("Создание...", "Creating...") : t("Создать", "Create")}</button>
          </div>
        </div>
      </div>
    );
  };

  const renderCreateEmployeeModal = () => {
    if (!employeeCreateOpen) {
      return null;
    }
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/50" onClick={() => setEmployeeCreateOpen(false)} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 z-10">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-bold text-foreground">{t("Добавить сотрудника", "Add employee")}</h3>
            <button onClick={() => setEmployeeCreateOpen(false)} className="p-1.5 hover:bg-muted rounded-lg"><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">{t("ФИО", "Full name")} *</label>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={employeeCreateFullName} onChange={(event) => setEmployeeCreateFullName(event.target.value)} placeholder="Иванов Иван" />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Email *</label>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="email" value={employeeCreateEmail} onChange={(event) => setEmployeeCreateEmail(event.target.value)} placeholder="employee@demobank.local" />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">{t("Пароль", "Password")} ({t("опционально", "optional")})</label>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="password" value={employeeCreatePassword} onChange={(event) => setEmployeeCreatePassword(event.target.value)} placeholder="Min 8 chars" />
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium flex-1" onClick={() => setEmployeeCreateOpen(false)}>{t("Отмена", "Cancel")}</button>
            <button className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 flex-1" onClick={() => void createEmployeeUser()} disabled={busy || !employeeCreateFullName.trim() || !employeeCreateEmail.trim()}>{busy ? t("Создание...", "Creating...") : t("Создать", "Create")}</button>
          </div>
        </div>
      </div>
    );
  };

  const renderEditEmployeeModal = () => {
    if (!employeeEditOpen) {
      return null;
    }
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/50" onClick={() => setEmployeeEditOpen(false)} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 z-10">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-bold text-foreground">{t("Редактировать сотрудника", "Edit employee")}</h3>
            <button onClick={() => setEmployeeEditOpen(false)} className="p-1.5 hover:bg-muted rounded-lg"><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">{t("ФИО", "Full name")} *</label>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={employeeEditFullName} onChange={(event) => setEmployeeEditFullName(event.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Email *</label>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="email" value={employeeEditEmail} onChange={(event) => setEmployeeEditEmail(event.target.value)} />
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium flex-1" onClick={() => setEmployeeEditOpen(false)}>{t("Отмена", "Cancel")}</button>
            <button className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 flex-1" onClick={() => void updateEmployeeUser()} disabled={busy || !employeeEditFullName.trim() || !employeeEditEmail.trim()}>{busy ? t("Сохранение...", "Saving...") : t("Сохранить", "Save")}</button>
          </div>
        </div>
      </div>
    );
  };

  const renderOpenClientAccountModal = () => {
    if (!openAccountModal) {
      return null;
    }
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/50" onClick={() => setOpenAccountModal(false)} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 z-10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold">{t("Открыть счёт", "Open Account")}</h3>
            <button onClick={() => setOpenAccountModal(false)}><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">{t("Тип счёта", "Account Type")}</label>
              <select value={newClientAccountType} onChange={(event) => setNewClientAccountType(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                <option value="CURRENT">CURRENT</option>
                <option value="SAVINGS">SAVINGS</option>
                <option value="CARD_ACCOUNT">CARD_ACCOUNT</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">{t("Валюта", "Currency")}</label>
              <select value={newClientAccountCurrency} onChange={(event) => setNewClientAccountCurrency(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                <option value="RUB">RUB</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium flex-1" onClick={() => setOpenAccountModal(false)}>{t("Отмена", "Cancel")}</button>
            <button className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 flex-1" onClick={() => void openAccountForClient()}>{t("Открыть", "Open")}</button>
          </div>
        </div>
      </div>
    );
  };

  const renderCreateOwnTicketModal = () => {
    if (!createTicketModalOpen) {
      return null;
    }
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/50" onClick={() => setCreateTicketModalOpen(false)} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 z-10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold">{t("Создать обращение", "Create Ticket")}</h3>
            <button onClick={() => setCreateTicketModalOpen(false)}><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">{t("Категория", "Category")}</label>
              <select value={ticketCategory} onChange={(event) => setTicketCategory(event.target.value)} className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-white">
                {[
                  "CARD",
                  "ACCOUNT",
                  "TRANSFER",
                  "COMPLAINT",
                  "TECHNICAL",
                  "OTHER",
                ].map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">{t("Тема", "Subject")} *</label>
              <input className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={ticketSubject} onChange={(event) => setTicketSubject(event.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">{t("Описание", "Description")} *</label>
              <textarea className="w-full px-3 py-2 text-sm border border-input rounded-lg resize-none h-24" value={ticketDescription} onChange={(event) => setTicketDescription(event.target.value)} />
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium flex-1" onClick={() => setCreateTicketModalOpen(false)}>{t("Отмена", "Cancel")}</button>
            <button className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 flex-1" onClick={() => void createOwnTicket()} disabled={!ticketSubject.trim() || !ticketDescription.trim()}>{t("Отправить", "Submit")}</button>
          </div>
        </div>
      </div>
    );
  };

  const navToolItems = STUDENT_TOOL_MENU_ORDER.flatMap((service) => {
    const slug = TOOL_SLUG_BY_SERVICE[service];
    if (!slug) {
      return [];
    }
    return [
      {
        path: `/student/tools/${slug}`,
        label: TOOL_MAP[service].title,
        icon: TOOL_ICON_BY_SERVICE[service],
      },
    ];
  });

  const navItems: Array<{ path: string; label: string; icon: React.ComponentType<{ className?: string }> }> = [
    { path: "/student/dashboard", label: t("Дашборд", "Dashboard"), icon: LayoutDashboard },
    { path: "/student/employees", label: t("Сотрудники", "Employees"), icon: Users },
    { path: "/student/clients", label: t("Клиенты", "Clients"), icon: UserCircle2 },
    ...navToolItems,
  ];

  const activePath = useMemo(() => {
    if (route.route !== "student") {
      return "/student/dashboard";
    }
    if (route.section === "employee-profile") {
      return "/student/employees";
    }
    if (route.section === "employee-workspace") {
      return "/student/employees";
    }
    if (route.section === "client-profile") {
      return "/student/clients";
    }
    if (route.section === "tools") {
      return navToolItems[0]?.path || "/student/dashboard";
    }
    if (route.section === "tool-detail" && route.toolSlug) {
      return `/student/tools/${route.toolSlug}`;
    }
    return `/student/${route.section}`;
  }, [route, navToolItems]);

  const shouldRestoreStudentSession =
    route.route === "student" &&
    (!sessionBootstrapped || (Boolean(refreshToken) && sessionRestoring && (!isAuthenticated || !profile)));

  if (shouldRestoreStudentSession) {
    return (
      <main className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
        <section className="w-full max-w-md rounded-2xl border border-border bg-white p-6 shadow-sm">
          <div className="text-sm text-muted-foreground text-center">{t("Восстанавливаем сессию...", "Restoring session...")}</div>
        </section>
      </main>
    );
  }

  if (route.route === "login" || !isAuthenticated || !profile) {
    return (
      <main className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
        <section className="w-full max-w-md rounded-2xl border border-border bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center text-white">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-foreground leading-tight">Easy IT Bank</h1>
              <p className="text-sm text-muted-foreground">{t("Кабинет студента", "Student Cabinet")}</p>
            </div>
          </div>

          <div className="space-y-1">
            <h2 className="text-base font-semibold text-foreground">{t("Вход в кабинет студента", "Student sign in")}</h2>
            <p className="text-sm text-muted-foreground">{t("Управление сотрудниками и клиентами в едином интерфейсе.", "Manage employees and clients in a single interface.")}</p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Email</label>
            <input className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">{t("Пароль", "Password")}</label>
            <input className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>

          <button className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50" onClick={() => void loginWithCredentials()} disabled={busy}>
            {busy ? t("Вход...", "Signing in...") : t("Войти", "Sign In")}
          </button>

          {notice && (
            <div className={cx("rounded-xl border px-3 py-2 text-sm", notice.includes("FORBIDDEN") || notice.includes("INVALID") || notice.includes("HTTP") ? "border-red-200 text-red-700 bg-red-50" : "border-blue-200 text-blue-700 bg-blue-50")}>
              {notice}
            </div>
          )}

          <div className="flex justify-center">
            <div className="inline-flex items-center rounded-full border border-input bg-muted p-0.5" role="group" aria-label="language switch">
              <button className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${lang === "ru" ? "bg-primary text-white" : "text-muted-foreground hover:text-foreground"}`} onClick={() => setLang("ru")}>
                RU
              </button>
              <button className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${lang === "en" ? "bg-primary text-white" : "text-muted-foreground hover:text-foreground"}`} onClick={() => setLang("en")}>
                EN
              </button>
            </div>
          </div>

          {renderDeveloperFooter()}
        </section>
      </main>
    );
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <aside
        className={cx(
          "fixed top-0 left-0 h-full w-64 z-40 flex flex-col bg-slate-900 text-white transition-transform duration-300 lg:translate-x-0 lg:static lg:z-auto",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <div className="px-5 py-4 border-b border-slate-700">
          <a href="#/student/dashboard" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-sm font-bold text-white">Easy IT Bank</div>
              <div className="text-xs text-slate-400">{t("Кабинет студента", "Student Portal")}</div>
            </div>
          </a>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const active = activePath === item.path;
            return (
              <a
                key={item.path}
                href={`#${item.path}`}
                onClick={() => setSidebarOpen(false)}
                className={cx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group",
                  active ? "bg-primary text-white" : "text-slate-400 hover:text-white hover:bg-slate-800"
                )}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1">{item.label}</span>
                {active && <ChevronRight className="w-3.5 h-3.5 opacity-70" />}
              </a>
            );
          })}
        </nav>

        <div className="px-4 py-4 border-t border-slate-700">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-blue-400 flex items-center justify-center text-white text-sm font-bold">
              {(profile.full_name || profile.first_name || profile.email || "U")[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">{profile.full_name || `${profile.first_name || ""} ${profile.last_name || ""}`.trim() || profile.email}</div>
              <div className="text-xs text-slate-400 font-mono truncate">
                {(profile.username || profile.email || "").includes("@") ? (profile.username || profile.email) : `@${profile.username || profile.email || "-"}`}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="inline-flex flex-1 items-center justify-center rounded-md border border-slate-700 px-2 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800" onClick={() => setLang((prev) => (prev === "ru" ? "en" : "ru"))}>{lang === "ru" ? "RU" : "EN"}</button>
            <button className="inline-flex flex-1 items-center justify-center rounded-md border border-slate-700 px-2 py-1.5 text-xs font-medium text-red-300 hover:bg-slate-800" onClick={logout}><LogOut className="w-3 h-3 mr-1" />{t("Выйти", "Logout")}</button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 border-b border-border bg-white flex items-center px-4 gap-3 flex-shrink-0">
          <button className="lg:hidden p-2 rounded-lg hover:bg-muted transition-colors" onClick={() => setSidebarOpen((prev) => !prev)}>
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1" />
          {route.route === "student" && route.section === "employees" && (
            <button className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-input hover:bg-muted" onClick={() => setEmployeeCreateOpen(true)}>
              <Plus className="w-3.5 h-3.5" />
              {t("Добавить сотрудника", "Add employee")}
            </button>
          )}
          <button className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-input hover:bg-muted" onClick={() => void refreshSession({ interactive: true })}>
            <RefreshCw className="w-3.5 h-3.5" />
            {t("Refresh", "Refresh")}
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="mx-auto flex min-h-full max-w-screen-2xl flex-col gap-4">
            <div className="flex-1">
              {route.route === "student" && route.section === "dashboard" && renderDashboard()}
              {route.route === "student" && route.section === "employees" && renderEmployeesPage()}
              {route.route === "student" && route.section === "employee-profile" && renderEmployeeProfilePage()}
              {route.route === "student" && route.section === "employee-workspace" && renderEmployeeWorkspacePage()}
              {route.route === "student" && route.section === "clients" && renderEmployeeClientsPage()}
              {route.route === "student" && route.section === "client-profile" && renderClientProfilePage()}
              {route.route === "student" && route.section === "tools" && renderToolsPanel()}
              {route.route === "student" && route.section === "tool-detail" && renderToolDetailPage()}
            </div>
            {renderDeveloperFooter("mt-auto")}
          </div>
        </main>
      </div>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {notice && (
        <div className={cx("fixed bottom-4 left-1/2 -translate-x-1/2 rounded-xl border px-4 py-2 text-sm bg-white shadow z-[120]", notice.includes("FORBIDDEN") || notice.includes("INVALID") || notice.includes("HTTP") ? "border-red-200 text-red-700" : "border-blue-200 text-blue-700")}>
          {notice}
        </div>
      )}

      {renderCreateClientModal()}
      {renderGenerateEntitiesConfirmModal()}
      {renderCreateEmployeeModal()}
      {renderEditEmployeeModal()}
      {renderOpenClientAccountModal()}
      {renderCreateOwnTicketModal()}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
