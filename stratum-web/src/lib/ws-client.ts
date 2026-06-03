"use client";

type ChangefeedEvent = {
  event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  timestamp: string;
};

type EventHandler = (event: ChangefeedEvent) => void;

// Unsubscribe function returned by on()
type Unsub = () => void;

class StratumWebSocketClient {
  private ws: WebSocket | null = null;
  private handlers: Map<string, EventHandler[]> = new Map();
  private reconnectAttempts = 0;
  private readonly maxReconnect = 5;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private currentToken: string | null = null;

  connect(token: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    this.currentToken = token;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    // SECURITY NOTE: token in query string appears in proxy/access logs.
    // Proper fix: Sec-WebSocket-Protocol header auth or short-lived ticket endpoint.
    // Both require backend changes (R-4 blocked for alpha). encodeURIComponent is
    // applied to prevent token injection but does not solve the logging exposure.
    // Track as: backend WS auth upgrade (post-alpha, before public launch).
    const wsUrl = `${proto}://${window.location.host}/ws?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.pingInterval = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send("ping");
        }
      }, 30_000);
    };

    this.ws.onmessage = (msg) => {
      if (msg.data === "pong") return;
      try {
        const event: ChangefeedEvent = JSON.parse(msg.data as string);
        const handlers = this.handlers.get(event.event_type) ?? [];
        const wildcards = this.handlers.get("*") ?? [];
        [...handlers, ...wildcards].forEach((h) => h(event));
      } catch (e) {
        console.error("[WS] parse error:", e);
      }
    };

    this.ws.onclose = () => {
      if (this.pingInterval) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }
      if (this.reconnectAttempts < this.maxReconnect && this.currentToken) {
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30_000);
        setTimeout(() => {
          this.reconnectAttempts++;
          if (this.currentToken) this.connect(this.currentToken);
        }, delay);
      }
    };

    this.ws.onerror = (e) => console.error("[WS] error:", e);
  }

  on(eventType: string, handler: EventHandler): Unsub {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, []);
    this.handlers.get(eventType)!.push(handler);
    return () => {
      const arr = this.handlers.get(eventType);
      if (arr) {
        const idx = arr.indexOf(handler);
        if (idx >= 0) arr.splice(idx, 1);
      }
    };
  }

  disconnect() {
    this.currentToken = null;
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}

export const wsClient = new StratumWebSocketClient();
