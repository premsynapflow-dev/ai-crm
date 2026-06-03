import { Outlet, Link, useNavigate, useLocation } from "react-router";
import { useAuth } from "../lib/auth-context";
import { useTheme } from "../lib/theme-context";
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
  Mail,
  Globe,
  Phone,
  Moon,
  Sun,
  BrainCircuit,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, Complaint } from "../lib/api";

const NOTIF_POLL_MS = 30_000;
const NOTIF_MAX_SHOW = 8;

function sourceIcon(source: string) {
  switch (source) {
    case "email":
    case "gmail":
      return <Mail className="size-3.5 shrink-0" />;
    case "whatsapp":
      return <MessageSquare className="size-3.5 shrink-0" />;
    case "voice":
      return <Phone className="size-3.5 shrink-0" />;
    default:
      return <Globe className="size-3.5 shrink-0" />;
  }
}

export function DashboardLayout() {
  const { user, logout, isAuthenticated } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [settingsOpen, setSettingsOpen] = useState(
    location.pathname.startsWith("/app/settings")
  );
  const [replyQueueCount, setReplyQueueCount] = useState(0);
  const [notifications, setNotifications] = useState<Complaint[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const [ticketsUsedLive, setTicketsUsedLive] = useState<number | null>(null);
  const notifTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    api.billing.getUsage()
      .then((data) => setTicketsUsedLive(data.current_usage ?? null))
      .catch(() => null);
  }, [isAuthenticated]);

  // Poll for recent new complaints and surface as notifications
  const pollNotifications = useRef(async () => {
    try {
      const items = await api.complaints.list({ status: "new" });
      const recent = items.slice(0, NOTIF_MAX_SHOW);
      setNotifications(recent);
    } catch {
      // silently ignore
    }
  });

  useEffect(() => {
    if (!isAuthenticated) return;
    pollNotifications.current();
    notifTimerRef.current = setInterval(() => pollNotifications.current(), NOTIF_POLL_MS);
    return () => {
      if (notifTimerRef.current) clearInterval(notifTimerRef.current);
    };
  }, [isAuthenticated]);

  const unseenCount = notifications.filter((n) => !seenIds.has(n.id)).length;

  const handleOpenNotifications = () => {
    setNotifOpen((o) => !o);
    setSeenIds(new Set(notifications.map((n) => n.id)));
  };

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
    { name: "Executive", href: "/app/executive", icon: BrainCircuit },
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

  const ticketsUsed = ticketsUsedLive ?? user.ticketsUsed ?? 0;
  const ticketsQuota = user.ticketsQuota ?? 50;

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-gray-900 border-r dark:border-gray-800 flex flex-col">
        <div className="p-4 border-b dark:border-gray-800">
          <Link to="/app/dashboard" className="flex items-center gap-2">
            <img src="/logo.png" alt="SynapFlow" className="size-8 object-contain" />
            <div>
              <div className="font-semibold dark:text-white">SynapFlow</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">{user.companyName || "Demo Company"}</div>
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
                      ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
                      : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
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

          <div className="mt-6 pt-6 border-t dark:border-gray-800">
            <button
              onClick={() => setSettingsOpen((o) => !o)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-md text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
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
                          ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
                          : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
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
        <div className="p-4 border-t dark:border-gray-800 space-y-3">
          <div className="text-xs text-gray-600 dark:text-gray-400">
            <div className="flex items-center justify-between mb-1">
              <span>Tickets this month</span>
              <span className="font-semibold">
                {ticketsUsed} / {ticketsQuota}
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
              <div
                className="bg-blue-600 h-1.5 rounded-full"
                style={{ width: `${Math.min(100, (ticketsUsed / Math.max(ticketsQuota, 1)) * 100)}%` }}
              />
            </div>
          </div>

          <Link to="/app/billing">
            <Button variant="outline" size="sm" className="w-full dark:border-gray-700 dark:text-gray-300">
              <CreditCard className="size-4 mr-2" />
              Upgrade Plan
            </Button>
          </Link>
        </div>

        {/* User Menu */}
        <div className="p-4 border-t dark:border-gray-800">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="w-full justify-start dark:hover:bg-gray-800">
                <User className="size-4 mr-2" />
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium dark:text-gray-200">{user.companyName || user.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{user.email}</div>
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
        <header className="bg-white dark:bg-gray-900 border-b dark:border-gray-800 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Badge variant="secondary" className="capitalize">
              {user.plan} Plan
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
            </Button>

            <DropdownMenu open={notifOpen} onOpenChange={setNotifOpen}>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="relative"
                  onClick={handleOpenNotifications}
                >
                  <Bell className="size-5" />
                  {unseenCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                      {unseenCount > 9 ? "9+" : unseenCount}
                    </span>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                <DropdownMenuLabel className="flex items-center justify-between">
                  <span>New Complaints</span>
                  {notifications.length > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {notifications.length}
                    </Badge>
                  )}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {notifications.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-gray-500">
                    No new complaints
                  </div>
                ) : (
                  notifications.map((n) => (
                    <DropdownMenuItem key={n.id} asChild>
                      <Link
                        to={`/app/complaints/${n.id}`}
                        className="flex flex-col items-start gap-1 px-3 py-2 cursor-pointer"
                        onClick={() => setNotifOpen(false)}
                      >
                        <div className="flex items-center gap-2 w-full">
                          {sourceIcon(n.source)}
                          <span className="text-xs font-medium text-gray-500">
                            {n.ticket_number || n.id.slice(0, 8)}
                          </span>
                          <span className="ml-auto text-[10px] text-gray-400">
                            {new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        <p className="text-sm font-medium line-clamp-1">{n.summary}</p>
                        <p className="text-xs text-gray-500">{n.customer_email}</p>
                      </Link>
                    </DropdownMenuItem>
                  ))
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link
                    to="/app/complaints"
                    className="text-center text-sm text-blue-600 font-medium py-2"
                    onClick={() => setNotifOpen(false)}
                  >
                    View all complaints →
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
