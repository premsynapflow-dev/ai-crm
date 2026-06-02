import { Outlet, Link, useNavigate, useLocation } from "react-router";
import { useAuth } from "../lib/auth-context";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import {
  LayoutDashboard,
  MessageSquare,
  Bot,
  Users,
  UserCog,
  BarChart3,
  Shield,
  BookOpen,
  Settings,
  Bell,
  CreditCard,
  Zap,
  LogOut,
  User,
  Link2,
  Webhook,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function DashboardLayout() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [settingsOpen, setSettingsOpen] = useState(
    location.pathname.startsWith("/app/settings")
  );
  const [replyQueueCount, setReplyQueueCount] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) return;
    api.replyQueue.list("pending")
      .then((data) => setReplyQueueCount(Array.isArray(data) ? data.length : 0))
      .catch(() => null);
  }, [isAuthenticated]);

  // Auto-expand settings when navigating to a settings page
  useEffect(() => {
    if (location.pathname.startsWith("/app/settings")) {
      setSettingsOpen(true);
    }
  }, [location.pathname]);

  if (!isAuthenticated || !user) {
    return null;
  }

  const navigation = [
    { name: "Dashboard", href: "/app/dashboard", icon: LayoutDashboard },
    { name: "Complaints", href: "/app/complaints", icon: MessageSquare },
    { name: "Reply Queue", href: "/app/reply-queue", icon: Bot, badge: replyQueueCount || undefined },
    { name: "Customers", href: "/app/customers", icon: Users },
    { name: "Assignments", href: "/app/assignments", icon: UserCog },
    { name: "Analytics", href: "/app/analytics", icon: BarChart3 },
    {
      name: "Compliance",
      href: "/app/compliance",
      icon: Shield,
      locked: !["scale", "enterprise"].includes(user.plan),
    },
    { name: "Knowledge Base", href: "/app/knowledge", icon: BookOpen },
  ];

  const settingsNav = [
    { name: "Profile", href: "/app/settings", icon: User },
    { name: "Connections", href: "/app/settings/connections", icon: Link2 },
    { name: "Notifications", href: "/app/settings/notifications", icon: Bell },
    { name: "Webhooks", href: "/app/settings/webhooks", icon: Webhook },
    { name: "Teams", href: "/app/settings/teams", icon: Users },
    { name: "Automations", href: "/app/settings/automations", icon: Zap },
  ];

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const isActive = (href: string) => {
    if (href === "/app/settings") {
      return location.pathname.startsWith("/app/settings");
    }
    return location.pathname === href || location.pathname.startsWith(href + "/");
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r flex flex-col">
        <div className="p-4 border-b">
          <Link to="/app/dashboard" className="flex items-center gap-2">
            <Bot className="size-8 text-blue-600" />
            <div>
              <div className="font-semibold">SynapFlow</div>
              <div className="text-xs text-gray-500">{user.companyName || "Demo Company"}</div>
            </div>
          </Link>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);

              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                    active
                      ? "bg-blue-50 text-blue-600"
                      : "text-gray-700 hover:bg-gray-100"
                  } ${item.locked ? "opacity-50" : ""}`}
                >
                  <Icon className="size-5 shrink-0" />
                  <span className="flex-1">{item.name}</span>
                  {item.badge && (
                    <Badge variant="secondary" className="ml-auto">
                      {item.badge}
                    </Badge>
                  )}
                  {item.locked && (
                    <Badge variant="outline" className="ml-auto text-xs">
                      Locked
                    </Badge>
                  )}
                </Link>
              );
            })}
          </nav>

          <div className="mt-6 pt-6 border-t">
            <button
              onClick={() => setSettingsOpen((o) => !o)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-md text-sm font-semibold text-gray-500 uppercase tracking-wide hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Settings className="size-4" />
                <span>Settings</span>
              </div>
              {settingsOpen ? (
                <ChevronDown className="size-4" />
              ) : (
                <ChevronRight className="size-4" />
              )}
            </button>
            {settingsOpen && (
              <nav className="mt-1 space-y-1">
                {settingsNav.map((item) => {
                  const Icon = item.icon;
                  const active = location.pathname === item.href;
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                        active
                          ? "bg-blue-50 text-blue-600"
                          : "text-gray-700 hover:bg-gray-100"
                      }`}
                    >
                      <Icon className="size-4 shrink-0" />
                      <span>{item.name}</span>
                    </Link>
                  );
                })}
              </nav>
            )}
          </div>
        </ScrollArea>

        {/* Usage & Upgrade */}
        <div className="p-4 border-t space-y-3">
          <div className="text-xs text-gray-600">
            <div className="flex items-center justify-between mb-1">
              <span>Tickets this month</span>
              <span className="font-semibold">
                {user.ticketsUsed} / {user.ticketsQuota}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div
                className="bg-blue-600 h-1.5 rounded-full"
                style={{ width: `${(user.ticketsUsed / user.ticketsQuota) * 100}%` }}
              />
            </div>
          </div>

          <Link to="/app/billing">
            <Button variant="outline" size="sm" className="w-full">
              <CreditCard className="size-4 mr-2" />
              Upgrade Plan
            </Button>
          </Link>
        </div>

        {/* User Menu */}
        <div className="p-4 border-t">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="w-full justify-start">
                <User className="size-4 mr-2" />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium">{user.name}</div>
                  <div className="text-xs text-gray-500">{user.email}</div>
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/app/settings">
                  <Settings className="size-4 mr-2" />
                  Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/app/billing">
                  <CreditCard className="size-4 mr-2" />
                  Billing
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="size-4 mr-2" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Badge variant="secondary" className="capitalize">
              {user.plan} Plan
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon">
              <Bell className="size-5" />
            </Button>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}