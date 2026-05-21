import type { Node, GraphResult, Graph, AgentProfile, AlertLevel } from './models';

export interface PSAClientConfig {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
}

function toSnake(node: Node): Record<string, unknown> {
  const out: Record<string, unknown> = {
    agent_id: node.agentId,
    agent_role: node.agentRole,
    content: node.content,
  };
  if (node.inputText !== undefined) out.input_text = node.inputText;
  if (node.parentIndex !== undefined) out.parent_index = node.parentIndex;
  if (node.edgeType !== undefined) out.edge_type = node.edgeType;
  return out;
}

export class PSAError extends Error {
  constructor(public status: number, message: string) {
    super(`PSA API error ${status}: ${message}`);
  }
}

export class PSAClient {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;
  private maxRetries: number;

  constructor(config: PSAClientConfig = {}) {
    this.apiKey = config.apiKey ?? process.env.PSA_API_KEY ?? '';
    this.baseUrl = (config.baseUrl ?? process.env.PSA_BASE_URL ?? 'https://splabs.io').replace(/\/$/, '');
    this.timeout = config.timeout ?? parseInt(process.env.PSA_TIMEOUT ?? '10', 10) * 1000;
    this.maxRetries = config.maxRetries ?? parseInt(process.env.PSA_MAX_RETRIES ?? '3', 10);

    if (!this.apiKey) throw new Error('PSA_API_KEY is required');
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
    };

    let lastError: Error | null = null;
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        const res = await fetch(url, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });
        clearTimeout(timer);

        if (res.status === 503 && attempt < this.maxRetries - 1) {
          await new Promise(r => setTimeout(r, 2 ** attempt * 1000));
          continue;
        }
        if (!res.ok) {
          throw new PSAError(res.status, await res.text());
        }
        const text = await res.text();
        return text ? JSON.parse(text) : ({} as T);
      } catch (e) {
        if (e instanceof PSAError) throw e;
        lastError = e as Error;
        if (attempt < this.maxRetries - 1) {
          await new Promise(r => setTimeout(r, 2 ** attempt * 1000));
        }
      }
    }
    throw new PSAError(0, `Request failed after ${this.maxRetries} attempts: ${lastError?.message}`);
  }

  async trace(nodes: Node[]): Promise<GraphResult> {
    const data = await this.request<Record<string, unknown>>('POST', '/api/v3/psa/graph', {
      nodes: nodes.map(toSnake),
    });
    return {
      graphId: String(data.graph_id ?? ''),
      alert: (data.alert as AlertLevel) ?? 'green',
      scs: data.scs as number | undefined,
      cahs: data.cahs as number | undefined,
      ppi: data.ppi as number | undefined,
      nodesCount: nodes.length,
    };
  }

  async query(options: { alert?: AlertLevel; limit?: number; page?: number } = {}): Promise<Graph[]> {
    const params = new URLSearchParams();
    params.set('page', String(options.page ?? 1));
    params.set('per_page', String(options.limit ?? 20));
    if (options.alert) params.set('alert', options.alert);

    const data = await this.request<{ items?: unknown[] } | unknown[]>('GET', `/api/v3/psa/graphs?${params}`);
    const items = Array.isArray(data) ? data : (data as { items?: unknown[] }).items ?? [];
    return (items as Record<string, unknown>[]).map(g => ({
      graphId: String(g.graph_id ?? g.id ?? ''),
      alert: (g.alert as AlertLevel) ?? 'green',
      createdAt: String(g.created_at ?? ''),
      nodesCount: Number(g.nodes_count ?? 0),
      scs: g.scs as number | undefined,
    }));
  }

  async profile(agentId: string): Promise<AgentProfile> {
    const data = await this.request<Record<string, unknown>>('GET', `/api/v3/psa/agent/${agentId}/profile`);
    return {
      agentId,
      scsTrend: data.scs_trend as string | undefined,
      cahsTrend: data.cahs_trend as string | undefined,
      totalGraphs: Number(data.total_graphs ?? 0),
      alertDistribution: (data.alert_distribution ?? {}) as Record<string, number>,
      lastSeen: data.last_seen as string | undefined,
    };
  }
}
