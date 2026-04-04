type AnalyticsValue = string | number | boolean | null | undefined;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    ym?: YandexMetrikaFn & { a?: unknown[][]; l?: number };
  }
}

type YandexMetrikaFn = ((counterId: number, method: string, ...args: unknown[]) => void) & {
  a?: unknown[][];
  l?: number;
};

const GA_MEASUREMENT_ID = "";
const YANDEX_METRIKA_ID = 0;

let analyticsInitialized = false;

function ensureScript(src: string): void {
  if (document.querySelector(`script[src="${src}"]`)) {
    return;
  }
  const script = document.createElement("script");
  script.async = true;
  script.src = src;
  document.head.appendChild(script);
}

function initializeGoogleAnalytics(): void {
  if (!GA_MEASUREMENT_ID) {
    return;
  }
  ensureScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA_MEASUREMENT_ID)}`);
  window.dataLayer = window.dataLayer || [];
  window.gtag =
    window.gtag ||
    function gtag(...args: unknown[]) {
      window.dataLayer?.push(args);
    };
  window.gtag("js", new Date());
  window.gtag("config", GA_MEASUREMENT_ID, {
    send_page_view: false,
    anonymize_ip: true,
  });
}

function initializeYandexMetrika(): void {
  if (!YANDEX_METRIKA_ID) {
    return;
  }
  if (typeof window.ym !== "function") {
    const ymStub: YandexMetrikaFn = function ymStub(counterId: number, method: string, ...args: unknown[]) {
      ymStub.a = ymStub.a || [];
      ymStub.a.push([counterId, method, ...args]);
    };
    ymStub.a = ymStub.a || [];
    ymStub.l = Number(new Date());
    window.ym = ymStub;
  }
  ensureScript("https://mc.yandex.ru/metrika/tag.js");
  window.ym(YANDEX_METRIKA_ID, "init", {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: true,
    trackHash: true,
  });
}

function normalizeParams(params: Record<string, AnalyticsValue>): Record<string, string | number | boolean> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null)
  ) as Record<string, string | number | boolean>;
}

function buildPageLocation(path: string): string {
  return `${window.location.origin}${path}`;
}

export function initAnalytics(appName: string): void {
  if (analyticsInitialized) {
    return;
  }
  analyticsInitialized = true;
  initializeGoogleAnalytics();
  initializeYandexMetrika();
  trackAnalyticsEvent("app_boot", { app_name: appName });
}

export function trackPageView(path: string, title = document.title): void {
  const normalizedPath = path || window.location.pathname || "/";
  if (GA_MEASUREMENT_ID && typeof window.gtag === "function") {
    window.gtag("event", "page_view", {
      page_title: title,
      page_path: normalizedPath,
      page_location: buildPageLocation(normalizedPath),
    });
  }
  if (YANDEX_METRIKA_ID && typeof window.ym === "function") {
    window.ym(YANDEX_METRIKA_ID, "hit", normalizedPath, { title });
  }
}

export function trackAnalyticsEvent(name: string, params: Record<string, AnalyticsValue> = {}): void {
  const normalizedParams = normalizeParams(params);
  if (GA_MEASUREMENT_ID && typeof window.gtag === "function") {
    window.gtag("event", name, normalizedParams);
  }
  if (YANDEX_METRIKA_ID && typeof window.ym === "function") {
    window.ym(YANDEX_METRIKA_ID, "reachGoal", name, normalizedParams);
  }
}
