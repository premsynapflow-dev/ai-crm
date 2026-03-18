// Sample complaints data
export interface Complaint {
  id: string
  customerName: string
  customerEmail: string
  customerPhone: string
  subject: string
  message: string
  category: 'billing' | 'technical' | 'general' | 'feedback'
  priority: 'low' | 'medium' | 'high' | 'critical'
  sentiment: 'positive' | 'neutral' | 'negative'
  aiConfidence: number
  status: 'new' | 'in-progress' | 'resolved' | 'escalated'
  createdAt: string
  updatedAt: string
  suggestedResponse?: string
}

export interface Invoice {
  id: string
  date: string
  plan: string
  amount: number
  status: 'paid' | 'pending' | 'failed'
}

const customerNames = [
  'Priya Sharma', 'Amit Patel', 'Neha Gupta', 'Rahul Verma', 'Anjali Singh',
  'Vikram Mehta', 'Pooja Reddy', 'Sanjay Kumar', 'Deepika Nair', 'Arjun Iyer',
  'Kavita Desai', 'Manish Joshi', 'Sunita Rao', 'Rajesh Malhotra', 'Anita Kapoor',
  'Suresh Pillai', 'Meera Bhat', 'Arun Thakur', 'Ritu Agarwal', 'Vivek Choudhary',
  'Swati Mishra', 'Gaurav Saxena', 'Nandini Bhatt', 'Rohit Pandey', 'Shreya Menon'
]

const subjects = [
  'Unable to access my account',
  'Billing discrepancy in last invoice',
  'Feature request: Export to PDF',
  'App crashes on mobile',
  'Slow response time from AI',
  'Wrong category assigned to ticket',
  'Need refund for accidental purchase',
  'Great product! Love the AI features',
  'Integration with Slack not working',
  'Cannot update payment method',
  'Password reset not working',
  'API rate limit too restrictive',
  'Data export taking too long',
  'Suggestion for UI improvement',
  'Webhook not triggering',
  'Double charged this month',
  'Login issues after update',
  'Need bulk import feature',
  'Dashboard loading slow',
  'Excellent customer support!'
]

const messages = [
  'I have been trying to access my account for the past 2 hours but keep getting an error message. Please help resolve this issue as soon as possible.',
  'I noticed that my last invoice shows ₹1,998 instead of ₹999. I believe I have been charged twice. Please look into this and process a refund.',
  'It would be great if you could add a feature to export reports to PDF format. This would help with our compliance requirements.',
  'The mobile app keeps crashing whenever I try to view complaint details. I am using Android 13 on Samsung Galaxy S23.',
  'The AI is taking more than 30 seconds to classify tickets. This is significantly slower than what was advertised.',
  'Multiple tickets are being assigned to the wrong category. The AI seems to be confusing billing issues with technical ones.',
  'I accidentally purchased the Business plan instead of Pro. Please process a refund and switch me to the correct plan.',
  'Just wanted to say that SynapFlow has transformed how we handle customer complaints. The AI suggestions are incredibly accurate!',
  'We set up Slack integration but notifications are not coming through. We have double-checked the webhook URL.',
  'The update payment method button redirects to a 404 page. Cannot add my new credit card.',
  'Password reset emails are not being delivered. I have checked spam folder as well.',
  'The API rate limit of 100 requests per minute is too low for our use case. Can this be increased?',
  'Trying to export 3 months of data but the export has been stuck at 50% for an hour.',
  'The dashboard could benefit from customizable widgets. Would love to arrange cards according to preference.',
  'Configured webhook for new complaints but it only triggers intermittently. Sometimes works, sometimes does not.',
  'Checked my bank statement and see two charges of ₹999 on the same date. Need this resolved urgently.',
  'After the latest update, I cannot log in. The app shows "invalid credentials" even though password is correct.',
  'Would it be possible to add a CSV bulk import feature? We have thousands of historical complaints to migrate.',
  'Dashboard takes over 10 seconds to load. Charts and stats are very slow to render.',
  'Your support team resolved my issue within minutes. Amazing service! Highly recommend SynapFlow.'
]

function getRandomItem<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function getRandomDate(daysAgo: number): string {
  const date = new Date()
  date.setDate(date.getDate() - Math.floor(Math.random() * daysAgo))
  date.setHours(Math.floor(Math.random() * 24), Math.floor(Math.random() * 60))
  return date.toISOString()
}

function generateEmail(name: string): string {
  const nameParts = name.toLowerCase().split(' ')
  const domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'company.com', 'business.in']
  return `${nameParts[0]}.${nameParts[1]}@${getRandomItem(domains)}`
}

function generatePhone(): string {
  return `+91 ${Math.floor(Math.random() * 9000000000 + 1000000000)}`
}

export function generateComplaints(count: number): Complaint[] {
  const complaints: Complaint[] = []
  const categories: Complaint['category'][] = ['billing', 'technical', 'general', 'feedback']
  const priorities: Complaint['priority'][] = ['low', 'medium', 'high', 'critical']
  const sentiments: Complaint['sentiment'][] = ['positive', 'neutral', 'negative']
  const statuses: Complaint['status'][] = ['new', 'in-progress', 'resolved', 'escalated']

  for (let i = 0; i < count; i++) {
    const customerName = getRandomItem(customerNames)
    const createdAt = getRandomDate(90)
    const category = getRandomItem(categories)
    const sentiment = getRandomItem(sentiments)
    
    complaints.push({
      id: `CMP-${String(1000 + i).padStart(4, '0')}`,
      customerName,
      customerEmail: generateEmail(customerName),
      customerPhone: generatePhone(),
      subject: getRandomItem(subjects),
      message: getRandomItem(messages),
      category,
      priority: getRandomItem(priorities),
      sentiment,
      aiConfidence: Math.floor(Math.random() * 20 + 80),
      status: getRandomItem(statuses),
      createdAt,
      updatedAt: createdAt,
      suggestedResponse: `Dear ${customerName.split(' ')[0]},\n\nThank you for reaching out to SynapFlow support. We understand your concern regarding ${category === 'billing' ? 'your billing issue' : category === 'technical' ? 'the technical difficulty you\'re experiencing' : 'your inquiry'}.\n\nOur team is actively looking into this matter and will provide a resolution within 24 hours. ${sentiment === 'negative' ? 'We sincerely apologize for any inconvenience caused.' : ''}\n\nIf you have any additional information to share, please reply to this email.\n\nBest regards,\nSynapFlow Support Team`
    })
  }

  return complaints.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
}

export function generateInvoices(count: number): Invoice[] {
  const invoices: Invoice[] = []
  const plans = ['Trial', 'Pro', 'Business']
  const amounts: Record<string, number> = { 'Trial': 0, 'Pro': 999, 'Business': 4999 }
  const statuses: Invoice['status'][] = ['paid', 'pending', 'failed']

  for (let i = 0; i < count; i++) {
    const plan = i === 0 ? 'Trial' : getRandomItem(plans)
    const status = i < count - 2 ? 'paid' : getRandomItem(statuses)
    
    invoices.push({
      id: `INV-${String(2024001 + i).padStart(7, '0')}`,
      date: getRandomDate(i * 30),
      plan,
      amount: amounts[plan],
      status
    })
  }

  return invoices.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

// Dashboard stats
export const dashboardStats = {
  totalComplaints: 1247,
  resolvedToday: 34,
  avgResponseTime: 45,
  customerSatisfaction: 4.2
}

// Chart data
export const complaintsOverTime = [
  { date: 'Mon', complaints: 45 },
  { date: 'Tue', complaints: 52 },
  { date: 'Wed', complaints: 38 },
  { date: 'Thu', complaints: 65 },
  { date: 'Fri', complaints: 48 },
  { date: 'Sat', complaints: 28 },
  { date: 'Sun', complaints: 22 }
]

export const sentimentDistribution = [
  { name: 'Positive', value: 25, fill: 'var(--chart-3)' },
  { name: 'Neutral', value: 45, fill: 'var(--chart-4)' },
  { name: 'Negative', value: 30, fill: 'var(--chart-5)' }
]

export const priorityBreakdown = [
  { priority: 'Low', count: 320, fill: 'var(--chart-3)' },
  { priority: 'Medium', count: 540, fill: 'var(--chart-4)' },
  { priority: 'High', count: 280, fill: 'var(--chart-1)' },
  { priority: 'Critical', count: 107, fill: 'var(--chart-5)' }
]

// Analytics data
export const complaintVolumeTrend = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
  complaints: Math.floor(Math.random() * 40 + 30)
}))

export const topCategories = [
  { category: 'Technical', count: 425 },
  { category: 'Billing', count: 312 },
  { category: 'General', count: 287 },
  { category: 'Feedback', count: 156 },
  { category: 'Feature Request', count: 67 }
]

export const resolutionStatus = [
  { name: 'Resolved', value: 720, fill: 'var(--chart-3)' },
  { name: 'In Progress', value: 340, fill: 'var(--chart-1)' },
  { name: 'Escalated', value: 120, fill: 'var(--chart-5)' },
  { name: 'New', value: 67, fill: 'var(--chart-4)' }
]

export const responseTimeTrend = Array.from({ length: 7 }, (_, i) => ({
  day: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
  time: Math.floor(Math.random() * 30 + 30)
}))

export const complaintsByHour = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i.toString().padStart(2, '0')}:00`,
  count: i >= 9 && i <= 18 ? Math.floor(Math.random() * 20 + 10) : Math.floor(Math.random() * 5)
}))

export const topSources = [
  { source: 'Email', count: 520 },
  { source: 'API', count: 380 },
  { source: 'Chat Widget', count: 210 },
  { source: 'Phone', count: 87 },
  { source: 'Social Media', count: 50 }
]

// Usage data
export const usageData = {
  ticketsUsed: 450,
  ticketsLimit: 500,
  overageCharges: 0,
  projectedUsage: 550
}

export const dailyUsage = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
  tickets: Math.floor(Math.random() * 25 + 10)
}))

export const usageByCategory = [
  { category: 'Technical', tickets: 180 },
  { category: 'Billing', tickets: 120 },
  { category: 'General', tickets: 95 },
  { category: 'Feedback', tickets: 55 }
]
