import { CircleAlert, Loader2, Rocket } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { publishApi } from '@/api/publish';
import type { JSONSchema } from '@/api/types';
import { Alert, AlertDescription } from '@/components/ui/alert.tsx';
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
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field.tsx';
import { Textarea } from '@/components/ui/textarea';
import { formatApiErrorForAlert } from '@/lib/api-error';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agentId: string;
	agentName: string;
	onPublished?: () => void;
}

const DEFAULT_INPUT_SCHEMA = `{
  "properties": {
    "input": {
      "type": "string",
      "title": "输入内容",
      "description": "请输入任务内容"
    }
  },
  "required": ["input"]
}`;

/**
 * Publish agent dialog — lets a developer publish an agent with
 * release notes, execution mode, and optional input schema.
 */
export function PublishAgentDialog({
	open,
	onOpenChange,
	agentId,
	agentName,
	onPublished,
}: Props) {
	const [releaseNotes, setReleaseNotes] = useState('');
	const [executionMode, setExecutionMode] = useState<'chat' | 'task'>('chat');
	const [inputSchemaText, setInputSchemaText] = useState(DEFAULT_INPUT_SCHEMA);
	const [submitting, setSubmitting] = useState(false);
	const [errorMsg, setErrorMsg] = useState('');

	useEffect(() => {
		if (!open) {
			setReleaseNotes('');
			setExecutionMode('chat');
			setInputSchemaText(DEFAULT_INPUT_SCHEMA);
			setErrorMsg('');
		}
	}, [open]);

	const handleSubmit = async () => {
		if (!releaseNotes.trim()) {
			setErrorMsg('请填写发布内容');
			return;
		}

		let inputSchema: JSONSchema | null = null;
		if (executionMode === 'task') {
			try {
				inputSchema = JSON.parse(inputSchemaText);
			} catch {
				setErrorMsg('input_schema 不是有效的 JSON');
				return;
			}
		}

		setSubmitting(true);
		setErrorMsg('');
		try {
			const result = await publishApi.publish(agentId, {
				release_notes: releaseNotes,
				execution_mode: executionMode,
				input_schema: inputSchema,
			});
			toast.success(`发布成功！版本号: ${result.version}`);
			onPublished?.();
			onOpenChange(false);
		} catch (e) {
			setErrorMsg(formatApiErrorForAlert(e));
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-lg">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						<Rocket className="size-4" />
						发布智能体
					</DialogTitle>
					<DialogDescription>
						发布「{agentName}」供终端用户使用
					</DialogDescription>
				</DialogHeader>

				<FieldGroup>
					<Field>
						<FieldLabel htmlFor="release-notes">
							发布内容 <span className="text-destructive">*</span>
						</FieldLabel>
						<Textarea
							id="release-notes"
							rows={3}
							value={releaseNotes}
							onChange={(e) => setReleaseNotes(e.target.value)}
							placeholder="描述本次发布的更新内容..."
						/>
						<FieldDescription>支持 Markdown 格式，将展示在版本历史中</FieldDescription>
					</Field>

					<Field>
						<FieldLabel>执行模式</FieldLabel>
						<div className="flex gap-2">
							<Button
								variant={executionMode === 'chat' ? 'default' : 'outline'}
								size="sm"
								onClick={() => setExecutionMode('chat')}
							>
								对话模式
							</Button>
							<Button
								variant={executionMode === 'task' ? 'default' : 'outline'}
								size="sm"
								onClick={() => setExecutionMode('task')}
							>
								任务模式
							</Button>
						</div>
						<FieldDescription>
							{executionMode === 'chat'
								? '用户与智能体自由对话'
								: '用户填写预定义表单，智能体根据参数执行任务'}
						</FieldDescription>
					</Field>

					{executionMode === 'task' && (
						<Field>
							<FieldLabel htmlFor="input-schema">
								输入参数定义 (JSON Schema)
							</FieldLabel>
							<Textarea
								id="input-schema"
								rows={8}
								value={inputSchemaText}
								onChange={(e) => setInputSchemaText(e.target.value)}
								className="font-mono text-xs"
								placeholder={DEFAULT_INPUT_SCHEMA}
							/>
							<FieldDescription>
								定义任务模式下用户需要填写的表单字段
							</FieldDescription>
						</Field>
					)}

					{errorMsg && (
						<Alert variant="destructive">
							<CircleAlert />
							<AlertDescription>{errorMsg}</AlertDescription>
						</Alert>
					)}
				</FieldGroup>

				<DialogFooter>
					<Button variant="outline" onClick={() => onOpenChange(false)}>
						取消
					</Button>
					<Button onClick={handleSubmit} disabled={submitting}>
						{submitting && <Loader2 className="size-3.5 animate-spin" />}
						{submitting ? '发布中...' : '发布'}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
