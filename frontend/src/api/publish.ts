import { client } from './client';
import type {
	PublishRequest,
	PublishResponse,
	PublishedAgentDetail,
	AgentVersion,
	AgentVersionDetail,
	ExecuteResponse,
} from './types';

/**
 * Publish API — agent publication and version management.
 *
 * Endpoints for publishing agents, managing versions, and executing
 * task-mode agents.
 */
export const publishApi = {
	/** Publish or update an agent (developer only). */
	publish: (agentId: string, body: PublishRequest) =>
		client.post<PublishResponse>(`/publish/agent/${agentId}`, body),

	/** Unpublish an agent (developer only). */
	unpublish: (agentId: string) =>
		client.post<{ agent_id: string; published: boolean }>(
			`/unpublish/agent/${agentId}`,
		),

	/** List all published agents (visible to end users). */
	listPublished: () =>
		client.get<PublishedAgentDetail[]>('/publish/list'),

	/** List agents published by the current developer. */
	listMyPublished: () =>
		client.get<PublishedAgentDetail[]>('/publish/my'),

	/** Get a single published agent's details (including input_schema). */
	getPublished: (agentId: string) =>
		client.get<PublishedAgentDetail>(`/publish/${agentId}`),

	/** Get version history for an agent. */
	getVersions: (agentId: string) =>
		client.get<AgentVersion[]>(`/publish/${agentId}/versions`),

	/** Get details of a specific version. */
	getVersion: (agentId: string, version: string) =>
		client.get<AgentVersionDetail>(
			`/publish/${agentId}/versions/${version}`,
		),

	/** Rollback an agent to a specific version (developer only). */
	rollback: (agentId: string, version: string) =>
		client.post<{ agent_id: string; version: string; rolled_back: boolean }>(
			`/publish/${agentId}/rollback/${version}`,
		),

	/** Execute a task-mode agent with form parameters. */
	execute: (agentId: string, params: Record<string, unknown>) =>
		client.post<ExecuteResponse>(`/publish/${agentId}/execute`, {
			input: params,
		}),
};
