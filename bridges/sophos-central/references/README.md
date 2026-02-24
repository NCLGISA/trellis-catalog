# Sophos Central Bridge -- References Directory

This directory holds **institutional knowledge** documents that customize the
Sophos Central bridge for your organization. The Tendril agent references these
files when answering questions about your endpoint security posture.

## What to put here

### Endpoint Group Map (`ik-endpoint-groups.md`)

Document your organization's endpoint grouping strategy, department-to-group
mappings, and policy assignment logic. This enables the agent to:

- Identify which department owns an endpoint
- Correlate alerts with responsible teams
- Audit policy coverage across groups
- Answer "what group is WORKSTATION01 in?" instantly

**Example group map:**

```markdown
| Group Name       | Department          | Policy Type        | Endpoints |
|------------------|---------------------|--------------------|-----------|
| IT_Dept          | Information Tech    | threat-protection  | ~30       |
| Finance          | Finance & Budget    | threat-protection  | ~15       |
| Public_Library   | Library System      | custom (relaxed)   | ~50       |
| Servers          | IT Infrastructure   | server-threat      | ~90       |
```

### Policy Standards (`ik-policy-standards.md`)

Document your baseline policy settings, deviations, and the rationale for
non-recommended configurations. Useful for:

- Policy compliance audits
- Understanding why certain threat protection settings differ
- Tracking approved exceptions

### IOC Playbook (`ik-ioc-playbook.md`)

Document your standard IOC response workflow:

- When to block vs. allow SHA256 hashes
- Escalation thresholds for alert severity
- XDR query templates for common threat hunts
- Isolation criteria and approval chain

### Other Reference Documents

You can add any Markdown files here that contain institutional knowledge:

- Endpoint lifecycle and refresh schedules
- Sophos MDR authorized contact list
- Scanning exclusion justifications
- Compliance requirements (CJIS, HIPAA, PCI scope)
- Network segmentation and isolation policies

## How the agent uses references

The Tendril agent's SKILL.md file points to this directory. When answering
questions, the agent reads these reference documents as context. Keeping them
accurate and up-to-date improves the quality of security audits and incident
response recommendations.
