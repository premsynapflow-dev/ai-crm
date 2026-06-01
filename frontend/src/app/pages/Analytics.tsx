import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Lock } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { Link } from "react-router";

export function Analytics() {
  const { user } = useAuth();
  const hasAdvancedAccess = user && ["max", "scale", "enterprise"].includes(user.plan);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Analytics</h1>
        <p className="text-gray-600">Insights and performance metrics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Ticket Volume Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center text-gray-400">
              Chart: Ticket volume over last 30 days
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Priority Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center text-gray-400">
              Chart: Priority breakdown
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Locked Features */}
      {!hasAdvancedAccess && (
        <Card className="border-2 border-dashed relative">
          <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center z-10 rounded-lg">
            <div className="text-center p-8">
              <Lock className="size-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">Upgrade to Access Advanced Analytics</h3>
              <p className="text-gray-600 mb-4">
                Get churn prediction, root cause analysis, and team performance insights
              </p>
              <Link to="/app/billing">
                <Button>Upgrade to Max Plan</Button>
              </Link>
            </div>
          </div>
          <CardHeader>
            <CardTitle>Advanced Analytics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 opacity-50">
              <div className="p-4 border rounded">Churn Risk Analysis</div>
              <div className="p-4 border rounded">Root Cause Summary</div>
              <div className="p-4 border rounded">Team Performance Metrics</div>
            </div>
          </CardContent>
        </Card>
      )}

      {hasAdvancedAccess && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Churn Risk Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600">High-risk customers and intervention recommendations</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Root Cause Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600">AI-generated insights on top complaint causes</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Team Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600">Per-agent metrics: resolution time, CSAT, SLA compliance</p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
