import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { Mode } from "../types";

interface MemoryState {
  memoryOn: boolean;
  mode: Mode;
  setMemoryOn: (on: boolean) => void;
  toggle: () => void;
}

const KEY = "calibrate.memory";
const MemoryContext = createContext<MemoryState | null>(null);

function readInitial(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function MemoryProvider({ children }: { children: ReactNode }) {
  const [memoryOn, setState] = useState(readInitial);

  const setMemoryOn = useCallback((on: boolean) => {
    setState(on);
    try {
      localStorage.setItem(KEY, on ? "on" : "off");
    } catch {
      /* storage unavailable */
    }
  }, []);

  const value = useMemo<MemoryState>(
    () => ({
      memoryOn,
      mode: memoryOn ? "on" : "off",
      setMemoryOn,
      toggle: () => setMemoryOn(!memoryOn),
    }),
    [memoryOn, setMemoryOn],
  );

  return <MemoryContext.Provider value={value}>{children}</MemoryContext.Provider>;
}

export function useMemory(): MemoryState {
  const ctx = useContext(MemoryContext);
  if (!ctx) throw new Error("useMemory must be used inside <MemoryProvider>");
  return ctx;
}
