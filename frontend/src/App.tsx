import { Toaster } from "@/components/ui/toaster-new";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate, Outlet, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { MiniAppGate } from "@/components/MiniAppGate";
import { RailAssistantChatbot } from "@/components/RailAssistantChatbot";
import { SOSWidget } from "@/components/SOSWidget";
import { NetworkStatusBanner } from "@/components/NetworkStatusBanner";
import { BottomNav } from "@/components/BottomNav";
import { DevBootstrap } from "@/components/DevBootstrap";
import { DevDebugPanel } from "@/components/DevDebugPanel";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { BookingFlowProvider } from "@/context/BookingFlowContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { IconSprite } from "./components/ui/IconSprite";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { queryClient } from "./infrastructure/queryClient";

// Lazy load pages
const Index = lazy(() => import("./pages/Index"));
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const SignupPage = lazy(() => import("./pages/auth/SignupPage"));
const SOS = lazy(() => import("./pages/SOS"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Bookings = lazy(() => import("./pages/Bookings"));
const Ticket = lazy(() => import("./pages/Ticket"));
const Responder = lazy(() => import("./pages/Responder"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Privacy = lazy(() => import("./pages/Privacy"));
const Terms = lazy(() => import("./pages/Terms"));
const Safety = lazy(() => import("./pages/Safety"));
const TrainTracking = lazy(() => import("./pages/TrainTracking"));
const SOSDashboard = lazy(() => import("./pages/SOSDashboard"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));

const MiniAppHome = lazy(() => import("./pages/mini-app/Home"));
const MiniAppSearch = lazy(() => import("./pages/mini-app/Search"));
const MiniAppBooking = lazy(() => import("./pages/mini-app/Booking"));
const MiniAppSOS = lazy(() => import("./pages/mini-app/SOS"));
const MiniAppTrack = lazy(() => import("./pages/mini-app/Track"));
const MiniAppSaved = lazy(() => import("./pages/mini-app/Saved"));
const MiniAppProfile = lazy(() => import("./pages/mini-app/Profile"));

const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen bg-background">
    <div className="flex flex-col items-center gap-4">
      <div className="w-12 h-12 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
      <p className="text-sm text-muted-foreground animate-pulse">Initializing Interface...</p>
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

const AppContent = () => {
  usePushNotifications();
  return (
    <TooltipProvider>
      <IconSprite />
      <Toaster />
      <Sonner />
      <NetworkStatusBanner />
      <SOSWidget />
      <DevBootstrap />
      <DevDebugPanel />
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<ErrorBoundary name="Landing"><Index /></ErrorBoundary>} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            
            <Route path="/sos" element={<ErrorBoundary name="SOS"><SOS /></ErrorBoundary>} />
            
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <ErrorBoundary name="Dashboard"><Dashboard /></ErrorBoundary>
              </ProtectedRoute>
            } />
            
            <Route path="/bookings" element={
              <ProtectedRoute>
                <ErrorBoundary name="Bookings"><Bookings /></ErrorBoundary>
              </ProtectedRoute>
            } />
            
            <Route path="/ticket/:bookingId" element={<ErrorBoundary name="Ticket"><Ticket /></ErrorBoundary>} />
            <Route path="/responder" element={<Responder />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/safety" element={<Safety />} />
            <Route path="/track/:trainNumber" element={<ErrorBoundary name="Tracking"><TrainTracking /></ErrorBoundary>} />
            <Route path="/ops/sos" element={<SOSDashboard />} />
            <Route path="/ops/admin" element={<AdminDashboard />} />

            {/* Mini App with Granular Resilience (Suggestion #25) */}
            <Route path="/mini-app" element={
              <ProtectedRoute>
                <MiniAppGate><ErrorBoundary name="MiniAppRoot"><Outlet /></ErrorBoundary></MiniAppGate>
              </ProtectedRoute>
            }>
              <Route index element={<Navigate to="home" replace />} />
              <Route path="home" element={<ErrorBoundary name="MiniHome"><MiniAppHome /></ErrorBoundary>} />
              <Route path="search" element={<ErrorBoundary name="MiniSearch"><MiniAppSearch /></ErrorBoundary>} />
              <Route path="booking" element={<ErrorBoundary name="MiniBooking"><MiniAppBooking /></ErrorBoundary>} />
              <Route path="sos" element={<MiniAppSOS />} />
              <Route path="track" element={<MiniAppTrack />} />
              <Route path="saved" element={<MiniAppSaved />} />
              <Route path="profile" element={<MiniAppProfile />} />
            </Route>
            
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
        <Routes>
          <Route path="*" element={<ChatbotWrapper />} />
        </Routes>
        <BottomNav />
      </BrowserRouter>
    </TooltipProvider>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <AuthProvider>
        <BookingFlowProvider>
          <AppContent />
        </BookingFlowProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
