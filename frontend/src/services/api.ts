
const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const TOKEN_KEY = "examguard_access_token";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  token?: string | null;
  auth?: boolean;
}

async function getErrorDetails(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  try {
    return await response.text();
  } catch {
    return null;
  }
}

function getErrorMessage(detail: unknown, status: number): string {
  if (
    detail &&
    typeof detail === "object" &&
    "detail" in detail
  ) {
    const value = (detail as { detail: unknown }).detail;

    if (typeof value === "string") {
      return value;
    }

    if (Array.isArray(value)) {
      return value
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String(item.msg)
            : String(item)
        )
        .join(", ");
    }
  }

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  return `API request failed with status ${status}.`;
}

function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem(TOKEN_KEY);
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    body,
    token,
    auth = true,
    headers: customHeaders,
    ...fetchOptions
  } = options;

  const headers = new Headers(customHeaders);

  headers.set("Accept", "application/json");

  if (auth) {
    const accessToken = token ?? getStoredToken();

    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }
  }

  let requestBody: BodyInit | undefined;

  if (body instanceof FormData) {
    // Let the browser set the multipart boundary automatically.
    requestBody = body;
  } else if (body !== undefined && body !== null) {
    headers.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
      body: requestBody,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Unable to connect to the ExamGuard AI server. Check your connection and backend URL.",
      0
    );
  }

  if (!response.ok) {
    const detail = await getErrorDetails(response);
    const message = getErrorMessage(detail, response.status);

    if (
      response.status === 401 &&
      /another device|login session is no longer active/i.test(message) &&
      typeof window !== "undefined"
    ) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem("examguard_user");
      for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
        const key = sessionStorage.key(index);
        if (
          key &&
          (
            key.startsWith("examguard_exam_token_") ||
            key.startsWith("examguard_exam_refresh_") ||
            key.startsWith("examguard_exam_id_")
          )
        ) {
          sessionStorage.removeItem(key);
        }
      }
      window.location.replace("/login?reason=session_replaced");
    }

    throw new ApiError(
      message,
      response.status,
      detail
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}

export const api = {
  get<T>(endpoint: string, options: RequestOptions = {}) {
    return request<T>(endpoint, {
      ...options,
      method: "GET",
    });
  },

  post<T>(
    endpoint: string,
    body?: unknown,
    options: RequestOptions = {}
  ) {
    return request<T>(endpoint, {
      ...options,
      method: "POST",
      body,
    });
  },

  put<T>(
    endpoint: string,
    body?: unknown,
    options: RequestOptions = {}
  ) {
    return request<T>(endpoint, {
      ...options,
      method: "PUT",
      body,
    });
  },

  patch<T>(
    endpoint: string,
    body?: unknown,
    options: RequestOptions = {}
  ) {
    return request<T>(endpoint, {
      ...options,
      method: "PATCH",
      body,
    });
  },

  delete<T>(endpoint: string, options: RequestOptions = {}) {
    return request<T>(endpoint, {
      ...options,
      method: "DELETE",
    });
  },

  upload<T>(
    endpoint: string,
    formData: FormData,
    options: RequestOptions = {}
  ) {
    return request<T>(endpoint, {
      ...options,
      method: "POST",
      body: formData,
    });
  },
};

export default api;
