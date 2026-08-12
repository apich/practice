import { ArrowLeft, RotateCcw } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button.tsx';
import { ChatViewport } from '@/pages/chat/ChatViewport';

/**
 * Task result page — shows task execution result with option to
 * continue chatting or resubmit the form.
 *
 * The agent's response is visible in the ChatViewport (the session
 * already has the task result as the first exchange). A header bar
 * provides "resubmit" (back to launchpad) and "back to list" actions.
 */
export function TaskResultPage() {
	const { agentId, sessionId } = useParams<{ agentId: string; sessionId?: string }>();
	const navigate = useNavigate();

	return (
		<div className="h-screen flex flex-col">
			{/* Action bar */}
			<header className="flex items-center justify-between px-4 py-2 border-b bg-canvas">
				<Button
					variant="ghost"
					size="sm"
					onClick={() => navigate('/space')}
				>
					<ArrowLeft className="size-4" />
					返回列表
				</Button>
				<Button
					variant="ghost"
					size="sm"
					onClick={() => navigate(`/space/launchpad/${agentId}`)}
				>
					<RotateCcw className="size-4" />
					重新提交
				</Button>
			</header>

			{/* Chat content */}
			<div className="flex-1 overflow-hidden">
				<ChatViewport
					agentId={agentId ?? null}
					sessionId={sessionId ?? null}
				/>
			</div>
		</div>
	);
}
