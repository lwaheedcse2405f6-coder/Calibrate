import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { BeliefUpdate, Mode, QuarterPoint } from "../types";

export type ReplayStatus = "idle" | "running" | "done" | "error";

export function useReplay(mode: Mode) {
  const [points, setPoints] = useState<QuarterPoint[]>([]);
  const [updates, setUpdates] = useState<BeliefUpdate[]>([]);
  const [status, setStatus] = useState<ReplayStatus>("idle");
  const [error, setError] = useState<string>();
  const stopRef = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
    stopRef.current?.();
    stopRef.current = null;
  }, []);

  const reset = useCallback(() => {
    stop();
    setPoints([]);
    setUpdates([]);
    setError(undefined);
    setStatus("idle");
  }, [stop]);

  const start = useCallback(() => {
    stop();
    setPoints([]);
    setUpdates([]);
    setError(undefined);
    setStatus("running");
    stopRef.current = api.replay(mode, {
      onQuarter: (q) => {
        setPoints((prev) => [...prev, q]);
        const fresh = (q.belief_updates ?? []).map((b) => ({ ...b, quarter: b.quarter ?? q.quarter }));
        if (fresh.length) setUpdates((prev) => [...fresh.reverse(), ...prev]);
      },
      onDone: () => {
        stopRef.current = null;
        setStatus("done");
      },
      onError: (message) => {
        stopRef.current = null;
        setError(message);
        setStatus("error");
      },
    });
  }, [mode, stop]);

  // Switching memory mode (or leaving the page) cancels a replay in progress.
  useEffect(() => reset, [mode, reset]);

  return { points, updates, status, error, start, reset };
}
