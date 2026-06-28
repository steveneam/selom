"use client";

/**
 * Thin typed fetch wrapper over the backend (`/api/*` — the Vercel rewrite → FastAPI).
 *
 * Centralizes JSON encoding, the **read-body-once** error discipline (a `Response` body is a
 * one-shot stream — reading it twice throws and silently swallows the real message
 * [[fetch-body-read-once-browser-verify]]), and a **pluggable auth-header hook** so wiring the
 * Clerk `Authorization: Bearer` at step 8 is a one-liner here, not a sweep across call sites. In dev
 * the header is empty (the backend's `dev` auth mode uses a fixed offline tenant — no header needed).
 */

export type AuthHeaderFn = () => Record<string, string> | Promise<Record<string, string>>;

let _authHeader: AuthHeaderFn = () => ({});

/** Step 8 wires the Clerk bearer here. Default = no header (dev mode / fixed offline tenant). */
export function setAuthHeader(fn: AuthHeaderFn): void {
  _authHeader = fn;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /**
   * A permanent failure the optimistic write should ROLL BACK (a 4xx the user can't fix by waiting —
   * quota/not-found/validation). 408/429 and 5xx/network are transient → the write queue retries.
   */
  get permanent(): boolean {
    return this.status >= 400 && this.status < 500 && this.status !== 408 && this.status !== 429;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { ...(await _authHeader()) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, "network error", e); // offline / DNS — transient (status 0)
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json(); // read the one-shot body ONCE
    } catch {
      /* non-JSON error body */
    }
    const d = (detail as { detail?: unknown } | null)?.detail;
    const msg = typeof d === "string" ? d : `request failed (${res.status})`;
    throw new ApiError(res.status, msg, detail);
  }
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    return undefined as T;
  }
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string, body?: unknown) => request<T>("DELETE", path, body),
};
