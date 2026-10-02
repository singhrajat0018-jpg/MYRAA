// ============================================================================
// MYRAA Circuit Breaker — Python Bridge Resilience
// ============================================================================

export type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export interface CircuitBreakerConfig {
  readonly failureThreshold: number;
  readonly cooldownMs: number;
  readonly halfOpenMaxAttempts: number;
}

const DEFAULT_CONFIG: CircuitBreakerConfig = {
  failureThreshold: 5,
  cooldownMs: 30000,
  halfOpenMaxAttempts: 2,
};

export interface CircuitBreakerStats {
  state: CircuitState;
  failures: number;
  successes: number;
  consecutiveFailures: number;
  lastSuccess: number;
  lastFailure: number;
  totalRequests: number;
  latencyMs: number;
}

export class CircuitBreaker {
  private state: CircuitState = 'CLOSED';
  private failures = 0;
  private successes = 0;
  private consecutiveFailures = 0;
  private lastSuccess = 0;
  private lastFailure = 0;
  private totalRequests = 0;
  private halfOpenAttempts = 0;
  private lastLatencyMs = 0;
  private readonly config: CircuitBreakerConfig;

  constructor(config?: Partial<CircuitBreakerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  getState(): CircuitState {
    if (this.state === 'OPEN') {
      const now = Date.now();
      if (now - this.lastFailure >= this.config.cooldownMs) {
        this.state = 'HALF_OPEN';
        this.halfOpenAttempts = 0;
      }
    }
    return this.state;
  }

  recordSuccess(latencyMs: number): void {
    this.totalRequests++;
    this.successes++;
    this.consecutiveFailures = 0;
    this.lastSuccess = Date.now();
    this.lastLatencyMs = latencyMs;

    if (this.state === 'HALF_OPEN') {
      this.state = 'CLOSED';
      this.failures = 0;
    }
  }

  recordFailure(): void {
    this.totalRequests++;
    this.failures++;
    this.consecutiveFailures++;
    this.lastFailure = Date.now();

    if (this.state === 'HALF_OPEN') {
      this.halfOpenAttempts++;
      if (this.halfOpenAttempts >= this.config.halfOpenMaxAttempts) {
        this.state = 'OPEN';
      }
      return;
    }

    if (this.consecutiveFailures >= this.config.failureThreshold) {
      this.state = 'OPEN';
    }
  }

  canExecute(): boolean {
    const current = this.getState();
    return current === 'CLOSED' || current === 'HALF_OPEN';
  }

  getStats(): CircuitBreakerStats {
    this.getState(); // force state transition check
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes,
      consecutiveFailures: this.consecutiveFailures,
      lastSuccess: this.lastSuccess,
      lastFailure: this.lastFailure,
      totalRequests: this.totalRequests,
      latencyMs: this.lastLatencyMs,
    };
  }

  reset(): void {
    this.state = 'CLOSED';
    this.failures = 0;
    this.consecutiveFailures = 0;
    this.halfOpenAttempts = 0;
  }
}
