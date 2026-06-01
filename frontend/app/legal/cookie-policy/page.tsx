export const metadata = {
  title: 'Cookie Policy — SynapFlow',
}

export default function CookiePolicyPage() {
  return (
    <article className="prose prose-slate max-w-none">
      <h1>Cookie Policy</h1>
      <p className="text-slate-500 text-sm">
        Version 1.0 · Effective date: June 1, 2026
      </p>
      <p>
        This Cookie Policy explains how SynapTec Pvt. Ltd. ("SynapFlow") uses cookies and similar
        tracking technologies on our website and platform. It should be read alongside our{' '}
        <a href="/legal/privacy-policy">Privacy Policy</a>.
      </p>

      <h2>1. What Are Cookies?</h2>
      <p>
        Cookies are small text files stored on your device when you visit a website. They help the website
        remember your preferences, keep you logged in, and understand how you use the service.
      </p>

      <h2>2. Cookies We Use</h2>
      <table>
        <thead>
          <tr>
            <th>Cookie name</th>
            <th>Type</th>
            <th>Purpose</th>
            <th>Duration</th>
            <th>Consent required?</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>session_token</code></td>
            <td>Strictly Necessary</td>
            <td>Maintains your authenticated session after login. Without this cookie, you would be logged out on every page.</td>
            <td>Session (deleted on browser close)</td>
            <td>No — essential for the service to function</td>
          </tr>
          <tr>
            <td><code>csrf_token</code></td>
            <td>Strictly Necessary</td>
            <td>Prevents Cross-Site Request Forgery (CSRF) attacks. Required for security.</td>
            <td>Session</td>
            <td>No — essential for security</td>
          </tr>
          <tr>
            <td><code>access_token</code></td>
            <td>Strictly Necessary</td>
            <td>Stores your JWT authentication token in localStorage (not a cookie, but similar function) for API authentication.</td>
            <td>60 minutes (renewable)</td>
            <td>No — essential for authentication</td>
          </tr>
          <tr>
            <td><code>razorpay_*</code></td>
            <td>Functional</td>
            <td>Set by Razorpay during the payment checkout flow. Required to complete payment processing.</td>
            <td>Session</td>
            <td>No — required for payment processing</td>
          </tr>
          <tr>
            <td><code>__analytics_id</code></td>
            <td>Analytics</td>
            <td>Identifies unique visitors for platform usage analytics. Helps us understand how the product is used to improve it.</td>
            <td>1 year</td>
            <td><strong>Yes — requires consent for EU visitors</strong></td>
          </tr>
        </tbody>
      </table>

      <h2>3. Strictly Necessary Cookies</h2>
      <p>
        Strictly necessary cookies are essential for the platform to function. They cannot be disabled.
        They do not track your browsing activity for advertising or analytics purposes.
        Under GDPR and Indian law, these do not require your consent.
      </p>

      <h2>4. Analytics Cookies</h2>
      <p>
        We use analytics cookies to understand how users interact with SynapFlow. This helps us improve
        features and fix usability issues. For EU visitors, analytics cookies require your explicit consent.
        You can withdraw consent at any time via the Cookie Settings link in the footer.
      </p>
      <p>
        Analytics data is aggregated and anonymised; we do not use it to identify individual users.
      </p>

      <h2>5. Third-Party Cookies</h2>
      <p>
        Razorpay (our payment processor) may set cookies during checkout. These are governed by
        Razorpay's own cookie and privacy policies. We do not control these cookies.
      </p>
      <p>
        We do not use third-party advertising cookies or social media tracking pixels.
      </p>

      <h2>6. Managing Your Cookie Preferences</h2>
      <p>You can control cookies in the following ways:</p>
      <ul>
        <li><strong>Browser settings:</strong> Most browsers allow you to block or delete cookies. Blocking strictly necessary cookies will prevent you from logging in.</li>
        <li><strong>Cookie consent banner:</strong> EU visitors will see a cookie consent banner on first visit. You can update your preferences at any time.</li>
        <li><strong>Opt out of analytics:</strong> Email <a href="mailto:privacy@synapflow.in">privacy@synapflow.in</a> to opt out of analytics tracking.</li>
      </ul>

      <h2>7. Changes to This Policy</h2>
      <p>
        We may update this Cookie Policy when we add or remove cookies. We will notify you of
        material changes via the cookie consent banner or email.
      </p>

      <h2>8. Contact</h2>
      <p>
        Questions? Email <a href="mailto:privacy@synapflow.in">privacy@synapflow.in</a>
      </p>
    </article>
  )
}
