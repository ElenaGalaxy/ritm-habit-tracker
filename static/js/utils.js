// Общие помощники: даты, форматирование, безопасный HTML, DOM.
// Модуль не зависит от API и может импортироваться где угодно.

export const MONTHS = [
  "январь", "февраль", "март", "апрель", "май", "июнь",
  "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
];
export const MONTHS_GEN = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];
export const WEEKDAYS = [
  "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье",
];
export const WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
export const WEEKDAYS_MIN = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

export const TIMEZONES = [
  "Europe/Kaliningrad", "Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg",
  "Asia/Omsk", "Asia/Novosibirsk", "Asia/Krasnoyarsk", "Asia/Irkutsk",
  "Asia/Yakutsk", "Asia/Vladivostok", "Asia/Magadan", "Asia/Kamchatka",
  "Europe/Minsk", "Europe/Kiev", "Asia/Almaty", "Asia/Tbilisi",
  "Asia/Yerevan", "Asia/Baku", "Asia/Tashkent", "Asia/Dubai",
  "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Istanbul",
  "America/New_York", "America/Chicago", "America/Los_Angeles", "Asia/Tokyo",
];

export const UNITS_BY_TYPE = {
  quantity: ["раз", "страница", "стакан", "шаг", "кг", "км"],
  duration: ["минута"],
};

// Русские формы единиц: [одна, две-четыре, много]. Ключи — любые встречающиеся
// написания, чтобы старые записи («минуты», «стаканы») тоже читались правильно.
const UNIT_FORMS = {
  "раз": ["раз", "раза", "раз"],
  "страница": ["страница", "страницы", "страниц"],
  "страницы": ["страница", "страницы", "страниц"],
  "страниц": ["страница", "страницы", "страниц"],
  "стакан": ["стакан", "стакана", "стаканов"],
  "стаканы": ["стакан", "стакана", "стаканов"],
  "стаканов": ["стакан", "стакана", "стаканов"],
  "шаг": ["шаг", "шага", "шагов"],
  "шаги": ["шаг", "шага", "шагов"],
  "шагов": ["шаг", "шага", "шагов"],
  "минута": ["минута", "минуты", "минут"],
  "минуты": ["минута", "минуты", "минут"],
  "минут": ["минута", "минуты", "минут"],
};

export function pluralUnit(unit, value) {
  const forms = UNIT_FORMS[String(unit || "").toLowerCase()];
  const n = Math.abs(Number(value) || 0);
  if (!forms) return unit;
  if (!Number.isInteger(n)) return forms[1];
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return forms[2];
  if (mod10 === 1) return forms[0];
  if (mod10 >= 2 && mod10 <= 4) return forms[1];
  return forms[2];
}

// ------------------------------------------------------------------ строки

export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export const escapeHTML = esc;

export function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function firstName(name) {
  return String(name || "").trim().split(/\s+/)[0] || "";
}

export function pluralRu(n, one, few, many) {
  const value = Math.abs(Number(n) || 0) % 100;
  if (value >= 11 && value <= 14) return many;
  const tail = value % 10;
  if (tail === 1) return one;
  if (tail >= 2 && tail <= 4) return few;
  return many;
}

export const daysWord = (n) => pluralRu(n, "день", "дня", "дней");
export const weeksWord = (n) => pluralRu(n, "неделя", "недели", "недель");
export const timesWord = (n) => pluralRu(n, "раз", "раза", "раз");
export const habitsWord = (n) => pluralRu(n, "привычка", "привычки", "привычек");

// ------------------------------------------------------------------ даты

export function parseISODate(iso) {
  if (iso instanceof Date) return new Date(iso.getTime());
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!match) return new Date(NaN);
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function toISODate(date) {
  const d = parseISODate(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function todayISO() {
  return toISODate(new Date());
}

export function addDays(date, amount) {
  const d = parseISODate(date);
  d.setDate(d.getDate() + Number(amount || 0));
  return d;
}

export function startOfWeek(date) {
  const d = parseISODate(date);
  const offset = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - offset);
  return d;
}

export function endOfWeek(date) {
  return addDays(startOfWeek(date), 6);
}

export function monthKey(date) {
  const d = parseISODate(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function shiftMonth(key, amount) {
  const [year, month] = String(key).split("-").map(Number);
  const d = new Date(year, month - 1 + Number(amount || 0), 1);
  return monthKey(d);
}

export function monthTitle(year, month) {
  return `${MONTHS[Number(month) - 1] || ""} ${year}`.replace(/^./, (c) => c.toUpperCase());
}

export function monthTitleFromKey(key) {
  const [year, month] = String(key).split("-").map(Number);
  return monthTitle(year, month);
}

export function formatDate(iso, { withYear = false, short = false } = {}) {
  const d = parseISODate(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const day = d.getDate();
  const month = short ? MONTHS[d.getMonth()] : MONTHS_GEN[d.getMonth()];
  return withYear ? `${day} ${month} ${d.getFullYear()}` : `${day} ${month}`;
}

export function formatDateLong(iso) {
  const d = parseISODate(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.getDate()} ${MONTHS_GEN[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatDateTime(isoTs) {
  if (!isoTs) return "—";
  const d = new Date(isoTs);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export function formatTime(isoTs) {
  if (!isoTs) return "—";
  const d = new Date(isoTs);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

export function weekdayName(iso) {
  const d = parseISODate(iso);
  if (Number.isNaN(d.getTime())) return "";
  return WEEKDAYS[(d.getDay() + 6) % 7];
}

export function weekdayShort(iso) {
  const d = parseISODate(iso);
  if (Number.isNaN(d.getTime())) return "";
  return WEEKDAYS_SHORT[(d.getDay() + 6) % 7];
}

export function isToday(iso) {
  return String(iso) === todayISO();
}

export function dateLabel(iso) {
  const today = todayISO();
  if (iso === today) return "Сегодня";
  if (iso === toISODate(addDays(today, 1))) return "Завтра";
  if (iso === toISODate(addDays(today, -1))) return "Вчера";
  return `${formatDate(iso, { withYear: true })}, ${weekdayName(iso).toLowerCase()}`;
}

export function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) return "Доброе утро";
  if (hour >= 12 && hour < 18) return "Добрый день";
  if (hour >= 18 && hour < 23) return "Добрый вечер";
  return "Доброй ночи";
}

// ------------------------------------------------------------------ числа

export function clamp(value, min, max) {
  const n = Number(value);
  if (Number.isNaN(n)) return min;
  return Math.min(max, Math.max(min, n));
}

export function num(value, maxFraction = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "0";
  const rounded = Math.round(n * 10 ** maxFraction) / 10 ** maxFraction;
  return String(rounded).replace(".", ",");
}

export function formatNumber(value, maxFraction = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("ru-RU", { maximumFractionDigits: maxFraction });
}

export function percent(value) {
  return `${Math.round(Number(value) || 0)}%`;
}

export function formatValue(value, unit = "") {
  const n = Number(value) || 0;
  const text = Number.isInteger(n) ? String(n) : num(n, 1);
  return unit ? `${text} ${pluralUnit(unit, n)}` : text;
}

export function targetText(habit) {
  if (!habit) return "";
  if (habit.type === "boolean") return "Да / нет";
  return formatValue(habit.target_value, habit.unit);
}

export function scheduleText(habit) {
  if (!habit) return "";
  if (habit.schedule === "weekdays") return "По будням";
  if (habit.schedule === "times_per_week") {
    const n = Number(habit.times_per_week) || 3;
    return `${n} ${timesWord(n)} в неделю`;
  }
  return "Каждый день";
}

export function streakText(habit) {
  const value = Number(habit?.current_streak) || 0;
  const unit = habit?.streak_unit === "weeks" ? "нед." : "дн.";
  return `${formatNumber(value)} ${unit}`;
}

export const STATUS_LABELS = {
  done: "Выполнено",
  partial: "Частично",
  skipped: "Пропуск",
  frozen: "Заморозка",
  missed: "Без отметки",
  empty: "Нет данных",
  rest: "Отдых",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || "Нет данных";
}

// ------------------------------------------------------------------ DOM

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

export function on(root, selector, event, handler, options) {
  const listener = (e) => {
    const target = e.target.closest(selector);
    if (target && root.contains(target)) handler(e, target);
  };
  root.addEventListener(event, listener, options);
  return () => root.removeEventListener(event, listener, options);
}

export function debounce(fn, wait = 300) {
  let timer = 0;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

export function groupBy(items, keyFn) {
  const out = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!out.has(key)) out.set(key, []);
    out.get(key).push(item);
  }
  return out;
}

export function sum(items, keyFn = (x) => x) {
  return items.reduce((acc, item) => acc + (Number(keyFn(item)) || 0), 0);
}

// ------------------------------------------------------------------ localStorage

export function storageGet(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function storageSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* приватный режим — не страшно */
  }
}

export function storageRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* noop */
  }
}

// ------------------------------------------------------------------ пересечения

export function dateRange(startISO, endISO) {
  const out = [];
  let cursor = parseISODate(startISO);
  const end = parseISODate(endISO);
  if (Number.isNaN(cursor.getTime()) || Number.isNaN(end.getTime())) return out;
  while (cursor <= end) {
    out.push(toISODate(cursor));
    cursor = addDays(cursor, 1);
  }
  return out;
}

export function sameMonth(iso, key) {
  return monthKey(iso) === key;
}

export function safeTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow";
  } catch {
    return "Europe/Moscow";
  }
}

export function timezoneOptions(current) {
  const zone = current || safeTimezone();
  const list = TIMEZONES.includes(zone) ? TIMEZONES : [zone, ...TIMEZONES];
  return list.map((item) => `<option value="${esc(item)}"${item === zone ? " selected" : ""}>${esc(item)}</option>`).join("");
}
