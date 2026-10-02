import {
  loadMemories,
  saveMemories,
  normalizeNewMemory,
  updateMemories,
  isSensitiveMemoryText,
} from "../../server_memory";
import type { ServerContext } from "./types";

export function registerMemoryRoutes(app: any, _ctx: ServerContext) {
  app.get("/api/memories", async (req: any, res: any) => {
    try {
      const memories = await loadMemories();
      res.json(memories);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post("/api/memories", async (req: any, res: any) => {
    try {
      const { category, text } = req.body;
      if (!category || !text) {
        return res.status(400).json({ error: "Category and text parameters are required." });
      }
      if (isSensitiveMemoryText(String(text))) {
        return res.status(400).json({ error: "Memory content contains sensitive data and was rejected." });
      }
      const newMemory = normalizeNewMemory(String(category), String(text));
      if (!newMemory) {
        return res.status(400).json({ error: "Memory content is empty or sensitive." });
      }
      const memories = await updateMemories((mList) => [...mList, newMemory as any]);
      res.status(201).json(newMemory);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.delete("/api/memories/:id", async (req: any, res: any) => {
    try {
      const { id } = req.params;
      let memories = await loadMemories();
      memories = memories.filter(m => m.id !== id);
      await saveMemories(memories);
      res.json({ success: true });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });
}
