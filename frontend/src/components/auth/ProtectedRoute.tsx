import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';

import { useAuth } from '@/hooks/useAuth';

interface Props {
	children?: ReactNode;
	/** If provided, only these roles can access. Others get redirected. */
	roles?: string[];
	/** Where to redirect when unauthenticated. Default: /login */
	redirectTo?: string;
	/** Where to redirect when role doesn't match. Default: / (role-based home) */
	roleMismatchRedirect?: string;
}

/**
 * Route guard — blocks unauthenticated users and optionally enforces roles.
 *
 * Usage in route definitions:
 *
 * ```tsx
 * <Route element={<ProtectedRoute roles={['developer']} />}>
 *   <Route path="/admin/*" element={<AdminLayout />} />
 * </Route>
 * ```
 */
	export function ProtectedRoute({
		children,
		roles,
		redirectTo = '/login',
		roleMismatchRedirect,
	}: Props) {
		const { user, loading, isAuthenticated } = useAuth();
		const location = useLocation();

		if (loading) {
			// Still checking auth state — show nothing to avoid flash
			return null;
		}

		if (!isAuthenticated || !user) {
			return <Navigate to={redirectTo} state={{ from: location }} replace />;
		}

		if (roles && !roles.includes(user.role)) {
			// Role mismatch — redirect to role-appropriate home
			const fallback =
				roleMismatchRedirect ??
				(user.role === 'developer' ? '/admin/chat' : '/space');
			return <Navigate to={fallback} replace />;
		}

		return <>{children ?? <Outlet />}</>;
	}
