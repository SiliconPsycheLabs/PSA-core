export { PSAClient, PSAError } from './client';
export type { PSAClientConfig } from './client';
export type { Node, GraphResult, Graph, AgentProfile, AgentRole, EdgeType, AlertLevel } from './models';

import { PSAClient } from './client';
import type { Node, GraphResult, Graph, AgentProfile, AlertLevel } from './models';

let _default: PSAClient | null = null;

function getDefault(): PSAClient {
  if (!_default) _default = new PSAClient();
  return _default;
}

export function trace(nodes: Node[]): Promise<GraphResult> {
  return getDefault().trace(nodes);
}

export function query(options?: { alert?: AlertLevel; limit?: number; page?: number }): Promise<Graph[]> {
  return getDefault().query(options);
}

export function profile(agentId: string): Promise<AgentProfile> {
  return getDefault().profile(agentId);
}
