import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Lock, Shield } from "lucide-react";
import { useAuth } from "../lib/auth-context";
import { Link } from "react-router";

export function Compliance() {
  const { user } = useAuth();
  const hasAccess = user && ["scale", "enterprise"].includes(user.plan);

  if (!hasAccess) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">RBI Compliance</h1>
          <p className="text-gray-600">Track regulatory TAT deadlines and generate MIS reports</p>
        </div>

        <Card className="border-2 border-dashed">
          <CardContent className="py-16 text-center">
            <Lock className="size-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-2xl font-semibold mb-2">Upgrade to Scale or Enterprise</h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              RBI compliance tracking, TAT monitoring, escalation management, and automated MIS
              reports are available on Scale and Enterprise plans.
            </p>
            <Link to="/app/billing">
              <Button size="lg">
                <Shield className="size-4 mr-2" />
                Upgrade Now
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">RBI Compliance</h1>
        <p className="text-gray-600">Track regulatory TAT deadlines and generate MIS reports</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Within TAT
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-600">12</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Approaching Breach
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-orange-600">3</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Breached
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-600">1</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total RBI Complaints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">16</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>RBI Complaints</CardTitle>
            <Button>Generate MIS Report</Button>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600">
            RBI-registered complaints with TAT tracking and escalation management
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
