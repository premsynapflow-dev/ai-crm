import { useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { PasswordInput } from "../components/ui/password-input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../lib/auth-context";
import { toast } from "sonner";

// Maps display labels to backend sector codes
const SECTOR_MAP: Record<string, string> = {
  "Fintech / Payments": "fintech_payments",
  "NBFC / HFC": "nbfc_hfc",
  "Bank": "bank",
  "Other RBI-regulated": "other_rbi_regulated",
  "D2C / E-commerce / Other": "not_rbi_regulated",
};

export function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { signup } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const sectorCode = SECTOR_MAP[businessType] || "not_rbi_regulated";
      await signup({ name, email, password, businessType: sectorCode, phone: phone || undefined });
      toast.success("Account created successfully!");
      navigate("/app/dashboard");
    } catch (error) {
      toast.error("Failed to create account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <img src="/logo.png" alt="SynapFlow" className="size-8 object-contain" />
            <span className="text-2xl font-semibold">SynapFlow</span>
          </div>
          <CardTitle>Create your account</CardTitle>
          <CardDescription>Start managing complaints with AI assistance</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                type="text"
                placeholder="Enter your full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <PasswordInput
                id="password"
                placeholder="Create a strong password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            <div>
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+91 98765 43210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="businessType">Business Type</Label>
              <Select value={businessType} onValueChange={setBusinessType} required>
                <SelectTrigger>
                  <SelectValue placeholder="Select your business type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Fintech / Payments">Fintech / Payments</SelectItem>
                  <SelectItem value="NBFC / HFC">NBFC / HFC</SelectItem>
                  <SelectItem value="Bank">Bank</SelectItem>
                  <SelectItem value="Other RBI-regulated">Other RBI-regulated</SelectItem>
                  <SelectItem value="D2C / E-commerce / Other">D2C / E-commerce / Other</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500 mt-1">
                RBI compliance is auto-enabled for Fintech, NBFC, and Bank
              </p>
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating account..." : "Sign up"}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-gray-600">Already have an account? </span>
            <Link to="/login" className="text-blue-600 hover:underline">
              Log in
            </Link>
          </div>

          <p className="text-xs text-gray-500 text-center mt-4">
            Free plan includes 50 tickets/month. No credit card required.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}