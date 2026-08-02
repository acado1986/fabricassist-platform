export type RunStreamLifecycleOptions = {
  recover: () => Promise<void>;
  open: (signal: AbortSignal, lastEventId: string | undefined) => Promise<void>;
  onReconnectFailure?: (attempt: number) => void;
  onTerminal?: () => Promise<void>;
};

/**
 * Coordinates canonical recovery and the transient run stream.
 * Recovery is always awaited before a stream is opened or reopened.
 */
export class RunStreamLifecycle {
  private readonly options: RunStreamLifecycleOptions;
  private active = false;
  private terminal = false;
  private paused = false;
  private recovering = false;
  private retryAttempt = 0;
  private lastEventId: string | undefined;
  private controller: AbortController | undefined;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(options: RunStreamLifecycleOptions) {
    this.options = options;
  }

  start(): void {
    this.active = true;
    this.terminal = false;
    this.paused = false;
    void this.recoverThenOpen();
  }

  resume(): void {
    if (!this.active || this.terminal) return;
    this.paused = false;
    this.controller?.abort();
    void this.recoverThenOpen();
  }

  pause(): void {
    this.paused = true;
    this.controller?.abort();
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = undefined;
    }
  }

  markEventId(eventId: string | undefined): void {
    if (eventId) this.lastEventId = eventId;
  }

  async handleTerminal(): Promise<void> {
    if (this.terminal) return;
    this.stop();
    await this.options.onTerminal?.();
  }

  stop(): void {
    this.active = false;
    this.terminal = true;
    this.paused = true;
    this.controller?.abort();
    if (this.retryTimer) clearTimeout(this.retryTimer);
  }

  private async recoverThenOpen(): Promise<void> {
    if (!this.active || this.terminal || this.paused || this.recovering) return;
    this.recovering = true;
    try {
      await this.options.recover();
      if (!this.active || this.terminal || this.paused) return;
      this.retryAttempt = 0;
      this.controller = new AbortController();
      await this.options.open(this.controller.signal, this.lastEventId);
      if (
        this.active &&
        !this.terminal &&
        !this.paused &&
        !this.controller.signal.aborted
      ) {
        this.scheduleReconnect();
      }
    } catch {
      if (!this.active || this.terminal || this.paused) return;
      this.retryAttempt += 1;
      this.options.onReconnectFailure?.(this.retryAttempt);
      this.scheduleReconnect();
    } finally {
      this.recovering = false;
    }
  }

  private scheduleReconnect(): void {
    if (!this.active || this.terminal || this.paused) return;
    const baseDelay = Math.min(1_000 * 2 ** this.retryAttempt, 15_000);
    const jitter = Math.floor(Math.random() * Math.max(1, baseDelay / 4));
    this.retryTimer = setTimeout(
      () => void this.recoverThenOpen(),
      baseDelay + jitter,
    );
  }
}
