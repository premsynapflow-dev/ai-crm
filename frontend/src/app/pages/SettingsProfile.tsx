import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { PasswordInput } from "../components/ui/password-input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { useAuth } from "../lib/auth-context";
import { toast } from "sonner";

export function SettingsProfile() {
  const { user } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [companyName, setCompanyName] = useState(user?.companyName || "");
  const [businessType, setBusinessType] = useState(user?.businessType || "");

  const handleSave = () => {
    toast.success("Profile updated successfully!");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Profile Settings</h1>
        <p className="text-gray-600">Manage your account information</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Personal Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="name">Full Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={user?.email || ""}
              disabled
              className="bg-gray-50"
            />
            <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
          </div>

          <div>
            <Label htmlFor="company">Company Name</Label>
            <Input
              id="company"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="businessType">Business Type</Label>
            <Select value={businessType} onValueChange={setBusinessType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Fintech">Fintech</SelectItem>
                <SelectItem value="NBFC">NBFC</SelectItem>
                <SelectItem value="Bank">Bank</SelectItem>
                <SelectItem value="D2C Brand">D2C Brand</SelectItem>
                <SelectItem value="E-commerce">E-commerce</SelectItem>
                <SelectItem value="Other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button onClick={handleSave}>Save Changes</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="currentPassword">Current Password</Label>
            <PasswordInput id="currentPassword" />
          </div>

          <div>
            <Label htmlFor="newPassword">New Password</Label>
            <PasswordInput id="newPassword" />
          </div>

          <div>
            <Label htmlFor="confirmPassword">Confirm New Password</Label>
            <PasswordInput id="confirmPassword" />
          </div>

          <Button>Update Password</Button>
        </CardContent>
      </Card>
    </div>
  );
}
