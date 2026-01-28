# GDPR Data Protection Policy

## Data Retention

### Application Logs
- **Retention period:** 30 days
- **Storage location:** EU datacenter (AWS eu-central-1)
- **Encryption:** AES-256 at rest
- **Access control:** Engineering team only (audit logged)

### Audit Logs
- **Retention period:** 90 days (security), 7 years (financial)
- **Storage location:** EU datacenter (AWS eu-central-1)
- **Encryption:** AES-256 at rest
- **Access control:** Compliance team + C-level (audit logged)

### User Data
- **Retention period:** Active account + 30 days post-deletion request
- **Storage location:** EU datacenter
- **Deletion process:** Automated via data-deletion-service
- **Verification:** Quarterly compliance audits

## Exceptions to Standard Retention

1. **Legal Hold**
   - Data preserved indefinitely if subject to active litigation
   - Requires Legal team approval
   - Documented in legal-hold-register.xlsx

2. **Financial Records**
   - 7 years retention for accounting compliance (EU Directive 2013/34/EU)
   - Applies to: invoices, payment records, tax documents

3. **Security Incidents**
   - 12 months retention for forensic analysis
   - Requires CISO approval

4. **Contractual Obligations**
   - As specified in customer agreements (typically 12-24 months)
   - Documented in contract management system

## Data Subject Rights

### Right to Access (GDPR Article 15)
- Response time: 30 days
- Format: Machine-readable JSON or PDF
- Tool: data-export-service

### Right to Erasure (GDPR Article 17)
- Processing time: 30 days
- Verification: Manual review by DPO
- Exceptions: Legal obligations, contractual requirements

### Right to Rectification (GDPR Article 16)
- Processing time: 48 hours
- Self-service: User dashboard → Profile → Edit
- Verification: Email confirmation required

## Cross-Border Data Transfers

### EU → US Transfers
- Mechanism: Standard Contractual Clauses (SCCs)
- Approved vendors: AWS, Google Cloud (with SCCs)
- Prohibited: TikTok, ByteDance, Alibaba Cloud

### Data Residency Requirements
- **Production data:** Must remain in EU
- **Development/staging:** EU preferred, US allowed with anonymization
- **Analytics:** Aggregated data only, no PII

## Breach Notification

### Internal Notification
- Timeline: Immediate (within 1 hour of detection)
- Recipients: CISO, DPO, Legal
- Channel: Slack #security-incidents + email

### Regulatory Notification (GDPR Article 33)
- Timeline: 72 hours to supervisory authority
- Responsibility: DPO
- Template: breach-notification-template.docx

### Customer Notification (GDPR Article 34)
- Condition: High risk to data subjects
- Timeline: Without undue delay
- Method: Email + status page notification

## Compliance Contacts
- Data Protection Officer (DPO): dpo@company.com
- CISO: ciso@company.com
- Legal: legal@company.com
