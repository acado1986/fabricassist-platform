import { RunStreamLifecycle } from '@fabricassist/api-client';

test('run stream lifecycle awaits canonical recovery before opening', async () => {
  const order: string[] = [];
  const lifecycle = new RunStreamLifecycle({
    recover: async () => {
      order.push('recover');
    },
    open: async () => {
      order.push('open');
    },
  });

  lifecycle.start();
  await new Promise((resolve) => setTimeout(resolve, 0));
  lifecycle.stop();

  expect(order).toEqual(['recover', 'open']);
});

test('terminal stream handling stops before awaiting canonical synchronization', async () => {
  const order: string[] = [];
  let resolveSync!: () => void;
  const sync = new Promise<void>((resolve) => {
    resolveSync = resolve;
  });
  const lifecycle = new RunStreamLifecycle({
    recover: async () => undefined,
    open: async () => undefined,
    onTerminal: async () => {
      order.push('sync-start');
      await sync;
      order.push('sync-end');
    },
  });

  const terminal = lifecycle.handleTerminal();
  expect(order).toEqual(['sync-start']);
  resolveSync();
  await terminal;
  expect(order).toEqual(['sync-start', 'sync-end']);
});
