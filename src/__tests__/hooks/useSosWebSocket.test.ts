import { renderHook, act } from "@testing-library/react";
import { useSosSocket } from "@/hooks/useSosWebSocket";
import { useAuth } from "@/context/AuthContext";
import { vi } from "vitest";

// mock auth context to provide token
vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn()
}));

describe("useSosSocket", () => {
  let OriginalWebSocket: any;

  beforeEach(() => {
    OriginalWebSocket = global.WebSocket;
    // simple mock websocket constructor with instance tracking
    const instances: any[] = [];
    class MockWS {
      url: string;
      onopen: any;
      onmessage: any;
      onclose: any;
      onerror: any;
      constructor(url: string) {
        this.url = url;
        instances.push(this);
        // simulate open shortly
        setTimeout(() => this.onopen && this.onopen());
      }
      send() {}
      close() { if (this.onclose) this.onclose(); }
    }
    (MockWS as any).instances = instances;
    global.WebSocket = MockWS as any;
    // expose for assertions
    (global as any).WebSocketInstances = instances;
  });

  afterEach(() => {
    global.WebSocket = OriginalWebSocket;
    vi.resetAllMocks();
  });

  it("opens websocket with token and calls alert callback", () => {
    const mockAuth = useAuth as vi.Mock;
    mockAuth.mockReturnValue({ token: "abc123" });
    const onAlert = vi.fn();
    const { result } = renderHook(() => useSosSocket(onAlert));
    // WebSocket constructor should have been called
    expect(result.current.connected).toBe(true);
    // verify url contains token
    const wsInst = (global as any).WebSocketInstances[0];
    expect(wsInst.url).toContain("token=abc123");
    // simulate incoming alert message and ensure callback invoked
    act(() => {
      wsInst.onmessage && wsInst.onmessage({ data: JSON.stringify({ type: "sos_alert", data: { id: "foo" } }) });
    });
    expect(onAlert).toHaveBeenCalledWith({ id: "foo" });

    // simulate token refresh by updating auth return and rerendering
    mockAuth.mockReturnValue({ token: "newtok" });
    const beforeCount = (global as any).WebSocketInstances.length;
    act(() => {
      // trigger rerender of hook
      renderHook(() => useSosSocket(onAlert));
    });
    const afterCount = (global as any).WebSocketInstances.length;
    expect(afterCount).toBeGreaterThan(beforeCount);
  });
});
