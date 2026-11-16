// Интерфейсные примитивы: тосты, модальные окна, меню, индикатор синхронизации.
import { icon } from "./icons.js";
import { esc } from "./utils.js";

// ------------------------------------------------------------------ тосты

const TOAST_ICONS = { success: "checkCircle", error: "alert", info: "info" };

export function toast(message, options = {}) {
  const region = document.getElementById("toast-region");
  if (!region) return { close() {} };
  const type = options.type || "success";
  const element = document.createElement("div");
  element.className = `toast ${type}`;
  element.setAttribute("role", type === "error" ? "alert" : "status");

  const iconBox = document.createElement("span");
  iconBox.className = "toast-icon";
  iconBox.innerHTML = icon(TOAST_ICONS[type] || "info");

  const text = document.createElement("div");
  text.className = "toast-message";
  text.textContent = message;

  element.append(iconBox, text);

  let timer = 0;
  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    clearTimeout(timer);
    element.classList.add("out");
    setTimeout(() => element.remove(), 230);
  }

  if (options.action && options.action.label) {
    const action = document.createElement("button");
    action.type = "button";
    action.className = "toast-action";
    action.textContent = options.action.label;
    action.addEventListener("click", async () => {
      close();
      try {
        await options.action.onClick?.();
      } catch {
        /* обработчик сам показывает ошибку */
      }
    });
    element.append(action);
  }

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "icon-btn toast-close";
  closeButton.setAttribute("aria-label", "Закрыть уведомление");
  closeButton.innerHTML = icon("close");
  closeButton.addEventListener("click", close);
  element.append(closeButton);

  region.append(element);
  while (region.children.length > 4) region.firstElementChild?.remove();

  const duration = options.duration ?? (options.action ? 10000 : type === "error" ? 6500 : 4200);
  if (duration > 0) timer = setTimeout(close, duration);
  return { close, element };
}

// ------------------------------------------------------------------ модальные окна

let openModals = 0;

export function modal(options = {}) {
  const root = document.getElementById("modal-root");
  if (!root) return { close() {} };

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "presentation");

  const box = document.createElement("div");
  box.className = ["modal", options.wide ? "wide" : "", options.narrow ? "narrow" : "", options.className || ""]
    .filter(Boolean).join(" ");
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");

  const head = document.createElement("div");
  head.className = "modal-head";

  const titleBlock = document.createElement("div");
  titleBlock.className = "modal-title-block";
  const heading = document.createElement("h2");
  heading.className = "modal-title";
  heading.id = `modal-title-${Date.now()}`;
  heading.textContent = options.title || "";
  titleBlock.append(heading);
  if (options.subtitle) {
    const subtitle = document.createElement("p");
    subtitle.className = "modal-sub";
    subtitle.textContent = options.subtitle;
    titleBlock.append(subtitle);
  }
  box.setAttribute("aria-labelledby", heading.id);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "icon-btn close-btn";
  closeButton.setAttribute("aria-label", "Закрыть");
  closeButton.innerHTML = icon("close");
  head.append(titleBlock, closeButton);

  const body = document.createElement("div");
  body.className = "modal-body";
  if (options.body instanceof Node) body.append(options.body);
  else body.innerHTML = options.body || "";

  const foot = document.createElement("div");
  foot.className = "modal-foot";
  foot.innerHTML = options.footer || "";
  if (!options.footer) foot.hidden = true;

  box.append(head, body, foot);
  overlay.append(box);
  root.append(overlay);

  const previousFocus = document.activeElement;
  const previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  openModals += 1;

  let closed = false;
  function close(result) {
    if (closed) return;
    closed = true;
    openModals = Math.max(0, openModals - 1);
    if (!openModals) document.body.style.overflow = previousOverflow;
    document.removeEventListener("keydown", onKeydown, true);
    overlay.remove();
    try {
      options.onClose?.(result);
    } catch (error) {
      console.error(error);
    }
    if (previousFocus && typeof previousFocus.focus === "function") {
      setTimeout(() => previousFocus.focus({ preventScroll: true }), 20);
    }
  }

  function focusables() {
    return Array.from(box.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )).filter((el) => el.offsetParent !== null);
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const items = focusables();
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function runOnMount() {
    requestAnimationFrame(() => {
      const preferred = box.querySelector("[autofocus]") || box.querySelector("input, textarea, select") || focusables()[0];
      preferred?.focus({ preventScroll: true });
    });
    try {
      options.onMount?.({ el: box, body, foot, close, overlay });
    } catch (error) {
      console.error(error);
    }
  }

  overlay.addEventListener("mousedown", (event) => {
    if (event.target === overlay) close();
  });
  closeButton.addEventListener("click", () => close());
  document.addEventListener("keydown", onKeydown, true);
  runOnMount();

  return { el: box, body, foot, overlay, close };
}

export function confirmDialog({
  title = "Подтвердить",
  message = "",
  confirmLabel = "Подтвердить",
  cancelLabel = "Отмена",
  danger = false,
  body = "",
} = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const dialog = modal({
      title,
      narrow: true,
      body: body || `<p class="small muted">${message}</p>`,
      footer: `
        <button type="button" class="btn btn-ghost" data-role="cancel">${esc(cancelLabel)}</button>
        <button type="button" class="btn ${danger ? "btn-danger" : "btn-primary"}" data-role="ok">${esc(confirmLabel)}</button>
      `,
      onClose: () => finish(false),
    });
    dialog.foot.querySelector('[data-role="cancel"]').addEventListener("click", () => {
      finish(false);
      dialog.close();
    });
    dialog.foot.querySelector('[data-role="ok"]').addEventListener("click", () => {
      finish(true);
      dialog.close();
    });
  });
}

export function promptWord({
  title = "Удаление аккаунта",
  message = "",
  word = "УДАЛИТЬ",
  confirmLabel = "Удалить навсегда",
  cancelLabel = "Отмена",
} = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const dialog = modal({
      title,
      narrow: true,
      body: `
        <div class="stack">
          <p class="small muted">${message}</p>
          <div class="field">
            <label class="label" for="confirm-word">Введите «${esc(word)}»</label>
            <input class="input" id="confirm-word" autocomplete="off" autocapitalize="characters" spellcheck="false">
          </div>
        </div>
      `,
      footer: `
        <button type="button" class="btn btn-ghost" data-role="cancel">${esc(cancelLabel)}</button>
        <button type="button" class="btn btn-danger" data-role="ok" disabled>${esc(confirmLabel)}</button>
      `,
      onMount: ({ body, foot }) => {
        const input = body.querySelector("#confirm-word");
        const ok = foot.querySelector('[data-role="ok"]');
        input.addEventListener("input", () => {
          ok.disabled = input.value.trim().toLowerCase() !== word.toLowerCase();
        });
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && !ok.disabled) {
            event.preventDefault();
            finish(input.value.trim());
            dialog.close();
          }
        });
        foot.querySelector('[data-role="cancel"]').addEventListener("click", () => {
          finish(null);
          dialog.close();
        });
        ok.addEventListener("click", () => {
          if (ok.disabled) return;
          finish(input.value.trim());
          dialog.close();
        });
      },
      onClose: () => finish(null),
    });
  });
}

// ------------------------------------------------------------------ контекстное меню

export function openMenu(anchor, items) {
  if (!anchor) return { close() {} };
  const menu = document.createElement("div");
  menu.className = "menu";
  menu.setAttribute("role", "menu");

  const close = () => {
    document.removeEventListener("mousedown", onDocumentDown, true);
    document.removeEventListener("keydown", onKeydown, true);
    window.removeEventListener("resize", close);
    window.removeEventListener("scroll", close, true);
    menu.remove();
  };

  const onDocumentDown = (event) => {
    if (!menu.contains(event.target) && event.target !== anchor && !anchor.contains(event.target)) close();
  };
  const onKeydown = (event) => {
    if (event.key === "Escape") close();
  };

  items.forEach((item) => {
    if (!item || item.sep) {
      const sep = document.createElement("div");
      sep.className = "menu-sep";
      menu.append(sep);
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.disabled = Boolean(item.disabled);
    button.setAttribute("role", "menuitem");
    if (item.danger) button.classList.add("danger");
    button.innerHTML = `${item.icon ? icon(item.icon) : ""}<span>${esc(item.label)}</span>`;
    button.addEventListener("click", () => {
      close();
      item.onClick?.();
    });
    menu.append(button);
  });

  document.body.append(menu);

  const rect = anchor.getBoundingClientRect();
  const width = menu.offsetWidth;
  const height = menu.offsetHeight;
  let left = rect.right - width;
  let top = rect.bottom + 6;
  if (left < 8) left = 8;
  if (left + width > window.innerWidth - 8) left = window.innerWidth - width - 8;
  if (top + height > window.innerHeight - 8) top = Math.max(8, rect.top - height - 6);
  menu.style.left = `${Math.round(left)}px`;
  menu.style.top = `${Math.round(top)}px`;

  document.addEventListener("mousedown", onDocumentDown, true);
  document.addEventListener("keydown", onKeydown, true);
  window.addEventListener("resize", close);
  window.addEventListener("scroll", close, true);
  setTimeout(() => menu.querySelector("button:not(:disabled)")?.focus({ preventScroll: true }), 10);

  return { close, element: menu };
}

// ------------------------------------------------------------------ синхронизация и кнопки

let syncTimer = 0;

export function sync(text, state = "saved", timeout = 1900) {
  const line = document.getElementById("global-sync");
  if (!line) return;
  const label = line.querySelector(".sync-text");
  if (label) label.textContent = text;
  line.classList.add("show");
  line.classList.toggle("saving", state === "saving");
  clearTimeout(syncTimer);
  if (state !== "saving") {
    syncTimer = setTimeout(() => line.classList.remove("show"), timeout);
  }
}

export function setButtonBusy(button, busy, label = "Сохраняем…") {
  if (!button) return;
  if (busy) {
    if (!button.dataset.original) button.dataset.original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spin" style="display:inline-grid;width:16px;height:16px">${icon("refresh")}</span><span>${esc(label)}</span>`;
  } else {
    button.disabled = false;
    if (button.dataset.original) {
      button.innerHTML = button.dataset.original;
      delete button.dataset.original;
    }
  }
}

// ------------------------------------------------------------------ заготовки

export function skeleton() {
  return `
    <div class="loading-block" aria-hidden="true">
      <div class="skeleton h1"></div>
      <div class="skeleton line"></div>
      <div class="skeleton card"></div>
      <div class="skeleton card"></div>
      <div class="skeleton card"></div>
    </div>
  `;
}

export function emptyState({ iconName = "spark", title, text = "", actions = "" }) {
  return `
    <div class="empty-state">
      <div class="empty-art">${icon(iconName)}</div>
      <h3>${esc(title)}</h3>
      ${text ? `<p>${esc(text)}</p>` : ""}
      ${actions ? `<div class="empty-actions">${actions}</div>` : ""}
    </div>
  `;
}

export function errorState(message, retryHTML = "") {
  return `
    <div class="card card-pad text-center">
      <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
      <h3 class="h2">Не получилось загрузить</h3>
      <p class="muted small mt-1">${esc(message)}</p>
      ${retryHTML ? `<div class="row end mt-3" style="justify-content:center">${retryHTML}</div>` : ""}
    </div>
  `;
}
