Goal
- Add minimal server-rendered UI for Projects and per-Project API Keys.
- Scope everything to the authenticated user’s Organization membership.

Non-goals (v0)
- Pagination/search
- Advanced RBAC
- Public API endpoints

Requirements
Projects
- User can list projects they have access to
- User can create a project (under an org they belong to)
- User can edit a project (under an org they belong to)
- User can delete a project (POST-only)
- User can view a project detail page

API Keys (per project)
- User can create an API key for a project
  - generate random raw key; store only sha256(raw_key) in hashed_key
  - raw key is shown once on success page/flash
- User can “delete” an API key (revoke)
  - sets revoked_at timestamp (do not hard-delete)

Project switching
- User can switch “current project”
  - stored in session current_project_id
  - switching must validate access (same org)

Security / access control
- All pages require authentication
- All queries are filtered to organizations the user belongs to
- All destructive actions are POST + CSRF

Templates
- Place templates in: projects/templates/projects/
- Minimal pages:
  - projects/list.html
  - projects/new.html
  - projects/detail.html (includes api key list + create form)
  - projects/key_created.html (optional; show raw key once)

Tests (Django TestCase)
- Auth: redirects/403 for unauthenticated
- Access control: cannot view/create/delete outside org
- Project: create + delete + list scoping
- ApiKey: create populates hashed_key; revoke sets revoked_at
- Switch: sets session current_project_id and enforces access

Repo hygiene
- Move tests into app folder: projects/tests/ (remove old tests.py)
- Templates remain app-local
- Use DJango best practices 
- Make incremental commits as functionality lands

