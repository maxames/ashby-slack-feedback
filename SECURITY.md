# Security Policy

## Reporting a Vulnerability
If you discover a security issue, please report it privately.

**Do not open public GitHub issues for security vulnerabilities.**

### How to Report
- **Email:** 23615949+maxames@users.noreply.github.com
- **Include:** description, steps to reproduce, and potential impact
I maintain this project in my spare time and will respond as soon as possible.

---

## Supported Versions
Use the **latest commit on `main`**.
No tagged releases or long-term support.

---

## Key Security Measures

### Webhooks
- **HMAC-SHA256 verification** for all Ashby webhooks
- **Timing-safe comparison** to prevent timing attacks
- **Strict signature format validation**

### Secrets
- **Environment variables only** — never stored in code
- **`.gitignore`** blocks accidental commits
- **`.env.example`** shows required secrets safely

### Database
- **Parameterized queries** through asyncpg
- **Automatic SQL injection protection**
- **Connection pooling** limits exposure

### API Layer
- **Rate limiting** (100 req/min/IP default)
- **Pydantic validation** for incoming data
- **HTTPS required** in production

### Application
- **Structured logging** (no sensitive data)
- **Non-root Docker user**
- **Official Slack SDK** for signature verification

---

## Known Limitations
This is a personal / portfolio project:

- No dedicated security team or SLA
- No formal audits or bug bounty
- No penetration testing
- If secrets leak (Slack token, Ashby key, DB creds), rotate them immediately

Dependencies rely on:
FastAPI • asyncpg • Slack SDK • Ashby API • your hosting platform
Keep them updated (`pip list --outdated`).

---

## Deployment Guidance
If you deploy this beyond demo use:
- Store secrets in a managed secrets service
- Enforce HTTPS
- Restrict admin routes (`/admin/*`) to internal access
- Enable database TLS and automated backups
- Monitor logs for webhook signature failures or unusual activity

---

## Disclaimer
This software follows modern security practices but is **not enterprise-grade**.
Use at your own risk. Review the code, test in your environment, and apply your organization’s compliance requirements.

---

**Questions?** Open a GitHub discussion.
**Found a vulnerability?** Email me privately.
