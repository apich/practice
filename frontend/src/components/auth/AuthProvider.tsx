import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { authApi } from '@/api/auth';
import { getAccessToken } from '@/api/client';

export interface AuthUser {
	user_id: string;
	username: string;
	role: 'developer' | 'end_user' | string;
}

export interface AuthContextValue {
	user: AuthUser | null;
	loading: boolean;
	isAuthenticated: boolean;
	login: (username: string, password: string) => Promise<AuthUser>;
	logout: () => void;
	refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface Props {
	children: ReactNode;
}

/**
 * Auth provider — manages authentication state globally.
 *
 * On mount, checks localStorage for a stored token and user. If a token
 * exists but user info doesn't (e.g. after a page refresh), fetches the
 * user from `/auth/me`.
 */
export function AuthProvider({ children }: Props) {
	const [user, setUser] = useState<AuthUser | null>(() =>
		authApi.getStoredUser(),
	);
	const [loading, setLoading] = useState(true);

	// On mount: resolve the current user from JWT
	useEffect(() => {
		const token = getAccessToken();

		if (token) {
			// JWT path — use stored user info or fetch from /auth/me
			const stored = authApi.getStoredUser();
			if (stored) {
				setUser(stored);
				setLoading(false);
				return;
			}

			authApi
				.me()
				.then((info) => {
					const u: AuthUser = {
						user_id: info.user_id,
						username: info.username,
						role: info.role,
					};
					setUser(u);
					localStorage.setItem('user_info', JSON.stringify(u));
				})
				.catch(() => {
					authApi.logout();
					setUser(null);
				})
				.finally(() => setLoading(false));
			return;
		}

		// No token — user needs to log in
		setLoading(false);
	}, []);

	const login = useCallback(async (username: string, password: string) => {
		const tokens = await authApi.login(username, password);
		const u: AuthUser = {
			user_id: tokens.user_id,
			username: tokens.username,
			role: tokens.role,
		};
		setUser(u);
		return u;
	}, []);

	const logout = useCallback(async () => {
		await authApi.logout();
		setUser(null);
	}, []);

	const refreshUser = useCallback(async () => {
		const info = await authApi.me();
		setUser({
			user_id: info.user_id,
			username: info.username,
			role: info.role,
		});
	}, []);

	const value = useMemo<AuthContextValue>(
		() => ({
			user,
			loading,
			isAuthenticated: !!user,
			login,
			logout,
			refreshUser,
		}),
		[user, loading, login, logout, refreshUser],
	);

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
