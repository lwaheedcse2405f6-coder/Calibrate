import { useCallback, useEffect, useState, type DependencyList } from "react";

export interface AsyncState<T> {
  data?: T;
  error?: string;
  loading: boolean;
  retry: () => void;
}

/** Runs `fn` whenever `deps` change. Keeps the previous data while reloading. */
export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [state, setState] = useState<Omit<AsyncState<T>, "retry">>({ loading: true });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    setState((s) => ({ data: s.data, loading: true }));
    fn()
      .then((data) => alive && setState({ data, loading: false }))
      .catch((e: Error) => alive && setState({ error: e.message, loading: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, retry };
}
