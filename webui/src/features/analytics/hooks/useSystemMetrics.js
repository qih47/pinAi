import { useState, useEffect } from 'react';
import { getApiBase } from '../../../services/endpoints';

let sharedEventSource = null;
let subscribers = 0;
let cachedMetrics = null;

export const useSystemMetrics = () => {
  const [metrics, setMetrics] = useState(cachedMetrics);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    subscribers++;
    
    if (!sharedEventSource) {
      const apiBase = getApiBase();
      sharedEventSource = new EventSource(`${apiBase}/api/analytics/metrics/stream`);
      
      sharedEventSource.onopen = () => {
        setIsConnected(true);
      };
      
      sharedEventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          cachedMetrics = data;
          setMetrics(data);
        } catch (e) {
          console.error("Failed to parse metrics", e);
        }
      };

      sharedEventSource.onerror = () => {
        setIsConnected(false);
      };
    } else {
      setIsConnected(sharedEventSource.readyState === EventSource.OPEN);
      if (cachedMetrics) {
        setMetrics(cachedMetrics);
      }
    }

    const onMessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setMetrics(data);
      } catch (e) {}
    };

    if (sharedEventSource) {
      sharedEventSource.addEventListener('message', onMessage);
    }

    return () => {
      subscribers--;
      if (sharedEventSource) {
        sharedEventSource.removeEventListener('message', onMessage);
      }
      
      if (subscribers === 0 && sharedEventSource) {
        sharedEventSource.close();
        sharedEventSource = null;
        cachedMetrics = null;
      }
    };
  }, []);

  return { metrics, isConnected };
};
