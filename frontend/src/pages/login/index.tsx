import { CircleAlert, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import { Alert, AlertDescription } from '@/components/ui/alert.tsx';
import { Button } from '@/components/ui/button.tsx';
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from '@/components/ui/card.tsx';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field.tsx';
import { Input } from '@/components/ui/input.tsx';
import { useAuth } from '@/hooks/useAuth.ts';
import { useTranslation } from '@/i18n/useI18n.ts';

interface LocationState {
	from?: { pathname: string };
}

export function LoginPage() {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const location = useLocation();
	const { login } = useAuth();

	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [loading, setLoading] = useState(false);
	const [errorMsg, setErrorMsg] = useState('');

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setLoading(true);
		setErrorMsg('');

		try {
			// Perform login via AuthProvider to update auth state
			const user = await login(username, password);

			// Redirect based on role or to the originally requested page
			const from = (location.state as LocationState)?.from?.pathname;
			if (from && from !== '/login') {
				navigate(from, { replace: true });
			} else if (user.role === 'developer') {
				navigate('/admin/chat', { replace: true });
			} else {
				navigate('/space', { replace: true });
			}
		} catch (err) {
			if (err instanceof Error) {
				const msg = err.message.toLowerCase();
				if (msg.includes('401') || msg.includes('unauthorized') || msg.includes('incorrect')) {
					setErrorMsg(t('login.errorInvalidCredentials'));
				} else if (msg.includes('fetch') || msg.includes('network') || msg.includes('connect')) {
					setErrorMsg(t('login.errorNetwork'));
				} else {
					setErrorMsg(err.message);
				}
			} else {
				setErrorMsg(t('login.errorInvalidCredentials'));
			}
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex items-center justify-center min-h-screen bg-canvas">
			<div className="flex flex-col gap-6 w-full max-w-sm px-4">
				<Card>
					<CardHeader>
						<CardTitle className="text-xl">{t('login.title')}</CardTitle>
						<CardDescription>{t('login.subtitle')}</CardDescription>
					</CardHeader>
					<CardContent>
						<form onSubmit={handleSubmit}>
							<FieldGroup>
								<Field>
									<FieldLabel htmlFor="login-username">
										{t('login.username')}
									</FieldLabel>
									<Input
										id="login-username"
										type="text"
										placeholder={t('login.usernamePlaceholder')}
										value={username}
										onChange={(e) => setUsername(e.target.value)}
										required
										autoFocus
									/>
								</Field>
								<Field>
									<FieldLabel htmlFor="login-password">
										{t('login.password')}
									</FieldLabel>
									<Input
										id="login-password"
										type="password"
										placeholder={t('login.passwordPlaceholder')}
										value={password}
										onChange={(e) => setPassword(e.target.value)}
										required
									/>
								</Field>
								{errorMsg && (
									<Alert variant="destructive">
										<CircleAlert />
										<AlertDescription>{errorMsg}</AlertDescription>
									</Alert>
								)}
								<Field>
									<Button type="submit" className="w-full" disabled={loading}>
										{loading && <Loader2 className="size-3.5 animate-spin" />}
										{loading ? t('login.loggingIn') : t('login.submit')}
									</Button>
								</Field>
							</FieldGroup>
						</form>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
