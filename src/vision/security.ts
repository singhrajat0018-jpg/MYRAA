// ============================================================================
// MYRAA Vision Core — Security Utilities
// ============================================================================

import type {
  ScreenCapture, ImageSecurityPolicy, CaptureFormat,
} from './contracts';
import { DEFAULT_SECURITY_POLICY } from './contracts';

// ============================================================================
// Rate Limiter
// ============================================================================

export class RateLimiter {
  private timestamps: number[] = [];
  private readonly windowMs: number;
  private readonly maxRequests: number;

  constructor(maxRequests: number, windowMs: number) {
    this.maxRequests = maxRequests;
    this.windowMs = windowMs;
  }

  tryAcquire(): boolean {
    const now = Date.now();
    this.prune(now);

    if (this.timestamps.length >= this.maxRequests) {
      return false;
    }

    this.timestamps.push(now);
    return true;
  }

  getRemaining(): number {
    this.prune(Date.now());
    return Math.max(0, this.maxRequests - this.timestamps.length);
  }

  getResetMs(): number {
    if (this.timestamps.length === 0) return 0;
    const oldest = this.timestamps[0];
    const resetAt = oldest + this.windowMs;
    return Math.max(0, resetAt - Date.now());
  }

  private prune(now: number): void {
    const cutoff = now - this.windowMs;
    while (this.timestamps.length > 0 && this.timestamps[0] <= cutoff) {
      this.timestamps.shift();
    }
  }
}

// ============================================================================
// Image Validator
// ============================================================================

export type ImageValidationResult =
  | { valid: true }
  | { valid: false; reason: string };

export class ImageValidator {
  private policy: ImageSecurityPolicy;
  private rateLimiter: RateLimiter;

  constructor(policy?: Partial<ImageSecurityPolicy>) {
    this.policy = { ...DEFAULT_SECURITY_POLICY, ...policy };
    this.rateLimiter = new RateLimiter(this.policy.rateLimitPerMinute, 60_000);
  }

  validate(capture: ScreenCapture): ImageValidationResult {
    if (!this.rateLimiter.tryAcquire()) {
      return { valid: false, reason: `Rate limit exceeded (${this.policy.rateLimitPerMinute}/min)` };
    }

    if (!this.policy.allowedFormats.includes(capture.format)) {
      return { valid: false, reason: `Format '${capture.format}' not allowed. Allowed: ${this.policy.allowedFormats.join(', ')}` };
    }

    const imageDataBytes = this.estimateBase64Size(capture.imageData);
    if (imageDataBytes > this.policy.maxImageSizeBytes) {
      return {
        valid: false,
        reason: `Image size ${imageDataBytes} exceeds max ${this.policy.maxImageSizeBytes} bytes`,
      };
    }

    if (capture.width > this.policy.maxImageWidth || capture.height > this.policy.maxImageHeight) {
      return {
        valid: false,
        reason: `Image dimensions ${capture.width}x${capture.height} exceed max ${this.policy.maxImageWidth}x${this.policy.maxImageHeight}`,
      };
    }

    if (capture.width <= 0 || capture.height <= 0) {
      return { valid: false, reason: `Invalid image dimensions: ${capture.width}x${capture.height}` };
    }

    if (!capture.imageData || capture.imageData.length === 0) {
      return { valid: false, reason: 'Image data is empty' };
    }

    return { valid: true };
  }

  getRemainingRequests(): number {
    return this.rateLimiter.getRemaining();
  }

  private estimateBase64Size(base64: string): number {
    const padding = (base64.match(/=+$/) ?? [''])[0].length;
    return Math.floor((base64.length * 3) / 4) - padding;
  }
}

// ============================================================================
// Content Sanitizer
// ============================================================================

export class ContentSanitizer {
  private sensitivePatterns: RegExp[] = [
    /\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b/g,
    /\b\d{3}-\d{2}-\d{4}\b/g,
    /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
    /password\s*[:=]\s*\S+/gi,
    /token\s*[:=]\s*\S+/gi,
    /api[_-]?key\s*[:=]\s*\S+/gi,
    /secret\s*[:=]\s*\S+/gi,
  ];

  sanitizeText(text: string): string {
    let sanitized = text;

    for (const pattern of this.sensitivePatterns) {
      sanitized = sanitized.replace(pattern, (match) => {
        if (match.length <= 4) return '****';
        return match.slice(0, 2) + '*'.repeat(match.length - 4) + match.slice(-2);
      });
    }

    return sanitized;
  }

  sanitizeForLog(text: string): string {
    return this.sanitizeText(text);
  }

  sanitizeForStorage(text: string): string {
    return this.sanitizeText(text);
  }

  containsSensitiveContent(text: string): boolean {
    return this.sensitivePatterns.some(p => p.test(text));
  }
}

// ============================================================================
// File Path Validator
// ============================================================================

export class FilePathValidator {
  private allowedDirectories: string[];
  private blockedPatterns: RegExp[];

  constructor(options?: {
    allowedDirectories?: string[];
    blockedPatterns?: RegExp[];
  }) {
    this.allowedDirectories = options?.allowedDirectories ?? [];
    this.blockedPatterns = options?.blockedPatterns ?? [
      /\.\./,
      /^[A-Z]:\\Windows/i,
      /\/etc\/passwd/i,
      /\/etc\/shadow/i,
    ];
  }

  validateCapturePath(path: string): { valid: boolean; reason?: string } {
    for (const pattern of this.blockedPatterns) {
      if (pattern.test(path)) {
        return { valid: false, reason: `Path matches blocked pattern: ${pattern.source}` };
      }
    }

    if (this.allowedDirectories.length > 0) {
      const normalized = path.replace(/\\/g, '/').toLowerCase();
      const allowed = this.allowedDirectories.some(dir =>
        normalized.startsWith(dir.replace(/\\/g, '/').toLowerCase())
      );
      if (!allowed) {
        return { valid: false, reason: 'Path is outside allowed directories' };
      }
    }

    return { valid: true };
  }

  sanitizePath(path: string): string {
    return path
      .replace(/[<>:"|?*]/g, '_')
      .replace(/\.\./g, '_')
      .replace(/\/+/g, '/')
      .replace(/\\+/g, '\\');
  }
}

// ============================================================================
// Vision Security Manager
// ============================================================================

export class VisionSecurityManager {
  readonly imageValidator: ImageValidator;
  readonly sanitizer: ContentSanitizer;
  readonly pathValidator: FilePathValidator;

  constructor(options?: {
    securityPolicy?: Partial<ImageSecurityPolicy>;
    allowedDirectories?: string[];
  }) {
    this.imageValidator = new ImageValidator(options?.securityPolicy);
    this.sanitizer = new ContentSanitizer();
    this.pathValidator = new FilePathValidator({
      allowedDirectories: options?.allowedDirectories,
    });
  }

  validateCapture(capture: ScreenCapture): ImageValidationResult {
    return this.imageValidator.validate(capture);
  }

  sanitizeForLog(text: string): string {
    return this.sanitizer.sanitizeForLog(text);
  }

  sanitizeCaptureForLog(capture: ScreenCapture): ScreenCapture {
    return {
      ...capture,
      imageData: '[SANITIZED]',
    };
  }

  validateAndSanitize(capture: ScreenCapture): {
    valid: boolean;
    reason?: string;
    sanitized: ScreenCapture;
  } {
    const validation = this.validateCapture(capture);
    if (validation.valid === false) {
      return {
        valid: false,
        reason: validation.reason,
        sanitized: this.sanitizeCaptureForLog(capture),
      };
    }

    return {
      valid: true,
      sanitized: capture,
    };
  }
}
