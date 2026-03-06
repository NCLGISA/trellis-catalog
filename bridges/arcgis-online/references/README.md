# ArcGIS Online Bridge -- References

This directory holds **institutional knowledge** documents that customize the
ArcGIS Online bridge for your organization. The Tendril agent reads these files
when answering questions about your environment.

## What to Put Here

Add Markdown documents that capture knowledge the API documentation does not
provide:

| Document Type | Example | Why It Helps |
|---------------|---------|--------------|
| Layer inventory | Feature service URLs, field mappings | Agent can query the right layers |
| Publishing standards | Sharing policies, naming conventions | Agent audits for compliance |
| Credit budget | Monthly allocation, high-cost operations | Agent warns before expensive ops |
| User role matrix | Who gets Publisher vs. Viewer | Agent validates access requests |
| Department map | Department names to ArcGIS group IDs | Agent resolves names to groups |

## How the Agent Uses References

The Tendril agent's SKILL.md points to this directory. When answering questions,
the agent reads these documents as context. Keeping them accurate and up-to-date
improves the quality of audits, troubleshooting, and recommendations.

## Naming Convention

Use the `ik-` prefix for institutional knowledge documents:

```
references/
  ik-layer-inventory.md
  ik-credit-budget.md
  ik-user-roles.md
  README.md (this file)
```
