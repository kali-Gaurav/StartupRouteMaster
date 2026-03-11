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
import VerificationGate from "@/components/auth/VerificationGate";
import { BookingFlowProvider } from "@/context/BookingFlowContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { useServerWarmup } from "@/hooks/useServerWarmup";
import { IconSprite } from "./components/ui/IconSprite";
import ErrorBoundary from "./components/ErrorBoundary";
import { queryClient } from "./infrastructure/queryClient";

// Lazy load pages
const Index = lazy(() => import("./pages/Index"));
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
const SignupPage = lazy(() => import("./pages/auth/SignupPage"));
const VerifyOTPPage = lazy(() => import("./pages/auth/VerifyOTPPage"));
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
const AdminOperations = lazy(() => import("./pages/AdminOperations"));
const AdminFinance = lazy(() => import("./pages/AdminFinance"));
const AdminGrowth = lazy(() => import("./pages/AdminGrowth"));
const AdminAI = lazy(() => import("./pages/AdminAI"));
const AdminSystem = lazy(() => import("./pages/AdminSystem"));
const AdminAudit = lazy(() => import("./pages/AdminAudit"));
const AdminSettings = lazy(() => import("./pages/AdminSettings"));

import ProtectedAdminRoute from "./components/auth/ProtectedAdminRoute";
import AdminLayout from "./components/layout/AdminLayout";

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

const ServerWarmupLoader = () => (
  <div className="flex items-center justify-center min-h-screen bg-slate-900 text-white">
    <div className="flex flex-col items-center gap-6 max-w-sm text-center px-6">
      <div className="relative">
        <div className="w-20 h-20 rounded-full border-4 border-blue-500/20 border-t-blue-500 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-10 h-10 bg-blue-500/10 rounded-full animate-pulse" />
        </div>
      </div>
      <div className="space-y-2">
        <h2 className="text-xl font-bold tracking-tight">Waking up server</h2>
        <p className="text-slate-400 text-sm leading-relaxed">
          The application is starting up on the cloud. This usually takes 10-20 seconds on the first load.
        </p>
      </div>
    </div>
  </div>
);

const AppContent = () => {
  usePushNotifications();
  const { isWakingUp } = useServerWarmup();

  if (isWakingUp && import.meta.env.PROD) {
    return <ServerWarmupLoader />;
  }

  return (
    <TooltipProvider>
      <IconSprite />
      <Toaster />
      <Sonner />
      <NetworkStatusBanner />
      <SOSWidget />
      <DevBootstrap />
      <DevDebugPanel />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<ErrorBoundary name="Landing"><Index /></ErrorBoundary>} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/verify-otp" element={<VerifyOTPPage />} />
            
            <Route path="/sos" element={<ErrorBoundary name="SOS"><SOS /></ErrorBoundary>} />
            
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <VerificationGate>
                  <ErrorBoundary name="Dashboard"><Dashboard /></ErrorBoundary>
                </VerificationGate>
              </ProtectedRoute>
            } />
            
            <Route path="/bookings" element={
              <ProtectedRoute>
                <VerificationGate>
                  <ErrorBoundary name="Bookings"><Bookings /></ErrorBoundary>
                </VerificationGate>
              </ProtectedRoute>
            } />
            
            <Route path="/ticket/:bookingId" element={<ErrorBoundary name="Ticket"><Ticket /></ErrorBoundary>} />
            <Route path="/responder" element={<Responder />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/safety" element={<Safety />} />
            <Route path="/track/:trainNumber" element={<ErrorBoundary name="Tracking"><TrainTracking /></ErrorBoundary>} />
            <Route path="/ops/sos" element={<SOSDashboard />} />
            
            {/* High-Tech Admin Portals (Task 10) */}
            <Route path="/ops/admin" element={
              <ProtectedAdminRoute>
                <AdminLayout />
              </ProtectedAdminRoute>
            }>
              <Route index element={<AdminDashboard />} />
              <Route path="operations" element={<AdminOperations />} />
              <Route path="finance" element={<AdminFinance />} />
              <Route path="growth" element={<AdminGrowth />} />
              <Route path="ai" element={<AdminAI />} />
              <Route path="system" element={<AdminSystem />} />
              <Route path="audit" element={<AdminAudit />} />
              <Route path="settings" element={<AdminSettings />} />
            </Route>

            {/* Mini App with Granular Resilience (Suggestion #25) */}
            <Route path="/mini-app" element={
              <ProtectedRoute>
                <VerificationGate>
                  <MiniAppGate><ErrorBoundary name="MiniAppRoot"><Outlet /></ErrorBoundary></MiniAppGate>
                </VerificationGate>
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
