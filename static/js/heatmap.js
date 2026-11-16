// Годовая тепловая карта — используется в календаре и статистике.
import { esc, formatDateLong, isToday, parseISODate } from "./utils.js";

export function heatLevel(day) {
  if (!day || !day.total || !day.done) return 0;
  const ratio = day.done / day.total;
  if (ratio >= 0.999) return 4;
  if (ratio >= 0.66) return 3;
  if (ratio >= 0.33) return 2;
  return 1;
}

export function heatmapHTML(days, { clickable = true } = {}) {
  if (!days || !days.length) {
    return `<p class="muted small" style="padding:18px 0">За этот год пока нет данных — начните отмечать привычки, и карта заполнится.</p>`;
  }
  const first = parseISODate(days[0].date);
  const pad = (first.getDay() + 6) % 7;
  const cells = [];
  for (let i = 0; i < pad; i += 1) {
    cells.push('<span class="heat-cell" style="visibility:hidden"></span>');
  }
  for (const day of days) {
    const level = heatLevel(day);
    const parts = [`${formatDateLong(day.date)}`];
    if (day.total) parts.push(`выполнено ${day.done} из ${day.total}`);
    else parts.push("нет запланированных привычек");
    const label = parts.join(" — ");
    const classes = ["heat-cell"];
    if (isToday(day.date)) classes.push("today");
    if (day.future) classes.push("future");
    if (clickable) {
      cells.push(
        `<button type="button" class="${classes.join(" ")}" data-level="${level}" data-date="${esc(day.date)}" title="${esc(label)}" aria-label="${esc(label)}"></button>`,
      );
    } else {
      cells.push(`<span class="${classes.join(" ")}" data-level="${level}" title="${esc(label)}"></span>`);
    }
  }
  return `<div class="heatmap" role="grid" aria-label="Тепловая карта за год">${cells.join("")}</div>`;
}

export function heatmapLegend() {
  return `
    <div class="heat-legend">
      <span>Меньше</span>
      <span class="squares" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
      <span>Больше</span>
    </div>
  `;
}

export function heatmapSummary(days) {
  const list = days || [];
  return {
    done: list.reduce((acc, day) => acc + (Number(day.done) || 0), 0),
    activeDays: list.filter((day) => day.done > 0).length,
    days: list.length,
  };
}
