import { client, getAccessToken } from './client';
import type { UserInfoResponse } from './types';

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
	user_id: string;
	username: string;
	role: string;
}

export interface RegisterRequest {
	username: string;
	password: string;
	role?: string;
}

export interface LoginUrlResponse {
	login_url: string;
	state: string;
	redirect_uri: string;
}

export interface OAuthCallbackRequest {
	code: string;
	state: string;
}

/**
 * Auth API — login, current user, refresh, register.
 */
export const authApi = {
	/**
	 * JSON login with username + password.
	 *
	 * Stores the resulting tokens in localStorage on success.
	 */
	login: async (username: string, password: string): Promise<TokenResponse> => {
		const tokens = await client.post<TokenResponse>(
			'/auth/login',
			{ username, password },
			undefined,
			{ silent: true },
		);

		// Persist tokens
		localStorage.setItem('access_token', tokens.access_token);
		localStorage.setItem('refresh_token', tokens.refresh_token);
		localStorage.setItem(
			'user_info',
			JSON.stringify({
				user_id: tokens.user_id,
				username: tokens.username,
				role: tokens.role,
			}),
		);
		// Also set username for X-User-ID fallback / agentscope compatibility
		localStorage.setItem('username', tokens.username);

		return tokens;
	},

	/** Get the current authenticated user's info. */
	me: () => client.get<UserInfoResponse>('/auth/me'),

	/** Refresh the access token using the stored refresh token. */
	refresh: async (): Promise<TokenResponse> => {
		const refreshToken = localStorage.getItem('refresh_token');
		if (!refreshToken) throw new Error('No refresh token');

		const url = new URL('/auth/refresh', window.location.origin);
		const res = await fetch(url.toString(), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				...(getAccessToken() && {
					Authorization: `Bearer ${getAccessToken()}`,
				}),
			},
			body: JSON.stringify({ refresh_token: refreshToken }),
		});

		if (!res.ok) {
			throw new Error('Token refresh failed');
		}

		const tokens = (await res.json()) as TokenResponse;
		localStorage.setItem('access_token', tokens.access_token);
		localStorage.setItem('refresh_token', tokens.refresh_token);
		localStorage.setItem(
			'user_info',
			JSON.stringify({
				user_id: tokens.user_id,
				username: tokens.username,
				role: tokens.role,
			}),
		);

		return tokens;
	},

	/** Register a new user (developer only). */
	register: (body: RegisterRequest) =>
		client.post<UserInfoResponse>('/auth/register', body),

	/** Get OAuth2.0 login URL (Authorization Code + PKCE). */
	getOAuthLoginUrl: () => client.get<LoginUrlResponse>('/auth/oauth/login'),

	/** OAuth2.0 callback: exchange code for local JWT. */
	oauthCallback: async (code: string, state: string): Promise<TokenResponse> => {
		const tokens = await client.post<TokenResponse>('/auth/callback', {
			code,
			state,
		});

		// Persist tokens
		localStorage.setItem('access_token', tokens.access_token);
		localStorage.setItem('refresh_token', tokens.refresh_token);
		localStorage.setItem(
			'user_info',
			JSON.stringify({
				user_id: tokens.user_id,
				username: tokens.username,
				role: tokens.role,
			}),
		);
		localStorage.setItem('username', tokens.username);

		return tokens;
	},

	/** Log out: call the backend endpoint then clear all auth state. */
	logout: async () => {
		try {
			await client.post<void>('/auth/logout', undefined, undefined, {
				silent: true,
			});
		} catch {
			// Network errors are fine — we still clear local state.
		}
		localStorage.removeItem('access_token');
		localStorage.removeItem('refresh_token');
		localStorage.removeItem('user_info');
		localStorage.removeItem('username');
	},

	/** Get stored user info (without an API call). */
	getStoredUser: (): { user_id: string; username: string; role: string } | null => {
		const raw = localStorage.getItem('user_info');
		if (!raw) return null;
		try {
			return JSON.parse(raw);
		} catch {
			return null;
		}
	},
};
