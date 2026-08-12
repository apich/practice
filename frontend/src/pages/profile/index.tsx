import { LogOut, UserRound } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar.tsx';
import { Badge } from '@/components/ui/badge.tsx';
import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import { useAuth } from '@/hooks/useAuth.ts';
import { useTranslation } from '@/i18n/useI18n.ts';
import { avatarTint } from '@/utils/common';

export function ProfilePage() {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const { user, logout } = useAuth();

	if (!user) return null;

	const handleLogout = async () => {
		await logout();
		navigate('/login', { replace: true });
	};

	return (
		<div className="flex size-full items-center justify-center p-6">
			<Card className="w-full max-w-md">
				<CardHeader className="text-center">
					<div className="mx-auto mb-3">
						<Avatar className="size-16">
							<AvatarImage src={undefined} alt={user.username} />
							<AvatarFallback
								className="text-lg"
								style={avatarTint(user.user_id)}
							>
								{user.username.slice(0, 1).toUpperCase()}
							</AvatarFallback>
						</Avatar>
					</div>
					<CardTitle className="text-xl">{user.username}</CardTitle>
					<CardDescription>{t('profile.subtitle')}</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="space-y-4">
						<div className="flex items-center justify-between rounded-lg bg-muted px-4 py-3">
							<span className="text-sm text-muted-foreground">
								{t('profile.userId')}
							</span>
							<span className="font-mono text-sm">{user.user_id}</span>
						</div>
						<div className="flex items-center justify-between rounded-lg bg-muted px-4 py-3">
							<span className="text-sm text-muted-foreground">
								{t('profile.username')}
							</span>
							<span className="text-sm font-medium">{user.username}</span>
						</div>
						<div className="flex items-center justify-between rounded-lg bg-muted px-4 py-3">
							<span className="text-sm text-muted-foreground">
								{t('profile.role')}
							</span>
							<Badge
								variant={
									user.role === 'developer' ? 'default' : 'secondary'
								}
							>
								<UserRound className="mr-1 size-3" />
								{user.role === 'developer'
									? t('profile.roleDeveloper')
									: t('profile.roleEndUser')}
							</Badge>
						</div>
					</div>
					<Button
						variant="destructive"
						className="w-full mt-2"
						onClick={handleLogout}
					>
						<LogOut className="mr-2 size-4" />
						{t('profile.logout')}
					</Button>
				</CardContent>
			</Card>
		</div>
	);
}
