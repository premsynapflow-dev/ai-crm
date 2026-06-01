import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

export function Teams() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Teams</h1>
          <p className="text-gray-600">Manage teams and routing rules</p>
        </div>
        <Button>Create Team</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Support Team</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Members</span>
              <span className="font-medium">5 agents</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Routing Categories</span>
              <div className="flex gap-1">
                <Badge variant="outline">Billing</Badge>
                <Badge variant="outline">Technical</Badge>
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline">Manage Members</Button>
              <Button size="sm" variant="outline">Edit Routing</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Escalations Team</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Members</span>
              <span className="font-medium">2 managers</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Routing Categories</span>
              <div className="flex gap-1">
                <Badge variant="outline">Escalated</Badge>
                <Badge variant="outline">Critical</Badge>
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline">Manage Members</Button>
              <Button size="sm" variant="outline">Edit Routing</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
