// Календарь: месяц, годовая тепловая карта и редактор прошедшего дня.
import { api } from "../api.js";
import { heatmapHTML, heatmapLegend } from "../heatmap.js";
import { habitIcon, icon } from "../icons.js";
import { modal, skeleton, sync, toast } from "../ui.js";
import {
  WEEKDAYS_MIN, clamp, esc, formatDate, formatValue, monthKey, monthTitleFromKey,
  parseISODate, pluralRu, shiftMonth, todayISO, weekdayName,
} from "../utils.js";

const STATUS_META = {
  done: { label: "Выполнено", cls: "badge-moss" },
  partial: { label: "Частично", cls: "badge-sand" },
  skipped: { label: "Пропуск", cls: "badge-muted" },
  frozen: { label: "Пауза", cls: "badge-blue" },
  missed: { label: "Без отметки", cls: "badge-muted" },
  empty: { label: "Нет отметки", cls: "badge-muted" },
  rest: { label: "Отдых", cls: "badge-muted" },
};

const LEGEND = [
  { cls: "done", label: "Выполнено" },
  { cls: "partial", label: "Частично" },
  { cls: "frozen", label: "Пауза" },
  { cls: "skipped", label: "Пропуск" },
  { cls: "missed", label: "Без отметки" },
];

export async function mount(root, ctx) {
  const today = todayISO();
  let mode = "month";
  let month = monthKey(today);
  let year = parseISODate(today).getFullYear();
  let data = null;
  let alive = true;
  let pendingDate = ctx.params?.date && /^\d{4}-\d{2}-\d{2}$/.test(ctx.params.date)
    ? ctx.params.date
    : null;

  if (pendingDate) {
    mode = "month";
    month = pendingDate.slice(0, 7);
    year = Number(pendingDate.slice(0, 4));
  }

  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      const params = mode === "month" ? { month } : { year };
      data = await api.get("/calendar", params);
      if (!alive) return;
      render();
      if (pendingDate && mode === "month") {
        const date = pendingDate;
        pendingDate = null;
        const exists = (data.days || []).some((day) => day.date === date);
        if (exists) openDay(date);
      }
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Не удалось загрузить календарь</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <button type="button" class="btn btn-primary mt-3" data-action="retry">Попробовать снова</button>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function render() {
    const title = mode === "month" ? monthTitleFromKey(month) : `${data.year}`;
    const summary = data.summary || {};

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">Календарь</span>
          <h1 class="display">Ритм <em>день за днём</em></h1>
          <p class="page-sub">Отмечайте прошедшие дни спокойно: пропуски остаются серыми, а пауза сохраняет серию.</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-soft" data-action="assistant">${icon("sparkles")} AI-обзор</button>
        </div>
      </div>

      <div class="cal-toolbar">
        <div class="segmented" role="tablist" aria-label="Режим календаря">
          <button type="button" class="seg-btn${mode === "month" ? " active" : ""}" data-mode="month"
                  role="tab" aria-selected="${mode === "month"}">Месяц</button>
          <button type="button" class="seg-btn${mode === "year" ? " active" : ""}" data-mode="year"
                  role="tab" aria-selected="${mode === "year"}">Год</button>
        </div>
        <div class="cal-month">${esc(title)}</div>
        <div class="spacer"></div>
        <div class="cal-nav">
          <button type="button" class="icon-btn sm bordered" data-nav="-1" aria-label="Предыдущий период">${icon("chevronLeft")}</button>
          <button type="button" class="btn btn-soft btn-sm" data-nav="0">Сегодня</button>
          <button type="button" class="icon-btn sm bordered" data-nav="1" aria-label="Следующий период">${icon("chevronRight")}</button>
        </div>
      </div>

      ${mode === "month" ? monthHTML(summary) : yearHTML(summary)}
    `;

    bind();
  }

  function monthHTML(summary) {
    const firstWeekday = Number(data.first_weekday) || 0;
    const cells = [];
    for (let i = 0; i < firstWeekday; i += 1) {
      cells.push('<span class="cal-cell blank" aria-hidden="true"></span>');
    }
    for (const day of data.days || []) {
      cells.push(dayCell(day));
    }
    const done = Number(summary.done) || 0;
    const planned = Number(summary.planned) || 0;
    const percent = planned ? Math.round((done / planned) * 100) : 0;

    return `
      <div class="card cal-card">
        <div class="row between mb-2" style="gap:12px;flex-wrap:wrap">
          <span class="pill">${icon("checkCircle")} ${done} из ${planned} ${pluralRu(planned, "отметки", "отметок", "отметок")}</span>
          <span class="pill">${icon("target")} ${percent}% месяца</span>
        </div>
        <div class="cal-weekdays" aria-hidden="true">
          ${WEEKDAYS_MIN.map((name) => `<span>${name}</span>`).join("")}
        </div>
        <div class="cal-grid" role="grid" aria-label="Календарь на месяц">
          ${cells.join("")}
        </div>
        <div class="cal-legend">
          ${LEGEND.map((item) => `<span><i class="legend-dot cal-dot ${item.cls}" style="border-radius:3px"></i>${esc(item.label)}</span>`).join("")}
          <span class="faint">Нажмите на день, чтобы изменить отметки</span>
        </div>
      </div>
    `;
  }

  function dayCell(day) {
    const status = day.status || "empty";
    const classes = ["cal-cell"];
    if (status && status !== "empty") classes.push(`is-${status}`);
    if (day.future) classes.push("future");
    if (day.date === today) classes.push("today");
    const dots = (day.entries || [])
      .filter((entry) => entry.status !== "empty")
      .slice(0, 8)
      .map((entry) => `<span class="cal-dot ${esc(entry.status || "missed")}"></span>`)
      .join("");
    const count = Number(day.total) ? `<span class="cal-count">${day.done}/${day.total}</span>` : "";
    const todayDot = day.date === today ? '<span class="cal-today-badge" aria-hidden="true"></span>' : "";
    const label = `${formatDate(day.date, { withYear: true })}${day.total ? `, выполнено ${day.done} из ${day.total}` : ", нет запланированных привычек"}`;

    return `
      <button type="button" class="${classes.join(" ")}" data-date="${esc(day.date)}"
              aria-label="${esc(label)}">
        <span class="cal-day">${day.day}</span>
        <span class="cal-dots">${dots}</span>
        ${count}
        ${todayDot}
      </button>
    `;
  }

  function yearHTML(summary) {
    const done = Number(summary.done) || 0;
    const activeDays = Number(summary.active_days) || 0;
    const totalDays = Number(summary.days) || 0;
    return `
      <div class="card card-pad">
        <div class="row between mb-2" style="gap:10px;flex-wrap:wrap">
          <span class="pill">${icon("checkCircle")} ${done} ${pluralRu(done, "отметка", "отметки", "отметок")} за год</span>
          <span class="pill">${icon("calendar")} ${activeDays} ${pluralRu(activeDays, "активный день", "активных дня", "активных дней")}</span>
        </div>
        <div class="heatmap-scroll">
          ${heatmapHTML(data.days || [], { clickable: true })}
        </div>
        ${heatmapLegend()}
        <p class="hint mt-2">Каждая клетка — день. Нажмите, чтобы открыть отметки. Всего дней с данными: ${totalDays}.</p>
      </div>

      <div class="summary-strip mt-3">
        <div class="summary-cell"><div class="k">Отметок за год</div><div class="v">${done}</div></div>
        <div class="summary-cell"><div class="k">Активных дней</div><div class="v">${activeDays}</div></div>
        <div class="summary-cell"><div class="k">Среднее</div><div class="v">${activeDays ? Math.round(done / activeDays) : 0} <small>в день</small></div></div>
      </div>
    `;
  }

  function bind() {
    root.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.mode === mode) return;
        mode = button.dataset.mode;
        load(false);
      });
    });

    root.querySelectorAll("[data-nav]").forEach((button) => {
      button.addEventListener("click", () => {
        const direction = Number(button.dataset.nav);
        if (!direction) {
          month = monthKey(today);
          year = parseISODate(today).getFullYear();
        } else if (mode === "month") {
          month = shiftMonth(month, direction);
        } else {
          year = clamp(year + direction, 2000, 2100);
        }
        load(false);
      });
    });

    root.querySelector('[data-action="assistant"]')?.addEventListener("click", () => ctx.navigate("assistant"));
    root.querySelectorAll("[data-date]").forEach((element) => {
      element.addEventListener("click", () => openDay(element.dataset.date));
    });
  }

  async function openDay(date) {
    let day;
    try {
      day = await api.get("/calendar/day", { date });
    } catch (error) {
      toast(error.message || "Не удалось открыть день.", { type: "error" });
      return;
    }
    if (day.future) {
      toast("Этот день ещё не наступил — вернёмся к нему вовремя.", { type: "info" });
      return;
    }
    if (!day.editable) {
      toast("Этот день нельзя редактировать.", { type: "info" });
      return;
    }

    let dirty = false;
    const editor = document.createElement("div");
    editor.className = "day-editor";
    editor.innerHTML = day.entries?.length
      ? day.entries.map((entry) => entryRow(entry, day)).join("")
      : `<p class="muted small" style="padding:8px 0">Для этой даты пока нет привычек.</p>`;

    const dialog = modal({
      title: `${weekdayName(date)}, ${formatDate(date, { withYear: true })}`,
      subtitle: "Можно отметить или изменить прошедший день. Изменения сохраняются сразу.",
      wide: true,
      body: "",
      footer: `
        <span class="tiny faint grow">Пропуск — не провал. Серия сохраняется при паузе.</span>
        <button type="button" class="btn btn-primary" data-role="done">Готово</button>
      `,
      onClose: () => {
        if (dirty) load(false);
      },
    });
    dialog.body.append(editor);
    dialog.foot.querySelector('[data-role="done"]').addEventListener("click", () => dialog.close());

    async function saveEntry(entry, payload) {
      try {
        const response = await api.post("/logs", {
          habit_id: entry.habit_id,
          date,
          value: payload.value ?? 0,
          status: payload.status ?? null,
          note: payload.note ?? entry.note ?? "",
        });
        dirty = true;
        if (response?.removed) {
          entry.status = "empty";
          entry.value = 0;
        } else if (response?.log) {
          entry.status = response.log.status || "done";
          entry.value = Number(response.log.value) || 0;
          entry.note = response.log.note || "";
        }
        if (response?.freezes_left !== undefined) {
          day.freezes = day.freezes || {};
          day.freezes[entry.habit_id] = {
            ...(day.freezes[entry.habit_id] || {}),
            left: Number(response.freezes_left) || 0,
          };
        }
        refreshRow(entry, day);
        sync("Сохранено");
        if (response?.events?.length) {
          const event = response.events[0];
          toast(`${event.title}: ${event.message}`, { type: "info", duration: 6000 });
        }
      } catch (error) {
        toast(error.message || "Не удалось сохранить отметку.", { type: "error" });
      }
    }

    async function removeEntry(entry) {
      try {
        const response = await api.delete(`/logs?habit_id=${entry.habit_id}&date=${encodeURIComponent(date)}`);
        dirty = true;
        entry.status = "empty";
        entry.value = 0;
        entry.note = "";
        if (response?.freezes_left !== undefined) {
          day.freezes = day.freezes || {};
          day.freezes[entry.habit_id] = {
            ...(day.freezes[entry.habit_id] || {}),
            left: Number(response.freezes_left) || 0,
          };
        }
        refreshRow(entry, day);
        sync("Отметка снята");
      } catch (error) {
        toast(error.message || "Не удалось снять отметку.", { type: "error" });
      }
    }

    async function unfreeze(entry) {
      try {
        const response = await api.delete(`/logs/freeze?habit_id=${entry.habit_id}&date=${encodeURIComponent(date)}`);
        dirty = true;
        entry.status = "empty";
        entry.value = 0;
        if (response?.freezes_left !== undefined) {
          day.freezes[entry.habit_id] = {
            ...(day.freezes[entry.habit_id] || {}),
            left: Number(response.freezes_left) || 0,
          };
        }
        refreshRow(entry, day);
        sync("Заморозка снята");
      } catch (error) {
        toast(error.message || "Не удалось снять заморозку.", { type: "error" });
      }
    }

    editor.addEventListener("click", async (event) => {
      const actionButton = event.target.closest("[data-action]");
      const row = event.target.closest("[data-habit-id]");
      if (!actionButton || !row) return;
      const entry = (day.entries || []).find((item) => String(item.habit_id) === row.dataset.habitId);
      if (!entry) return;
      const action = actionButton.dataset.action;

      if (action === "step") {
        const input = row.querySelector('[data-role="value"]');
        const step = Number(actionButton.dataset.step) || 1;
        const target = Math.max(0.1, Number(entry.target_value) || 1);
        const next = clamp((Number(input.value) || 0) + step, 0, target);
        input.value = String(next);
        return;
      }
      if (action === "mark-done") {
        await saveEntry(entry, {
          value: entry.type === "boolean" ? 1 : Number(entry.target_value) || 1,
          status: "done",
        });
        return;
      }
      if (action === "mark-skip") {
        await saveEntry(entry, { value: 0, status: "skipped" });
        return;
      }
      if (action === "mark-freeze") {
        if (entry.status === "frozen") {
          await unfreeze(entry);
          return;
        }
        const freeze = day.freezes?.[entry.habit_id] || {};
        if (Number(freeze.left) <= 0) {
          toast("Заморозки на этот месяц закончились. Пропуск тоже нормален.", { type: "info" });
          return;
        }
        await saveEntry(entry, { value: 0, status: "frozen" });
        return;
      }
      if (action === "save-value") {
        const input = row.querySelector('[data-role="value"]');
        const value = Math.max(0, Number(String(input.value).replace(",", ".")) || 0);
        if (value <= 0) {
          await removeEntry(entry);
          return;
        }
        await saveEntry(entry, { value, status: null, note: entry.note || "" });
        return;
      }
      if (action === "clear") {
        await removeEntry(entry);
      }
    });

    function refreshRow(entry) {
      const row = editor.querySelector(`[data-habit-id="${entry.habit_id}"]`);
      if (!row) return;
      const wrapper = document.createElement("div");
      wrapper.innerHTML = entryRow(entry, day);
      row.replaceWith(wrapper.firstElementChild);
    }

    editor.addEventListener("change", async (event) => {
      const input = event.target.closest('[data-role="note"]');
      const row = event.target.closest("[data-habit-id]");
      if (!input || !row) return;
      const entry = (day.entries || []).find((item) => String(item.habit_id) === row.dataset.habitId);
      if (!entry) return;
      const note = input.value.trim();
      if (["done", "partial", "skipped", "frozen"].includes(entry.status)) {
        await saveEntry(entry, { value: entry.value, status: entry.status, note });
      } else if (note) {
        toast("Сначала отметьте привычку — заметку можно добавить к отметке.", { type: "info" });
      }
    });
  }

  function entryRow(entry, day) {
    const meta = STATUS_META[entry.status] || STATUS_META.empty;
    const freeze = day.freezes?.[entry.habit_id] || {};
    const numeric = entry.type !== "boolean";
    const target = Math.max(0.1, Number(entry.target_value) || 1);
    const step = target >= 100 ? Math.max(1, Math.round(target / 100)) : target >= 20 ? 5 : 1;
    const value = clamp(Number(entry.value) || 0, 0, target);
    const freezeLabel = entry.status === "frozen"
      ? "Снять паузу"
      : Number(freeze.left) > 0 ? "Пауза" : "Паузы закончились";

    return `
      <div class="day-habit" data-habit-id="${entry.habit_id}">
        <div class="day-habit-head">
          <span class="habit-icon" style="--icon-color:${esc(entry.color || "#2E685F")}" aria-hidden="true">${habitIcon(entry.icon)}</span>
          <div class="grow">
            <div class="day-habit-title">${esc(entry.title)}</div>
            <div class="day-habit-target">
              ${esc(entry.schedule_label || "")}${entry.type === "boolean" ? "" : ` · цель ${esc(formatValue(entry.target_value, entry.unit))}`}
            </div>
          </div>
          <span class="badge ${meta.cls}" data-role="status">${esc(meta.label)}</span>
        </div>
        <div class="day-habit-controls">
          ${numeric ? `
            <div class="stepper">
              <button type="button" data-action="step" data-step="-${step}" aria-label="Уменьшить">${icon("minus")}</button>
              <input type="number" data-role="value" min="0" max="${target}" step="any" value="${value}"
                     aria-label="Значение привычки ${esc(entry.title)}">
              <button type="button" data-action="step" data-step="${step}" aria-label="Увеличить">${icon("plus")}</button>
            </div>
            <button type="button" class="btn btn-xs btn-soft" data-action="save-value">Сохранить</button>
          ` : ""}
          <div class="status-chips">
            <button type="button" class="status-chip${entry.status === "done" ? " active" : ""}" data-status="done"
                    data-action="mark-done">${numeric ? "Цель" : "Выполнено"}</button>
            <button type="button" class="status-chip${entry.status === "skipped" ? " active" : ""}" data-status="skipped"
                    data-action="mark-skip">Пропуск</button>
            <button type="button" class="status-chip${entry.status === "frozen" ? " active" : ""}" data-status="frozen"
                    data-action="mark-freeze"${Number(freeze.left) <= 0 && entry.status !== "frozen" ? " disabled" : ""}>${esc(freezeLabel)}</button>
            ${entry.status && entry.status !== "empty" ? `<button type="button" class="status-chip" data-action="clear">Снять</button>` : ""}
          </div>
          <span class="tiny faint">${icon("snow")} ${Number(freeze.used) || 0}/${Number(freeze.limit) || 2}</span>
        </div>
        <div class="day-note-row">
          <input class="input" data-role="note" maxlength="500" value="${esc(entry.note || "")}"
                 placeholder="Заметка к отметке (необязательно)" aria-label="Заметка для ${esc(entry.title)}">
        </div>
      </div>
    `;
  }

  await load(true);
  return () => {
    alive = false;
  };
}
