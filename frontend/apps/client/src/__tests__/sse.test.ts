import { SseFrameParser } from '@fabricassist/api-client';

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
});
