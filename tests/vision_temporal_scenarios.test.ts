import { describe, it, expect, vi } from 'vitest';
import { VisionEngine } from '../src/vision/index';
import { VisualEventEngine } from '../src/vision/visualEventEngine';
import type { ActiveWindowInfo } from '../src/vision/contracts';

describe('Vision Temporal Scenarios & State Machine', () => {
  it('Scenario 1: VS Code open with identical screen produces no change event and reuses cached OCR', async () => {
    let callCount = 0;
    const mockCapture: any = {
      captureScreen: vi.fn().mockImplementation(async () => {
        callCount++;
        return {
          buffer: Buffer.from('dummy'),
          width: 1920,
          height: 1080,
          mimeType: 'image/jpeg',
          timestamp: Date.now(),
          activeWindow: { application: 'Code', title: 'server.ts — MYRAA', active: true },
        };
      }),
    };

    const mockOcr: any = {
      recognizeWithMetadata: vi.fn().mockResolvedValue({
        text: 'import express from "express";',
        blocks: [{ text: 'import express from "express";', confidence: 0.95, bbox: { x: 0, y: 0, width: 200, height: 20 } }],
        confidence: 0.95,
        hasErrors: false,
        sensitiveRedacted: false,
      }),
    };

    const engine = new VisionEngine({
      captureAdapter: mockCapture,
      ocrAdapter: mockOcr,
    });

    // 1st observation: initial capture
    const scene1 = await engine.observeOnce();
    expect(scene1.delta?.changed).toBe(true);
    expect(mockOcr.recognizeWithMetadata).toHaveBeenCalledTimes(1);

    // 2nd observation: identical screen
    const scene2 = await engine.observeOnce();
    expect(scene2.delta?.changed).toBe(false);
    expect(scene2.events.some(e => e.type === 'USER_IDLE_VISUALLY')).toBe(true);

    const telemetry = engine.getTelemetry();
    expect(telemetry.framesCaptured).toBe(2);
    expect(telemetry.framesSkipped).toBeGreaterThanOrEqual(1); // Cached OCR reused
  });

  it('Scenario 2: Terminal empty -> terminal shows build complete emits TERMINAL_OUTPUT_CHANGED', () => {
    const eventEngine = new VisualEventEngine();

    const prev = {
      activeWindow: { application: 'Windows Terminal', title: 'PowerShell', active: true },
      textContent: 'npm run build',
      timestamp: Date.now() - 5000,
    };

    const curr = {
      activeWindow: { application: 'Windows Terminal', title: 'PowerShell', active: true },
      textContent: 'npm run build\nBuild succeeded in 1.4s',
      timestamp: Date.now(),
      ocrBlocks: [
        { text: 'npm run build', confidence: 0.95, bbox: { x: 0, y: 0, width: 100, height: 20 } },
        { text: 'Build succeeded in 1.4s', confidence: 0.95, bbox: { x: 0, y: 24, width: 150, height: 20 } },
      ],
    };

    const events = eventEngine.detectEvents(prev, curr);
    expect(events.length).toBeGreaterThan(0);
    const termEvent = events.find(e => e.type === 'TERMINAL_OUTPUT_CHANGED');
    expect(termEvent).toBeDefined();
    expect(termEvent?.description).toContain('Terminal build completed');
    expect(termEvent?.significance).toBeGreaterThanOrEqual(0.8);
  });

  it('Scenario 3: No dialog -> security dialog appears emits DIALOG_APPEARED with high significance', () => {
    const eventEngine = new VisualEventEngine();

    const prev = {
      activeWindow: { application: 'Explorer', title: 'Downloads', active: true },
      textContent: 'setup.exe',
      timestamp: Date.now() - 3000,
    };

    const curr = {
      activeWindow: { application: 'Consent.exe', title: 'User Account Control Warning Dialog', active: true },
      textContent: 'Do you want to allow this app to make changes?',
      timestamp: Date.now(),
      ocrBlocks: [{ text: 'Do you want to allow this app to make changes?', confidence: 0.95, bbox: { x: 0, y: 0, width: 300, height: 40 } }],
    };

    const events = eventEngine.detectEvents(prev, curr);
    const dialogEvent = events.find(e => e.type === 'DIALOG_APPEARED');
    expect(dialogEvent).toBeDefined();
    expect(dialogEvent?.significance).toBeGreaterThanOrEqual(0.9);
  });

  it('Scenario 4: Browser page A -> browser page B emits PAGE_CHANGED', () => {
    const eventEngine = new VisualEventEngine();

    const prev = {
      activeWindow: { application: 'Google Chrome', title: 'Google Search - Home', active: true },
      textContent: 'Search Google or type a URL',
      timestamp: Date.now() - 4000,
    };

    const curr = {
      activeWindow: { application: 'Google Chrome', title: 'GitHub: Let’s build from here', active: true },
      textContent: 'Where the world builds software',
      timestamp: Date.now(),
      ocrBlocks: [{ text: 'Where the world builds software', confidence: 0.95, bbox: { x: 0, y: 0, width: 250, height: 30 } }],
    };

    const events = eventEngine.detectEvents(prev, curr);
    const pageEvent = events.find(e => e.type === 'PAGE_CHANGED');
    expect(pageEvent).toBeDefined();
    expect(pageEvent?.significance).toBeGreaterThanOrEqual(0.6);
  });

  it('Scenario 5: 20 consecutive unchanged frames tracks consecutive idle cycles cleanly', async () => {
    const mockCapture: any = {
      captureScreen: vi.fn().mockResolvedValue({
        buffer: Buffer.from('img'),
        width: 1920,
        height: 1080,
        mimeType: 'image/jpeg',
        timestamp: Date.now(),
        activeWindow: { application: 'Notepad', title: 'notes.txt', active: true },
      }),
    };

    const mockOcr: any = {
      recognizeWithMetadata: vi.fn().mockResolvedValue({
        text: 'constant notes content',
        blocks: [],
        confidence: 0.9,
        hasErrors: false,
        sensitiveRedacted: false,
      }),
    };

    const engine = new VisionEngine({
      captureAdapter: mockCapture,
      ocrAdapter: mockOcr,
    });

    for (let i = 0; i < 20; i++) {
      await engine.observeOnce();
    }

    const telemetry = engine.getTelemetry();
    expect(telemetry.totalObservations).toBe(20);
    expect(telemetry.consecutiveNoChangeCount).toBeGreaterThanOrEqual(18);
  });

  it('Scenario 6: Desktop Agent capture failure enters DEGRADED state without crash', async () => {
    const failingCapture: any = {
      captureScreen: vi.fn().mockRejectedValue(new Error('Connection refused to Desktop Agent on :8765')),
    };

    const mockOcr: any = {
      recognizeWithMetadata: vi.fn().mockResolvedValue({ text: '', blocks: [], confidence: 0, hasErrors: false, sensitiveRedacted: false }),
    };

    const engine = new VisionEngine({
      captureAdapter: failingCapture,
      ocrAdapter: mockOcr,
    });

    await expect(engine.observeOnce()).rejects.toThrow('Connection refused');
    expect(engine.status).toBe('DEGRADED');
  });
});
