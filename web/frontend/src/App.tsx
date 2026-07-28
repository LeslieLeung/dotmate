import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import { Layout } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { authApi, type AuthStatus } from "@/lib/api";
import { DeviceDetailPage } from "@/pages/DeviceDetailPage";
import { DevicesPage } from "@/pages/DevicesPage";
import { LoginPage } from "@/pages/LoginPage";
import { SettingsPage } from "@/pages/SettingsPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const checkAuthentication = useCallback(async () => {
    setFailed(false);
    try {
      setStatus(await authApi.status());
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void checkAuthentication();
  }, [checkAuthentication]);

  if (failed) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Empty className="max-w-md border">
          <EmptyHeader>
            <EmptyMedia variant="icon"><ShieldAlert /></EmptyMedia>
            <EmptyTitle>Unable to verify access</EmptyTitle>
            <EmptyDescription>Check the server connection and try again.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button onClick={() => void checkAuthentication()}>Try Again</Button>
          </EmptyContent>
        </Empty>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="flex w-full max-w-sm flex-col gap-3">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (status.auth_required && !status.authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Toaster />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/devices" replace />} />
            <Route path="devices" element={<DevicesPage />} />
            <Route path="devices/:id" element={<DeviceDetailPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  );
}
