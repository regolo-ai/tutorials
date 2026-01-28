# Production Incident Response Runbook

## Severity Levels

### Critical (P0)
- Complete service outage
- Data breach or security incident
- Response time: Immediate
- Escalation: CTO + CEO notification required

### High (P1)
- Degraded service affecting >50% users
- Payment processing failures
- Response time: < 30 minutes
- Escalation: Engineering lead notification

### Medium (P2)
- Partial feature unavailable
- Performance degradation
- Response time: < 2 hours
- Escalation: Team lead notification

### Low (P3)
- Minor bugs
- UI issues
- Response time: Next business day
- Escalation: Standard ticket workflow

## Incident Response Steps

1. **Detection & Acknowledgment**
   - Acknowledge alert within 5 minutes
   - Create incident ticket in Jira
   - Update status page

2. **Triage & Assessment**
   - Determine severity level
   - Identify affected components
   - Estimate user impact

3. **Mitigation**
   - For P0: Consider immediate rollback
   - For P1-P2: Investigate root cause
   - Implement temporary fix if needed

4. **Communication**
   - Internal: Slack #incidents channel
   - External: Status page updates every 30min
   - Customer-facing incidents: Support team notification

5. **Resolution**
   - Deploy permanent fix
   - Verify in production
   - Monitor for 2 hours post-fix

6. **Post-Mortem**
   - Required for P0 and P1 incidents
   - Template: `postmortem-template.md`
   - Timeline: Within 48 hours of resolution

## Common Scenarios

### Database Connection Pool Exhaustion
**Symptoms:** 5xx errors, slow queries
**Immediate action:** Scale up connection pool OR restart app servers
**Root cause check:** Check for connection leaks, slow queries

### High CPU Usage
**Symptoms:** Slow response times, timeouts
**Immediate action:** Scale horizontally OR identify expensive queries
**Root cause check:** APM traces, query analysis

### Deployment Rollback
**When:** >2% error rate increase post-deploy
**How:** `kubectl rollout undo deployment/app-name`
**Verify:** Monitor error rates for 15 minutes

## Contacts
- On-call engineer: PagerDuty rotation
- DevOps lead: @devops-lead in Slack
- CTO: cto@company.com (P0 only)
