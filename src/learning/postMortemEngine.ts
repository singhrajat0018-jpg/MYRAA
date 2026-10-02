export class PostMortemEngine {
  getAllPostMortems() { return []; }
  getPostMortem(id: string) { return null; }
  getFailurePatterns() { return new Map<string, number>(); }
}
export const postMortemEngine = new PostMortemEngine();
