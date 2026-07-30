/**
 * WebSocket Topic Manager (Suggestion #9)
 */
class WebSocketManager {
  private static instance: WebSocketManager;
  private socket: WebSocket | null = null;
  private subscribers: Map<string, Set<(data: any) => void>> = new Map();

  static getInstance() {
    if (!this.instance) this.instance = new WebSocketManager();
    return this.instance;
  }

  connect(url: string) {
    if (this.socket?.readyState === WebSocket.OPEN) return;
    this.socket = new WebSocket(url);
    
    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const topic = payload.topic || "global";
        const topicSubs = this.subscribers.get(topic);
        if (topicSubs) {
          topicSubs.forEach(cb => cb(payload.data));
        }
      } catch (e) {
        console.error("WS Parse Error:", e);
      }
    };

    this.socket.onclose = () => setTimeout(() => this.connect(url), 5000);
  }

  /**
   * Subscribe to a specific train number or topic
   */
  subscribe(topic: string, callback: (data: any) => void) {
    if (!this.subscribers.has(topic)) {
      this.subscribers.set(topic, new Set());
      // Inform backend we want this topic (if protocol supports it)
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "SUBSCRIBE", topic }));
      }
    }
    
    this.subscribers.get(topic)!.add(callback);
    
    return () => {
      const topicSubs = this.subscribers.get(topic);
      if (topicSubs) {
        topicSubs.delete(callback);
        if (topicSubs.size === 0) {
          this.subscribers.delete(topic);
          if (this.socket?.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type: "UNSUBSCRIBE", topic }));
          }
        }
      }
    };
  }
}

export const wsManager = WebSocketManager.getInstance();
