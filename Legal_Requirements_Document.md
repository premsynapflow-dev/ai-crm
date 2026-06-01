# SynapFlow — Legal Protection Requirements Document

> **Purpose:** This document is a structured specification for Claude Code. It defines every legal requirement SynapFlow must implement across its codebase, legal pages, and infrastructure to be compliant with Indian, EU, and US law. Each section is actionable and maps directly to a deliverable.

> **Product Context:** SynapFlow is a B2B AI-powered complaint intelligence SaaS platform targeting Indian Banks, NBFCs, and FinTechs. It processes customer complaint data (including sensitive personal data), uses Google Gemini AI for classification and text generation, integrates with Razorpay for billing, and ingests data via API webhooks, Gmail, and WhatsApp.

---

## Governing Laws Covered

| Jurisdiction | Law / Regulation | Compliance Deadline |
|---|---|---|
| India | Digital Personal Data Protection (DPDP) Act, 2023 | May 13, 2027 |
| India | DPDP Rules, 2025 (notified Nov 13, 2025) | May 13, 2027 |
| India | IT Act, 2000 — Sections 43A, 72A | Active now |
| India | IT (SPDI) Rules, 2011 | Active now (until DPDP supersedes) |
| India | RBI Data Localization Directive (Apr 2018, updated May 2025) | Active now |
| India | RBI Digital Lending Guidelines (May 2025) | Active now |
| EU | GDPR (General Data Protection Regulation) | Active now |
| EU | EU AI Act | August 2, 2026 |
| US | CCPA / CPRA (California) | Active now |
| US | CAN-SPAM Act | Active now |

---

## PART 1 — LEGAL DOCUMENTS TO CREATE

These are standalone pages/files that must exist in the product (website + app).

---

### 1.1 Privacy Policy

**File to create:** `frontend/app/legal/privacy-policy/page.tsx` (or equivalent route)

**Must include all of the following sections and clauses:**

#### A. Identity & Contact (All Laws)
- Full legal name of the data controller/fiduciary (SynapFlow / your registered entity name)
- Registered address in India
- Contact email dedicated to privacy: `privacy@synapflow.in` (or equivalent)
- Name and contact of Data Protection Officer (DPO) — **required under DPDP if designated as Significant Data Fiduciary; recommended now as best practice**

#### B. Data We Collect (DPDP §4, GDPR Art. 13/14, CCPA §1798.100)
List every category of personal data collected, split by:
- **Data Principals / End Users** (the customers of SynapFlow's clients whose complaints are processed)
- **Business Users / Operators** (the agents and admins who log in to SynapFlow)

Categories to enumerate:
- Identity data: name, email, phone number
- Financial data: payment method, billing address, transaction history (via Razorpay)
- Complaint content: free-text complaints, attachments — **this is Sensitive Personal Data under IT (SPDI) Rules 2011**
- Behavioral/Usage data: login timestamps, feature usage, IP addresses
- AI-inferred data: sentiment scores, urgency scores, churn risk scores, complaint categories
- Communication metadata: WhatsApp message metadata, Gmail integration access tokens

#### C. Legal Basis for Processing (GDPR Art. 6 & 9, DPDP §4–§7)
For each category above, state the legal basis:
- **Consent** — for data collected directly from Data Principals via client-facing widgets
- **Contractual necessity** — for processing Business Users' data to deliver the SaaS service
- **Legitimate interest** — for fraud prevention, security, platform analytics
- **Legal obligation** — for RBI TAT/MIS reporting mandated for FinTech clients

#### D. Purpose Limitation (DPDP §4, GDPR Art. 5(1)(b))
State explicitly that data is collected only for:
1. Providing complaint management and analytics services
2. AI-driven classification, sentiment analysis, and auto-reply drafting
3. Regulatory compliance reporting (RBI MIS reports)
4. Billing and subscription management via Razorpay
5. Platform security, fraud prevention, and audit logging
6. Service improvement (anonymised/aggregated only)

Data must **not** be used for: selling to third parties, advertising, profiling for purposes unrelated to complaint management.

#### E. Data Retention (DPDP §8(7), GDPR Art. 5(1)(e), CCPA)
Provide a retention schedule table:

| Data Category | Retention Period | Reason |
|---|---|---|
| Complaint tickets & content | Duration of client contract + 3 years | Regulatory audit requirements |
| AI interaction logs (audit trail) | 1 year minimum | DPDP Rules 2025, §8 |
| Access/traffic logs | 1 year minimum | DPDP Rules 2025 |
| Payment transaction data | 8 years | Indian tax/GST laws |
| Account data (Business Users) | Duration of subscription + 1 year | Contractual |
| Deleted/churned account data | 30 days post-deletion, then purged | DPDP §8(7) |

#### F. Data Sharing & Sub-processors (GDPR Art. 28, DPDP §8(2), CCPA)
List all third parties who receive personal data:

| Sub-processor | Purpose | Location | Safeguard |
|---|---|---|---|
| Google (Gemini AI API) | AI classification & text generation | US/Global | Standard Contractual Clauses (SCCs) |
| Supabase (PostgreSQL) | Database hosting | Configure: India region mandatory | DPA in place |
| Razorpay | Payment processing | India | PCI-DSS compliant; RBI regulated |
| Gmail API (Google) | Email ingestion | US/Global | OAuth 2.0; limited scope |
| WhatsApp Business API | Complaint ingestion | US/Global | Meta DPA; SCCs |

**Statement required:** "We do not sell personal data to third parties."

#### G. Data Localization (RBI Directive 2018, DPDP)
- All payment-related data processed via Razorpay is stored exclusively on servers in India per RBI mandate.
- If any processing occurs outside India, data is deleted from foreign servers and returned to Indian servers within 24 hours.
- SynapFlow's primary database (Supabase/PostgreSQL) must be configured to use an India-region data center.

#### H. Data Principal / User Rights (DPDP §12–§14, GDPR Art. 15–22, CCPA §1798.100–§1798.125)

State that users have the following rights and how to exercise them:

**Under Indian Law (DPDP):**
- Right to access — obtain summary of personal data processed and processing activities
- Right to correction and erasure — correct inaccurate data or request erasure when purpose is fulfilled
- Right to grievance redressal — raise complaints with SynapFlow's grievance officer within 48 hours of acknowledgement
- Right to nominate — nominate another person to exercise rights in case of death/incapacity
- Right to withdraw consent — at any time; withdrawal does not affect prior lawful processing

**Under EU Law (GDPR):**
- Right to access (Art. 15)
- Right to rectification (Art. 16)
- Right to erasure / "right to be forgotten" (Art. 17)
- Right to restriction of processing (Art. 18)
- Right to data portability (Art. 20) — provide data in machine-readable format (JSON/CSV)
- Right to object to automated decision-making (Art. 21 & 22) — **critical for AI sentiment/churn scoring**
- Right to lodge complaint with supervisory authority (EU DPA)

**Under US Law (CCPA/CPRA):**
- Right to know what personal information is collected and how it's used
- Right to delete
- Right to correct inaccurate personal information
- Right to opt out of sale/sharing (SynapFlow does not sell data — state this explicitly)
- Right to limit use of sensitive personal information
- Response time: **45 days** for all requests (CCPA requirement)

**How to exercise rights:** Provide a dedicated email (e.g., `dpo@synapflow.in`) and state SynapFlow will respond within 48 hours of receipt for Indian requests, 30 days for GDPR requests, and 45 days for CCPA requests.

#### I. Automated Decision-Making & AI Transparency (GDPR Art. 22, EU AI Act, DPDP)
- Disclose that SynapFlow uses AI (Google Gemini) to automatically classify complaints, score sentiment, assign urgency, and predict churn risk.
- State that all AI-generated draft replies are subject to human review before being sent (HITL — Human-in-the-Loop).
- State that automated scoring does not constitute a final binding decision; human agents make final determinations.
- Users (Business Users / Data Principals acting through clients) have the right to request human review of any AI-generated outcome.

#### J. Cookies & Tracking (GDPR, ePrivacy Directive)
- List all cookies used: session cookies, authentication tokens, analytics cookies.
- State which are strictly necessary (no consent required) vs. functional/analytics (consent required).
- Link to Cookie Policy (see §1.4 below).

#### K. Breach Notification (DPDP §8(6), GDPR Art. 33–34)
- In case of a personal data breach, SynapFlow will:
  - Notify the Data Protection Board of India within 72 hours (once DPDP Board is operational)
  - Notify affected Data Principals without undue delay
  - Notify affected EU supervisory authority within 72 hours (for EU data subjects)
  - Provide details of the breach, likely consequences, and mitigation steps taken

#### L. Changes to Privacy Policy
- SynapFlow will provide at least 15 days' advance notice of material changes via email and in-app notification.
- Continued use of the platform after notice period constitutes acceptance.

---

### 1.2 Terms of Service (Terms of Use)

**File to create:** `frontend/app/legal/terms-of-service/page.tsx`

#### A. Acceptance & Eligibility
- Minimum age: 18 years. SynapFlow does not knowingly collect data from minors.
- By creating an account, the user agrees to these Terms and the Privacy Policy.
- If using on behalf of a business entity, the individual warrants they have authority to bind that entity.

#### B. Service Description & License
- Grant of a limited, non-exclusive, non-transferable, revocable license to use SynapFlow for the subscriber's internal business purposes only.
- Explicitly prohibit: reselling, white-labeling (unless under a separate Enterprise agreement), reverse-engineering, scraping, or using the service to train competing AI models.

#### C. Client Responsibilities & Data Ownership
- **The client (Business User) owns all complaint data they upload to SynapFlow.** SynapFlow processes it on their behalf as a Data Processor/Fiduciary-as-instructed.
- The client warrants they have lawful basis to share customer complaint data with SynapFlow.
- The client is responsible for obtaining necessary consents from their end customers (Data Principals) before uploading their data.
- The client must ensure their use of SynapFlow complies with applicable laws in their sector (e.g., RBI guidelines for Banks/NBFCs).

#### D. Subscription, Billing & Overage (Razorpay Integration)
- Subscriptions are billed monthly/annually in INR via Razorpay.
- Overage charges apply when ticket volume exceeds plan limits; pricing detailed at [pricing page URL].
- All prices are exclusive of GST (18%); GST will be added at checkout.
- Subscriptions auto-renew unless cancelled at least 7 days before renewal date.
- **No refunds** on monthly plans after the billing cycle begins, except as required by Indian Consumer Protection Act 2019.
- Trial accounts (7-day, 50-ticket limit) convert automatically to paid or deactivate.

#### E. Acceptable Use Policy (AUP)
Users must not use SynapFlow to:
- Upload unlawfully obtained personal data
- Violate the privacy rights of any individual
- Transmit malware, spam, or abusive content
- Attempt to breach or test security without written permission
- Circumvent subscription limits or access controls
- Use AI outputs to make discriminatory decisions against customers

#### F. Intellectual Property
- SynapFlow retains all IP in the platform, AI models, algorithms, and documentation.
- Client retains all IP in their complaint data and configurations.
- Anonymised, aggregated, non-identifiable insights derived from aggregate usage may be used by SynapFlow to improve the platform; no individual data is used for this.

#### G. Confidentiality
- Both parties agree to treat each other's confidential information (including client complaint data, SynapFlow's proprietary algorithms) as confidential.
- Obligation survives termination for 3 years.

#### H. Limitation of Liability
- SynapFlow's total aggregate liability to a client shall not exceed the amount paid by that client in the 12 months preceding the claim.
- SynapFlow is not liable for: indirect, consequential, punitive, or special damages; loss of profits; loss of data caused by client actions; third-party service failures (Google, Razorpay, WhatsApp).
- **Note:** Indian courts may not enforce blanket liability exclusions — clause must be reviewed by Indian legal counsel before finalisation.

#### I. Indemnification
- Client indemnifies SynapFlow against claims arising from: (a) client's unlawful processing of customer data, (b) client's violation of applicable laws, (c) client's breach of these Terms.

#### J. Service Availability & SLA
- SynapFlow targets 99.5% monthly uptime, excluding scheduled maintenance.
- Scheduled maintenance will be notified 48 hours in advance.
- No SLA credits are offered on Trial accounts.

#### K. Termination
- Either party may terminate with 30 days' written notice.
- SynapFlow may suspend accounts immediately for AUP violations, non-payment (after 7-day grace), or court/regulatory orders.
- On termination: client data is retained for 30 days post-termination for export, then permanently deleted.

#### L. Governing Law & Dispute Resolution
- These Terms are governed by the laws of India.
- Disputes will first be subject to 30-day good-faith negotiation.
- Thereafter, disputes will be resolved by arbitration under the Arbitration and Conciliation Act, 1996 (India), with the seat of arbitration in [City, India].
- For EU users: nothing in these Terms limits statutory rights under EU consumer/business protection law.
- For CCPA purposes: California residents may have additional rights as stated in the Privacy Policy.

#### M. Amendments
- SynapFlow may amend these Terms with 30 days' notice for material changes. Continued use = acceptance.

---

### 1.3 Data Processing Agreement (DPA)

**File to create:** `frontend/app/legal/dpa/page.tsx` (also available as downloadable PDF)

This is a **separate, critical document** for B2B clients, required under GDPR Art. 28 and strongly recommended under DPDP.

#### Required Clauses:
- **Scope:** Define exact personal data categories processed and permitted processing activities.
- **Instructions:** SynapFlow processes data only on documented client instructions.
- **Confidentiality:** All SynapFlow personnel with data access are bound by confidentiality.
- **Security:** SynapFlow implements ISO 27001-aligned technical and organisational measures (encryption at rest AES-256, encryption in transit TLS 1.2+, access controls, audit logging).
- **Sub-processors:** List of approved sub-processors (Google, Supabase, Razorpay, Meta/WhatsApp). Client is notified 30 days before adding new sub-processors.
- **Data Subject Rights:** SynapFlow assists clients in fulfilling data subject rights requests within 5 business days.
- **Breach notification:** SynapFlow notifies the client of any confirmed breach within 24 hours of discovery.
- **Return/deletion of data:** On termination, SynapFlow returns or deletes all client personal data within 30 days per client instruction.
- **Audits:** Clients may audit SynapFlow's compliance once per year with 30 days' notice, or review SynapFlow's SOC 2 / security certification in lieu of audit.
- **International transfers:** Data transfers outside India are governed by Standard Contractual Clauses (SCCs) for EU data; for Indian data, SynapFlow ensures transfer is to countries on the permitted list under DPDP Rules once published.

---

### 1.4 Cookie Policy

**File to create:** `frontend/app/legal/cookie-policy/page.tsx`

List all cookies:

| Cookie Name | Type | Purpose | Duration | Consent Required |
|---|---|---|---|---|
| `session_token` | Strictly Necessary | Authentication session | Session | No |
| `csrf_token` | Strictly Necessary | CSRF protection | Session | No |
| `__analytics_id` | Analytics | Platform usage analytics | 1 year | Yes |
| `razorpay_*` | Functional | Payment flow | Session | No |

- Provide a cookie consent banner on first visit for EU users (using geolocation-based detection).
- Cookie preferences must be changeable at any time via a "Cookie Settings" link in the footer.

---

### 1.5 Grievance Officer Disclosure (IT Act 2000, §5(9) SPDI Rules)

**Must appear on:** Privacy Policy page, Contact/Support page, and app footer.

```
Grievance Officer
Name: [Name]
Designation: [e.g., Data Protection Officer]
SynapFlow (or registered entity name)
Address: [Registered Indian address]
Email: grievance@synapflow.in
Phone: [Indian phone number]
Available: Monday–Friday, 9 AM–6 PM IST
Response time: Complaints acknowledged within 48 hours, resolved within 1 month
```

**Legal basis:** IT (SPDI) Rules 2011, Rule 5(9); DPDP Act §13; Consumer Protection Act 2019.

---

## PART 2 — TECHNICAL & CODE REQUIREMENTS

These are changes Claude Code must make to the codebase to achieve compliance.

---

### 2.1 Consent Management (DPDP §6, GDPR Art. 7)

- **Implement a Consent Management System.** Before any personal data is collected from a Data Principal (e.g., via embedded widget or API), a consent notice must be shown.
- Consent must be: freely given, specific, informed, unambiguous, and withdrawable.
- Consent records must be stored with: timestamp, version of notice shown, IP address, user ID.
- **Database schema addition required:**
  ```sql
  CREATE TABLE consent_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    consent_type VARCHAR(100) NOT NULL, -- e.g., 'data_processing', 'marketing'
    version VARCHAR(20) NOT NULL,       -- policy version at time of consent
    granted BOOLEAN NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```

### 2.2 Data Subject Rights Request Portal (DPDP §12, GDPR Art. 15–22)

- Build a self-service portal (or dedicated email workflow) where users can:
  - Submit a Subject Access Request (SAR)
  - Request data deletion
  - Request data correction
  - Download their data in JSON/CSV format (data portability)
  - Withdraw consent
- All requests must be logged with timestamp and status.
- System must auto-generate a confirmation email to the requester.
- **SLA:** Respond to Indian requests within 48 hours acknowledgement + resolve within 30 days. GDPR: 30 days. CCPA: 45 days.

### 2.3 Audit Logging (DPDP Rules 2025, IT Act 43A, GDPR Art. 5(2))

- All of the following must generate immutable audit log entries:
  - User login/logout (with IP, timestamp, device)
  - Every complaint ticket state change
  - Every AI interaction (prompt sent to Gemini, response received, agent action taken)
  - Every data access to personal information (who accessed what and when)
  - Every data export
  - Every consent grant/withdrawal
  - Every admin configuration change
- **Minimum retention of logs: 1 year** (DPDP Rules 2025 mandate).
- Audit logs must be write-only; no deletion or modification by any user including admins.
- **Recommended:** Store audit logs in a separate, append-only Postgres table with row-level security.

### 2.4 Data Retention & Automated Deletion (DPDP §8(7), GDPR Art. 5(1)(e))

- Implement a background job (in the existing in-process worker) that:
  - Flags data that has exceeded its retention period (per the schedule in §1.1.E)
  - Sends a deletion confirmation email to the client/admin before final deletion
  - Permanently deletes (or anonymises) data after the retention period
  - Logs each deletion event in the audit trail
- **No data must be retained indefinitely without a documented legal basis.**

### 2.5 Data Minimisation (GDPR Art. 5(1)(c), DPDP §4)

- Review all API endpoints and forms. Remove any fields that collect data not strictly necessary for the stated purpose.
- For the Gmail integration: request only the minimum OAuth scopes needed (`gmail.readonly` for ingestion; do not request `gmail.modify` or `contacts`).
- For WhatsApp integration: store only the message content and sender phone number; do not store unnecessary metadata.
- AI prompts sent to Gemini must be reviewed — **do not send raw PII to Gemini if anonymised/pseudonymised data suffices** for the classification task.

### 2.6 Encryption Requirements (IT Act 43A, DPDP, GDPR Art. 32)

- **At rest:** All PostgreSQL/Supabase data must be encrypted at rest (AES-256). Verify Supabase India region supports this (it does).
- **In transit:** Enforce TLS 1.2 minimum on all API endpoints. Reject connections below TLS 1.2.
- **Sensitive fields:** Passwords must be hashed (bcrypt, min cost 12). API keys and OAuth tokens stored in the database must be encrypted using application-level encryption (not just DB-at-rest).
- **Razorpay:** Never store raw card numbers. Razorpay tokenisation handles this — verify no raw PAN data touches SynapFlow servers.

### 2.7 Data Localization — RBI Compliance

- **Supabase database region must be set to `ap-south-1` (Mumbai, AWS) or equivalent India-region.**
- Verify this in Supabase project settings. If currently set to a non-India region, **migrate immediately**.
- Payment data flowing through Razorpay is already India-localised (Razorpay is RBI-compliant).
- For Gemini AI API calls: complaint content (which may include financial data) is sent to Google's servers. This creates a potential RBI data localization issue for FinTech clients. **Implement the following:**
  - **Option A (Recommended):** Anonymise/pseudonymise complaint content before sending to Gemini (replace PAN, account numbers, phone numbers with tokens before the API call; detokenize results after).
  - **Option B:** Use Gemini Enterprise with a data residency guarantee for India, or use a Google Cloud Vertex AI deployment in `asia-south1` (Mumbai) region.
  - Document your chosen approach in the DPA and Privacy Policy.

### 2.8 AI Transparency & Human-in-the-Loop (GDPR Art. 22, EU AI Act, DPDP)

- The existing HITL review dashboard satisfies the human oversight requirement. **Ensure the following are implemented:**
  - AI-generated drafts must be visually distinguished from human-written content in the UI (e.g., "AI Draft — Pending Review" label).
  - Audit log must record: whether the final response was AI-generated, human-written, or AI-assisted (edited by human).
  - Agents must not be able to send an AI draft without at least one affirmative action (click "Approve" — not just the send button).
  - In the customer-facing reply, do **not** indicate the response was AI-generated unless legally required (currently not mandated in India but good practice).
- **EU AI Act consideration:** SynapFlow's churn risk scoring and urgency scoring may qualify as "limited risk" AI. Implement transparency notices in the UI informing operators that these scores are AI-generated estimates, not determinations.

### 2.9 Breach Detection & Response Infrastructure (DPDP §8(6), GDPR Art. 33)

- Implement alerting (via existing notification worker) for:
  - Unusual bulk data exports (> X records exported in < Y minutes)
  - Multiple failed login attempts (brute force detection)
  - Access from unusual geographies or IPs
- Prepare a **Breach Response Runbook** (internal doc) with steps for:
  1. Contain the breach
  2. Assess scope and affected data subjects
  3. Notify client within 24 hours
  4. Notify Data Protection Board (India) within 72 hours
  5. Notify affected EU supervisory authority within 72 hours
  6. Notify affected Data Principals without undue delay

### 2.10 Age Verification & Minor Protection (COPPA, DPDP §9)

- SynapFlow is a B2B platform; end-user minors should not directly interact with it.
- Add a declaration checkbox during account creation: "I confirm I am 18 years of age or older."
- In the Privacy Policy, state: "SynapFlow does not knowingly collect personal data from individuals under 18 years of age."
- DPDP §9 imposes additional obligations if data of minors is processed — ensure clients are contractually prohibited from uploading complaints from individuals under 18 without verifiable parental consent.

### 2.11 Email Marketing Compliance (CAN-SPAM, DPDP)

- All marketing/transactional emails must include:
  - Physical postal address of SynapFlow
  - Clear "Unsubscribe" / opt-out mechanism in every email
  - Unsubscribe requests processed within 10 business days (CAN-SPAM) / immediately (best practice)
- Maintain a suppression list of unsubscribed emails; never email suppressed addresses.
- Separate opt-in consent for marketing emails from consent for transactional/service emails.

### 2.12 GSTIN & Invoice Compliance (Indian GST Law)

- Razorpay invoices/receipts must include SynapFlow's GSTIN.
- GST at 18% (SAC code for SaaS/software services) must be added to all INR invoices.
- HSN/SAC code for SaaS: **998314** (IT design and development services) or **998315** — confirm with a CA.
- Generate GST-compliant invoices for every transaction; store for minimum 8 years.

---

## PART 3 — INFRASTRUCTURE REQUIREMENTS

### 3.1 Data Residency
- Primary database (Supabase): India region (`ap-south-1`, Mumbai)
- File/media storage (if any): India region
- Gemini AI API: implement PII anonymisation layer before API calls (see §2.7)
- Backups: India region only

### 3.2 Security Certifications (Recommended for Enterprise Sales)
- Target **ISO 27001** certification (or at minimum implement ISO 27001-aligned controls)
- Consider **SOC 2 Type 2** for US/global enterprise clients
- Conduct annual penetration testing by a certified third party
- Implement a Vulnerability Disclosure Program (VDP)

### 3.3 Sub-processor Agreements
Before going live, ensure signed DPAs/agreements exist with:
- [ ] Google (for Gemini API) — Google Cloud DPA
- [ ] Supabase — Supabase DPA
- [ ] Razorpay — already covered under their merchant agreement; verify data handling clauses
- [ ] Meta (WhatsApp Business API provider) — Meta DPA
- [ ] Google (Gmail API) — Google API Terms of Service + DPA

---

## PART 4 — COMPLIANCE TIMELINE & PRIORITIES

### Immediate (Before Launch / Now)
- [ ] Create and publish Privacy Policy (§1.1)
- [ ] Create and publish Terms of Service (§1.2)
- [ ] Create and publish Grievance Officer disclosure (§1.5)
- [ ] Ensure Supabase DB is in India region (§3.1)
- [ ] Implement TLS 1.2+ enforcement and field-level encryption for sensitive data (§2.6)
- [ ] Implement audit logging (§2.3)
- [ ] Add age verification checkbox to sign-up flow (§2.10)
- [ ] Ensure Razorpay invoices include GSTIN and GST (§2.12)

### Short-Term (Within 3 Months)
- [ ] Create and publish DPA (§1.3)
- [ ] Create and publish Cookie Policy + consent banner (§1.4)
- [ ] Implement consent management system and DB schema (§2.1)
- [ ] Build data subject rights request workflow (§2.2)
- [ ] Implement data retention job and automated deletion (§2.4)
- [ ] Implement PII anonymisation layer for Gemini API calls (§2.7)
- [ ] Implement breach detection alerting (§2.9)
- [ ] Sign DPAs with all sub-processors (§3.3)

### Medium-Term (Before May 2027 DPDP Deadline)
- [ ] Full DPDP Rules 2025 compliance audit
- [ ] Appoint DPO if designated as Significant Data Fiduciary
- [ ] Conduct Data Protection Impact Assessment (DPIA)
- [ ] Implement EU AI Act transparency requirements (§2.8) before August 2026
- [ ] CCPA compliance for US clients (rights portal, privacy policy update)
- [ ] Pursue ISO 27001 / SOC 2 certification (§3.2)

---

## PART 5 — DISCLAIMER & NEXT STEPS

> ⚠️ **This document was prepared using publicly available legal information and AI research. It is not a substitute for legal advice from a qualified Indian advocate specialising in data protection, IT law, and fintech regulation.** Before publishing any legal pages or implementing compliance measures, have them reviewed by:
> 1. An Indian advocate familiar with DPDP Act 2023, IT Act 2000, and RBI guidelines
> 2. A GDPR-specialist for EU compliance
> 3. A CA/tax consultant for GST compliance

**Recommended legal counsel areas to engage:**
- Data protection / privacy law (India)
- FinTech / RBI regulatory compliance
- Contract / SaaS terms review
- GST / tax for SaaS

---

*Document version: 1.0 | Prepared: May 2026 | Next review: November 2026*
*Based on: DPDP Act 2023, DPDP Rules 2025 (notified Nov 13 2025), IT Act 2000, RBI Directive Apr 2018 / May 2025, GDPR, EU AI Act, CCPA/CPRA*
