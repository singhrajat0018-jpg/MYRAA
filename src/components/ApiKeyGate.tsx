/**
 * ApiKeyGate — first-run onboarding.
 *
 * MYRAA runs in local-first mode. Optional API keys (e.g. Tavily)
 * can enhance research features but are not required.
 */

import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";

type Phase = "checking" | "needsKey" | "ready";

export function ApiKeyGate({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("checking");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/config", { cache: "no-store" });
        const data = await res.json();
        if (cancelled) return;
        // Local-first: always ready (API keys are optional)
        setPhase(data.mode === "local-first" || data.hasApiKey ? "ready" : "needsKey");
      } catch {
        // Backend not up yet — assume ready for local-first
        if (!cancelled) setPhase("ready");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (phase === "ready") return <>{children}</>;

  if (phase === "checking") {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center text-white" style={{ background: "#070b14" }}>
        <div className="flex flex-col items-center gap-4 text-white/60">
          <Loader2 className="h-7 w-7 animate-spin" />
          <span className="text-sm tracking-wide">Starting MYRAA…</span>
        </div>
      </div>
    );
  }

  // Shouldn't reach here in local-first mode, but provide a skip path
  return <>{children}</>;
}
