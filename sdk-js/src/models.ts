export type AgentRole = 'orchestrator' | 'researcher' | 'planner' | 'executor' | 'reviewer' | 'validator';
export type EdgeType = 'delegation' | 'collaboration' | 'sequential';
export type AlertLevel = 'green' | 'yellow' | 'red';

export interface Node {
  agentId: string;
  agentRole: AgentRole;
  content: string;
  inputText?: string;
  parentIndex?: number;
  edgeType?: EdgeType;
}

export interface GraphResult {
  graphId: string;
  alert: AlertLevel;
  scs?: number;
  cahs?: number;
  ppi?: number;
  nodesCount: number;
}

export interface Graph {
  graphId: string;
  alert: AlertLevel;
  createdAt: string;
  nodesCount: number;
  scs?: number;
}

export interface AgentProfile {
  agentId: string;
  scsTrend?: string;
  cahsTrend?: string;
  totalGraphs: number;
  alertDistribution: Record<string, number>;
  lastSeen?: string;
}
