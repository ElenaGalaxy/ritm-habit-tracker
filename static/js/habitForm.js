// Форма создания и редактирования привычки.
import { api } from "./api.js";
import { COLOR_CHOICES, ICON_CHOICES, habitIcon, icon } from "./icons.js";
import { modal, setButtonBusy, sync, toast } from "./ui.js";
import { esc, formatNumber, UNITS_BY_TYPE } from "./utils.js";

const TYPES = [
  { id: "boolean", label: "Да / нет", hint: "Один тап — и готово" },
  { id: "quantity", label: "Количество", hint: "Стаканы, шаги, страницы" },
  { id: "duration", label: "Время", hint: "Минуты или часы" },
];

const SCHEDULES = [
  { id: "daily", label: "Каждый день" },
  { id: "weekdays", label: "По будням" },
  { id: "times_per_week", label: "N раз в неделю" },
];

export function openHabitForm({ habit = null, template = null, onSaved } = {}) {
  const source = habit || template || {};
  const isEdit = Boolean(habit && habit.id);
  const initialType = source.type || "boolean";
  const initialSchedule = source.schedule || "daily";
  const initialIcon = source.icon || "spark";
  const initialColor = source.color || "#2E685F";

  const body = `
    <form id="habit-form" class="form-grid" novalidate>
      <div class="field">
        <label class="label" for="habit-title">Название <span class="optional">до 80 символов</span></label>
        <input class="input" id="habit-title" name="title" maxlength="80" autocomplete="off"
               placeholder="Например, прогулка 20 минут" value="${esc(source.title || "")}" autofocus>
      </div>

      <div class="field">
        <label class="label" for="habit-description">Описание <span class="optional">необязательно</span></label>
        <textarea class="textarea" id="habit-description" name="description" maxlength="300"
                  placeholder="Зачем эта привычка и что помогает её сделать">${esc(source.description || "")}</textarea>
      </div>

      <fieldset class="fieldset">
        <legend>Тип привычки</legend>
        <div class="segmented block" data-role="type">
          ${TYPES.map((item) => `
            <button type="button" class="seg-btn${item.id === initialType ? " active" : ""}"
                    data-type="${item.id}" title="${esc(item.hint)}">${esc(item.label)}</button>
          `).join("")}
        </div>
        <p class="hint" data-role="type-hint">${esc(TYPES.find((t) => t.id === initialType)?.hint || "")}</p>
      </fieldset>

      <div class="form-row" data-role="target-row"${initialType === "boolean" ? " hidden" : ""}>
        <div class="field">
          <label class="label" for="habit-target">Цель</label>
          <input class="input" id="habit-target" name="target_value" type="number"
                 inputmode="decimal" min="0.1" step="any" value="${esc(formatNumber(source.target_value ?? 1, 2))}">
        </div>
        <div class="field">
          <label class="label" for="habit-unit">Единица</label>
          <input class="input" id="habit-unit" name="unit" maxlength="20" list="habit-units"
                 autocomplete="off" placeholder="${initialType === "duration" ? "минуты" : "раз"}"
                 value="${esc(source.unit || "")}">
        </div>
      </div>

      <fieldset class="fieldset">
        <legend>Расписание</legend>
        <div class="segmented block" data-role="schedule">
          ${SCHEDULES.map((item) => `
            <button type="button" class="seg-btn${item.id === initialSchedule ? " active" : ""}"
                    data-schedule="${item.id}">${esc(item.label)}</button>
          `).join("")}
        </div>
      </fieldset>

      <div class="field" data-role="weekly-row"${initialSchedule !== "times_per_week" ? " hidden" : ""}>
        <label class="label" for="habit-times">Сколько раз в неделю</label>
        <div class="row">
          <input class="input input-sm" id="habit-times" name="times_per_week" type="number"
                 inputmode="numeric" min="1" max="7" step="1" style="width:96px"
                 value="${esc(source.times_per_week ?? 3)}">
          <span class="hint">Любые дни недели. Заморозка засчитывается в недельную цель.</span>
        </div>
      </div>

      <div class="form-row">
        <div class="field">
          <label class="label" for="habit-reminder">Время напоминания</label>
          <input class="input" id="habit-reminder" name="reminder_time" type="time"
                 value="${esc(source.reminder_time || "09:00")}">
        </div>
        <div class="field">
          <label class="label" for="habit-freeze">Заморозок в месяц</label>
          <select class="select" id="habit-freeze" name="freeze_limit">
            ${[0, 1, 2, 3, 4, 5].map((n) => `<option value="${n}"${Number(source.freeze_limit ?? 2) === n ? " selected" : ""}>${n}</option>`).join("")}
          </select>
        </div>
      </div>

      <fieldset class="fieldset">
        <legend>Иконка</legend>
        <div class="chips" data-role="icons">
          ${ICON_CHOICES.map((name) => `
            <button type="button" class="chip icon-chip${name === initialIcon ? " active" : ""}"
                    data-icon="${name}" aria-label="${name}" title="${name}">${habitIcon(name)}</button>
          `).join("")}
        </div>
      </fieldset>

      <fieldset class="fieldset">
        <legend>Цвет</legend>
        <div class="chips" data-role="colors">
          ${COLOR_CHOICES.map((color) => `
            <button type="button" class="color-swatch${color === initialColor ? " active" : ""}"
                    data-color="${color}" style="--swatch:${color}" aria-label="Цвет ${color}" title="${color}"></button>
          `).join("")}
        </div>
      </fieldset>

      <datalist id="habit-units">
        ${[...UNITS_BY_TYPE.quantity, ...UNITS_BY_TYPE.duration, ""].filter(Boolean)
          .map((unit) => `<option value="${esc(unit)}"></option>`).join("")}
      </datalist>

      <p class="error-text" data-role="error" hidden></p>
    </form>
  `;

  const dialog = modal({
    title: isEdit ? "Изменить привычку" : "Новая привычка",
    subtitle: isEdit ? "Изменения сохранятся сразу" : "Маленький шаг, который хочется повторять",
    wide: true,
    body,
    footer: `
      <button type="button" class="btn btn-ghost" data-role="cancel">Отмена</button>
      <button type="submit" form="habit-form" class="btn btn-primary" data-role="save">
        ${isEdit ? "Сохранить" : "Создать привычку"}
      </button>
    `,
  });

  const form = dialog.body.querySelector("#habit-form");
  const errorBox = form.querySelector('[data-role="error"]');
  const targetRow = form.querySelector('[data-role="target-row"]');
  const weeklyRow = form.querySelector('[data-role="weekly-row"]');
  const typeHint = form.querySelector('[data-role="type-hint"]');
  const unitInput = form.querySelector("#habit-unit");
  const saveButton = dialog.foot.querySelector('[data-role="save"]');

  let currentType = initialType;
  let currentSchedule = initialSchedule;
  let currentIcon = initialIcon;
  let currentColor = initialColor;

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    errorBox.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function applyType(type) {
    currentType = type;
    form.querySelectorAll("[data-type]").forEach((button) => {
      button.classList.toggle("active", button.dataset.type === type);
    });
    targetRow.hidden = type === "boolean";
    typeHint.textContent = TYPES.find((item) => item.id === type)?.hint || "";
    if (type === "boolean") {
      unitInput.value = "";
    } else if (!unitInput.value) {
      unitInput.placeholder = type === "duration" ? "минуты" : "раз";
    }
    clearError();
  }

  function applySchedule(schedule) {
    currentSchedule = schedule;
    form.querySelectorAll("[data-schedule]").forEach((button) => {
      button.classList.toggle("active", button.dataset.schedule === schedule);
    });
    weeklyRow.hidden = schedule !== "times_per_week";
    clearError();
  }

  form.querySelectorAll("[data-type]").forEach((button) => {
    button.addEventListener("click", () => applyType(button.dataset.type));
  });
  form.querySelectorAll("[data-schedule]").forEach((button) => {
    button.addEventListener("click", () => applySchedule(button.dataset.schedule));
  });
  form.querySelectorAll("[data-icon]").forEach((button) => {
    button.addEventListener("click", () => {
      currentIcon = button.dataset.icon;
      form.querySelectorAll("[data-icon]").forEach((item) => {
        item.classList.toggle("active", item.dataset.icon === currentIcon);
      });
    });
  });
  form.querySelectorAll("[data-color]").forEach((button) => {
    button.addEventListener("click", () => {
      currentColor = button.dataset.color;
      form.querySelectorAll("[data-color]").forEach((item) => {
        item.classList.toggle("active", item.dataset.color === currentColor);
      });
    });
  });

  let saving = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saving) return;
    clearError();

    const title = form.title.value.trim();
    if (!title) {
      showError("Введите название привычки.");
      form.title.focus();
      return;
    }
    let target = 1;
    if (currentType !== "boolean") {
      target = Number(form.target_value.value.replace(",", "."));
      if (!Number.isFinite(target) || target <= 0) {
        showError("Цель должна быть больше нуля.");
        form.target_value.focus();
        return;
      }
    }
    let times = Number(form.times_per_week.value) || 3;
    if (!Number.isInteger(times) || times < 1 || times > 7) {
      showError("Для «N раз в неделю» укажите число от 1 до 7.");
      form.times_per_week.focus();
      return;
    }
    if (currentSchedule !== "times_per_week") times = Number(source.times_per_week) || 3;

    const payload = {
      title,
      description: form.description.value.trim(),
      type: currentType,
      target_value: currentType === "boolean" ? 1 : target,
      unit: currentType === "boolean" ? "" : form.unit.value.trim(),
      schedule: currentSchedule,
      times_per_week: times,
      reminder_time: form.reminder_time.value || "09:00",
      freeze_limit: Number(form.freeze_limit.value) || 0,
      icon: currentIcon,
      color: currentColor,
    };

    saving = true;
    setButtonBusy(saveButton, true, "Сохраняем…");
    try {
      const data = isEdit
        ? await api.patch(`/habits/${habit.id}`, payload)
        : await api.post("/habits", payload);
      sync("Сохранено");
      toast(isEdit ? "Привычка обновлена" : "Привычка создана", { type: "success" });
      dialog.close();
      onSaved?.(data?.habit, { created: !isEdit });
    } catch (error) {
      showError(error.message || "Не удалось сохранить привычку.");
    } finally {
      saving = false;
      setButtonBusy(saveButton, false);
    }
  });

  dialog.foot.querySelector('[data-role="cancel"]').addEventListener("click", () => dialog.close());

  return dialog;
}
