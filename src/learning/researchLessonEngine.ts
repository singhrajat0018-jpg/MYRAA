export class ResearchLessonEngine {
  getLessonsByStrategy(strategyId: string) { return []; }
  getLessonsByRegime(regime: string) { return []; }
  getAllLessons() { return []; }
  createLesson(data: any) { return { id: `lesson-${Date.now()}`, ...data }; }
  getActiveLessons() { return []; }
  getConflictingLessons(strategyId: string) { return []; }
}
export const researchLessonEngine = new ResearchLessonEngine();
