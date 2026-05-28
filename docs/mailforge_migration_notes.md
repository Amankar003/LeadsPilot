# MailForge Migration Notes

## Purpose

This document explains how legacy outreach tables and flows map to MailForge in the current codebase.

## Current source of truth

- Draft generation and review: `mailforge_drafts`
- Follow-up draft scheduling: `mailforge_followups`
- Send logs: `mailforge_email_logs`
- Suppression controls: `mailforge_suppression_list`
- Sender configuration: `sender_accounts`

## Legacy table compatibility

Legacy tables are still present for backward compatibility and historical data access:

- `email_drafts`
- `email_logs`
- `followups`
- `suppression_list`

These are no longer used by primary Streamlit navigation and MailForge workflows.

## UI migration status

- Main sidebar email pages were removed in favor of `MailForge`.
- CRM and Settings suppression actions now write to MailForge suppression.
- Intelligence report viewer now saves generated/approved drafts to MailForge.

## Data transition guidance

If you need historical continuity, run one-time migration scripts to copy legacy outreach records into MailForge tables:

- `email_drafts` -> `mailforge_drafts`
- `email_logs` -> `mailforge_email_logs`
- `followups` -> `mailforge_followups`
- `suppression_list` -> `mailforge_suppression_list`

Do this in maintenance windows and validate row counts before switching analytics consumers.

## Notes

- Analytics placeholders for open/click/reply remain intentionally marked as "Not configured yet".
- Local SQLite and production PostgreSQL/Supabase remain supported.
