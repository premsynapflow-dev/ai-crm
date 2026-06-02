import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { api, Customer } from "../lib/api";
import { Search, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router";

export function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadCustomers();
  }, []);

  const loadCustomers = async () => {
    setLoading(true);
    try {
      const data = await api.customers.list({ search: searchQuery || undefined });
      setCustomers(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || "Failed to load customers";
      console.error("Failed to load customers:", err);
      // 401 is handled globally in api.ts; show toast for other errors
      if (!msg.includes("Session expired")) {
        toast.error(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const getChurnBadge = (risk: string) => {
    const colors: Record<string, string> = {
      low: "bg-green-100 text-green-800",
      medium: "bg-yellow-100 text-yellow-800",
      high: "bg-red-100 text-red-800",
    };
    return <Badge className={colors[risk]}>{risk} risk</Badge>;
  };

  const filteredCustomers = customers.filter((customer) =>
    customer.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    customer.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Customer 360</h1>
        <p className="text-gray-600">View customer profiles and health metrics</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Total Customers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{customers.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              High Churn Risk
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-600">
              {customers.filter((c) => c.churn_risk === "high").length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Active Tickets
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {customers.reduce((sum, c) => sum + c.open_tickets, 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">
              Avg Satisfaction
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {(
                customers.reduce((sum, c) => sum + c.avg_satisfaction_score, 0) /
                customers.length
              ).toFixed(1)}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Customers</CardTitle>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-gray-400" />
              <Input
                placeholder="Search customers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading customers...</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Total Tickets</TableHead>
                  <TableHead>Open</TableHead>
                  <TableHead>Sentiment</TableHead>
                  <TableHead>Churn Risk</TableHead>
                  <TableHead>LTV</TableHead>
                  <TableHead>Last Contact</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCustomers.map((customer) => (
                  <TableRow key={customer.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{customer.name}</div>
                        <div className="text-sm text-gray-500">{customer.email}</div>
                        {customer.company_name && (
                          <div className="text-xs text-gray-400">{customer.company_name}</div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="capitalize">{customer.customer_type}</TableCell>
                    <TableCell>{customer.total_tickets}</TableCell>
                    <TableCell>
                      <Badge variant={customer.open_tickets > 0 ? "secondary" : "outline"}>
                        {customer.open_tickets}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          customer.sentiment_label === "positive"
                            ? "bg-green-100 text-green-800"
                            : customer.sentiment_label === "negative"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-800"
                        }
                      >
                        {customer.sentiment_label}
                      </Badge>
                    </TableCell>
                    <TableCell>{getChurnBadge(customer.churn_risk)}</TableCell>
                    <TableCell>
                      {customer.lifetime_value
                        ? `₹${customer.lifetime_value.toLocaleString()}`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">
                      {new Date(customer.last_interaction_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Link to={`/app/customers/${customer.id}`}>
                        <Button size="sm" variant="ghost">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
