import { createBrowserRouter } from "react-router";
import { LandingPage } from "./pages/LandingPage";
import { SignupPage } from "./pages/SignupPage";
import { LoginPage } from "./pages/LoginPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { Dashboard } from "./pages/Dashboard";
import { ComplaintsInbox } from "./pages/ComplaintsInbox";
import { ReplyQueue } from "./pages/ReplyQueue";
import { Customers } from "./pages/Customers";
import { CustomerProfile } from "./pages/CustomerProfile";
import { Assignments } from "./pages/Assignments";
import { Analytics } from "./pages/Analytics";
import { Compliance } from "./pages/Compliance";
import { SettingsProfile } from "./pages/SettingsProfile";
import { SettingsConnections } from "./pages/SettingsConnections";
import { SettingsNotifications } from "./pages/SettingsNotifications";
import { SettingsWebhooks } from "./pages/SettingsWebhooks";
import { Teams } from "./pages/Teams";
import { KnowledgeBase } from "./pages/KnowledgeBase";
import { Automations } from "./pages/Automations";
import { BillingPage } from "./pages/BillingPage";
import { AdminPanel } from "./pages/AdminPanel";
import { ComplaintDetail } from "./pages/ComplaintDetail";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: LandingPage,
  },
  {
    path: "/signup",
    Component: SignupPage,
  },
  {
    path: "/login",
    Component: LoginPage,
  },
  {
    path: "/forgot-password",
    Component: ForgotPasswordPage,
  },
  {
    path: "/app",
    Component: DashboardLayout,
    children: [
      {
        path: "dashboard",
        Component: Dashboard,
      },
      {
        path: "complaints",
        Component: ComplaintsInbox,
      },
      {
        path: "complaints/:id",
        Component: ComplaintDetail,
      },
      {
        path: "reply-queue",
        Component: ReplyQueue,
      },
      {
        path: "customers",
        Component: Customers,
      },
      {
        path: "customers/:id",
        Component: CustomerProfile,
      },
      {
        path: "assignments",
        Component: Assignments,
      },
      {
        path: "analytics",
        Component: Analytics,
      },
      {
        path: "compliance",
        Component: Compliance,
      },
      {
        path: "knowledge",
        Component: KnowledgeBase,
      },
      {
        path: "settings",
        Component: SettingsProfile,
      },
      {
        path: "settings/connections",
        Component: SettingsConnections,
      },
      {
        path: "settings/notifications",
        Component: SettingsNotifications,
      },
      {
        path: "settings/webhooks",
        Component: SettingsWebhooks,
      },
      {
        path: "settings/teams",
        Component: Teams,
      },
      {
        path: "settings/automations",
        Component: Automations,
      },
      {
        path: "billing",
        Component: BillingPage,
      },
    ],
  },
  {
    path: "/admin",
    Component: AdminPanel,
  },
]);
