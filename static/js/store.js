// Небольшое состояние приложения и тема оформления.
import { api } from "./api.js";
import { storageGet, storageSet } from "./utils.js";

const THEME_KEY = "rhythm.theme";
const listeners = new Map();

export const store = {
  user: null,
  today: null,
  templates: null,
  aiStatus: null,
  theme: "light",

  on(event, handler) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event).add(handler);
    return () => listeners.get(event)?.delete(handler);
  },

  emit(event, payload) {
    for (const handler of listeners.get(event) || []) {
      try {
        handler(payload);
      } catch (error) {
        console.error(error);
      }
    }
  },

  initTheme() {
    const stored = storageGet(THEME_KEY, null);
    this.applyTheme(stored === "dark" || stored === "light" ? stored : "light", { persist: false });
  },

  applyTheme(theme, { persist = true } = {}) {
    this.theme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = this.theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", this.theme === "dark" ? "#0f1c1a" : "#F0FEFF");
    if (persist) storageSet(THEME_KEY, this.theme);
    this.emit("theme", this.theme);
  },

  toggleTheme() {
    this.applyTheme(this.theme === "dark" ? "light" : "dark");
    return this.theme;
  },

  setUser(user) {
    this.user = user || null;
    if (user?.theme && !storageGet(THEME_KEY, null)) this.applyTheme(user.theme, { persist: false });
    this.emit("user", this.user);
  },

  get isAdmin() {
    return this.user?.role === "admin";
  },

  clear() {
    this.user = null;
    this.today = null;
    this.aiStatus = null;
    this.emit("user", null);
  },

  async loadTemplates(force = false) {
    if (this.templates && !force) return this.templates;
    const data = await api.get("/templates");
    this.templates = data?.templates || [];
    return this.templates;
  },
};
