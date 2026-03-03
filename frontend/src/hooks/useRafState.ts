import { useRef, useCallback, useEffect, useState } from 'react';

/**
 * useRafState (Suggestion #4)
 * A hook that debounces state updates to requestAnimationFrame boundaries.
 * Ideal for high-frequency events like scrolling, resizing, or rapid typing.
 */
export function useRafState<S>(initialState: S | (() => S)): [S, (value: S | ((prevState: S) => S)) => void] {
  const frame = useRef(0);
  const [state, setState] = useState(initialState);

  const setRafState = useCallback((value: S | ((prevState: S) => S)) => {
    cancelAnimationFrame(frame.current);

    frame.current = requestAnimationFrame(() => {
      setState(value);
    });
  }, []);

  useEffect(() => {
    return () => cancelAnimationFrame(frame.current);
  }, []);

  return [state, setRafState];
}
