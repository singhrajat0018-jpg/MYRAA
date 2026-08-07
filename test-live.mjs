import { GoogleGenAI, Modality } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

(async () => {
  try {
    console.log("Before connect");

    const session = await ai.live.connect({
      model: "gemini-3.1-flash-live-preview",

      callbacks: {
        onopen: () => console.log("✅ OPEN"),
        onmessage: (msg) => console.log("MESSAGE:", msg),
        onerror: (err) => console.error("ERROR:", err),
        onclose: (e) => console.log("CLOSE:", e),
      },

      config: {
        responseModalities: [Modality.AUDIO],
      },
    });

    console.log("✅ CONNECTED");

    // Keep the session alive for 10 seconds
    await new Promise(resolve => setTimeout(resolve, 10000));

    await session.close();
  } catch (err) {
    console.error(err);
  }
})();