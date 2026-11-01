# End-to-end software overview

## Product type
**Private brokerage OS** for your team — not InviteMySponsors-style public marketplace.

## Modules (what is in the software)

| # | Module | Purpose | Sub-points |
|---|--------|---------|------------|
| 1 | **Dashboard** | Command center | KPIs, agent run log, link to your tasks |
| 2 | **Events pipeline** | Supply (organizers) | Add event, planning stage, LOI flag, footfall, packages notes |
| 3 | **Brand CRM** | Demand (sponsors) | Budget, city, category, goals, contacts — **private** |
| 4 | **Private matcher** | Fit without leakage | Score city/category/budget/timing; tiers exact/strong/partial |
| 5 | **Outreach queue** | Lead conversion prep | Agent drafts email; founder approves; you send manually |
| 6 | **Deals & commission** | Revenue | Deal amount, 10–20% commission auto-calculated |
| 7 | **Founder tasks** | Human-in-the-loop | Exact list of what **you** must do after agents run |
| 8 | **Agent orchestrator** | Daily team run | 6 agents in sequence via CLI |

## Agent team (6 agents)

1. **Event Scout** — surfaces events needing LOI calls  
2. **Brand Scout** — flags brands missing contact info  
3. **Fit Matcher** — creates private match rows (score ≥ 50)  
4. **Outreach Writer** — drafts organizer outreach (draft only)  
5. **Pipeline Chief** — daily brief + priority task  
6. **Deal Desk** — payment collection reminders on agreed deals  

## Data flow

```
Lead signals → Events/Brands CRM → Matcher → Outreach drafts
       → YOU: approve/send/call/intro → Deal record → Commission
```

## What agents do NOT do

- Send email/WhatsApp automatically  
- Sign contracts or negotiate price  
- Share brand database with organizers  
- Close payments  

## Production readiness checklist

- [x] SQLite database with schema  
- [x] Web UI for all modules  
- [x] Agent orchestrator CLI  
- [x] Demo seed data  
- [x] Pytest E2E tests  
- [ ] Your real events/brands imported  
- [ ] Optional: OPENAI_API_KEY for richer drafts (future)  

## Your daily part (non-negotiable)

| Time | Action |
|------|--------|
| Morning | Run `python -m agents.orchestrator --daily` |
| 15 min | Complete top 3 **Founder tasks** |
| Ongoing | Approve outreach → send from your account |
| Ongoing | LOI calls + hosted intros |
| Weekly | Enter closed deals; chase commission payments |
