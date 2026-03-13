import { useEffect, useRef } from 'react';
import { useSystemStatus } from '@/store/useSystemStatus';

export function useFPS() {
  const { setSystemStatus } = useSystemStatus();
  const frameCount = useRef(0);
  const lastTime = useRef(performance.now());
  const requestRef = useRef<number>(null);

  useEffect(() => {
    const animate = (time: number) => {
      frameCount.current++;
      
      if (time - lastTime.current >= 1000) {
        const fps = Math.round((frameCount.current * 1000) / (time - lastTime.current));
        setSystemStatus({ fps });
        
        frameCount.current = 0;
        lastTime.current = time;
      }
      
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [setSystemStatus]);
}
