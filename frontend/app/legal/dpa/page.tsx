export const metadata = {
  title: 'Data Processing Agreement — SynapFlow',
}

export default function DPAPage() {
  return (
    <article className="prose prose-slate max-w-none">
      <h1>Data Processing Agreement (DPA)</h1>
      <p className="text-slate-500 text-sm">
        Version 1.0 · Effective date: June 1, 2026
      </p>
      <p>
        This Data Processing Agreement ("DPA") is entered into between SynapTec Pvt. Ltd. ("SynapFlow",
        "Data Processor") and the Client ("Controller" / "Data Fiduciary") and forms part of the{' '}
        <a href="/legal/terms-of-service">Terms of Service</a>.
      </p>
      <p>
        This DPA is required under <strong>GDPR Article 28</strong> and is strongly recommended under the
        <strong>DPDP Act, 2023</strong> and <strong>IT (SPDI) Rules, 2011</strong>.
      </p>

      <h2>1. Definitions</h2>
      <ul>
        <li><strong>Controller / Data Fiduciary:</strong> The Client who determines the purposes and means of personal data processing.</li>
        <li><strong>Processor / Data Fiduciary-as-Instructed:</strong> SynapFlow, which processes personal data on behalf of the Client.</li>
        <li><strong>Data Principal / Data Subject:</strong> The individuals (customers) whose personal data is processed.</li>
        <li><strong>Personal Data:</strong> Any information relating to an identified or identifiable natural person.</li>
      </ul>

      <h2>2. Scope of Processing</h2>
      <p><strong>Categories of personal data processed:</strong></p>
      <ul>
        <li>Identity data: name, email address, phone number of Data Principals</li>
        <li>Complaint content: free-text complaints submitted by Data Principals (may constitute Sensitive Personal Data under IT SPDI Rules)</li>
        <li>AI-inferred data: sentiment scores, urgency scores, complaint categories</li>
        <li>Communication metadata: email thread identifiers, WhatsApp message metadata</li>
      </ul>
      <p><strong>Permitted processing activities:</strong></p>
      <ul>
        <li>Storing, retrieving, and displaying complaint data within the SynapFlow platform</li>
        <li>Transmitting complaint content to the Gemini AI API for classification and reply generation (pseudonymised)</li>
        <li>Generating RBI TAT/MIS compliance reports on behalf of the Client</li>
        <li>Creating and maintaining audit logs as required by law</li>
      </ul>

      <h2>3. Processing on Instructions Only</h2>
      <p>
        SynapFlow processes personal data only on documented instructions from the Client. SynapFlow will
        immediately notify the Client if it believes an instruction infringes GDPR, DPDP, or other applicable law.
      </p>

      <h2>4. Confidentiality</h2>
      <p>
        All SynapFlow personnel with access to personal data are subject to binding confidentiality obligations.
        Access is restricted on a need-to-know basis.
      </p>

      <h2>5. Security Measures</h2>
      <p>SynapFlow implements the following technical and organisational security measures:</p>
      <ul>
        <li><strong>Encryption at rest:</strong> AES-256 via Supabase (PostgreSQL)</li>
        <li><strong>Encryption in transit:</strong> TLS 1.2 minimum on all API endpoints</li>
        <li><strong>Access controls:</strong> Role-based access control (RBAC); multi-tenant row-level security</li>
        <li><strong>Audit logging:</strong> Immutable audit trail for all data access and changes (1-year minimum retention)</li>
        <li><strong>API authentication:</strong> JWT-based authentication; API key per client</li>
        <li><strong>Password security:</strong> bcrypt hashing (minimum cost 12)</li>
        <li><strong>Vulnerability management:</strong> Regular dependency updates; security checks on startup</li>
      </ul>

      <h2>6. Sub-processors</h2>
      <p>
        SynapFlow uses the following approved sub-processors. The Client provides general authorisation
        for these sub-processors. SynapFlow will notify the Client at least 30 days before adding a new
        sub-processor.
      </p>
      <table>
        <thead>
          <tr><th>Sub-processor</th><th>Purpose</th><th>Location</th></tr>
        </thead>
        <tbody>
          <tr><td>Google (Gemini AI API)</td><td>AI classification &amp; reply generation (pseudonymised data only)</td><td>US / Global</td></tr>
          <tr><td>Supabase</td><td>PostgreSQL database hosting</td><td>India (ap-south-1, Mumbai)</td></tr>
          <tr><td>Razorpay</td><td>Payment processing</td><td>India</td></tr>
          <tr><td>Google (Gmail API)</td><td>Email inbox ingestion (gmail.readonly scope only)</td><td>US / Global</td></tr>
          <tr><td>Meta (WhatsApp Business API)</td><td>WhatsApp message ingestion</td><td>US / Global</td></tr>
          <tr><td>Railway</td><td>Application hosting</td><td>Asia-Pacific</td></tr>
        </tbody>
      </table>

      <h2>7. Data Subject Rights Assistance</h2>
      <p>
        SynapFlow will assist the Client in fulfilling data subject (Data Principal) rights requests within
        <strong>5 business days</strong> of receiving a request from the Client.
      </p>
      <p>This includes: access requests, correction requests, erasure requests, data portability (JSON/CSV export), and consent withdrawal.</p>

      <h2>8. Breach Notification</h2>
      <p>
        In the event of a confirmed personal data breach, SynapFlow will notify the Client within
        <strong>24 hours of discovery</strong>, including:
      </p>
      <ul>
        <li>Nature of the breach and categories of data affected</li>
        <li>Approximate number of data subjects affected</li>
        <li>Likely consequences of the breach</li>
        <li>Measures taken or proposed to address the breach</li>
      </ul>

      <h2>9. Data Deletion &amp; Return</h2>
      <p>
        Upon termination of the service agreement, SynapFlow will, at the Client's choice, return or
        permanently delete all personal data within <strong>30 days</strong>. Deletion will be certified
        in writing upon request.
      </p>
      <p>
        Exceptions: data retained for legal, regulatory, or tax compliance purposes per our{' '}
        <a href="/legal/privacy-policy#retention">retention schedule</a>.
      </p>

      <h2>10. Audits &amp; Compliance Verification</h2>
      <p>
        Clients may audit SynapFlow's data processing compliance once per calendar year with 30 days'
        written notice. In lieu of an on-site audit, SynapFlow may provide security certifications
        (ISO 27001, SOC 2 Type 2 — when available) or a completed security questionnaire.
      </p>

      <h2>11. International Data Transfers</h2>
      <p>
        Transfers of EU personal data outside the EU/EEA are governed by Standard Contractual Clauses (SCCs).
        Transfers of Indian personal data outside India comply with DPDP Rules 2025 permitted country lists
        once published by the Data Protection Board of India.
      </p>
      <p>
        For Gemini AI processing: complaint content is pseudonymised before transmission; identifiers are
        replaced with tokens and detokenised on receipt. Raw PII is not permanently stored outside India.
      </p>

      <h2>12. Governing Law</h2>
      <p>
        This DPA is governed by the laws of India. For EU Clients, GDPR requirements take precedence
        where applicable.
      </p>

      <p className="text-sm text-slate-500 mt-8 border-t pt-4">
        To execute a signed copy of this DPA for your organisation, contact{' '}
        <a href="mailto:legal@synapflow.in">legal@synapflow.in</a>. ·{' '}
        ⚠️ This DPA should be reviewed by qualified legal counsel before use.
      </p>
    </article>
  )
}
