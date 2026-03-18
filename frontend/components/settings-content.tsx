"use client"

import { useState } from 'react'
import { useAuth } from '@/lib/auth-context'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { FieldGroup, Field, FieldLabel, FieldDescription } from '@/components/ui/field'
import {
  User,
  Building2,
  Key,
  Webhook,
  Bell,
  Users,
  Upload,
  Copy,
  Eye,
  EyeOff,
  Trash2,
  Plus,
  ExternalLink,
  Check,
  RefreshCw
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export function SettingsContent() {
  const { user } = useAuth()
  const [showApiKey, setShowApiKey] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Profile state
  const [profile, setProfile] = useState({
    name: user?.name || 'Rajesh Kumar',
    email: user?.email || 'rajesh.kumar@company.com',
    phone: '+91 9876543210',
    timezone: 'Asia/Kolkata',
    language: 'en'
  })

  // Company state
  const [company, setCompany] = useState({
    name: 'TechCorp India Pvt. Ltd.',
    industry: 'Technology',
    website: 'https://techcorp.in',
    address: '123 Tech Park, Bangalore, Karnataka 560001',
    gstNumber: '29ABCDE1234F1Z5'
  })

  // API Keys
  const [apiKey] = useState('sk_live_synapflow_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6')

  // Webhooks
  const [webhooks, setWebhooks] = useState([
    { id: '1', url: 'https://api.techcorp.in/webhooks/synapflow', events: ['complaint.created', 'complaint.resolved'], status: 'active' },
    { id: '2', url: 'https://slack.com/webhooks/notifications', events: ['complaint.escalated'], status: 'active' }
  ])

  // Notifications
  const [notifications, setNotifications] = useState({
    emailOnNewComplaint: true,
    emailOnEscalation: true,
    emailOnResolution: false,
    slackIntegration: false,
    frequency: 'instant'
  })

  // Team Members
  const teamMembers = [
    { id: '1', name: 'Rajesh Kumar', email: 'rajesh.kumar@company.com', role: 'Admin', status: 'active' },
    { id: '2', name: 'Priya Sharma', email: 'priya.sharma@company.com', role: 'Manager', status: 'active' },
    { id: '3', name: 'Amit Patel', email: 'amit.patel@company.com', role: 'Agent', status: 'active' },
    { id: '4', name: 'Neha Gupta', email: 'neha.gupta@company.com', role: 'Agent', status: 'pending' }
  ]

  const handleSave = async () => {
    setIsSaving(true)
    await new Promise(resolve => setTimeout(resolve, 1000))
    setIsSaving(false)
    toast.success('Settings saved successfully')
  }

  const handleCopyApiKey = () => {
    navigator.clipboard.writeText(apiKey)
    toast.success('API key copied to clipboard')
  }

  const handleGenerateNewKey = () => {
    toast.success('New API key generated')
  }

  const handleRevokeKey = () => {
    toast.success('API key revoked')
  }

  const handleDeleteWebhook = (id: string) => {
    setWebhooks(prev => prev.filter(w => w.id !== id))
    toast.success('Webhook deleted')
  }

  const handleTestWebhook = (id: string) => {
    toast.success(`Test event sent to webhook ${id}`)
  }

  const isBusinessPlan = user?.plan === 'business'

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account and application settings</p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="bg-muted/50 p-1">
          <TabsTrigger value="profile" className="gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="company" className="gap-2">
            <Building2 className="h-4 w-4" />
            Company
          </TabsTrigger>
          <TabsTrigger value="api" className="gap-2">
            <Key className="h-4 w-4" />
            API Keys
          </TabsTrigger>
          <TabsTrigger value="webhooks" className="gap-2">
            <Webhook className="h-4 w-4" />
            Webhooks
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="h-4 w-4" />
            Notifications
          </TabsTrigger>
          {isBusinessPlan && (
            <TabsTrigger value="team" className="gap-2">
              <Users className="h-4 w-4" />
              Team
            </TabsTrigger>
          )}
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>Update your personal details and preferences</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Avatar */}
              <div className="flex items-center gap-6">
                <Avatar className="h-20 w-20">
                  <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-white text-2xl">
                    {profile.name.split(' ').map(n => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <Button variant="outline" className="gap-2">
                    <Upload className="h-4 w-4" />
                    Upload Photo
                  </Button>
                  <p className="text-sm text-muted-foreground mt-2">
                    JPG, PNG or GIF. Max size 2MB.
                  </p>
                </div>
              </div>

              <Separator />

              <FieldGroup>
                <div className="grid gap-4 md:grid-cols-2">
                  <Field>
                    <FieldLabel>Full Name</FieldLabel>
                    <Input
                      value={profile.name}
                      onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Email Address</FieldLabel>
                    <Input
                      type="email"
                      value={profile.email}
                      onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Phone Number</FieldLabel>
                    <Input
                      value={profile.phone}
                      onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Timezone</FieldLabel>
                    <Select
                      value={profile.timezone}
                      onValueChange={(v) => setProfile({ ...profile, timezone: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Asia/Kolkata">Asia/Kolkata (IST)</SelectItem>
                        <SelectItem value="America/New_York">America/New_York (EST)</SelectItem>
                        <SelectItem value="Europe/London">Europe/London (GMT)</SelectItem>
                        <SelectItem value="Asia/Singapore">Asia/Singapore (SGT)</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel>Language</FieldLabel>
                    <Select
                      value={profile.language}
                      onValueChange={(v) => setProfile({ ...profile, language: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="hi">Hindi</SelectItem>
                        <SelectItem value="ta">Tamil</SelectItem>
                        <SelectItem value="te">Telugu</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
              </FieldGroup>

              <Separator />

              {/* Password Change */}
              <div>
                <h3 className="text-lg font-medium mb-4">Change Password</h3>
                <FieldGroup>
                  <div className="grid gap-4 md:grid-cols-3">
                    <Field>
                      <FieldLabel>Current Password</FieldLabel>
                      <Input type="password" placeholder="Enter current password" />
                    </Field>
                    <Field>
                      <FieldLabel>New Password</FieldLabel>
                      <Input type="password" placeholder="Enter new password" />
                    </Field>
                    <Field>
                      <FieldLabel>Confirm Password</FieldLabel>
                      <Input type="password" placeholder="Confirm new password" />
                    </Field>
                  </div>
                </FieldGroup>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Company Tab */}
        <TabsContent value="company">
          <Card>
            <CardHeader>
              <CardTitle>Company Details</CardTitle>
              <CardDescription>Update your organization information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <FieldGroup>
                <div className="grid gap-4 md:grid-cols-2">
                  <Field>
                    <FieldLabel>Company Name</FieldLabel>
                    <Input
                      value={company.name}
                      onChange={(e) => setCompany({ ...company, name: e.target.value })}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Industry</FieldLabel>
                    <Select
                      value={company.industry}
                      onValueChange={(v) => setCompany({ ...company, industry: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Technology">Technology</SelectItem>
                        <SelectItem value="E-commerce">E-commerce</SelectItem>
                        <SelectItem value="Healthcare">Healthcare</SelectItem>
                        <SelectItem value="Finance">Finance</SelectItem>
                        <SelectItem value="Education">Education</SelectItem>
                        <SelectItem value="Other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel>Website</FieldLabel>
                    <Input
                      value={company.website}
                      onChange={(e) => setCompany({ ...company, website: e.target.value })}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>GST Number</FieldLabel>
                    <Input
                      value={company.gstNumber}
                      onChange={(e) => setCompany({ ...company, gstNumber: e.target.value })}
                    />
                  </Field>
                </div>
                <Field>
                  <FieldLabel>Address</FieldLabel>
                  <Textarea
                    value={company.address}
                    onChange={(e) => setCompany({ ...company, address: e.target.value })}
                    rows={3}
                  />
                </Field>
              </FieldGroup>

              <div className="flex justify-end">
                <Button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* API Keys Tab */}
        <TabsContent value="api">
          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>Manage your API keys for integrating with SynapFlow</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {!isBusinessPlan ? (
                <div className="p-8 text-center bg-muted/50 rounded-lg">
                  <Key className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">API Access Not Available</h3>
                  <p className="text-muted-foreground mb-4">
                    API access is only available on the Business plan. Upgrade to get programmatic access to SynapFlow.
                  </p>
                  <Button className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700">
                    Upgrade to Business
                  </Button>
                </div>
              ) : (
                <>
                  <div className="p-4 border rounded-lg space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Live API Key</p>
                        <p className="text-sm text-muted-foreground">Use this key for production requests</p>
                      </div>
                      <Badge className="bg-green-100 text-green-700">Active</Badge>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <div className="flex-1 p-3 bg-muted rounded-md font-mono text-sm overflow-x-auto">
                        {showApiKey ? apiKey : apiKey.replace(/./g, '•')}
                      </div>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => setShowApiKey(!showApiKey)}
                      >
                        {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={handleCopyApiKey}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="flex gap-2">
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="outline" className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Generate New Key
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Generate New API Key?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will invalidate your current API key. Any applications using the old key will stop working.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={handleGenerateNewKey}>
                              Generate New Key
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>

                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="outline" className="gap-2 text-red-600 hover:text-red-700">
                            <Trash2 className="h-4 w-4" />
                            Revoke Key
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Revoke API Key?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently revoke your API key. You will need to generate a new one to use the API.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={handleRevokeKey} className="bg-red-600 hover:bg-red-700">
                              Revoke Key
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <ExternalLink className="h-4 w-4" />
                    <a href="#" className="hover:text-primary underline">
                      View API Documentation
                    </a>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Webhooks Tab */}
        <TabsContent value="webhooks">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Webhooks</CardTitle>
                <CardDescription>Configure webhooks to receive real-time updates</CardDescription>
              </div>
              <Button className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700">
                <Plus className="h-4 w-4" />
                Add Webhook
              </Button>
            </CardHeader>
            <CardContent>
              {webhooks.length === 0 ? (
                <div className="p-8 text-center bg-muted/50 rounded-lg">
                  <Webhook className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Webhooks Configured</h3>
                  <p className="text-muted-foreground mb-4">
                    Add a webhook to receive real-time notifications about complaint events.
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>URL</TableHead>
                      <TableHead>Events</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {webhooks.map((webhook) => (
                      <TableRow key={webhook.id}>
                        <TableCell className="font-mono text-sm max-w-[300px] truncate">
                          {webhook.url}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {webhook.events.map((event) => (
                              <Badge key={event} variant="outline" className="text-xs">
                                {event}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={cn(
                            webhook.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                          )}>
                            {webhook.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleTestWebhook(webhook.id)}
                            >
                              Test
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteWebhook(webhook.id)}
                              className="text-red-600 hover:text-red-700"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>Configure how and when you receive notifications</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <h3 className="font-medium">Email Notifications</h3>
                
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">New Complaint Received</p>
                    <p className="text-sm text-muted-foreground">Get notified when a new complaint is submitted</p>
                  </div>
                  <Switch
                    checked={notifications.emailOnNewComplaint}
                    onCheckedChange={(checked) => setNotifications({ ...notifications, emailOnNewComplaint: checked })}
                  />
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">Complaint Escalated</p>
                    <p className="text-sm text-muted-foreground">Get notified when a complaint is escalated</p>
                  </div>
                  <Switch
                    checked={notifications.emailOnEscalation}
                    onCheckedChange={(checked) => setNotifications({ ...notifications, emailOnEscalation: checked })}
                  />
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">Complaint Resolved</p>
                    <p className="text-sm text-muted-foreground">Get notified when a complaint is resolved</p>
                  </div>
                  <Switch
                    checked={notifications.emailOnResolution}
                    onCheckedChange={(checked) => setNotifications({ ...notifications, emailOnResolution: checked })}
                  />
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <h3 className="font-medium">Integrations</h3>
                
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">Slack Integration</p>
                    <p className="text-sm text-muted-foreground">Send notifications to a Slack channel</p>
                  </div>
                  <Switch
                    checked={notifications.slackIntegration}
                    onCheckedChange={(checked) => setNotifications({ ...notifications, slackIntegration: checked })}
                  />
                </div>
              </div>

              <Separator />

              <Field>
                <FieldLabel>Notification Frequency</FieldLabel>
                <FieldDescription>How often would you like to receive notifications?</FieldDescription>
                <Select
                  value={notifications.frequency}
                  onValueChange={(v) => setNotifications({ ...notifications, frequency: v })}
                >
                  <SelectTrigger className="w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instant">Instant</SelectItem>
                    <SelectItem value="daily">Daily Digest</SelectItem>
                    <SelectItem value="weekly">Weekly Summary</SelectItem>
                  </SelectContent>
                </Select>
              </Field>

              <div className="flex justify-end">
                <Button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Team Tab (Business Plan Only) */}
        {isBusinessPlan && (
          <TabsContent value="team">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Team Members</CardTitle>
                  <CardDescription>Manage who has access to your SynapFlow account</CardDescription>
                </div>
                <Button className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700">
                  <Plus className="h-4 w-4" />
                  Invite Member
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Member</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {teamMembers.map((member) => (
                      <TableRow key={member.id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-white text-xs">
                                {member.name.split(' ').map(n => n[0]).join('')}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-medium">{member.name}</p>
                              <p className="text-sm text-muted-foreground">{member.email}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{member.role}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={cn(
                            member.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                          )}>
                            {member.status === 'active' ? (
                              <>
                                <Check className="h-3 w-3 mr-1" />
                                Active
                              </>
                            ) : 'Pending'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={member.role === 'Admin'}
                            className="text-red-600 hover:text-red-700"
                          >
                            Remove
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
