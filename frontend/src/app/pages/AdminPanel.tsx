import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Shield } from "lucide-react";
import { useState } from "react";

export function AdminPanel() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const [adminData, setAdminData] = useState<Record<string, unknown> | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { api } = await import("../lib/api");
      const data = await api.admin.getOverview(password) as Record<string, unknown>;
      setAdminData(data);
      setIsAuthenticated(true);
    } catch {
      alert("Invalid admin credentials");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="flex items-center justify-center gap-2 mb-4">
              <Shield className="size-8 text-blue-600" />
            </div>
            <CardTitle>Admin Panel</CardTitle>
            <p className="text-sm text-gray-600">Internal access only</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  required
                />
              </div>

              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  required
                />
              </div>

              <Button type="submit" className="w-full">
                Login to Admin Panel
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Shield className="size-8 text-blue-600" />
          <div>
            <h1 className="text-3xl font-bold">Admin Panel</h1>
            <p className="text-gray-600">System-wide tenant management</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Tenants
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{String(adminData?.total_tenants ?? "—")}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Active Tenants
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{String(adminData?.active_tenants ?? "—")}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Tickets
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{String(adminData?.total_tickets ?? "—")}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Active Subscriptions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{String(adminData?.active_subscriptions ?? "—")}</div>
              <p className="text-xs text-gray-500 mt-1">MRR</p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Tenant List</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {((adminData?.tenants_by_plan as Array<{ plan: string; count: number }>) || []).map(
                (row, i) => (
                  <div key={i} className="flex items-center justify-between p-4 border rounded">
                    <div>
                      <div className="font-medium capitalize">{row.plan || "Unknown"} plan</div>
                    </div>
                    <div className="flex items-center gap-4">
                      <Badge className="capitalize">{row.plan}</Badge>
                      <span className="text-sm text-gray-600">{row.count} tenants</span>
                    </div>
                  </div>
                )
              )}
              {!adminData?.tenants_by_plan && (
                <p className="text-center text-gray-500 py-4">No tenant data available</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
