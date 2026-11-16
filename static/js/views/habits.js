// Управление привычками: фильтры, пауза, архив, удаление и восстановление.
import { api } from "../api.js";
import { openHabitForm } from "../habitForm.js";
import { habitIcon, icon } from "../icons.js";
import { store } from "../store.js";
import { openMenu, skeleton, toast } from "../ui.js";
import {
  clamp, esc, formatNumber, percent, pluralRu, scheduleText, streakText, targetText,
} from "../utils.js";

const FILTERS = [
  { id: "all", label: "Все" },
  { id: "active", label: "Активные" },
  { id: "paused", label: "На паузе" },
  { id: "completed", label: "Завершённые" },
  { id: "archived", label: "Архив" },
];

const STATUS_BADGES = {
  paused: { label: "Пауза", cls: "badge-blue" },
  archived: { label: "В архиве", cls: "badge-muted" },
  completed: { label: "Завершена", cls: "badge-moss" },
};

export async function mount(root, ctx) {
  let data = null;
  let filter = "all";
  let alive = true;
  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      const [habitsData, templatesResult] = await Promise.all([
        api.get("/habits", { status: "all" }),
        store.loadTemplates().then((templates) => ({ ok: true, templates })).catch(() => ({ ok: false, templates: [] })),
      ]);
      if (!alive) return;
      data = habitsData;
      data.habits = data.habits || [];
      data.templates = templatesResult.templates || [];
      render();
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Не удалось загрузить привычки</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <button class="btn btn-primary mt-3" type="button" data-action="retry">Попробовать снова</button>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function counts() {
    const habits = data?.habits || [];
    return {
      all: habits.length,
      active: habits.filter((h) => h.status === "active").length,
      paused: habits.filter((h) => h.status === "paused").length,
      completed: habits.filter((h) => h.status === "completed").length,
      archived: habits.filter((h) => h.status === "archived").length,
    };
  }

  function visibleHabits() {
    const habits = data?.habits || [];
    if (filter === "all") return habits;
    return habits.filter((habit) => habit.status === filter);
  }

  function render() {
    const countsMap = counts();
    const activeCount = Number(data?.active_count) || countsMap.active;
    const limit = Number(data?.active_limit) || 30;
    const list = visibleHabits();

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">Привычки</span>
          <h1 class="display">Ваш <em>набор</em></h1>
          <p class="page-sub">${activeCount} из ${limit} активных. Лимит MVP — ${limit}; пауза освобождает место.</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-primary" data-action="add">${icon("plus")} Новая привычка</button>
        </div>
      </div>

      <div class="row wrap between mb-2" style="gap:10px">
        <div class="chips" role="tablist" aria-label="Фильтр привычек">
          ${FILTERS.map((item) => `
            <button type="button" class="chip${filter === item.id ? " active" : ""}" data-filter="${item.id}"
                    role="tab" aria-selected="${filter === item.id}">
              ${esc(item.label)} <span class="faint" style="margin-left:3px">${countsMap[item.id]}</span>
            </button>
          `).join("")}
        </div>
        <span class="pill">${icon("target")} ${activeCount}/${limit}</span>
      </div>

      ${data.templates.length ? `
        <div class="card card-tight mb-3">
          <div class="row between mb-2">
            <span class="h3">Быстрый старт</span>
            <span class="tiny faint">шаблоны можно изменить</span>
          </div>
          <div class="chips">
            ${data.templates.map((template, index) => `
              <button type="button" class="chip" data-template="${index}" title="Создать по шаблону">
                ${habitIcon(template.icon)} ${esc(template.title)}
              </button>
            `).join("")}
          </div>
        </div>
      ` : ""}

      ${list.length ? `<div class="habit-list">${list.map(habitCard).join("")}</div>` : emptyHTML()}
    `;
    bind();
  }

  function habitCard(habit) {
    const badge = STATUS_BADGES[habit.status];
    const week = clamp(Number(habit.week_percent) || 0, 0, 100);
    const paused = habit.status !== "active";

    return `
      <article class="habit-card${paused ? " is-paused" : ""}" data-habit-id="${habit.id}" style="${paused ? "opacity:.86" : ""}">
        <span class="habit-icon" style="--icon-color:${esc(habit.color || "#2E685F")}" aria-hidden="true">${habitIcon(habit.icon)}</span>
        <div class="habit-main">
          <div class="habit-title-row">
            <span class="habit-title">${esc(habit.title)}</span>
            ${badge ? `<span class="badge ${badge.cls}">${esc(badge.label)}</span>` : ""}
          </div>
          <div class="habit-meta">
            <span>${esc(habit.schedule_label || scheduleText(habit))}</span>
            <span class="dot"></span>
            <span>${esc(targetText(habit))}</span>
            <span class="dot"></span>
            <span>${icon("flame")} ${esc(streakText(habit))}</span>
            <span class="dot"></span>
            <span>неделя ${percent(week)}</span>
          </div>
          ${habit.description ? `<p class="tiny muted mt-1" style="max-width:60ch">${esc(habit.description)}</p>` : ""}
          <div class="progress-line mt-1" aria-hidden="true"><i style="width:${week}%;background:${esc(habit.color || "#4F7D70")}"></i></div>
        </div>
        <div class="habit-side">
          <button type="button" class="icon-btn sm bordered" data-action="edit"
                  aria-label="Изменить привычку ${esc(habit.title)}">${icon("edit")}</button>
          <button type="button" class="icon-btn habit-menu-btn" data-action="menu"
                  aria-label="Действия с привычкой ${esc(habit.title)}">${icon("more")}</button>
        </div>
      </article>
    `;
  }

  function emptyHTML() {
    if (filter !== "all") {
      return `
        <div class="empty-state">
          <div class="empty-art">${icon("filter")}</div>
          <h3>В этом фильтре пусто</h3>
          <p>Выберите другой статус или добавьте привычку — она появится здесь.</p>
          <div class="empty-actions">
            <button type="button" class="btn btn-soft" data-action="reset-filter">Показать все</button>
            <button type="button" class="btn btn-primary" data-action="add">${icon("plus")} Добавить</button>
          </div>
        </div>
      `;
    }
    return `
      <div class="empty-state">
        <div class="empty-art">${icon("habits")}</div>
        <h3>Пока нет привычек</h3>
        <p>Начните с одной. Можно выбрать шаблон выше или описать свою привычку — это займёт меньше минуты.</p>
        <div class="empty-actions">
          <button type="button" class="btn btn-primary" data-action="add">${icon("plus")} Первая привычка</button>
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
    root.querySelector('[data-action="reset-filter"]')?.addEventListener("click", () => {
      filter = "all";
      render();
    });
    root.querySelectorAll("[data-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        filter = button.dataset.filter;
        render();
      });
    });
    root.querySelectorAll("[data-template]").forEach((button) => {
      button.addEventListener("click", () => {
        const template = data.templates[Number(button.dataset.template)];
        if (template) openHabitForm({ template, onSaved: () => load(false) });
      });
    });
    root.querySelectorAll('[data-action="edit"]').forEach((button) => {
      button.addEventListener("click", () => {
        const habit = habitFrom(button);
        if (habit) openHabitForm({ habit, onSaved: () => load(false) });
      });
    });
    root.querySelectorAll('[data-action="menu"]').forEach((button) => {
      button.addEventListener("click", () => {
        const habit = habitFrom(button);
        if (habit) openMenu(button, habitMenu(habit));
      });
    });
  }

  function habitFrom(element) {
    const card = element.closest("[data-habit-id]");
    return (data?.habits || []).find((item) => String(item.id) === card?.dataset.habitId);
  }

  function habitMenu(habit) {
    const items = [{
      label: "Изменить",
      icon: "edit",
      onClick: () => openHabitForm({ habit, onSaved: () => load(false) }),
    }];
    if (habit.status === "active") {
      items.push({
        label: "Поставить на паузу",
        icon: "pause",
        onClick: () => updateStatus(habit, "paused", "Привычка на паузе. Место в лимите освободилось."),
      });
    } else if (habit.status === "paused" || habit.status === "completed") {
      items.push({
        label: "Вернуть в работу",
        icon: "play",
        onClick: () => updateStatus(habit, "active", "Привычка снова активна."),
      });
    }
    if (habit.status === "archived") {
      items.push({
        label: "Восстановить из архива",
        icon: "undo",
        onClick: () => restore(habit),
      });
    } else {
      items.push({
        label: "В архив",
        icon: "archive",
        onClick: () => archive(habit),
      });
    }
    items.push({ sep: true });
    items.push({
      label: "Удалить",
      icon: "trash",
      danger: true,
      onClick: () => deleteHabit(habit),
    });
    return items;
  }

  async function updateStatus(habit, status, message) {
    try {
      await api.patch(`/habits/${habit.id}`, { status });
      toast(message, { type: "success" });
      await load(false);
    } catch (error) {
      toast(error.message || "Не удалось изменить статус.", { type: "error" });
    }
  }

  async function restore(habit) {
    try {
      await api.post(`/habits/${habit.id}/restore`);
      toast("Привычка восстановлена", { type: "success" });
      await load(false);
    } catch (error) {
      toast(error.message || "Не удалось восстановить привычку.", { type: "error" });
    }
  }

  async function archive(habit) {
    try {
      await api.delete(`/habits/${habit.id}?mode=archive`);
      toast("Привычка в архиве", { type: "info" });
      await load(false);
    } catch (error) {
      toast(error.message || "Не удалось отправить в архив.", { type: "error" });
    }
  }

  async function deleteHabit(habit) {
    data.habits = data.habits.filter((item) => item.id !== habit.id);
    data.active_count = data.habits.filter((item) => item.status === "active").length;
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
      await load(false);
      toast(error.message || "Не удалось удалить привычку.", { type: "error" });
    }
  }

  await load(true);
  return () => {
    alive = false;
  };
}
