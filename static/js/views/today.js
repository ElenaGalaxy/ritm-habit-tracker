// Экран «Сегодня»: один тап для boolean, значение для quantity/duration.
import { api } from "../api.js";
import { openHabitForm } from "../habitForm.js";
import { habitIcon, icon } from "../icons.js";
import { openMenu, modal, setButtonBusy, skeleton, sync, toast } from "../ui.js";
import {
  clamp, daysWord, esc, firstName, formatDate, formatNumber, formatValue,
  greeting, percent, pluralRu, scheduleText, streakText, targetText, todayISO,
  weekdayName,
} from "../utils.js";

export async function mount(root, ctx) {
  let data = null;
  let alive = true;
  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      data = await api.get("/today");
      if (!alive) return;
      data.habits = data.habits || [];
      data.summary = computeSummary(data.habits);
      render();
      ctx.setBadge?.("today", (data.unseen_events || []).length);
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Не удалось загрузить день</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <button type="button" class="btn btn-primary mt-3" data-action="retry">Попробовать снова</button>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function computeSummary(habits) {
    const total = habits.length;
    const done = habits.filter((h) => h.today_status === "done").length;
    const partial = habits.filter((h) => h.today_status === "partial").length;
    return {
      total,
      done,
      partial,
      remaining: Math.max(0, total - done),
      percent: total ? Math.round((done / total) * 100) : 0,
      freezes_left: habits.reduce((acc, h) => acc + (Number(h.freezes_left) || 0), 0),
      best_current_streak: habits.reduce((acc, h) => Math.max(acc, Number(h.current_streak) || 0), 0),
    };
  }

  function render() {
    const summary = computeSummary(data.habits);
    data.summary = summary;
    const total = summary.total;
    const done = summary.done;
    const freezes = data.habits.reduce((acc, h) => acc + (Number(h.freezes_left) || 0), 0);
    const best = data.habits.reduce((acc, h) => Math.max(acc, Number(h.current_streak) || 0), 0);
    const hasWeekly = data.habits.some((h) => h.streak_unit === "weeks");
    const streakUnit = hasWeekly ? "нед." : "дн.";

    const circumference = 2 * Math.PI * 50;
    const offset = circumference * (1 - Math.min(1, summary.percent / 100));

    let headline = "Спокойный старт";
    if (!total) headline = "Начнём с одного шага";
    else if (summary.percent >= 100) headline = "Всё отмечено";
    else if (summary.percent >= 50) headline = "Хороший ритм";
    else if (done > 0) headline = "Начало положено";

    const subtitleBits = [];
    if (total) subtitleBits.push(`${done} из ${total} ${pluralRu(total, "привычки", "привычек", "привычек")} отмечено`);
    else subtitleBits.push("Пока нет привычек на сегодня");
    if (summary.remaining && total) subtitleBits.push(`осталось ${summary.remaining}`);
    if (data.next_reminder) subtitleBits.push(`напоминание в ${data.next_reminder}`);

    const unseen = data.unseen_events || [];
    const event = unseen[0];

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">${esc(weekdayName(data.date))}, ${esc(formatDate(data.date, { withYear: true }))}</span>
          <h1 class="display">${esc(greeting())}, <em>${esc(firstName(data.name))}</em></h1>
          <p class="page-sub">${esc(subtitleBits.join(" · "))}</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-primary" data-action="add">
            ${icon("plus")} Новая привычка
          </button>
        </div>
      </div>

      <div class="card today-hero">
        <div class="hero-copy">
          <div class="hero-date">${total ? `${percent(summary.percent)} плана дня` : "Первый день"}</div>
          <h2 class="display">${esc(headline)}</h2>
          <p class="hero-sub">${esc(data.tip || "Один маленький шаг сегодня — уже достаточно.")}</p>
          <div class="hero-meta">
            <span class="pill pill-flame">${icon("flame")} серия ${formatNumber(best)} ${streakUnit}</span>
            <span class="pill pill-freeze">${icon("snow")} ${formatNumber(freezes)} ${pluralRu(freezes, "заморозка", "заморозки", "заморозок")}</span>
            ${data.next_reminder ? `<span class="pill">${icon("clock")} ${esc(data.next_reminder)}</span>` : ""}
            ${data.telegram_connected ? `<span class="pill pill-done">${icon("telegram")} Telegram</span>` : ""}
          </div>
          ${data.goal ? `<div class="hero-goal"><strong>Цель:</strong> ${esc(data.goal)}</div>` : ""}
        </div>
        <div class="hero-ring">
          <div class="ring-wrap">
            <svg width="118" height="118" viewBox="0 0 118 118" aria-hidden="true">
              <circle class="ring-track" cx="59" cy="59" r="50"></circle>
              <circle class="ring-fill" cx="59" cy="59" r="50" stroke-dasharray="${circumference.toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"></circle>
            </svg>
            <div class="ring-center">
              <span class="ring-num">${summary.percent}<span style="font-size:18px">%</span></span>
              <span class="ring-label">дня</span>
            </div>
          </div>
          <span class="ring-caption">${done} из ${total} отмечено</span>
        </div>
      </div>

      ${event ? `
        <div class="tip-card" data-event-banner style="justify-content:space-between;align-items:center">
          <span style="display:flex;gap:11px;align-items:flex-start">${icon("bell")}<span><strong>${esc(event.title)}</strong><br>${esc(event.message)}</span></span>
          <button type="button" class="btn btn-xs btn-soft" data-action="seen">Понятно</button>
        </div>
      ` : ""}

      <div class="summary-strip mt-3">
        <div class="summary-cell"><div class="k">Готово</div><div class="v">${done} <small>из ${total}</small></div></div>
        <div class="summary-cell"><div class="k">Частично</div><div class="v">${summary.partial} <small>${pluralRu(summary.partial, "шаг", "шага", "шагов")}</small></div></div>
        <div class="summary-cell"><div class="k">Заморозки</div><div class="v">${freezes} <small>осталось</small></div></div>
      </div>

      <div class="section-head">
        <h2 class="section-title">На сегодня</h2>
        <button type="button" class="section-link" data-action="add">Добавить</button>
      </div>

      ${total ? `<div class="habit-list">${data.habits.map(habitCard).join("")}</div>` : emptyHTML()}
    `;

    bind();
  }

  function habitCard(habit) {
    const done = habit.today_status === "done";
    const partial = habit.today_status === "partial";
    const frozen = habit.today_status === "frozen";
    const skipped = habit.today_status === "skipped";
    const numeric = habit.type !== "boolean";
    const value = Number(habit.today?.value) || 0;
    const statusClass = done ? " is-done" : partial ? " is-partial" : "";

    return `
      <article class="habit-card${statusClass}" data-habit-id="${habit.id}">
        <span class="habit-icon" style="--icon-color:${esc(habit.color || "#2E685F")}" aria-hidden="true">${habitIcon(habit.icon)}</span>
        <div class="habit-main">
          <div class="habit-title-row">
            <span class="habit-title">${esc(habit.title)}</span>
            ${partial ? `<span class="badge badge-sand">${esc(statusWord("partial"))}</span>` : ""}
            ${frozen ? `<span class="badge badge-blue">${esc(statusWord("frozen"))}</span>` : ""}
            ${skipped ? `<span class="badge badge-muted">${esc(statusWord("skipped"))}</span>` : ""}
          </div>
          <div class="habit-meta">
            <span>${esc(habit.schedule_label || scheduleText(habit))}</span>
            <span class="dot"></span>
            <span>${icon("flame")} ${esc(streakText(habit))}</span>
            <span class="dot"></span>
            <span>${icon("snow")} ${habit.freezes_left}/${habit.freeze_limit ?? 2}</span>
            ${numeric ? `<span class="dot"></span><span>${formatValue(value)} из ${formatValue(habit.target_value, habit.unit)}</span>` : ""}
          </div>
        </div>
        <div class="habit-side">
          ${numeric
            ? `<button type="button" class="habit-value-btn ${done ? "done" : partial ? "partial" : ""}" data-action="value"
                       aria-label="Изменить значение привычки ${esc(habit.title)}">
                 ${formatNumber(value)}<span>/ ${esc(formatValue(habit.target_value, habit.unit))}</span>
               </button>`
            : `<button type="button" class="check-btn${done ? " done" : ""}" data-action="check"
                       aria-pressed="${done}" aria-label="${done ? "Снять отметку" : `Отметить «${esc(habit.title)}»`}">
                 ${icon("check")}
               </button>`}
          <button type="button" class="icon-btn habit-menu-btn" data-action="menu"
                  aria-label="Действия с привычкой ${esc(habit.title)}">${icon("more")}</button>
        </div>
      </article>
    `;
  }

  function emptyHTML() {
    return `
      <div class="empty-state">
        <div class="empty-art">${icon("today")}</div>
        <h3>Пока пусто — и это нормально</h3>
        <p>Добавьте одну маленькую привычку. Больше не нужно: ритм начинается с одного шага.</p>
        <div class="empty-actions">
          <button type="button" class="btn btn-primary" data-action="add">${icon("plus")} Добавить привычку</button>
          <button type="button" class="btn btn-soft" data-action="assistant">${icon("sparkles")} Подобрать с ассистентом</button>
        </div>
      </div>
    `;
  }

  function bind() {
    root.querySelectorAll('[data-action="add"]').forEach((button) => {
      button.addEventListener("click", () => openHabitForm({ onSaved: () => load(false) }));
    });
    root.querySelector('[data-action="assistant"]')?.addEventListener("click", () => ctx.navigate("assistant"));
    root.querySelector('[data-action="seen"]')?.addEventListener("click", markEventsSeen);

    root.querySelectorAll('[data-action="check"]').forEach((button) => {
      button.addEventListener("click", () => {
        const card = button.closest("[data-habit-id]");
        const habit = data.habits.find((item) => String(item.id) === card?.dataset.habitId);
        if (habit) toggleBoolean(habit);
      });
    });
    root.querySelectorAll('[data-action="value"]').forEach((button) => {
      button.addEventListener("click", () => {
        const card = button.closest("[data-habit-id]");
        const habit = data.habits.find((item) => String(item.id) === card?.dataset.habitId);
        if (habit) openValueEditor(habit);
      });
    });
    root.querySelectorAll('[data-action="menu"]').forEach((button) => {
      button.addEventListener("click", () => {
        const card = button.closest("[data-habit-id]");
        const habit = data.habits.find((item) => String(item.id) === card?.dataset.habitId);
        if (habit) openMenu(button, habitMenu(habit));
      });
    });
  }

  function statusWord(status) {
    return { partial: "Частично", frozen: "Пауза", skipped: "Пропуск" }[status] || "";
  }

  async function markEventsSeen() {
    const events = data.unseen_events || [];
    try {
      for (const event of events) {
        await api.post("/events/seen", { id: event.id });
      }
      data.unseen_events = [];
      ctx.setBadge?.("today", 0);
      root.querySelector("[data-event-banner]")?.remove();
      sync("Отмечено");
    } catch (error) {
      toast(error.message || "Не удалось скрыть событие.", { type: "error" });
    }
  }

  function applyHabit(updated) {
    if (!updated) return;
    const index = data.habits.findIndex((item) => item.id === updated.id);
    if (index >= 0) data.habits[index] = updated;
    else data.habits.push(updated);
    data.summary = computeSummary(data.habits);
    const scroll = window.scrollY;
    render();
    window.scrollTo({ top: scroll });
  }

  function showEvents(events) {
    if (!events || !events.length) return;
    const event = events[0];
    toast(`${event.title}: ${event.message}`, { type: "info", duration: 6000 });
    ctx.setBadge?.("today", (Number(data.unseen_events?.length) || 0) + events.length);
  }

  async function saveLog(habit, payload, { optimisticStatus, optimisticValue } = {}) {
    const snapshot = { ...habit, today: habit.today ? { ...habit.today } : null };
    if (optimisticStatus !== undefined) habit.today_status = optimisticStatus;
    if (optimisticValue !== undefined) {
      habit.today = { ...(habit.today || {}), value: optimisticValue, status: optimisticStatus };
    }
    applyHabit(habit);
    try {
      const response = await api.post("/logs", {
        habit_id: habit.id,
        date: data.date,
        value: payload.value,
        status: payload.status ?? null,
        note: payload.note || "",
      });
      if (response?.habit) applyHabit(response.habit);
      else await load(false);
      if (response?.removed) sync("Отметка снята");
      else sync("Сохранено");
      showEvents(response?.events);
      return response;
    } catch (error) {
      const index = data.habits.findIndex((item) => item.id === snapshot.id);
      if (index >= 0) data.habits[index] = snapshot;
      applyHabit(data.habits[index] || snapshot);
      toast(error.message || "Не удалось сохранить отметку.", { type: "error" });
      throw error;
    }
  }

  async function toggleBoolean(habit) {
    if (habit.today_status === "done") {
      try {
        const response = await api.delete(`/logs?habit_id=${habit.id}&date=${encodeURIComponent(data.date)}`);
        if (response?.habit) applyHabit(response.habit);
        sync("Отметка снята");
        showEvents(response?.events);
      } catch (error) {
        toast(error.message || "Не удалось снять отметку.", { type: "error" });
      }
      return;
    }
    await saveLog(habit,
      { value: Number(habit.target_value) || 1, status: "done" },
      { optimisticStatus: "done", optimisticValue: Number(habit.target_value) || 1 },
    ).catch(() => {});
  }

  function openValueEditor(habit) {
    const target = Math.max(0.1, Number(habit.target_value) || 1);
    let value = clamp(Number(habit.today?.value) || 0, 0, target);
    const step = target >= 100 ? Math.max(1, Math.round(target / 100)) : target >= 20 ? 5 : 1;

    const dialog = modal({
      title: habit.title,
      subtitle: `Цель — ${targetText(habit)}. Частичное выполнение тоже считается шагом.`,
      body: `
        <div class="stack">
          <div class="row between">
            <span class="small muted">Сколько получилось</span>
            <span class="h3 num" data-role="value-text">${formatValue(value, habit.unit)}</span>
          </div>
          <input type="range" class="range" data-role="range" min="0" max="${target}" step="${step}" value="${value}"
                 aria-label="Значение привычки">
          <div class="row" style="justify-content:center">
            <div class="stepper">
              <button type="button" data-action="minus" aria-label="Уменьшить">${icon("minus")}</button>
              <input type="number" data-role="number" min="0" max="${target}" step="any" value="${value}" aria-label="Точное значение">
              <button type="button" data-action="plus" aria-label="Увеличить">${icon("plus")}</button>
            </div>
          </div>
          <div class="row wrap" style="justify-content:center;gap:8px">
            <button type="button" class="btn btn-soft btn-sm" data-action="zero">Сбросить</button>
            <button type="button" class="btn btn-soft btn-sm" data-action="target">Выполнено: ${esc(formatValue(target, habit.unit))}</button>
          </div>
          <p class="hint">Можно сохранить меньше цели — это будет «частично», серия не обнулится.</p>
        </div>
        <p class="error-text" data-role="error" hidden></p>
      `,
      footer: `
        <button type="button" class="btn btn-ghost" data-role="cancel">Отмена</button>
        <button type="button" class="btn btn-primary" data-role="save">Сохранить</button>
      `,
    });

    const range = dialog.body.querySelector('[data-role="range"]');
    const number = dialog.body.querySelector('[data-role="number"]');
    const label = dialog.body.querySelector('[data-role="value-text"]');
    const saveButton = dialog.foot.querySelector('[data-role="save"]');
    const errorBox = dialog.body.querySelector('[data-role="error"]');

    function setValue(next, { silent = false } = {}) {
      value = clamp(next, 0, target);
      range.value = String(value);
      number.value = String(value);
      label.textContent = formatValue(value, habit.unit);
      range.style.setProperty("--pct", `${(value / target) * 100}%`);
      if (!silent) errorBox.hidden = true;
    }

    setValue(value, { silent: true });
    range.addEventListener("input", () => setValue(Number(range.value)));
    number.addEventListener("input", () => {
      const parsed = Number(String(number.value).replace(",", "."));
      if (Number.isFinite(parsed)) setValue(parsed, { silent: true });
    });
    dialog.body.querySelector('[data-action="minus"]').addEventListener("click", () => setValue(value - step));
    dialog.body.querySelector('[data-action="plus"]').addEventListener("click", () => setValue(value + step));
    dialog.body.querySelector('[data-action="zero"]').addEventListener("click", () => setValue(0));
    dialog.body.querySelector('[data-action="target"]').addEventListener("click", () => setValue(target));
    dialog.foot.querySelector('[data-role="cancel"]').addEventListener("click", () => dialog.close());

    saveButton.addEventListener("click", async () => {
      setButtonBusy(saveButton, true, "Сохраняем…");
      try {
        await saveLog(habit, { value, status: null }, {
          optimisticStatus: value >= target ? "done" : value > 0 ? "partial" : "empty",
          optimisticValue: value,
        });
        dialog.close();
        if (value <= 0) toast("Отметка снята", { type: "info" });
        else if (value >= target) toast("Выполнено — отличный шаг.", { type: "success" });
        else toast("Сохранено как частичное выполнение. Серия сохранится.", { type: "info" });
      } catch {
        setButtonBusy(saveButton, false);
      }
    });
  }

  function habitMenu(habit) {
    const frozen = habit.today_status === "frozen";
    const marked = ["done", "partial", "skipped", "frozen"].includes(habit.today_status);
    const items = [];
    items.push({
      label: "Изменить",
      icon: "edit",
      onClick: () => openHabitForm({ habit, onSaved: () => load(false) }),
    });
    if (frozen) {
      items.push({
        label: "Снять заморозку",
        icon: "play",
        onClick: () => unfreeze(habit),
      });
    } else {
      items.push({
        label: habit.freezes_left > 0 ? "Заморозка на сегодня" : "Заморозки на месяц закончились",
        icon: "snow",
        disabled: habit.freezes_left <= 0,
        onClick: () => freeze(habit),
      });
    }
    items.push({
      label: "Пропустить сегодня",
      icon: "pause",
      disabled: habit.today_status === "skipped",
      onClick: () => saveLog(habit, { value: 0, status: "skipped" },
        { optimisticStatus: "skipped", optimisticValue: 0 }).catch(() => {}),
    });
    if (marked) {
      items.push({
        label: "Снять отметку",
        icon: "undo",
        onClick: () => removeLog(habit),
      });
    }
    items.push({ sep: true });
    items.push({
      label: "В архив",
      icon: "archive",
      onClick: () => archive(habit),
    });
    items.push({
      label: "Удалить",
      icon: "trash",
      danger: true,
      onClick: () => deleteHabit(habit),
    });
    return items;
  }

  async function freeze(habit) {
    try {
      const response = await api.post("/logs", {
        habit_id: habit.id, date: data.date, value: 0, status: "frozen",
      });
      if (response?.habit) applyHabit(response.habit);
      sync("Заморозка поставлена");
      toast("Пауза на сегодня. Серия сохранится.", { type: "info" });
      showEvents(response?.events);
    } catch (error) {
      toast(error.message || "Не удалось поставить заморозку.", { type: "error" });
    }
  }

  async function unfreeze(habit) {
    try {
      const response = await api.delete(`/logs/freeze?habit_id=${habit.id}&date=${encodeURIComponent(data.date)}`);
      if (response?.habit) applyHabit(response.habit);
      sync("Заморозка снята");
      toast("Заморозка снята", { type: "info" });
    } catch (error) {
      toast(error.message || "Не удалось снять заморозку.", { type: "error" });
    }
  }

  async function removeLog(habit) {
    try {
      const response = await api.delete(`/logs?habit_id=${habit.id}&date=${encodeURIComponent(data.date)}`);
      if (response?.habit) applyHabit(response.habit);
      sync("Отметка снята");
    } catch (error) {
      toast(error.message || "Не удалось снять отметку.", { type: "error" });
    }
  }

  async function archive(habit) {
    try {
      await api.delete(`/habits/${habit.id}?mode=archive`);
      data.habits = data.habits.filter((item) => item.id !== habit.id);
      data.summary = computeSummary(data.habits);
      render();
      toast("Привычка в архиве. Вернуть можно в разделе «Привычки».", { type: "info" });
    } catch (error) {
      toast(error.message || "Не удалось отправить в архив.", { type: "error" });
    }
  }

  async function deleteHabit(habit) {
    const index = data.habits.findIndex((item) => item.id === habit.id);
    if (index < 0) return;
    data.habits.splice(index, 1);
    data.summary = computeSummary(data.habits);
    render();
    try {
      await api.delete(`/habits/${habit.id}`);
      toast(`«${habit.title}» удалена. Вернуть можно в течение 10 секунд.`, {
        type: "info",
        duration: 10000,
        action: {
          label: "Вернуть",
          onClick: async () => {
            try {
              await api.post(`/habits/${habit.id}/restore`);
              toast("Привычка возвращена", { type: "success" });
              await load(false);
            } catch (error) {
              toast(error.message || "Не удалось вернуть привычку.", { type: "error" });
            }
          },
        },
      });
    } catch (error) {
      data.habits.splice(index, 0, habit);
      data.summary = computeSummary(data.habits);
      render();
      toast(error.message || "Не удалось удалить привычку.", { type: "error" });
    }
  }

  await load(true);
  return () => {
    alive = false;
    ctx.setBadge?.("today", undefined);
  };
}
