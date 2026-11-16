// Обёртка над fetch: JSON, понятные ошибки, реакция на истёкшую сессию.

export class ApiError extends Error {
  constructor(message, { status = 0, code = "", details = {}, data = null } = {}) {
    super(message || "Не удалось выполнить запрос");
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details || {};
    this.data = data;
  }
}

function buildUrl(path, params) {
  if (!params) return path;
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.set(key, String(value));
  });
  const text = query.toString();
  return text ? `${path}${path.includes("?") ? "&" : "?"}${text}` : path;
}

async function request(path, { method = "GET", body, params, signal, headers = {} } = {}) {
  const options = {
    method,
    credentials: "same-origin",
    signal,
    headers: { Accept: "application/json", ...headers },
  };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(buildUrl(path, params), options);
  } catch (error) {
    if (error && error.name === "AbortError") throw error;
    throw new ApiError("Нет связи с сервером. Проверьте подключение и попробуйте ещё раз.", {
      code: "network",
    });
  }

  const contentType = response.headers.get("Content-Type") || "";
  let data = null;
  if (contentType.includes("application/json")) {
    data = await response.json().catch(() => null);
  } else if (contentType.includes("text/")) {
    data = await response.text().catch(() => null);
  }

  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("app:unauthorized"));
    }
    throw new ApiError(
      (data && data.error) || `Ошибка ${response.status}`,
      {
        status: response.status,
        code: (data && data.code) || "",
        details: (data && data.details) || {},
        data,
      },
    );
  }
  return data;
}

export const api = {
  get: (path, params, options = {}) => request(path, { ...options, params }),
  post: (path, body = {}, options = {}) => request(path, { ...options, method: "POST", body }),
  patch: (path, body = {}, options = {}) => request(path, { ...options, method: "PATCH", body }),
  delete: (path, body, options = {}) => request(path, {
    ...options,
    method: "DELETE",
    body,
  }),
};

export function download(path, filename = "") {
  const link = document.createElement("a");
  link.href = path;
  link.rel = "noopener";
  if (filename) link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}
