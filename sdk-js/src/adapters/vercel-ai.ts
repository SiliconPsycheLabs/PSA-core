/**
 * Vercel AI SDK adapter — PSAMiddleware integrates with experimental_telemetry.
 *
 * Usage:
 *   import { PSAMiddleware } from '@psa/sdk/adapters/vercel-ai';
 *   const result = await generateText({
 *     model: openai('gpt-4o'),
 *     prompt: '...',
 *     experimental_telemetry: PSAMiddleware({ agentId: 'my-agent' }),
 *   });
 */
import { PSAClient } from '../client';

export interface PSAMiddlewareConfig {
  agentId: string;
  agentRole?: string;
  apiKey?: string;
  baseUrl?: string;
}

export function PSAMiddleware(config: PSAMiddlewareConfig) {
  const client = new PSAClient({ apiKey: config.apiKey, baseUrl: config.baseUrl });
  const agentId = config.agentId;
  const agentRole = (config.agentRole ?? 'orchestrator') as 'orchestrator';

  return {
    isEnabled: true,
    recordInputs: true,
    recordOutputs: true,
    functionId: `psa-${agentId}`,
    metadata: { agentId },
    tracer: {
      startActiveSpan<T>(name: string, fn: (span: unknown) => T): T {
        return fn({
          setAttribute: () => {},
          setStatus: () => {},
          end: () => {},
          recordException: () => {},
        });
      },
    },
    onFinish: async (result: { text?: string; usage?: { promptTokens?: number; completionTokens?: number } }) => {
      const content = `[TASK: vercel-ai call] model output: ${(result.text ?? '').slice(0, 300)}`;
      try {
        await client.trace([{ agentId, agentRole, content }]);
      } catch {
        // best-effort
      }
    },
  };
}
