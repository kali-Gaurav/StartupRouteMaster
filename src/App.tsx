import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate, Outlet, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { MiniAppGate } from "@/components/MiniAppGate";
import { RailAssistantChatbot } from "@/components/RailAssistantChatbot";
import { NetworkStatusBanner } from "@/components/NetworkStatusBanner";
import { DevBootstrap } from "@/components/DevBootstrap";
import { DevDebugPanel } from "@/components/DevDebugPanel";
import { AuthProvider } from "@/context/AuthContext";
import { BookingFlowProvider } from "@/context/BookingFlowContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { queryClient } from "@/infrastructure/queryClient";

// Lazy load pages for code splitting
const Index = lazy(() => import("./pages/Index"));
const SOS = lazy(() => import("./pages/SOS"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Bookings = lazy(() => import("./pages/Bookings"));
const Ticket = lazy(() => import("./pages/Ticket"));
const NotFound = lazy(() => import("./pages/NotFound"));

// Lazy load Mini App pages
const MiniAppHome = lazy(() => import("./pages/mini-app/Home"));
const MiniAppSearch = lazy(() => import("./pages/mini-app/Search"));
const MiniAppSOS = lazy(() => import("./pages/mini-app/SOS"));
const MiniAppTrack = lazy(() => import("./pages/mini-app/Track"));
const MiniAppSaved = lazy(() => import("./pages/mini-app/Saved"));
const MiniAppProfile = lazy(() => import("./pages/mini-app/Profile"));

// Loading fallback component
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen bg-background">
    <div className="flex flex-col items-center gap-4">
      <div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
      <p className="text-sm text-muted-foreground">Loading page...</p>
    </div>
  </div>
);

function ChatbotWrapper() {
  const navigate = useNavigate();
  const onSearch = (fromCode: string, toCode: string, date?: string, correlationId?: string) => {
    const params = new URLSearchParams({ from: fromCode.trim().toUpperCase(), to: toCode.trim().toUpperCase() });
    const useDate = date?.trim() || new Date().toISOString().slice(0, 10);
    params.set("date", useDate);
    navigate(`/?${params.toString()}`, { replace: true });
    window.dispatchEvent(
      new CustomEvent("rail-assistant-search", {
        detail: { fromCode: fromCode.trim().toUpperCase(), toCode: toCode.trim().toUpperCase(), date: useDate, correlationId },
      })
    );
  };
  const onSort = (sortBy: "duration" | "cost") => {
    window.dispatchEvent(new CustomEvent("rail-assistant-sort", { detail: { sortBy } }));
  };
  const onNavigate = (path: string) => {
    navigate(path);
  };
  return <RailAssistantChatbot onSearchRequest={onSearch} onSortChange={onSort} onNavigate={onNavigate} />;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <AuthProvider>
        <BookingFlowProvider>
          <TooltipProvider>
        <Toaster />
        <Sonner />
        <NetworkStatusBanner />
        <DevBootstrap />
        <DevDebugPanel />
        <BrowserRouter>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/sos" element={<SOS />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/bookings" element={<Bookings />} />
              <Route path="/ticket/:bookingId" element={<Ticket />} />

              {/* Mini App Routes: gate runs Telegram initData → JWT auth then renders child */}
              <Route path="/mini-app" element={<MiniAppGate><Outlet /></MiniAppGate>}>
                <Route index element={<Navigate to="home" replace />} />
                <Route path="home" element={<MiniAppHome />} />
                <Route path="search" element={<MiniAppSearch />} />
                <Route path="sos" element={<MiniAppSOS />} />
                <Route path="track" element={<MiniAppTrack />} />
                <Route path="saved" element={<MiniAppSaved />} />
                <Route path="profile" element={<MiniAppProfile />} />
              </Route>
              
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
          <Routes>
            <Route path="*" element={<ChatbotWrapper />} />
          </Routes>
        </BrowserRouter>
          </TooltipProvider>
        </BookingFlowProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
