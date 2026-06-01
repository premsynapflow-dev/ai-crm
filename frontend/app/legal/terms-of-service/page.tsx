export const metadata = {
  title: 'Terms of Service — SynapFlow',
}

export default function TermsOfServicePage() {
  return (
    <article className="prose prose-slate max-w-none">
      <h1>Terms of Service</h1>
      <p className="text-slate-500 text-sm">
        Version 1.0 · Effective date: June 1, 2026 · Governed by the laws of India
      </p>
      <p>
        These Terms of Service ("Terms") constitute a binding agreement between SynapTec Pvt. Ltd.
        ("SynapFlow", "we", "us") and the entity or individual ("Client", "you") accessing or using the
        SynapFlow platform. By creating an account or using the service, you agree to these Terms and our{' '}
        <a href="/legal/privacy-policy">Privacy Policy</a>.
      </p>

      <h2>1. Acceptance &amp; Eligibility</h2>
      <ul>
        <li>You must be at least 18 years of age to use SynapFlow.</li>
        <li>SynapFlow does not knowingly provide services to individuals under 18.</li>
        <li>If you are accepting these Terms on behalf of a business entity, you represent and warrant that you have the authority to bind that entity.</li>
        <li>By creating an account, you accept these Terms and our Privacy Policy in full.</li>
      </ul>

      <h2>2. Service Description &amp; License</h2>
      <p>
        SynapFlow grants you a limited, non-exclusive, non-transferable, revocable licence to use the
        SynapFlow platform solely for your internal business complaint management purposes.
      </p>
      <p><strong>You may not:</strong></p>
      <ul>
        <li>Resell, sublicense, or white-label the platform (unless under a separate Enterprise agreement)</li>
        <li>Reverse-engineer, decompile, or extract source code</li>
        <li>Scrape or harvest data from the platform</li>
        <li>Use outputs to train competing AI models</li>
        <li>Use the platform in a way that violates applicable law</li>
      </ul>

      <h2>3. Client Responsibilities &amp; Data Ownership</h2>
      <ul>
        <li><strong>You own all complaint data you upload to SynapFlow.</strong> SynapFlow processes it on your behalf as a Data Processor.</li>
        <li>You warrant that you have a lawful basis to share your customers' personal data with SynapFlow.</li>
        <li>You are responsible for obtaining necessary consents from your end customers (Data Principals) before uploading their data.</li>
        <li>You must ensure your use of SynapFlow complies with applicable laws in your sector, including RBI guidelines for Banks, NBFCs, and FinTechs.</li>
        <li>You are responsible for keeping your account credentials secure. Notify us immediately of any unauthorised access.</li>
      </ul>

      <h2>4. Subscription, Billing &amp; Overage</h2>
      <ul>
        <li>Subscriptions are billed monthly or annually in INR via Razorpay.</li>
        <li>All prices are exclusive of GST (18%); GST will be added at checkout as applicable under Indian law (SAC code 998314).</li>
        <li>Overage charges apply when ticket volume exceeds plan limits; current pricing is at <a href="/pricing">synapflow.in/pricing</a>.</li>
        <li>Subscriptions auto-renew unless cancelled at least 7 days before the renewal date.</li>
        <li>No refunds are issued on monthly plans after the billing cycle begins, except as required by the Indian Consumer Protection Act, 2019.</li>
        <li>Annual plan refunds are pro-rated subject to a written request within 30 days of payment, less any consumed usage.</li>
        <li>Trial accounts (7-day, 50-ticket limit) do not automatically convert to paid; they deactivate upon expiry.</li>
      </ul>

      <h2>5. Acceptable Use Policy</h2>
      <p>You must not use SynapFlow to:</p>
      <ul>
        <li>Upload unlawfully obtained personal data</li>
        <li>Violate the privacy rights of any individual</li>
        <li>Transmit malware, spam, or abusive content</li>
        <li>Attempt to breach or test security without our prior written permission</li>
        <li>Circumvent subscription limits or access controls</li>
        <li>Use AI outputs to make discriminatory decisions against customers</li>
        <li>Engage in any activity that violates Indian, EU, or US law</li>
      </ul>
      <p>
        Violations of this policy may result in immediate suspension or termination of your account
        without prior notice.
      </p>

      <h2>6. Intellectual Property</h2>
      <ul>
        <li>SynapFlow retains all intellectual property rights in the platform, AI models, algorithms, interfaces, and documentation.</li>
        <li>You retain all intellectual property rights in your complaint data and configurations.</li>
        <li>Anonymised, aggregated, non-identifiable usage insights may be used by SynapFlow to improve the platform. No individual personal data is used for this purpose.</li>
      </ul>

      <h2>7. Confidentiality</h2>
      <p>
        Both parties agree to maintain the confidentiality of the other party's confidential information,
        including client complaint data, SynapFlow's proprietary algorithms, pricing, and business information.
        This obligation survives termination for 3 years.
      </p>

      <h2>8. Limitation of Liability</h2>
      <p>
        SynapFlow's total aggregate liability to a client shall not exceed the total fees paid by that
        client in the 12 months immediately preceding the claim.
      </p>
      <p>
        To the maximum extent permitted by applicable law, SynapFlow is not liable for:
        indirect, consequential, punitive, or special damages; loss of profits; loss of data
        caused by client actions; or failures of third-party services including Google, Razorpay,
        Meta / WhatsApp, or Railway.
      </p>
      <p className="text-sm text-slate-500">
        Note: Indian courts may not enforce blanket liability exclusions. This clause should be reviewed
        by Indian legal counsel before the Terms are published.
      </p>

      <h2>9. Indemnification</h2>
      <p>
        You agree to indemnify, defend, and hold harmless SynapFlow and its officers, directors, and
        employees from and against any claims, damages, or expenses (including legal fees) arising from:
      </p>
      <ul>
        <li>Your unlawful processing of customer personal data</li>
        <li>Your violation of applicable laws, regulations, or RBI guidelines</li>
        <li>Your breach of these Terms</li>
        <li>Your misuse of the SynapFlow platform</li>
      </ul>

      <h2>10. Service Availability</h2>
      <ul>
        <li>SynapFlow targets 99.5% monthly uptime, excluding scheduled maintenance.</li>
        <li>Scheduled maintenance will be communicated at least 48 hours in advance.</li>
        <li>No SLA credits are offered on Trial accounts.</li>
        <li>Uptime metrics are calculated across the calendar month excluding scheduled maintenance windows.</li>
      </ul>

      <h2>11. Termination</h2>
      <ul>
        <li>Either party may terminate with 30 days' written notice.</li>
        <li>SynapFlow may suspend or terminate your account immediately for: AUP violations, non-payment (after a 7-day grace period following notice), court or regulatory orders.</li>
        <li>Upon termination: your data is retained for 30 days to allow export, then permanently and irreversibly deleted.</li>
        <li>You may export your data at any time from the Settings page during the 30-day post-termination window.</li>
      </ul>

      <h2>12. Governing Law &amp; Dispute Resolution</h2>
      <ul>
        <li>These Terms are governed by the laws of India.</li>
        <li>Disputes will first be subject to 30-day good-faith negotiation between the parties.</li>
        <li>Unresolved disputes will be referred to binding arbitration under the Arbitration and Conciliation Act, 1996 (India), with the seat of arbitration in [INSERT CITY], India.</li>
        <li>For EU users: nothing in these Terms limits statutory rights under EU consumer or business protection law.</li>
        <li>For California residents: additional rights apply as described in our Privacy Policy.</li>
      </ul>

      <h2>13. Changes to These Terms</h2>
      <p>
        We may update these Terms with 30 days' advance notice for material changes, delivered by email and
        in-app notification. Continued use of SynapFlow after the notice period constitutes acceptance of
        the updated Terms.
      </p>

      <h2>14. Contact</h2>
      <p>
        For any queries regarding these Terms: <a href="mailto:legal@synapflow.in">legal@synapflow.in</a>
      </p>

      <p className="text-sm text-slate-500 mt-8 border-t pt-4">
        ⚠️ These Terms have been prepared based on publicly available legal information. They should be reviewed
        by a qualified Indian advocate specialising in SaaS, IT law, and FinTech regulation before publication.
      </p>
    </article>
  )
}
