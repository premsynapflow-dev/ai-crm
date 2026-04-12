"use client"

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { isRbiEligibleCompany } from '@/lib/company-profile'
import { planIncludesFeature } from '@/lib/plan-features'
import { Logo } from '@/components/logo'
import { notificationsAPI, type NotificationItem } from '@/lib/api/notifications'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  LayoutDashboard,
  Inbox,
  BarChart3,
  CreditCard,
  Activity,
  Settings,
  LogOut,
  Bell,
  Search,
  Menu,
  ChevronLeft,
  User,
  Users,
  FolderKanban,
  Sparkles,
  ShieldCheck,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [lastReadAt, setLastReadAt] = useState<string | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)

  const notificationStorageKey = useMemo(() => {
    if (!user?.id) {
      return null
    }
    return `synapflow.notifications.lastRead.${user.id}`
  }, [user?.id])

  useEffect(() => {
    if (!notificationStorageKey || typeof window === 'undefined') {
      setLastReadAt(null)
      return
    }

    setLastReadAt(window.localStorage.getItem(notificationStorageKey))
  }, [notificationStorageKey])

  useEffect(() => {
    let cancelled = false

    const loadNotifications = async () => {
      try {
        const items = await notificationsAPI.list(12)
        if (!cancelled) {
          setNotifications(items)
        }
      } catch {
        if (!cancelled) {
          setNotifications([])
        }
      }
    }

    void loadNotifications()
    const intervalId = window.setInterval(() => {
      void loadNotifications()
    }, 30000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const unreadNotifications = useMemo(() => {
    if (!lastReadAt) {
      return notifications
    }

    const lastReadTimestamp = new Date(lastReadAt).getTime()
    if (Number.isNaN(lastReadTimestamp)) {
      return notifications
    }

    return notifications.filter((item) => {
      const createdAt = item.created_at ? new Date(item.created_at).getTime() : 0
      return createdAt > lastReadTimestamp
    })
  }, [lastReadAt, notifications])

  const unreadCount = unreadNotifications.length
  const canAccessRbiCompliance =
    isRbiEligibleCompany(user?.business_sector, user?.is_rbi_regulated) &&
    planIncludesFeature(user?.plan_id, 'rbi_compliance')
  const navItems = [
    { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { href: '/complaints', icon: Inbox, label: 'Complaints Inbox' },
    { href: '/customers', icon: User, label: 'Customer 360' },
    { href: '/assignments', icon: FolderKanban, label: 'Assignments' },
    { href: '/settings/teams', icon: Users, label: 'Teams' },
    { href: '/reply-queue', icon: Sparkles, label: 'AI Reply Queue' },
    ...(canAccessRbiCompliance ? [{ href: '/compliance', icon: ShieldCheck, label: 'RBI Compliance' }] : []),
    { href: '/analytics', icon: BarChart3, label: 'Analytics' },
    { href: '/pricing', icon: CreditCard, label: 'Billing & Plans' },
    { href: '/usage', icon: Activity, label: 'Usage & Limits' },
    { href: '/settings', icon: Settings, label: 'Settings' },
  ]

  const handleLogout = () => {
    logout()
  }

  const handleMarkNotificationsRead = () => {
    const latestTimestamp = notifications[0]?.created_at ?? new Date().toISOString()
    if (notificationStorageKey && typeof window !== 'undefined') {
      window.localStorage.setItem(notificationStorageKey, latestTimestamp)
    }
    setLastReadAt(latestTimestamp)
  }

  const formatRelativeTime = (value: string | null): string => {
    if (!value) {
      return 'Just now'
    }

    const deltaMs = Date.now() - new Date(value).getTime()
    if (Number.isNaN(deltaMs) || deltaMs < 60000) {
      return 'Just now'
    }
    const minutes = Math.floor(deltaMs / 60000)
    if (minutes < 60) {
      return `${minutes} min ago`
    }
    const hours = Math.floor(minutes / 60)
    if (hours < 24) {
      return `${hours} hr ago`
    }
    const days = Math.floor(hours / 24)
    return `${days} day${days === 1 ? '' : 's'} ago`
  }

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className={cn(
        "flex items-center h-16 px-4 border-b border-sidebar-border",
        collapsed ? "justify-center" : "justify-between"
      )}>
        {!collapsed && <Logo size="md" />}
        {collapsed && (
          <svg viewBox="0 0 32 32" fill="none" className="w-8 h-8" aria-hidden="true">
            <defs>
              <linearGradient id="sidebarLogoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3B82F6" />
                <stop offset="100%" stopColor="#8B5CF6" />
              </linearGradient>
            </defs>
            <circle cx="16" cy="8" r="3" fill="url(#sidebarLogoGradient)" />
            <circle cx="8" cy="20" r="3" fill="url(#sidebarLogoGradient)" />
            <circle cx="24" cy="20" r="3" fill="url(#sidebarLogoGradient)" />
            <circle cx="16" cy="24" r="2" fill="url(#sidebarLogoGradient)" />
            <path d="M16 11V22" stroke="url(#sidebarLogoGradient)" strokeWidth="2" strokeLinecap="round" />
            <path d="M14 10L9 18" stroke="url(#sidebarLogoGradient)" strokeWidth="2" strokeLinecap="round" />
            <path d="M18 10L23 18" stroke="url(#sidebarLogoGradient)" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="hidden lg:flex"
          onClick={() => setCollapsed(!collapsed)}
        >
          <ChevronLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
        </Button>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        <TooltipProvider delayDuration={0}>
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                      isActive
                        ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md"
                        : "text-sidebar-foreground hover:bg-sidebar-accent",
                      collapsed && "justify-center px-2"
                    )}
                  >
                    <item.icon className={cn("h-5 w-5 shrink-0", isActive ? "text-white" : "")} />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                </TooltipTrigger>
                {collapsed && (
                  <TooltipContent side="right">
                    {item.label}
                  </TooltipContent>
                )}
              </Tooltip>
            )
          })}
        </TooltipProvider>
      </nav>

      <div className="p-3 border-t border-sidebar-border">
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleLogout}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 w-full transition-all",
                  collapsed && "justify-center px-2"
                )}
              >
                <LogOut className="h-5 w-5 shrink-0" />
                {!collapsed && <span>Logout</span>}
              </button>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">
                Logout
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.08),_transparent_30%),linear-gradient(180deg,_rgba(248,250,252,1),_rgba(241,245,249,1))]">
      {/* Desktop Sidebar */}
      <aside className={cn(
        "fixed left-0 top-0 z-40 h-screen bg-sidebar border-r border-sidebar-border transition-all duration-300 hidden lg:block",
        collapsed ? "w-16" : "w-64"
      )}>
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden fixed left-4 top-4 z-50"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-64">
          <SidebarContent />
        </SheetContent>
      </Sheet>

      {/* Main Content */}
      <div className={cn(
        "transition-all duration-300",
        collapsed ? "lg:ml-16" : "lg:ml-64"
      )}>
        {/* Header */}
        <header className="sticky top-0 z-30 h-16 border-b border-border bg-card/80 backdrop-blur-sm">
          <div className="flex items-center justify-between h-full px-4 lg:px-6">
            <div className="flex items-center gap-4 lg:hidden">
              <div className="w-10" /> {/* Spacer for mobile menu button */}
            </div>

            {/* Search */}
            <div className="hidden md:flex flex-1 max-w-md">
              <div className="relative w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search complaints, customers..."
                  className="pl-10 bg-muted/50 border-0"
                />
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-2">
              {user?.plan_id && (
                <Badge variant="outline" className="hidden border-emerald-200 bg-emerald-50 text-emerald-700 md:inline-flex">
                  {user.plan_id}
                </Badge>
              )}
              {/* Notifications */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="relative">
                    <Bell className="h-5 w-5" />
                    {unreadCount > 0 && (
                      <Badge className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs bg-red-500 hover:bg-red-500">
                        {Math.min(unreadCount, 99)}
                      </Badge>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-80">
                  <DropdownMenuLabel>Notifications</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <div className="max-h-64 overflow-auto">
                    {notifications.length === 0 ? (
                      <div className="p-3 text-sm text-muted-foreground">
                        No live complaint notifications yet.
                      </div>
                    ) : (
                      notifications.map((item) => {
                        const isUnread = unreadNotifications.some((entry) => entry.id === item.id)
                        return (
                          <DropdownMenuItem key={item.id} asChild className="cursor-pointer p-0">
                            <Link href={item.href} className="flex w-full gap-3 p-3">
                              <div className={cn(
                                "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                                item.severity === 'success' && "bg-emerald-500",
                                item.severity === 'high' && "bg-red-500",
                                item.severity === 'medium' && "bg-amber-500",
                                item.severity === 'info' && "bg-blue-500",
                              )} />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-start justify-between gap-2">
                                  <p className={cn("text-sm", isUnread ? "font-semibold" : "font-medium")}>
                                    {item.title}
                                  </p>
                                  {isUnread && (
                                    <span className="mt-1 h-2 w-2 rounded-full bg-primary" aria-hidden="true" />
                                  )}
                                </div>
                                <p className="line-clamp-2 text-xs text-muted-foreground">
                                  {item.message}
                                </p>
                                <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                                  {item.ticket_id ? `${item.ticket_id} • ` : ''}{formatRelativeTime(item.created_at)}
                                </p>
                              </div>
                            </Link>
                          </DropdownMenuItem>
                        )
                      })
                    )}
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-center text-sm text-primary cursor-pointer justify-center"
                    onClick={handleMarkNotificationsRead}
                  >
                    Mark all as read
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* User Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="gap-2 px-2">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-white text-sm">
                        {user?.name.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <span className="hidden sm:inline text-sm font-medium">
                      {user?.name}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>
                    <div>
                      <p className="font-medium">{user?.name}</p>
                      <p className="text-xs text-muted-foreground">{user?.email}</p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/settings" className="cursor-pointer">
                      <User className="h-4 w-4 mr-2" />
                      Profile Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/pricing" className="cursor-pointer">
                      <CreditCard className="h-4 w-4 mr-2" />
                      Billing
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-red-600 cursor-pointer">
                    <LogOut className="h-4 w-4 mr-2" />
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-4 lg:p-6">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t border-border py-4 px-6 text-center text-sm text-muted-foreground">
          &copy; 2026 SynapTec Pvt. Ltd. All rights reserved.
        </footer>
      </div>
    </div>
  )
}
