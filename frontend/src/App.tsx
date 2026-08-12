import { Onborda, OnbordaProvider } from 'onborda';
import { useMemo } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { Toaster } from 'sonner';

import { MCPHubPage } from './pages/mcp';
import { SkillHubPage } from './pages/skill';
import { RouteError } from '@/components/error/RouteError';
import { AppLayout } from '@/components/layout/AppLayout';
import { AuthProvider } from '@/components/auth/AuthProvider';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { buildChatTour } from '@/components/tour/chatTourSteps';
import { TourCard } from '@/components/tour/TourCard';
import { UploadProvider } from '@/context/UploadContext';
import { useTranslation } from '@/i18n/useI18n';
import { ChannelPage } from '@/pages/channel';
import { ChatPage } from '@/pages/chat';
import { CredentialPage } from '@/pages/credential';
import { KnowledgePage } from '@/pages/knowledge';
import { LoginPage } from '@/pages/login';
import { ProfilePage } from '@/pages/profile';
import { SchedulePage } from '@/pages/schedule';
import { SpacePage } from '@/pages/space';
import { LaunchpadPage } from '@/pages/space/launchpad';
import { SpaceChatPage } from '@/pages/space/chat';
import { TaskResultPage } from '@/pages/space/task';



const router = createBrowserRouter([
	// ── Public routes ────────────────────────────────────────────────────
	{ path: '/login', element: <LoginPage />, errorElement: <RouteError /> },

	// ── Admin routes (developer only) ───────────────────────────────────
	{
		element: <ProtectedRoute roles={['developer']} />,
		errorElement: <RouteError />,
		children: [
			{
				element: <AppLayout />,
				children: [
					{
						errorElement: <RouteError />,
						children: [
							{ path: '/admin', element: <Navigate to="/admin/chat" replace /> },
							{
								path: '/admin/chat/:agentId?/:sessionId?/:memberId?',
								element: <ChatPage />,
							},
							{ path: '/admin/schedule', element: <SchedulePage /> },
							{ path: '/admin/channel', element: <ChannelPage /> },
							{ path: '/admin/credential', element: <CredentialPage /> },
							{ path: '/admin/mcp', element: <MCPHubPage /> },
							{ path: '/admin/mcp/:hubId', element: <MCPHubPage /> },
							{ path: '/admin/skill', element: <SkillHubPage /> },
							{ path: '/admin/skill/:hubId', element: <SkillHubPage /> },
							{ path: '/admin/knowledge', element: <KnowledgePage /> },
							{ path: '/admin/knowledge/:kbId', element: <KnowledgePage /> },
							{ path: '/profile', element: <ProfilePage /> },
						],
					},
				],
			},
		],
	},

	// ── Space routes (end_user, developer can also access) ──────────────
	{
		element: <ProtectedRoute roles={['end_user', 'developer']} />,
		errorElement: <RouteError />,
		children: [
			{ path: '/space', element: <SpacePage /> },
			{ path: '/space/launchpad/:agentId', element: <LaunchpadPage /> },
			{ path: '/space/chat/:agentId/:sessionId?', element: <SpaceChatPage /> },
			{ path: '/space/task/:agentId/:sessionId?', element: <TaskResultPage /> },
		],
	},

	// ── Root redirect (auth-aware, handled by ProtectedRoute) ───────────
	// If authenticated as developer → /admin/chat
	// If authenticated as end_user → /space
	// If not authenticated → /login (via ProtectedRoute redirect)
	{
		path: '/',
		element: <ProtectedRoute roles={['developer']} />,
		errorElement: <RouteError />,
		children: [
			{ path: '/', element: <Navigate to="/admin/chat" replace /> },
		],
	},
	{
		path: '/',
		element: <ProtectedRoute roles={['end_user']} />,
		errorElement: <RouteError />,
		children: [
			{ path: '/', element: <Navigate to="/space" replace /> },
		],
	},
]);

function App() {
	const { t } = useTranslation();
	const tours = useMemo(() => [buildChatTour(t)], [t]);

	return (
		<AuthProvider>
			<OnbordaProvider>
				<Onborda
					steps={tours}
					cardComponent={TourCard}
					shadowOpacity="0.6"
					cardTransition={{ type: 'spring', duration: 0.4 }}
				>
					<UploadProvider>
						<RouterProvider router={router} />
					</UploadProvider>
					<Toaster richColors position="top-right" />
				</Onborda>
			</OnbordaProvider>
		</AuthProvider>
	);
}

export default App;
