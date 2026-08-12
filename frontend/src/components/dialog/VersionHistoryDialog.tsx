import { History, Loader2, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { publishApi } from '@/api/publish';
import type { AgentVersion } from '@/api/types';
import { Badge } from '@/components/ui/badge.tsx';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import {
	Drawer,
	DrawerContent,
	DrawerHeader,
	DrawerTitle,
} from '@/components/ui/drawer';
import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/utils';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agentId: string;
	agentName: string;
}

/**
 * Version history dialog/drawer — shows a timeline of all published
 * versions with rollback capability.
 *
 * On desktop: a dialog. On mobile: a drawer.
 */
export function VersionHistoryDialog({
	open,
	onOpenChange,
	agentId,
	agentName,
}: Props) {
	const isMobile = useIsMobile();
	const [versions, setVersions] = useState<AgentVersion[]>([]);
	const [loading, setLoading] = useState(false);
	const [rollbackTarget, setRollbackTarget] = useState<AgentVersion | null>(null);
	const [rollingBack, setRollingBack] = useState(false);

	useEffect(() => {
		if (!open || !agentId) return;
		setLoading(true);
		publishApi
			.getVersions(agentId)
			.then((data) => setVersions(data))
			.catch(() => setVersions([]))
			.finally(() => setLoading(false));
	}, [open, agentId]);

	const handleRollback = async () => {
		if (!rollbackTarget) return;
		setRollingBack(true);
		try {
			await publishApi.rollback(agentId, rollbackTarget.version);
			toast.success(`已回滚到版本 ${rollbackTarget.version}`);
			setRollbackTarget(null);
			// Refresh version list
			const data = await publishApi.getVersions(agentId);
			setVersions(data);
		} catch (e) {
			toast.error('回滚失败');
		} finally {
			setRollingBack(false);
		}
	};

	const renderTimeline = () => (
		<div className="space-y-4">
			{loading ? (
				<div className="flex items-center justify-center py-8 text-muted-fg">
					<Loader2 className="size-4 animate-spin" />
					<span className="ml-2">加载中...</span>
				</div>
			) : versions.length === 0 ? (
				<div className="text-center text-muted-fg py-8">暂无版本历史</div>
			) : (
				versions.map((v, idx) => (
					<div
						key={v.id}
						className={cn(
							'relative pl-6 pb-4',
							idx < versions.length - 1 && 'border-l border-border',
						)}
						style={{ marginLeft: '-1px' }}
					>
						{/* Timeline dot */}
						<div
							className={cn(
								'absolute left-0 top-0 size-3 rounded-full border-2',
								v.is_current
									? 'bg-primary border-primary'
									: 'bg-background border-muted-fg',
							)}
						/>

						<div className="flex items-start justify-between gap-2">
							<div className="flex-1">
								<div className="flex items-center gap-2 mb-1">
									<code className="text-xs font-mono font-medium">
										{v.version}
									</code>
									<Badge variant={v.execution_mode === 'task' ? 'secondary' : 'default'}>
										{v.execution_mode === 'task' ? '任务' : '对话'}
									</Badge>
									{v.is_current && (
										<Badge variant="outline">当前</Badge>
									)}
								</div>
								<p className="text-xs text-muted-fg mb-1">
									{new Date(v.published_at).toLocaleString()}
								</p>
								<p className="text-sm whitespace-pre-wrap">{v.release_notes}</p>
							</div>
							{!v.is_current && (
								<Button
									variant="ghost"
									size="sm"
									onClick={() => setRollbackTarget(v)}
									className="shrink-0"
								>
									<RotateCcw className="size-3" />
									回滚
								</Button>
							)}
						</div>
					</div>
				))
			)}
		</div>
	);

	const renderRollbackConfirm = () => (
		<Dialog open={!!rollbackTarget} onOpenChange={(v) => !v && setRollbackTarget(null)}>
			<DialogContent className="max-w-sm">
				<DialogHeader>
					<DialogTitle>确认回滚</DialogTitle>
					<DialogDescription>
						确定要回滚到版本{' '}
						<code className="font-mono font-medium">
							{rollbackTarget?.version}
						</code>
						{' '}吗？此操作将使该版本成为当前活跃版本。
					</DialogDescription>
				</DialogHeader>
				<DialogFooter>
					<Button variant="outline" onClick={() => setRollbackTarget(null)}>
						取消
					</Button>
					<Button onClick={handleRollback} disabled={rollingBack}>
						{rollingBack && <Loader2 className="size-3.5 animate-spin" />}
						确认回滚
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);

	if (isMobile) {
		return (
			<>
				<Drawer open={open} onOpenChange={onOpenChange}>
					<DrawerContent>
						<DrawerHeader>
							<DrawerTitle className="flex items-center gap-2">
								<History className="size-4" />
								版本历史 — {agentName}
							</DrawerTitle>
						</DrawerHeader>
						<div className="p-4 overflow-auto">
							{renderTimeline()}
						</div>
					</DrawerContent>
				</Drawer>
				{renderRollbackConfirm()}
			</>
		);
	}

	return (
		<>
			<Dialog open={open} onOpenChange={onOpenChange}>
				<DialogContent className="max-w-lg max-h-[80vh] overflow-auto">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<History className="size-4" />
							版本历史
						</DialogTitle>
						<DialogDescription>{agentName}</DialogDescription>
					</DialogHeader>
					{renderTimeline()}
				</DialogContent>
			</Dialog>
			{renderRollbackConfirm()}
		</>
	);
}
