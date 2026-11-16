// Каркас приложения: загрузка сессии, hash-роутер, навигация и тема.
import { api } from "./api.js";
import { icon } from "./icons.js";
import { store } from "./store.js";
import { toast } from "./ui.js";
import { esc, initials } from "./utils.js";
import * as adminView from "./views/admin.js";
import * as assistantView from "./views/assistant.js";
import * as authView from "./views/auth.js";
import * as calendarView from "./views/calendar.js";
import * as docsView from "./views/docs.js";
import * as habitsView from "./views/habits.js";
import * as onboardingView from "./views/onboarding.js";
import * as settingsView from "./views/settings.js";
import * as statsView from "./views/stats.js";
import * as todayView from "./views/today.js";

const ROUTES = {
  today: { title: "Сегодня", icon: "today", group: "ritm", mobile: true },
  habits: { title: "Привычки", icon: "habits", group: "ritm", mobile: true },
  calendar: { title: "Календарь", icon: "calendar", group: "ritm", mobile: true },
  stats: { title: "Статистика", icon: "stats", group: "ritm", mobile: true },
  assistant: { title: "AI-ассистент", icon: "ai", group: "ai", mobile: true },
  settings: { title: "Настройки", icon: "settings", group: "system" },
  docs: { title: "Документы", icon: "docs", group: "system" },
  admin: { title: "Админка", icon: "admin", group: "system", adminOnly: true },
};

const VIEWS = {
  today: todayView.mount,
  habits: habitsView.mount,
  calendar: calendarView.mount,
  stats: statsView.mount,
  assistant: assistantView.mount,
  settings: settingsView.mount,
  docs: docsView.mount,
  admin: adminView.mount,
};

const appRoot = document.getElementById("app");
const state = {
  user: null,
  onboardingNeeded: false,
  cleanup: null,
  currentRoute: "",
};

function parseHash() {
  const raw = location.hash || "#/today";
  const path = raw.replace(/^#\/?/, "");
  const parts = path.split("/").filter(Boolean);
  const name = ROUTES[parts[0]] ? parts[0] : "today";
  return { name, param: parts.slice(1).join("/") || null, raw };
}

function routeHref(name) {
  return `#/${name}`;
}

function navigate(target) {
  const next = String(target || "today").startsWith("#") ? String(target) : `#/${target}`;
  if (location.hash === next) {
    renderRoute();
  } else {
    location.hash = next;
  }
}

function navItem(name, active) {
  const route = ROUTES[name];
  if (!route) return "";
  const badge = name === "today"
    ? '<span class="nav-badge" data-nav-badge="today" hidden></span>'
    : "";
  return `
    <a class="nav-item${active === name ? " active" : ""}" href="${routeHref(name)}" data-route="${name}">
      ${icon(route.icon)}<span>${esc(route.title)}</span>${badge}
    </a>
  `;
}

function mobileItem(name, active) {
  const route = ROUTES[name];
  if (!route) return "";
  return `
    <a class="mnav-item${active === name ? " active" : ""}" href="${routeHref(name)}" data-route="${name}">
      ${icon(route.icon)}<span>${esc(route.title)}</span>
    </a>
  `;
}

function themeIcon() {
  return store.theme === "dark" ? "sun" : "moon";
}

function renderShell(active) {
  const user = state.user || {};
  const isAdmin = user.role === "admin";
  const adminItem = isAdmin ? navItem("admin", active) : "";
  const mobile = ["today", "habits", "calendar", "stats", "assistant"];

  appRoot.removeAttribute("aria-busy");
  appRoot.innerHTML = `
    <div class="shell">
      <aside class="sidebar">
        <a class="brand" href="#/today">ритм<span>.</span></a>
        <nav class="nav" aria-label="Основная навигация">
          <span class="nav-label">Ритм</span>
          ${["today", "habits", "calendar", "stats"].map((name) => navItem(name, active)).join("")}
          <span class="nav-label">Ассистент</span>
          ${navItem("assistant", active)}
          <span class="nav-label">Система</span>
          ${navItem("settings", active)}
          ${navItem("docs", active)}
          ${adminItem}
        </nav>
        <div class="sidebar-foot">
          <a class="user-chip" href="#/settings">
            <span class="avatar" data-user-initials>${esc(initials(user.name))}</span>
            <span class="grow" style="min-width:0">
              <span class="user-name" data-user-name style="display:block">${esc(user.name || "")}</span>
              <span class="user-goal" data-user-goal style="display:block">${esc(user.goal || "Ваш личный ритм")}</span>
            </span>
          </a>
          <div class="sidebar-actions">
            <button type="button" class="icon-btn bordered" data-action="theme" aria-label="Сменить тему">
              <span data-theme-icon>${icon(themeIcon())}</span>
            </button>
            <button type="button" class="icon-btn bordered" data-action="logout" aria-label="Выйти">
              ${icon("logout")}
            </button>
          </div>
        </div>
      </aside>

      <div class="main-col">
        <header class="topbar">
          <a class="brand" href="#/today">ритм<span>.</span></a>
          <div class="topbar-actions">
            <button type="button" class="icon-btn" data-action="theme" aria-label="Сменить тему">
              <span data-theme-icon>${icon(themeIcon())}</span>
            </button>
            <a class="icon-btn" href="#/settings" aria-label="Настройки">${icon("settings")}</a>
          </div>
        </header>
        <main id="view" class="view" tabindex="-1"></main>
      </div>
    </div>

    <nav class="mobile-nav" aria-label="Мобильная навигация">
      <div class="mobile-nav-inner">
        ${mobile.map((name) => mobileItem(name, active)).join("")}
      </div>
    </nav>

    <div id="global-sync" class="sync-line" role="status" aria-live="polite">
      <span class="sync-dot"></span><span class="sync-text">Сохранено</span>
    </div>
  `;
  return appRoot.querySelector("#view");
}

function renderAuth() {
  if (state.cleanup) {
    try { state.cleanup(); } catch { /* noop */ }
    state.cleanup = null;
  }
  appRoot.removeAttribute("aria-busy");
  authView.mount(appRoot, makeCtx({ name: "auth", param: null }));
}

function renderOnboarding() {
  if (state.cleanup) {
    try { state.cleanup(); } catch { /* noop */ }
    state.cleanup = null;
  }
  appRoot.removeAttribute("aria-busy");
  onboardingView.mount(appRoot, makeCtx({ name: "today", param: null }));
}

function makeCtx(route) {
  return {
    get user() {
      return store.user;
    },
    params: { date: route.param || null },
    navigate,
    setBadge,
    updateUser,
    logout,
    onAuth,
    accountDeleted,
  };
}

async function renderRoute() {
  const route = parseHash();
  const changed = route.name !== state.currentRoute;
  state.currentRoute = route.name;

  if (!state.user) {
    renderAuth();
    document.title = "Вход — Ритм";
    return;
  }
  if (state.onboardingNeeded) {
    renderOnboarding();
    document.title = "Настройка — Ритм";
    return;
  }
  if (ROUTES[route.name]?.adminOnly && !store.isAdmin) {
    toast("Этот раздел доступен только администратору.", { type: "info" });
    navigate("today");
    return;
  }

  if (state.cleanup) {
    try { state.cleanup(); } catch { /* noop */ }
    state.cleanup = null;
  }

  const viewRoot = renderShell(route.name);
  document.title = `${ROUTES[route.name]?.title || "Ритм"} — Ритм`;
  if (changed) window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

  const mountView = VIEWS[route.name];
  try {
    const cleanup = await mountView(viewRoot, makeCtx(route));
    if (typeof cleanup === "function") state.cleanup = cleanup;
  } catch (error) {
    console.error(error);
    viewRoot.innerHTML = `
      <div class="card card-pad text-center">
        <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
        <h2 class="h2">Что-то пошло не так</h2>
        <p class="muted small mt-1">${esc(error.message || "Не удалось открыть раздел.")}</p>
        <div class="row mt-3" style="justify-content:center;gap:8px">
          <button type="button" class="btn btn-soft" data-action="home">На главную</button>
          <button type="button" class="btn btn-primary" data-action="retry-route">Повторить</button>
        </div>
      </div>
    `;
    viewRoot.querySelector('[data-action="home"]')?.addEventListener("click", () => navigate("today"));
    viewRoot.querySelector('[data-action="retry-route"]')?.addEventListener("click", () => renderRoute());
  }
}

function onAuth(data) {
  if (!data?.user) return;
  state.user = data.user;
  store.setUser(data.user);
  state.onboardingNeeded = Boolean(data.onboarding_needed);
  state.currentRoute = "";
  if (!state.onboardingNeeded) loadBadge();
  renderRoute();
}

function updateUser(user) {
  if (!user) return;
  state.user = user;
  store.setUser(user);
  const initialsNode = appRoot.querySelector("[data-user-initials]");
  const nameNode = appRoot.querySelector("[data-user-name]");
  const goalNode = appRoot.querySelector("[data-user-goal]");
  if (initialsNode) initialsNode.textContent = initials(user.name);
  if (nameNode) nameNode.textContent = user.name || "";
  if (goalNode) goalNode.textContent = user.goal || "Ваш личный ритм";
}

async function logout() {
  try {
    await api.post("/auth/logout");
  } catch {
    /* сессия могла уже истечь */
  }
  state.user = null;
  state.onboardingNeeded = false;
  state.currentRoute = "";
  store.clear();
  setBadge("today", 0);
  renderAuth();
  toast("Вы вышли. Возвращайтесь, когда будет удобно.", { type: "info" });
}

function accountDeleted() {
  state.user = null;
  state.onboardingNeeded = false;
  state.currentRoute = "";
  store.clear();
  renderAuth();
}

function toggleTheme() {
  const theme = store.toggleTheme();
  appRoot.querySelectorAll("[data-theme-icon]").forEach((node) => {
    node.innerHTML = icon(theme === "dark" ? "sun" : "moon");
  });
  if (state.user) {
    api.patch("/settings", { theme }).then((response) => {
      if (response?.user) {
        state.user = response.user;
        store.setUser(response.user);
      }
    }).catch(() => {
      /* тема уже применена локально */
    });
  }
}

function setBadge(key, value) {
  const count = Number(value) || 0;
  appRoot.querySelectorAll(`[data-nav-badge="${key}"]`).forEach((node) => {
    node.textContent = String(count);
    node.hidden = count <= 0;
  });
}

async function loadBadge() {
  try {
    const data = await api.get("/events", { unseen: 1 });
    setBadge("today", (data.events || []).length);
  } catch {
    /* бейдж не критичен */
  }
}

async function boot() {
  store.initTheme();
  try {
    const me = await api.get("/auth/me");
    if (me?.user) {
      state.user = me.user;
      state.onboardingNeeded = Boolean(me.onboarding_needed);
      store.setUser(me.user);
      if (!state.onboardingNeeded) loadBadge();
    }
    renderRoute();
  } catch (error) {
    appRoot.removeAttribute("aria-busy");
    appRoot.innerHTML = `
      <div class="boot-screen">
        <div class="boot-mark">ритм<span>.</span></div>
        <p class="muted small">${esc(error.message || "Нет связи с сервером.")}</p>
        <button type="button" class="btn btn-primary" data-action="retry-boot">Попробовать снова</button>
      </div>
    `;
    appRoot.querySelector('[data-action="retry-boot"]')?.addEventListener("click", () => {
      appRoot.setAttribute("aria-busy", "true");
      boot();
    });
  }
}

appRoot.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "theme") toggleTheme();
  if (action === "logout") logout();
});

window.addEventListener("hashchange", () => renderRoute());
window.addEventListener("app:unauthorized", () => {
  if (!state.user) return;
  state.user = null;
  state.onboardingNeeded = false;
  state.currentRoute = "";
  store.clear();
  renderAuth();
  toast("Сессия истекла. Войдите снова — данные сохранены.", { type: "info" });
});

boot();
