// Статистика: серии, проценты, график и годовая тепловая карта.
import { api } from "../api.js";
import { heatmapHTML, heatmapLegend } from "../heatmap.js";
import { habitIcon, icon } from "../icons.js";
import { skeleton, toast } from "../ui.js";
import {
  daysWord, esc, formatDate, formatNumber, percent, pluralRu, scheduleText,
  streakText, todayISO,
} from "../utils.js";

const PERIODS = [
  { days: 7, label: "7 дней" },
  { days: 30, label: "30 дней" },
  { days: 90, label: "90 дней" },
  { days: 365, label: "Год" },
];

export async function mount(root, ctx) {
  let days = 30;
  let data = null;
  let heat = null;
  let heatYear = Number(todayISO().slice(0, 4));
  let alive = true;
  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      const [statsData, heatData] = await Promise.all([
        api.get("/stats", { days }),
        api.get("/stats/heatmap", { year: heatYear }),
      ]);
      if (!alive) return;
      data = statsData;
      heat = heatData;
      heatYear = Number(heatData.year) || heatYear;
      render();
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Не удалось загрузить статистику</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <button type="button" class="btn btn-primary mt-3" data-action="retry">Попробовать снова</button>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function render() {
    const overview = data.overview || {};
    const habits = data.habits || [];
    const series = data.series || [];
    const bestDay = overview.best_weekday || {};

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">Статистика</span>
          <h1 class="display">Спокойный <em>взгляд</em></h1>
          <p class="page-sub">Не про идеальность, а про то, что уже получается. Паузы и частичные шаги здесь тоже видны.</p>
        </div>
        <div class="page-actions">
          <div class="chips" role="tablist" aria-label="Период статистики">
            ${PERIODS.map((item) => `
              <button type="button" class="chip${days === item.days ? " active" : ""}" data-days="${item.days}"
                      role="tab" aria-selected="${days === item.days}">${esc(item.label)}</button>
            `).join("")}
          </div>
        </div>
      </div>

      <div class="stat-grid">
        <article class="stat-card accent">
          <div class="stat-label">${icon("flame")} Текущая серия</div>
          <div class="stat-value">${formatNumber(overview.current_streak)} <small>${unitFor("current", habits)}</small></div>
          <div class="stat-foot">Лучшая — ${formatNumber(overview.best_streak)}</div>
        </article>
        <article class="stat-card">
          <div class="stat-label">${icon("target")} Неделя</div>
          <div class="stat-value">${percent(overview.week_percent)}</div>
          <div class="stat-foot">Месяц — ${percent(overview.month_percent)}</div>
        </article>
        <article class="stat-card">
          <div class="stat-label">${icon("snow")} Заморозки</div>
          <div class="stat-value">${formatNumber(overview.freezes_left)} <small>осталось</small></div>
          <div class="stat-foot">2 в календарный месяц на привычку</div>
        </article>
        <article class="stat-card">
          <div class="stat-label">${icon("calendar")} Лучший день</div>
          <div class="stat-value" style="font-size:24px">${esc(bestDay.name || "—")}</div>
          <div class="stat-foot">${bestDay.count ? `${formatNumber(bestDay.count)} ${pluralRu(bestDay.count, "отметка", "отметки", "отметок")} · ` : ""}${formatNumber(overview.total_habits)} ${pluralRu(overview.total_habits, "привычка", "привычки", "привычек")} в статистике</div>
        </article>
      </div>

      ${chartHTML(series)}

      <div class="section-head">
        <h2 class="section-title">По привычкам</h2>
        <span class="tiny faint">${days} ${daysWord(days)}</span>
      </div>
      <div class="card card-pad">
        ${habits.length ? habits.map(habitRow).join("") : `
          <p class="muted small">Пока нет активных привычек для статистики.</p>
        `}
      </div>

      ${heatmapCard()}
    `;
    bind();
  }

  function unitFor(kind, habits) {
    if (!habits.length) return "дн.";
    const weekly = habits.every((habit) => habit.streak_unit === "weeks");
    return weekly ? "нед." : "дн.";
  }

  function chartHTML(series) {
    if (!series.length) {
      return `
        <div class="card card-pad mt-3">
          <p class="muted small">График появится, когда накопятся отметки.</p>
        </div>
      `;
    }
    const groups = [];
    const chunk = series.length > 62 ? 7 : 1;
    for (let index = 0; index < series.length; index += chunk) {
      const slice = series.slice(index, index + chunk);
      const total = slice.reduce((acc, item) => acc + (Number(item.total) || 0), 0);
      const done = slice.reduce((acc, item) => acc + (Number(item.done) || 0), 0);
      groups.push({
        from: slice[0].date,
        to: slice[slice.length - 1].date,
        percent: total ? Math.round((done / total) * 100) : 0,
        done,
        total,
      });
    }
    const average = groups.length
      ? Math.round(groups.reduce((acc, item) => acc + item.percent, 0) / groups.length)
      : 0;

    return `
      <div class="card chart-card mt-3">
        <div class="chart-head">
          <div>
            <h2 class="h2">Ритм по ${chunk === 7 ? "неделям" : "дням"}</h2>
            <p class="tiny muted mt-1">${formatDate(data.period.from)} — ${formatDate(data.period.to, { withYear: true })}</p>
          </div>
          <span class="pill">${icon("target")} в среднем ${average}%</span>
        </div>
        <div class="chart" role="img" aria-label="График выполнения по дням">
          ${groups.map((group) => `
            <div class="bar-wrap">
              <div class="bar${group.percent >= 100 ? " has-value" : group.percent > 0 && group.percent < 60 ? " partial" : group.percent > 0 ? " has-value" : ""}"
                   style="height:${Math.max(3, group.percent)}%"></div>
              <span class="bar-tip">${esc(formatDate(group.from))}${group.to !== group.from ? ` — ${esc(formatDate(group.to))}` : ""}: ${group.percent}%</span>
            </div>
          `).join("")}
        </div>
        <div class="chart-axis">
          <span>${esc(formatDate(series[0].date))}</span>
          <span>${esc(formatDate(series[series.length - 1].date))}</span>
        </div>
      </div>
    `;
  }

  function habitRow(habit) {
    return `
      <div class="habit-stat-row">
        <div class="habit-stat-name">
          <span class="habit-icon" style="--icon-color:${esc(habit.color || "#2E685F")}" aria-hidden="true">${habitIcon(habit.icon)}</span>
          <div class="grow">
            <div class="n">${esc(habit.title)}</div>
            <div class="s">${esc(habit.schedule_label || scheduleText(habit))} · серия ${esc(streakText(habit))}</div>
            <div class="progress-line mt-1" aria-hidden="true">
              <i style="width:${Math.min(100, Number(habit.month_percent) || 0)}%;background:${esc(habit.color || "#4F7D70")}"></i>
            </div>
          </div>
        </div>
        <div class="habit-stat-cell"><b>${formatNumber(habit.current_streak)}</b>серия</div>
        <div class="habit-stat-cell"><b>${percent(habit.week_percent)}</b>неделя</div>
        <div class="habit-stat-cell"><b>${percent(habit.month_percent)}</b>месяц</div>
      </div>
    `;
  }

  function heatmapCard() {
    const summary = heat?.summary || {};
    return `
      <div class="section-head">
        <h2 class="section-title">Год в клетках</h2>
        <div class="cal-nav">
          <button type="button" class="icon-btn sm bordered" data-heat="-1" aria-label="Предыдущий год">${icon("chevronLeft")}</button>
          <span class="pill">${heatYear}</span>
          <button type="button" class="icon-btn sm bordered" data-heat="1" aria-label="Следующий год">${icon("chevronRight")}</button>
        </div>
      </div>
      <div class="card card-pad">
        <div class="row between mb-2" style="gap:10px;flex-wrap:wrap">
          <span class="pill">${icon("checkCircle")} ${formatNumber(summary.done)} ${pluralRu(summary.done, "отметка", "отметки", "отметок")}</span>
          <span class="pill">${icon("calendar")} ${formatNumber(summary.active_days)} ${pluralRu(summary.active_days, "активный день", "активных дня", "активных дней")}</span>
        </div>
        <div class="heatmap-scroll">${heatmapHTML(heat?.days || [], { clickable: true })}</div>
        ${heatmapLegend()}
      </div>
    `;
  }

  function bind() {
    root.querySelectorAll("[data-days]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = Number(button.dataset.days) || 30;
        if (next === days) return;
        days = next;
        load(false);
      });
    });
    root.querySelectorAll("[data-heat]").forEach((button) => {
      button.addEventListener("click", async () => {
        const next = heatYear + (Number(button.dataset.heat) || 0);
        if (next < 2000 || next > 2100) return;
        heatYear = next;
        try {
          heat = await api.get("/stats/heatmap", { year: heatYear });
          if (alive) render();
        } catch (error) {
          toast(error.message || "Не удалось загрузить год.", { type: "error" });
        }
      });
    });
    root.querySelectorAll(".heat-cell[data-date]").forEach((cell) => {
      cell.addEventListener("click", () => ctx.navigate(`calendar/${cell.dataset.date}`));
    });
  }

  await load(true);
  return () => {
    alive = false;
  };
}
