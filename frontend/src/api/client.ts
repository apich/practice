import { toast } from 'sonner';

export const getUserId = () => localStorage.getItem('username') ?? '';

// ── JWT token helpers ──────────────────────────────────────────────────────
export const getAccessToken = () => localStorage.getItem('access_token') ?? '';
export const isAuthenticated = () => !!localStorage.getItem('access_token');

/** Clear all auth state and redirect to /login (if not already there). */
export function clearAuthAndRedirect() {
	localStorage.removeItem('access_token');
	localStorage.removeItem('refresh_token');
	localStorage.removeItem('user_info');
	if (window.location.pathname !== '/login') {
		window.location.href = '/login';
	}
}

/**
 * Structured error thrown for non-2xx HTTP responses.
 * `message` contains the human-readable detail extracted from the backend.
 */
export class ApiError extends Error {
	readonly status: number;
	readonly detail: string;

	constructor(status: number, detail: string) {
		super(detail);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
	}
}

interface RequestOptions {
	method?: string;
	body?: unknown;
	params?: Record<string, string>;
	/** When true, suppresses the automatic error toast. Useful when the caller shows its own inline error UI. */
	silent?: boolean;
	signal?: AbortSignal;
	/** Gives up after this many ms and reports {@link TIMEOUT_STATUS}. Off by default — a streaming chat is meant to stay open. */
	timeoutMs?: number;
	/** Skip Authorization / X-User-ID headers (e.g. health probes that don't need auth). */
	skipAuth?: boolean;
}

/** Reported when `timeoutMs` elapses. Real 408s come from a server, so either way the request did not complete in time. */
export const TIMEOUT_STATUS = 408;

function buildHeaders(hasBody: boolean, skipAuth?: boolean): Record<string, string> {
	const headers: Record<string, string> = {};

	if (skipAuth) {
		if (hasBody) headers['Content-Type'] = 'application/json';
		return headers;
	}

	// JWT takes precedence; fall back to X-User-ID for dev-mode / backward compat
	const token = getAccessToken();
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}
	const uid = getUserId();
	if (uid) {
		headers['X-User-ID'] = uid;
	}

	if (hasBody) headers['Content-Type'] = 'application/json';
	return headers;
}

/** Parse the response body and extract the `detail` field if the backend returned JSON. */
async function extractErrorDetail(res: Response): Promise<string> {
	const text = await res.text();
	try {
		const json = JSON.parse(text) as { detail?: unknown };
		if (typeof json.detail === 'string') return json.detail;
		if (json.detail !== undefined) return JSON.stringify(json.detail);
	} catch {
		// not JSON – fall through
	}
	return text || res.statusText;
}

async function streamRequest(path: string, options: RequestOptions = {}): Promise<Response> {
	const {
		method = 'GET',
		body,
		params,
		signal,
		silent = false,
		timeoutMs,
	} = options;
	const url = new URL(path, window.location.origin);
	if (params) {
		Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
	}

	// AbortSignal.timeout aborts with a TimeoutError, which is what lets the
	// catch below tell "too slow" apart from the caller's own cancellation.
	const deadline = timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined;
	const combined =
		deadline && signal ? AbortSignal.any([signal, deadline]) : (deadline ?? signal);

	let res: Response;
	try {
		res = await fetch(url.toString(), {
			method,
			headers: buildHeaders(body !== undefined, options?.skipAuth),
			body: body ? JSON.stringify(body) : undefined,
			signal: combined,
		});
	} catch (e) {
		// An abort is the caller's own doing — pass it through untouched.
		if (e instanceof DOMException && e.name === 'AbortError') throw e;
		// A server that accepts the connection then stalls would otherwise
		// leave the caller waiting forever.
		const timedOut = e instanceof DOMException && e.name === 'TimeoutError';
		// Otherwise fetch only rejects when the request never reached the
		// server: wrong address, DNS failure, refused connection, blocked
		// preflight. Status 0 distinguishes that from any HTTP-level failure.
		const error = timedOut
			? new ApiError(TIMEOUT_STATUS, 'The server took too long to respond.')
			: new ApiError(
					0,
					'Cannot reach the server. Check the server address and your network.',
				);
		if (!silent) toast.error(error.detail);
		throw error;
	}

	if (!res.ok) {
		const detail = await extractErrorDetail(res);
		const error = new ApiError(res.status, detail);

		// 401 → token expired or invalid. Clear auth state and redirect to login.
		// Skip for /auth/ endpoints (login/refresh) so the caller can handle it.
		if (res.status === 401 && !path.startsWith('/auth/')) {
			clearAuthAndRedirect();
		}

		if (!silent) toast.error(detail);
		throw error;
	}

	return res;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const res = await streamRequest(path, options);
	if (res.status === 204) return undefined as T;
	return res.json() as Promise<T>;
}

export const client = {
	get: <T>(
		path: string,
		params?: Record<string, string>,
		options?: { silent?: boolean; timeoutMs?: number; skipAuth?: boolean },
	) => request<T>(path, { method: 'GET', params, ...options }),
	post: <T>(
		path: string,
		body?: unknown,
		params?: Record<string, string>,
		options?: { silent?: boolean },
	) => request<T>(path, { method: 'POST', body, params, silent: options?.silent }),
	patch: <T>(
		path: string,
		body?: unknown,
		params?: Record<string, string>,
		options?: { silent?: boolean },
	) => request<T>(path, { method: 'PATCH', body, params, silent: options?.silent }),
	delete: <T = void>(path: string, params?: Record<string, string>) =>
		request<T>(path, { method: 'DELETE', params }),
	stream: (path: string, options?: RequestOptions) => streamRequest(path, options),
};
