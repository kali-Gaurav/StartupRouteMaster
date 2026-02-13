import React from "react";
import { render, screen } from "@testing-library/react";
import { AuthProvider } from "@/context/AuthContext";
import SOS from "@/pages/SOS";

test("renders SOS page", () => {
  render(
    <AuthProvider>
      <SOS />
    </AuthProvider>
  );
  // In test env location is unsupported, so page shows "Location Required" or similar
  const heading = screen.getByText(/Location Required|SOS|Emergency/i);
  expect(heading).toBeInTheDocument();
});