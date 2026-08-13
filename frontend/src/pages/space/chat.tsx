import { useParams } from 'react-router-dom';

import { ChatViewport } from '@/pages/chat/ChatViewport';
import { SidebarProvider } from '@/components/ui/sidebar';

/**
 * Space chat page — simplified chat for end users.
 *
 * Reuses the existing ChatViewport. Developer-specific panels are
 * hidden via conditional rendering based on the user's role
 * (handled in Phase 5).
 */
export function SpaceChatPage() {
	const { agentId, sessionId } = useParams<{ agentId: string; sessionId?: string }>();

	return (
		<SidebarProvider>
			<div className="h-screen">
				<ChatViewport
					agentId={agentId ?? null}
					sessionId={sessionId ?? null}
				/>
			</div>
		</SidebarProvider>
	);
}
