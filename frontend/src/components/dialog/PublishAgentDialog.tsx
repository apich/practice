import { CircleAlert, Code, Loader2, Plus, Rocket, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { publishApi } from '@/api/publish';
import type { JSONSchema } from '@/api/types';
import { Alert, AlertDescription } from '@/components/ui/alert.tsx';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field.tsx';
import { Input } from '@/components/ui/input';
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { formatApiErrorForAlert } from '@/lib/api-error';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agentId: string;
	agentName: string;
	onPublished?: () => void;
}

interface FormField {
	key: string;
	type: 'string' | 'number' | 'integer' | 'boolean';
	title: string;
	description: string;
	required: boolean;
}

const DEFAULT_FIELDS: FormField[] = [
	{
		key: 'input',
		type: 'string',
		title: '输入内容',
		description: '请输入任务内容',
		required: true,
	},
];

function fieldsToJsonSchema(fields: FormField[]): JSONSchema {
	const properties: JSONSchema['properties'] = {};
	const required: string[] = [];

	for (const f of fields) {
		if (!f.key.trim()) continue;
		const prop: Record<string, unknown> = { type: f.type };
		if (f.title.trim()) prop.title = f.title;
		if (f.description.trim()) prop.description = f.description;
		properties[f.key] = prop as JSONSchema['properties'][string];
		if (f.required) required.push(f.key);
	}

	return {
		properties,
		required: required.length > 0 ? required : undefined,
	};
}

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
	const [formFields, setFormFields] = useState<FormField[]>(DEFAULT_FIELDS);
	const [showJsonPreview, setShowJsonPreview] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [errorMsg, setErrorMsg] = useState('');

	useEffect(() => {
		if (!open) {
			setReleaseNotes('');
			setExecutionMode('chat');
			setFormFields(DEFAULT_FIELDS);
			setShowJsonPreview(false);
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
			inputSchema = fieldsToJsonSchema(formFields);
			if (Object.keys(inputSchema.properties).length === 0) {
				setErrorMsg('请至少添加一个输入参数');
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
			<DialogContent className="max-w-3xl sm:max-w-3xl">
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
						<>
							<Field>
								<div className="flex items-center justify-between mb-2">
									<FieldLabel>输入参数</FieldLabel>
									<Button
										type="button"
										variant="ghost"
										size="sm"
										className="h-6 text-xs gap-1"
										onClick={() =>
											setFormFields((prev) => [
												...prev,
												{
													key: '',
													type: 'string',
													title: '',
													description: '',
													required: false,
												},
											])
										}
									>
										<Plus className="size-3" />
										添加字段
									</Button>
								</div>
								<FieldDescription className="mb-3">
									定义任务模式下用户需要填写的表单字段
								</FieldDescription>

								{formFields.length === 0 && (
									<div className="text-center py-6 text-muted-fg">
										<p className="text-sm">暂无字段</p>
										<p className="text-xs mt-1">点击上方按钮添加输入参数</p>
									</div>
								)}

								<div className="max-h-52 overflow-y-auto space-y-2 pr-1">
									{formFields.map((field, idx) => (
										<div
											key={idx}
											className="rounded-lg border border-border bg-muted/20 px-3 py-2 transition-colors hover:bg-muted/40"
										>
											<div className="flex items-end gap-2">
												<div className="flex-1 min-w-0">
													<label className="text-xs font-medium text-foreground mb-1 block">
														字段名 <span className="text-destructive">*</span>
													</label>
													<Input
														value={field.key}
														onChange={(e) => {
															const next = [...formFields];
															next[idx] = { ...next[idx], key: e.target.value };
															setFormFields(next);
														}}
														placeholder="例如: input"
														className="h-7 text-xs"
													/>
												</div>
												<div className="w-24 shrink-0">
													<label className="text-xs font-medium text-foreground mb-1 block">
														类型
													</label>
													<Select
														value={field.type}
														onValueChange={(v) => {
															const next = [...formFields];
															next[idx] = {
																...next[idx],
																type: v as FormField['type'],
															};
															setFormFields(next);
														}}
													>
														<SelectTrigger className="h-7 text-xs w-full">
															<SelectValue />
														</SelectTrigger>
														<SelectContent>
															<SelectItem value="string">文本</SelectItem>
															<SelectItem value="number">数字</SelectItem>
															<SelectItem value="integer">整数</SelectItem>
															<SelectItem value="boolean">布尔</SelectItem>
														</SelectContent>
													</Select>
												</div>
												<div className="flex-1 min-w-0">
													<label className="text-xs font-medium text-foreground mb-1 block">
														显示标题
													</label>
													<Input
														value={field.title}
														onChange={(e) => {
															const next = [...formFields];
															next[idx] = { ...next[idx], title: e.target.value };
															setFormFields(next);
														}}
														placeholder="例如: 输入内容"
														className="h-7 text-xs"
													/>
												</div>
												<div className="flex-1 min-w-0">
													<label className="text-xs font-medium text-foreground mb-1 block">
														描述
													</label>
													<Input
														value={field.description}
														onChange={(e) => {
															const next = [...formFields];
															next[idx] = {
																...next[idx],
																description: e.target.value,
															};
															setFormFields(next);
														}}
														placeholder="字段说明"
														className="h-7 text-xs"
													/>
												</div>
												<div className="flex items-center gap-1 pb-0.5 shrink-0">
													<Checkbox
														id={`required-${idx}`}
														checked={field.required}
														onCheckedChange={(checked) => {
															const next = [...formFields];
															next[idx] = { ...next[idx], required: !!checked };
															setFormFields(next);
														}}
													/>
													<label
														htmlFor={`required-${idx}`}
														className="text-xs text-muted-fg cursor-pointer select-none"
													>
														必填
													</label>
												</div>
												<Button
													type="button"
													variant="ghost"
													size="sm"
													className="h-7 w-7 p-0 text-muted-fg hover:text-destructive shrink-0"
													onClick={() =>
														setFormFields((prev) => prev.filter((_, i) => i !== idx))
													}
												>
													<Trash2 className="size-3.5" />
												</Button>
											</div>
										</div>
									))}
								</div>

								<div className="flex justify-end mt-1">
									<Button
										type="button"
										variant="ghost"
										size="sm"
										className="text-xs gap-1 text-muted-fg"
										onClick={() => setShowJsonPreview((v) => !v)}
									>
										<Code className="size-3" />
										{showJsonPreview ? '隐藏' : '查看'} JSON Schema 预览
									</Button>
								</div>

								{showJsonPreview && (
									<Textarea
										readOnly
										rows={6}
										value={JSON.stringify(
											fieldsToJsonSchema(formFields),
											null,
											2,
										)}
										className="font-mono text-xs bg-muted/50"
									/>
								)}
							</Field>
						</>
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
