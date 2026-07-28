import { useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut, Menu, Monitor, Settings } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { clearToken, getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/devices", label: "Devices", icon: Monitor },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    clearToken();
    navigate("/login", { replace: true });
  }

  function navigation(onNavigate?: () => void) {
    return (
      <nav className="flex flex-1 flex-col gap-1 p-2" aria-label="Primary navigation">
        {navItems.map(({ to, label, icon: Icon }) => {
          const active = location.pathname.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon />
              {label}
            </Link>
          );
        })}
      </nav>
    );
  }

  function accountActions() {
    if (!getToken()) return null;
    return (
      <div className="p-2">
        <Button
          variant="ghost"
          className="w-full justify-start text-muted-foreground"
          onClick={handleLogout}
        >
          <LogOut data-icon="inline-start" />
          Log Out
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center gap-3 border-b px-4 md:hidden">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation"
          onClick={() => setMobileOpen(true)}
        >
          <Menu />
        </Button>
        <span className="font-semibold">Dotmate</span>
      </header>

      <div className="flex min-h-[calc(100vh-3.5rem)] md:min-h-screen">
        <aside className="hidden w-56 flex-col border-r bg-muted/30 md:flex">
          <div className="p-4 text-lg font-semibold">Dotmate</div>
          <Separator />
          {navigation()}
          {getToken() && <Separator />}
          {accountActions()}
        </aside>

        <main className="min-w-0 flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-72 gap-0" showCloseButton>
          <SheetHeader>
            <SheetTitle>Dotmate</SheetTitle>
          </SheetHeader>
          <Separator />
          {navigation(() => setMobileOpen(false))}
          {getToken() && <Separator />}
          {accountActions()}
        </SheetContent>
      </Sheet>
    </div>
  );
}
