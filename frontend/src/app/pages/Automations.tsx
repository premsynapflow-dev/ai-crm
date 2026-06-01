import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { api, AutomationRule } from "../lib/api";
import { Zap, Plus } from "lucide-react";

export function Automations() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    setLoading(true);
    try {
      const data = await api.automations.list();
      setRules(data);
    } catch (error) {
      console.error("Failed to load rules:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleRule = async (id: string, enabled: boolean) => {
    try {
      await api.automations.update(id, { enabled });
      loadRules();
    } catch (error) {
      console.error("Failed to toggle rule:", error);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Automation Rules</h1>
          <p className="text-gray-600">Create "if this, then that" rules for complaints</p>
        </div>
        <Button>
          <Plus className="size-4 mr-2" />
          Create Rule
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total Rules
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{rules.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Active Rules
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {rules.filter((r) => r.enabled).length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Last Triggered
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm">
              {rules[0]?.last_triggered
                ? new Date(rules[0].last_triggered).toLocaleString()
                : "Never"}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Automation Rules</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading rules...</div>
          ) : rules.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Zap className="size-12 mx-auto mb-3 text-gray-400" />
              <p>No automation rules yet</p>
              <Button className="mt-4">
                <Plus className="size-4 mr-2" />
                Create Your First Rule
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {rules.map((rule) => (
                <div key={rule.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold">{rule.name}</h3>
                        <Badge variant={rule.enabled ? "default" : "outline"}>
                          {rule.enabled ? "Active" : "Disabled"}
                        </Badge>
                      </div>

                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="text-gray-600">Trigger: </span>
                          <code className="bg-gray-100 px-2 py-0.5 rounded">
                            {rule.trigger}
                          </code>
                        </div>

                        <div>
                          <span className="text-gray-600">Conditions: </span>
                          {rule.conditions.map((c, i) => (
                            <Badge key={i} variant="outline" className="mr-1">
                              {c.field} {c.operator} {c.value}
                            </Badge>
                          ))}
                        </div>

                        <div>
                          <span className="text-gray-600">Actions: </span>
                          {rule.actions.map((a, i) => (
                            <Badge key={i} variant="secondary" className="mr-1">
                              {a.type}
                            </Badge>
                          ))}
                        </div>
                      </div>

                      {rule.last_triggered && (
                        <div className="text-xs text-gray-500 mt-2">
                          Last triggered: {new Date(rule.last_triggered).toLocaleString()}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      <Switch
                        checked={rule.enabled}
                        onCheckedChange={(checked) => toggleRule(rule.id, checked)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
