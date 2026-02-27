import { render, screen } from "@testing-library/react";
import ResponderPage from "@/pages/Responder";
import { useAuth } from "@/context/AuthContext";
import { vi } from "vitest";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("ResponderPage", () => {
  it("shows login prompt when not authenticated", () => {
    const mockAuth = useAuth as unknown as any;
    mockAuth.mockReturnValue({ user: null, isAuthenticated: false });
    render(<ResponderPage />);
    expect(screen.getByText(/Please login to view SOS alerts/i)).toBeInTheDocument();
  });

  it("blocks non-responder roles", () => {
    const mockAuth = useAuth as unknown as any;
    mockAuth.mockReturnValue({ user: { role: "user" }, isAuthenticated: true });
    render(<ResponderPage />);
    expect(screen.getByText(/not authorized/i)).toBeInTheDocument();
  });
});
