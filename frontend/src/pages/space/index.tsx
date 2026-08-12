import { Bot, MessageSquare, Search } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { publishApi } from '@/api/publish';
import type { PublishedAgentDetail } from '@/api/types';
import { Badge } from '@/components/ui/badge.tsx';
import { Button } from '@/components/ui/button.tsx';
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from '@/components/ui/card.tsx';
import { Input } from '@/components/ui/input.tsx';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from '@/i18n/useI18n';

/**
 * Space home — agent marketplace for end users.
 *
 * Shows published agents as cards. Clicking a card navigates to the
 * launchpad page where the user can start a chat or fill a task form.
 */
export function SpacePage() {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const { user, logout } = useAuth();
	const [agents, setAgents] = useState<PublishedAgentDetail[]>([]);
	const [loading, setLoading] = useState(true);
	const [search, setSearch] = useState('');

	// Fetch published agents on mount
	useState(() => {
		publishApi
			.listPublished()
			.then((data) => setAgents(data))
			.catch(() => setAgents([]))
			.finally(() => setLoading(false));
	});

	const filtered = agents.filter(
		(a) =>
			!search ||
			a.agent_name.toLowerCase().includes(search.toLowerCase()) ||
			a.agent_description.toLowerCase().includes(search.toLowerCase()),
	);

	return (
		<div className="h-screen flex flex-col bg-canvas">
			{/* Header */}
			<header className="flex items-center justify-between px-6 py-4 border-b">
				<div className="flex items-center gap-2">
					<Bot className="size-5" />
					<h1 className="text-lg font-semibold">{t('common.chat')}</h1>
				</div>
				<div className="flex items-center gap-3">
					<span className="text-sm text-muted-fg">{user?.username}</span>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => {
							logout();
							navigate('/login');
						}}
					>
						{t('common.settings')}
					</Button>
				</div>
			</header>

			{/* Content */}
			<main className="flex-1 overflow-auto p-6">
				<div className="max-w-4xl mx-auto">
					{/* Search */}
					<div className="relative mb-6">
						<Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-fg" />
						<Input
							placeholder="搜索智能体..."
							value={search}
							onChange={(e) => setSearch(e.target.value)}
							className="pl-10"
						/>
					</div>

					{/* Agent grid */}
					{loading ? (
						<div className="text-center text-muted-fg py-12">加载中...</div>
					) : filtered.length === 0 ? (
						<div className="text-center text-muted-fg py-12">
							{search ? '未找到匹配的智能体' : '暂无已发布的智能体'}
						</div>
					) : (
						<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
							{filtered.map((agent) => (
								<Card
									key={agent.agent_id}
									className="cursor-pointer hover:border-primary/50 transition-colors"
									onClick={() =>
										navigate(`/space/launchpad/${agent.agent_id}`)
									}
								>
									<CardHeader>
										<div className="flex items-start justify-between">
											<CardTitle className="text-base">
												{agent.agent_name}
											</CardTitle>
											<Badge
												variant={
													agent.execution_mode === 'task'
														? 'secondary'
														: 'default'
												}
											>
												{agent.execution_mode === 'task'
													? '任务'
													: '对话'}
											</Badge>
										</div>
										<CardDescription className="line-clamp-2">
											{agent.agent_description || '暂无描述'}
										</CardDescription>
									</CardHeader>
									<CardContent>
										<div className="flex items-center justify-between text-xs text-muted-fg">
											<span>v{agent.current_version}</span>
											<span className="flex items-center gap-1">
												<MessageSquare className="size-3" />
												{t('common.chat')}
											</span>
										</div>
									</CardContent>
								</Card>
							))}
						</div>
					)}
				</div>
			</main>
		</div>
	);
}
