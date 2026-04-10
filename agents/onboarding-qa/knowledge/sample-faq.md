# Company Handbook — Frequently Asked Questions

Welcome to the team! This FAQ covers the most common questions new hires ask during their first few weeks. If something isn't covered here, ask in #ask-people-ops on Slack.

---

## Time Off & Leave

### 1. What's the PTO policy?
We offer unlimited PTO with a 10-day minimum. That means you must take at least 10 days off per year. Most people take 15-20. You don't need approval for days off — just block your calendar, post in your team's Slack channel at least 3 business days in advance (2 weeks for vacations longer than 5 days), and make sure your work is covered.

### 2. How do I request time off?
Log into BambooHR, go to "Time Off," and submit the dates. Your manager gets an automatic notification. There's no formal approval step — the submission is the notice.

### 3. Are there company-wide holidays?
Yes. We observe 10 US federal holidays plus a company-wide winter break from December 24 through January 1. The full list is in BambooHR under "Holiday Calendar."

### 4. What's the parental leave policy?
16 weeks fully paid for all new parents (birth, adoption, or foster placement). You can take it all at once or split it into two blocks within the first year. Talk to People Ops to set up your plan.

### 5. Can I work from another country?
Yes, for up to 4 weeks per year. You need to notify People Ops at least 2 weeks before departure for tax compliance. Some countries have restrictions — check with People Ops first.

---

## Expenses & Equipment

### 6. How do I submit an expense report?
Use Brex. Open the Brex app, snap a photo of the receipt, categorize it, and submit. Reports under $200 are auto-approved. Over $200 requires manager approval. Submit within 30 days of the expense.

### 7. What's my equipment budget?
Every new hire gets a $2,500 equipment stipend for their first year. This covers monitors, keyboards, chairs, standing desks — whatever you need to do your best work. After year one, you get $1,000/year for upgrades and replacements.

### 8. Can I expense coworking spaces?
Yes, up to $300/month. Use your Brex card and tag it as "Coworking." No pre-approval needed.

### 9. How do I get a new laptop?
Laptops are provisioned by IT. If your machine is slow or broken, file a ticket in the #it-help Slack channel. Standard machines are MacBook Pro 14" with 32GB RAM. Specialty roles (ML, video) can request upgraded specs.

---

## Tech Stack & Development

### 10. What's our tech stack?
- **Backend:** Elixir/Phoenix with PostgreSQL
- **Frontend:** Next.js (React) with TypeScript
- **Infrastructure:** Google Cloud Platform (GKE, Cloud SQL, Cloud Run)
- **CI/CD:** GitHub Actions
- **Monitoring:** Datadog for metrics and logs, PagerDuty for alerts
- **Feature flags:** LaunchDarkly
- **Error tracking:** Sentry

### 11. How do I set up my dev environment?
Follow the Dev Environment Setup guide in the engineering wiki (Notion > Engineering > Getting Started). The short version: clone the monorepo, run `make setup`, and it handles Homebrew dependencies, Docker, database seeding, and environment variables. Total setup time is about 30 minutes on a fresh machine.

### 12. What's the PR review process?
1. Open a PR against `main`
2. The Code Review Bot auto-reviews within 5 minutes
3. Request a human reviewer (the bot suggests one based on code ownership)
4. One human approval required to merge
5. Squash-merge is the default; the bot enforces conventional commit prefixes in the merge commit

### 13. How do deployments work?
We deploy to production multiple times per day. Merging to `main` triggers a CI pipeline that runs tests, builds a container image, and deploys to staging automatically. Promotion to production requires clicking "Approve" in the GitHub Actions deployment workflow. Rollbacks are one-click in the same UI.

### 14. What's the on-call rotation?
Each team has a weekly on-call rotation managed in PagerDuty. New hires shadow on-call for their first 2 rotations before going solo. On-call engineers get a $500/week stipend. Escalation path: on-call engineer > team lead > engineering manager > VP Engineering.

---

## Onboarding Checklist

### 15. What should I do in my first week?
- [ ] Complete BambooHR profile and tax forms
- [ ] Set up your dev environment (see question 11)
- [ ] Join the required Slack channels: #general, #engineering, #your-team, #ask-people-ops
- [ ] Schedule 1:1s with your manager, your onboarding buddy, and 3 teammates
- [ ] Read the Architecture Decision Records (ADRs) in the engineering wiki
- [ ] Complete the security awareness training in KnowBe4
- [ ] Ship your first PR (your onboarding buddy will help pick a good starter issue)

### 16. Who is my onboarding buddy?
Your manager assigns an onboarding buddy before your start date. They'll reach out on Slack on day one. If nobody has reached out by end of day one, ping your manager.

---

## Who to Ask

### 17. I have a question about benefits or HR policies.
Ask in #ask-people-ops or email people-ops@company.com. Response time is usually under 4 hours.

### 18. I have a question about the codebase or architecture.
Ask in #engineering or your team's channel. For architecture questions, tag @platform-team. For specific service questions, check the CODEOWNERS file to find the team that owns that code.

### 19. I need access to a tool or service.
File a request in #it-help. Common access requests (GitHub, GCP, Datadog, Sentry) are pre-provisioned during onboarding. If something is missing, IT can usually grant access same-day.

### 20. I found a security issue.
Do NOT post it in Slack. Email security@company.com or use the #security-private channel (invite-only — ask your manager to add you if needed). For critical issues, page the security on-call via PagerDuty.

---

## Benefits

### 21. What health insurance do we offer?
We offer three medical plans through Aetna (PPO, HMO, and HDHP with HSA), plus dental (Delta Dental) and vision (VSP). The company covers 90% of employee premiums and 70% of dependent premiums. Open enrollment is in November; outside of that, you can only change plans with a qualifying life event.

### 22. Is there a 401(k)?
Yes. We offer a 401(k) through Fidelity with a 4% company match (100% match on the first 4% you contribute). You're auto-enrolled at 6% on your start date. Vesting is immediate.

### 23. Do we get stock options?
Yes. All full-time employees receive an equity grant as part of their offer. Vesting is 4 years with a 1-year cliff. Refresh grants are reviewed annually during the compensation cycle.

### 24. Is there a learning & development budget?
Yes. $2,000/year for conferences, courses, books, and certifications. Submit via Brex and tag as "Learning & Development." No pre-approval needed for individual purchases under $500.

### 25. Do we offer mental health support?
Yes. We provide free access to Spring Health for therapy and coaching (up to 8 sessions/year covered at 100%). EAP services are available 24/7 through the same platform.

---

## Office & Remote Work

### 26. Where are the offices?
- **HQ:** San Francisco, CA (SoMa district, 4th & Harrison)
- **Engineering hub:** Austin, TX (East 6th Street)
- **Sales office:** New York, NY (Flatiron)

All offices are open Monday-Friday, 7am-8pm local time. Badge access is set up during onboarding.

### 27. Is the company remote-friendly?
Yes. About 60% of the company is fully remote. There's no requirement to be in an office. Teams that have local clusters sometimes do optional in-person days, but nothing is mandatory.

### 28. How does the home office stipend work?
In addition to the $2,500 first-year equipment budget, fully remote employees get a one-time $500 home office setup stipend for things like a desk, lamp, webcam, or cable management. Submit receipts via Brex.

---

## Miscellaneous

### 29. How does the referral bonus work?
$5,000 for engineering hires, $3,000 for all other roles. Paid out 50% at the referral's start date and 50% after 90 days. Submit referrals through Greenhouse.

### 30. Where do I find company policies and docs?
- **HR policies:** BambooHR > Documents
- **Engineering docs:** Notion > Engineering wiki
- **Architecture decisions:** GitHub repo `internal/adrs`
- **Runbooks:** Notion > Engineering > Runbooks
- **This FAQ:** Ask the Onboarding Q&A bot any time!
