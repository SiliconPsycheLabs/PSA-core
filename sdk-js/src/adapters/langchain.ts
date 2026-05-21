/**
 * LangChain.js adapter — PSACallbackHandler auto-submits a trace on chain completion.
 *
 * Usage:
 *   import { PSACallbackHandler } from '@psa/sdk/adapters/langchain';
 *   const handler = new PSACallbackHandler({ agentId: 'my-agent' });
 *   await chain.invoke({ input: '...' }, { callbacks: [handler] });
 */
import { PSAClient } from '../client';
import type { Node } from '../models';

export interface PSACallbackHandlerConfig {
  agentId: string;
  agentRole?: string;
  apiKey?: string;
  baseUrl?: string;
}

export class PSACallbackHandler {
  private agentId: string;
  private agentRole: string;
  private client: PSAClient;
  private steps: Node[] = [];
  private inputText = '';

  constructor(config: PSACallbackHandlerConfig) {
    this.agentId = config.agentId;
    this.agentRole = config.agentRole ?? 'orchestrator';
    this.client = new PSAClient({ apiKey: config.apiKey, baseUrl: config.baseUrl });
  }

  async handleChainStart(_chain: unknown, inputs: Record<string, unknown>): Promise<void> {
    this.steps = [];
    this.inputText = JSON.stringify(inputs).slice(0, 500);
  }

  async handleChainEnd(outputs: Record<string, unknown>): Promise<void> {
    const content = `[TASK: langchain execution] agent_id=${this.agentId}. Outcome: ${JSON.stringify(outputs).slice(0, 300)}`;
    const nodes: Node[] = [
      {
        agentId: this.agentId,
        agentRole: this.agentRole as Node['agentRole'],
        content,
        inputText: this.inputText,
      },
      ...this.steps,
    ];
    try {
      await this.client.trace(nodes);
    } catch {
      // best-effort
    }
  }

  async handleAgentAction(action: { tool: string; toolInput: unknown }): Promise<void> {
    this.steps.push({
      agentId: `${this.agentId}-tool`,
      agentRole: 'executor',
      content: `[TOOL: ${action.tool}] ${JSON.stringify(action.toolInput).slice(0, 200)}`,
      parentIndex: 0,
      edgeType: 'delegation',
    });
  }
}
