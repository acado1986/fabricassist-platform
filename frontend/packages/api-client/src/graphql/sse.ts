export type RunEvent = {
  schema_version: number;
  event_id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  data: Record<string, unknown>;
};

export type ParsedSseEvent = { id?: string; event: string; data: string };

export function parseRunEvent(data: string): RunEvent | null {
  try {
    const value: unknown = JSON.parse(data);
    if (!value || typeof value !== 'object') return null;
    const event = value as Partial<RunEvent>;
    if (
      typeof event.schema_version !== 'number' ||
      typeof event.event_id !== 'string' ||
      typeof event.run_id !== 'string' ||
      typeof event.sequence !== 'number' ||
      typeof event.timestamp !== 'string' ||
      !event.data ||
      typeof event.data !== 'object'
    )
      return null;
    return event as RunEvent;
  } catch {
    return null;
  }
}

/** Incremental SSE parser: accepts partial and multiple event frames. */
export class SseFrameParser {
  private buffer = '';

  push(chunk: string): ParsedSseEvent[] {
    this.buffer += chunk.replace(/\r\n/g, '\n');
    const frames = this.buffer.split('\n\n');
    this.buffer = frames.pop() ?? '';
    return frames.flatMap((frame) => {
      const fields: Record<string, string[]> = {};
      for (const line of frame.split('\n')) {
        const separator = line.indexOf(':');
        if (separator < 0) continue;
        const key = line.slice(0, separator);
        const value = line.slice(separator + 1).replace(/^ /, '');
        (fields[key] ??= []).push(value);
      }
      const data = fields.data?.join('\n');
      return data === undefined
        ? []
        : [{ id: fields.id?.[0], event: fields.event?.[0] ?? 'message', data }];
    });
  }
}

export async function streamRunEvents(
  url: string,
  token: string | null,
  onEvent: (event: ParsedSseEvent) => void,
  signal?: AbortSignal,
  lastEventId?: string,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  const response = await fetchImpl(url, {
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
    },
    signal,
  });
  if (!response.ok || !response.body)
    throw new Error(`SSE request failed (${response.status}).`);
  const parser = new SseFrameParser();
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        for (const event of parser.push(decoder.decode())) onEvent(event);
        return;
      }
      for (const event of parser.push(decoder.decode(value, { stream: true })))
        onEvent(event);
    }
  } finally {
    reader.releaseLock();
  }
}
