<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 2.0.0 (MAJOR - Complete Architectural Rewrite)
Amendment Rationale: Project pivoting from config-file-based Pi dashboard to
                     multi-tenant web application with database backend

Modified Principles:
  - "Configuration-First Design" → REMOVED
  - "Raspberry Pi Compatibility" → "Cloud-Ready with Optional Pi Support"
  - "Dual-Component Isolation" → REMOVED (no longer dual-component)
  - "Documentation as Configuration" → "Living Documentation"
  - "Simplicity Over Features" → RETAINED (unchanged)

Added Principles:
  - I. Database-First Design (new)
  - II. Multi-Tenancy & Authentication (new)
  - III. Traditional Web Architecture (new)

Added Sections:
  - "Data & Privacy" section
  - Database deployment requirements

Removed Sections:
  - "Dual-Component Isolation" principle
  - Static site generator references
  - config.yaml-specific guidance

Templates Status:
  ⚠ .specify/templates/plan-template.md - NEEDS UPDATE (Constitution Check)
  ⚠ .specify/templates/spec-template.md - REVIEW for multi-tenancy patterns
  ⚠ .specify/templates/tasks-template.md - REVIEW for auth/db task types
  ⚠ CLAUDE.md - WILL NEED MAJOR UPDATE after rewrite complete

Follow-up TODOs:
  - Run /speckit.specify for the rewrite feature specification
  - Update CLAUDE.md after implementation to reflect new architecture
  - Update README.md to reflect web app instead of Pi dashboard
  - Archive old config.yaml or create migration guide
-->

# DinkyDash Constitution

## Core Principles

### I. Database-First Design
All dashboard content (tasks, countdowns, family data) MUST be stored in a relational database. The application MUST support both SQLite (for Pi/local deployment) and PostgreSQL/MySQL (for cloud deployment). Database schema MUST use migrations for version control. Direct file-based configuration (like config.yaml) MUST NOT be used for runtime data.

**Rationale**: Multi-family support requires persistent, queryable data storage. Database-first design enables user management, data isolation, and scalable architecture while maintaining Pi deployment option via SQLite.

### II. Multi-Tenancy & Authentication
The application MUST support multiple families with isolated data. User authentication MUST be required for dashboard access and management. Each family's data MUST be logically separated (row-level or schema-level). Session management MUST be secure with appropriate timeout and CSRF protection.

**Rationale**: Transitioning from single-family Pi app to multi-family web service requires secure user isolation and authentication to protect family data privacy.

### III. Traditional Web Architecture
The application MUST use server-side rendering (Flask templates) for primary UI. JavaScript MUST be used sparingly for progressive enhancement only. API endpoints MAY be provided for mobile/future use but MUST NOT be required for core functionality. The application MUST function with JavaScript disabled for basic operations.

**Rationale**: Server-side rendering keeps architecture simple, improves performance on constrained devices (Pi), ensures compatibility, and reduces frontend complexity compared to SPA frameworks.

### IV. Simplicity Over Features
New features MUST be evaluated against core use case: families managing recurring tasks and countdowns. Features requiring complex UI, significant dependencies, or architectural changes MUST be justified against maintenance burden. The codebase MUST remain understandable to developers with basic Python/Flask knowledge.

**Rationale**: This principle carries forward from v1.0.0—scope creep threatens maintainability. The dashboard's value lies in simplicity and reliability, not feature richness.

### V. Living Documentation
Database schema MUST be documented with migrations and comments. Setup instructions (README.md) MUST include both local (SQLite/Pi) and cloud (PostgreSQL) deployment paths. Architecture decisions MUST be recorded in CLAUDE.md. API endpoints (if added) MUST be documented with examples.

**Rationale**: Documentation drift causes maintenance friction. Living documentation ensures the project remains accessible to contributors and operators across deployment scenarios.

## Data & Privacy

### Data Isolation Requirements
- Each family MUST have a unique tenant identifier
- Database queries MUST filter by tenant_id to prevent cross-family data leaks
- User sessions MUST be bound to tenant context
- Administrative functions MUST respect tenant boundaries unless explicitly privileged

### Privacy Standards
- Passwords MUST be hashed (bcrypt/argon2)
- Personal information (names, dates) MUST be tenant-scoped
- File uploads (profile images) MUST be validated and tenant-isolated
- No third-party analytics or tracking without explicit consent

## Deployment & Operations

### Database Requirements
- **SQLite mode** (Pi/local): Single-file database, migrations applied on startup
- **PostgreSQL/MySQL mode** (cloud): Connection pooling, migration scripts, backup strategy
- Migrations MUST be reversible and tested
- Schema changes MUST NOT cause downtime for existing users

### Deployment Targets
- **Raspberry Pi**: Lightweight process, SQLite, systemd service, nginx/gunicorn
- **Cloud (optional)**: Docker container, PostgreSQL, horizontal scaling support
- Both targets MUST share same codebase (environment-based configuration)

### Operations Standards
- Application MUST log authentication events and errors
- Database backups MUST be documented for both SQLite and cloud modes
- Health check endpoint MUST be available for monitoring
- Deployment MUST support zero-downtime updates (cloud) or quick restart (Pi)

## Development Workflow

### Change Process
1. **Schema changes**: Write migration, test up/down, document in commit
2. **Feature additions**: Update tests if needed, ensure tenant isolation, test on SQLite and PostgreSQL
3. **Documentation updates**: Update README for deployment changes, CLAUDE.md for architecture changes

### Testing Standards
- Authentication flows MUST be tested (login, logout, session management)
- Tenant isolation MUST be verified (cannot access other family data)
- Database migrations MUST be tested (both upgrade and rollback)
- Both SQLite and PostgreSQL MUST be tested for compatibility

### Security Reviews
- All user input MUST be validated and sanitized
- SQL injection vectors MUST be prevented (use parameterized queries/ORM)
- CSRF protection MUST be enabled for state-changing operations
- Password reset flows MUST be secure (time-limited tokens)

## Governance

This constitution establishes non-negotiable principles for DinkyDash development post-rewrite. All changes MUST align with these principles.

**Version 2.0.0 represents a complete architectural pivot** from the original config-file-based Pi dashboard to a multi-tenant web application. This MAJOR version change acknowledges that v1.x principles (Configuration-First, Dual-Component) are incompatible with the new direction.

### Amendment Requirements
1. MAJOR bump: Backward-incompatible principle changes, architectural pivots
2. MINOR bump: New principles/sections added, materially expanded guidance
3. PATCH bump: Clarifications, wording improvements, non-semantic fixes

All amendments MUST:
- Document clear justification in commit or PR
- Update Sync Impact Report at top of this file
- Verify dependent templates and documentation are updated

**Compliance Review**: All PRs MUST verify constitution compliance. Complexity introduced MUST be justified against Principle IV (Simplicity Over Features). Multi-tenancy violations (data leakage) are CRITICAL BLOCKERS.

See `CLAUDE.md` for runtime development guidance (will be updated post-rewrite).

**Version**: 2.0.0 | **Ratified**: 2025-12-04 | **Last Amended**: 2025-12-04
