# Adobe Sign Bridge -- References

This directory holds **institutional knowledge** documents that customize the
bridge for your organization. The Tendril agent reads these files when answering
questions about your environment.

## What to Put Here

Add Markdown documents that capture knowledge the API documentation does not
provide:

| Document Type | Example | Why It Helps |
|---------------|---------|--------------|
| Configuration standards | VLAN numbering, naming conventions | Agent can audit for compliance |
| Architecture decisions | Why certain settings were chosen | Agent explains context, not just state |
| Compliance requirements | PCI scope, audit boundaries | Agent respects security boundaries |
| Operational runbooks | Incident response, change procedures | Agent follows your processes |
| Environment maps | Site lists, department IDs, tenant details | Agent resolves names to IDs |

## How the Agent Uses References

The Tendril agent's SKILL.md points to this directory. When answering questions,
the agent reads these documents as context. Keeping them accurate and up-to-date
improves the quality of audits, troubleshooting, and recommendations.

## Naming Convention

Use the `ik-` prefix for institutional knowledge documents:

```
references/
  ik-network-topology.md
  ik-department-map.md
  ik-compliance-scope.md
  README.md (this file)
```
