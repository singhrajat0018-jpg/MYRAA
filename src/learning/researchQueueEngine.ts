export class ResearchQueueEngine {
  private queue: any[] = [];
  private running: any[] = [];
  private completed: any[] = [];

  getQueue() { return this.queue; }
  enqueue(item: any) { this.queue.push(item); return item; }
  dequeue() { return this.queue.shift() || null; }
  getQueueLength() { return this.queue.length; }
  getRunning() { return this.running; }
  getCompleted() { return this.completed; }
  getDailyCount() { return this.completed.length; }
}
export const researchQueueEngine = new ResearchQueueEngine();
