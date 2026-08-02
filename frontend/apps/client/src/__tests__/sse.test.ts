import { SseFrameParser, parseRunEvent } from '@fabricassist/api-client';

describe('SseFrameParser', () => {
  it('reassembles partial frames and parses multiple events', () => {
    const parser = new SseFrameParser();
    expect(parser.push('id: 1\nevent: run.progress\ndata: {"a":')).toEqual([]);
    expect(
      parser.push('1}\n\nid: 2\nevent: run.completed\ndata: {}\n\n'),
    ).toEqual([
      { id: '1', event: 'run.progress', data: '{"a":1}' },
      { id: '2', event: 'run.completed', data: '{}' },
    ]);
  });

  it('normalizes lone carriage returns between frames', () => {
    const parser = new SseFrameParser();
    expect(parser.push('event: one\rdata: first\r\r')).toEqual([
      { id: undefined, event: 'one', data: 'first' },
    ]);
  });
});

test('parseRunEvent rejects malformed event envelopes', () => {
  expect(parseRunEvent('{"sequence":"1","data":{}}')).toBeNull();
  expect(
    parseRunEvent(
      JSON.stringify({
        schema_version: 1,
        event_id: 'event-1',
        run_id: 'run-1',
        sequence: 1,
        timestamp: '2026-08-02T00:00:00Z',
        data: { message_id: 'message-1', delta: 'Safe answer' },
      }),
    ),
  ).toEqual({
    schema_version: 1,
    event_id: 'event-1',
    run_id: 'run-1',
    sequence: 1,
    timestamp: '2026-08-02T00:00:00Z',
    data: { message_id: 'message-1', delta: 'Safe answer' },
  });
});
