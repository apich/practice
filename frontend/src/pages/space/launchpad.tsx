import { ArrowLeft, Bot, Play } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { publishApi } from '@/api/publish';
import type { PublishedAgentDetail } from '@/api/types';
import { SchemaForm, defaultValuesFromSchema, type SchemaFormValue } from '@/components/form/SchemaForm';
import { Button } from '@/components/ui/button.tsx';
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from '@/components/ui/card.tsx';
import { FieldGroup } from '@/components/ui/field.tsx';

/**
 * Launchpad — start confirmation page.
 *
 * Chat mode: shows agent info + "Start Chat" button.
 * Task mode: renders a dynamic form from input_schema, submits to execute.
 */
export function LaunchpadPage() {
	const navigate = useNavigate();
	const { agentId } = useParams<{ agentId: string }>();
	const [agent, setAgent] = useState<PublishedAgentDetail | null>(null);
	const [loading, setLoading] = useState(true);
	const [formValues, setFormValues] = useState<Record<string, SchemaFormValue>>({});
	const [submitting, setSubmitting] = useState(false);

	// Fetch agent details on mount
	useState(() => {
		if (!agentId) return;
		publishApi
			.getPublished(agentId)
			.then((data) => {
				setAgent(data);
				if (data.input_schema) {
					setFormValues(defaultValuesFromSchema(data.input_schema));
				}
			})
			.catch(() => setAgent(null))
			.finally(() => setLoading(false));
	});

	const handleStartChat = async () => {
		if (!agentId) return;
		try {
			const { session_id: sessionId } = await publishApi.startChat(agentId);
			navigate(`/space/chat/${agentId}/${sessionId}`);
		} catch {
			// error handled by client
		}
	};

	const handleExecuteTask = async () => {
		if (!agentId) return;
		setSubmitting(true);
		try {
			const { session_id: sessionId } = await publishApi.execute(
				agentId,
				formValues as Record<string, unknown>,
			);
			navigate(`/space/chat/${agentId}/${sessionId}`);
		} catch {
			// error handled by client
		} finally {
			setSubmitting(false);
		}
	};

	if (loading) {
		return (
			<div className="h-screen flex items-center justify-center text-muted-fg">
				加载中...
			</div>
		);
	}

	if (!agent) {
		return (
			<div className="h-screen flex items-center justify-center text-muted-fg">
				未找到该智能体
			</div>
		);
	}

	return (
		<div className="h-screen flex flex-col bg-canvas">
			<header className="flex items-center gap-3 px-6 py-4 border-b">
				<Button variant="ghost" size="sm" onClick={() => navigate('/space')}>
					<ArrowLeft className="size-4" />
					返回
				</Button>
			</header>

			<main className="flex-1 overflow-auto p-6">
				<div className="max-w-2xl mx-auto">
					<Card>
						<CardHeader>
							<div className="flex items-center gap-3">
								<div className="flex items-center justify-center size-10 rounded-lg bg-primary/10">
									<Bot className="size-5 text-primary" />
								</div>
								<div>
									<CardTitle className="text-xl">{agent.agent_name}</CardTitle>
									<CardDescription>
										v{agent.current_version} ·{' '}
										{agent.execution_mode === 'task' ? '任务模式' : '对话模式'}
									</CardDescription>
								</div>
							</div>
						</CardHeader>
						<CardContent>
							{agent.agent_description && (
								<p className="text-sm text-muted-fg mb-6">
									{agent.agent_description}
								</p>
							)}

							{agent.execution_mode === 'chat' ? (
								<div className="flex flex-col items-center gap-4 py-8">
									<p className="text-sm text-muted-fg">
										点击下方按钮开始与智能体对话
									</p>
									<Button size="lg" onClick={handleStartChat}>
										<Play className="size-4" />
										开始对话
									</Button>
								</div>
							) : (
								<div>
									<h3 className="font-medium mb-4">填写任务参数</h3>
									<FieldGroup>
										{agent.input_schema && (
											<SchemaForm
												schema={agent.input_schema}
												values={formValues}
												onChange={(key, value) =>
													setFormValues((prev) => ({ ...prev, [key]: value }))
												}
												skipFields={new Set()}
											/>
										)}
									</FieldGroup>
									<div className="mt-6 flex justify-end">
										<Button size="lg" onClick={handleExecuteTask} disabled={submitting}>
											<Play className="size-4" />
											{submitting ? '执行中...' : '提交执行'}
										</Button>
									</div>
								</div>
							)}
						</CardContent>
					</Card>
				</div>
			</main>
		</div>
	);
}
