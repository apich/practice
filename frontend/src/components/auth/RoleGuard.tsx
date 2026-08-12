import type { ReactNode } from 'react';

import { useAuth } from '@/hooks/useAuth';

interface Props {
	children: ReactNode;
	roles: string[];
	/** Content to show when the role doesn't match (default: null). */
	fallback?: ReactNode;
}

/**
 * Role guard component — conditionally renders children based on role.
 *
 * Unlike ProtectedRoute, this does NOT redirect — it just hides content.
 * Useful for showing/hiding UI elements within a shared layout.
 *
 * ```tsx
 * <RoleGuard roles={['developer']}>
 *   <AdminOnlyButton />
 * </RoleGuard>
 * ```
 */
export function RoleGuard({ children, roles, fallback = null }: Props) {
	const { user } = useAuth();

	if (!user || !roles.includes(user.role)) {
		return <>{fallback}</>;
	}

	return <>{children}</>;
}
