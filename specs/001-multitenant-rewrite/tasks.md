# Tasks: Multi-Tenant Web Application Rewrite

**Input**: Design documents from `/specs/001-multitenant-rewrite/`
**Prerequisites**: plan.md, spec.md (user stories P1-P7), research.md, data-model.md, contracts/routes.md, contracts/forms.md, contracts/templates.md

**Tests**: Tests included for tenant isolation, auth flows, and migrations as requested in spec.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create Flask application package structure dinkydash/ with __init__.py, models/, routes/, forms/, templates/, static/, utils/, migrations/
- [X] T002 Initialize Python project with requirements.txt (Flask 3.0+, SQLAlchemy 2.0+, Flask-Login, Flask-WTF, Flask-Migrate, Werkzeug, Pillow, pytest, pytest-flask)
- [X] T003 [P] Create development requirements-dev.txt (pytest-cov, black, flake8)
- [X] T004 [P] Create configuration classes in dinkydash/config.py (DevelopmentConfig, ProductionConfig, TestConfig)
- [X] T005 [P] Create environment variable template .env.example with SECRET_KEY, DATABASE_URL, UPLOAD_FOLDER
- [X] T006 [P] Create Flask CLI config .flaskenv with FLASK_APP=app.py
- [X] T007 Create application entry point app.py with Flask app factory pattern
- [X] T008 [P] Create static CSS directory structure dinkydash/static/css/style.css
- [X] T009 [P] Create uploads directory structure dinkydash/static/uploads/ with .gitkeep

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database & Models (ALL user stories depend on these)

- [X] T010 [P] Create Family model in dinkydash/models/family.py with id, name, created_at
- [X] T011 [P] Create User model in dinkydash/models/user.py with id, email, password_hash, tenant_id, created_at, Flask-Login integration
- [X] T012 [P] Create Dashboard model in dinkydash/models/dashboard.py with id, tenant_id, name, layout_size, is_default, created_at
- [X] T013 [P] Create Task model in dinkydash/models/task.py with id, dashboard_id, name, rotation_json, icon_type, icon_value, created_at
- [X] T014 [P] Create Countdown model in dinkydash/models/countdown.py with id, dashboard_id, name, date_month, date_day, icon_type, icon_value, created_at
- [X] T015 Initialize database models in dinkydash/models/__init__.py with SQLAlchemy and Flask-Migrate setup
- [X] T016 Generate initial migration with flask db migrate -m "Create initial schema"
- [X] T017 Test migration on SQLite database (verify all tables, constraints, indexes created)
- [X] T018 Test migration on PostgreSQL database (verify compatibility)

### Authentication & Tenant Isolation (ALL user stories need this)

- [X] T019 Setup Flask-Login in dinkydash/__init__.py with user_loader callback
- [X] T020 Implement tenant isolation filter in dinkydash/utils/tenant.py with SQLAlchemy event listener for automatic tenant_id filtering
- [X] T021 Create CSRF protection setup in dinkydash/__init__.py with Flask-WTF
- [X] T022 Implement password hashing utilities in dinkydash/utils/auth.py using Werkzeug.security

### Core Utilities (Multiple user stories need these)

- [X] T023 [P] Implement rotation calculation logic in dinkydash/utils/rotation.py with get_current_person(rotation_list, day_of_year)
- [X] T024 [P] Implement countdown calculation logic in dinkydash/utils/countdown.py with calculate_days_remaining(month, day) and auto-rollover
- [X] T025 [P] Implement image upload utilities in dinkydash/utils/images.py with save_image(file, tenant_id, entity_type, entity_id), validate_image(file), delete_image(filepath)

### Error Handlers (ALL routes need these)

- [X] T026 [P] Create 403 error template in dinkydash/templates/errors/403.html
- [X] T027 [P] Create 404 error template in dinkydash/templates/errors/404.html
- [X] T028 [P] Create 500 error template in dinkydash/templates/errors/500.html
- [X] T029 Register error handlers in dinkydash/__init__.py for 403, 404, 500

### Base Template (ALL templates extend this)

- [X] T030 Create base template in dinkydash/templates/base.html with HTMX, CSRF meta tag, navigation, flash messages, meta refresh fallback

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - View Family Dashboard (Priority: P1) 🎯 MVP

**Goal**: Family members can view dashboard with today's task assignments and countdown calculations, auto-refreshing every 30 seconds

**Independent Test**: Seed database with sample family data (tasks, countdowns) and verify dashboard displays correct rotations and countdown days

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T031 [P] [US1] Integration test for dashboard viewing with sample data in tests/test_integration/test_dashboard_viewing.py
- [X] T032 [P] [US1] Unit test for rotation calculation logic in tests/test_utils/test_rotation.py
- [X] T033 [P] [US1] Unit test for countdown calculation logic in tests/test_utils/test_countdown.py
- [X] T034 [P] [US1] Route test for dashboard view endpoint in tests/test_routes/test_dashboard.py
- [X] T035 [P] [US1] Route test for HTMX polling endpoint in tests/test_routes/test_dashboard.py

### Implementation for User Story 1

- [ ] T036 [US1] Create dashboard list template in dinkydash/templates/dashboard/list.html (shows all dashboards for family)
- [ ] T037 [US1] Create dashboard view template in dinkydash/templates/dashboard/view.html with HTMX polling, task cards, countdown cards, layout size classes
- [ ] T038 [US1] Implement dashboard list route GET / in dinkydash/routes/dashboard.py with tenant filtering, auto-redirect if single dashboard
- [ ] T039 [US1] Implement dashboard view route GET /dashboard/<id> in dinkydash/routes/dashboard.py with task rotation calculation, countdown calculation, sorting
- [ ] T040 [US1] Implement HTMX polling route GET /dashboard/<id>/content in dinkydash/routes/dashboard.py returning partial HTML
- [ ] T041 [US1] Register dashboard blueprint in dinkydash/__init__.py
- [ ] T042 [US1] Add CSS styling for dashboard cards and layout sizes (small, medium, large) in dinkydash/static/css/style.css

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Dashboard displays tasks and countdowns with auto-refresh.

---

## Phase 4: User Story 2 - User Registration and Authentication (Priority: P2)

**Goal**: Family administrators can register accounts and log in to access their dashboard

**Independent Test**: Register new family account, log in with credentials, log out, verify session management and redirect behavior

### Tests for User Story 2

- [X] T043 [P] [US2] Integration test for registration flow in tests/test_integration/test_auth_flow.py (implemented in tests/test_auth.py)
- [X] T044 [P] [US2] Integration test for login/logout flow in tests/test_integration/test_auth_flow.py (implemented in tests/test_auth.py)
- [X] T045 [P] [US2] Route test for registration endpoint in tests/test_routes/test_auth.py (implemented in tests/test_auth.py)
- [X] T046 [P] [US2] Route test for login endpoint in tests/test_routes/test_auth.py (implemented in tests/test_auth.py)
- [X] T047 [P] [US2] Route test for logout endpoint in tests/test_routes/test_auth.py (implemented in tests/test_auth.py)
- [X] T048 [P] [US2] Route test for protected dashboard access in tests/test_routes/test_dashboard.py
- [X] T049 [P] [US2] Form validation test for RegistrationForm in tests/test_forms/test_auth.py (implemented in tests/test_auth.py)
- [X] T050 [P] [US2] Form validation test for LoginForm in tests/test_forms/test_auth.py (implemented in tests/test_auth.py)

### Implementation for User Story 2

- [X] T051 [P] [US2] Create RegistrationForm in dinkydash/forms/auth.py with family_name, email, password, confirm_password, email uniqueness validator
- [X] T052 [P] [US2] Create LoginForm in dinkydash/forms/auth.py with email, password, remember_me
- [X] T053 [P] [US2] Create registration template in dinkydash/templates/auth/register.html
- [X] T054 [P] [US2] Create login template in dinkydash/templates/auth/login.html
- [X] T055 [US2] Implement registration routes GET/POST /register in dinkydash/routes/auth.py (creates Family, User, default Dashboard)
- [X] T056 [US2] Implement login routes GET/POST /login in dinkydash/routes/auth.py with session creation and remember_me
- [X] T057 [US2] Implement logout route GET /logout in dinkydash/routes/auth.py
- [X] T058 [US2] Register auth blueprint in dinkydash/__init__.py
- [ ] T059 [US2] Add @login_required decorator to dashboard routes in dinkydash/routes/dashboard.py
- [X] T060 [US2] Add CSS styling for auth forms in dinkydash/static/css/style.css

**Checkpoint**: At this point, User Stories 1 AND 2 should both work. Users can register, log in, and see their dashboard.

---

## Phase 5: User Story 3 - Manage Recurring Tasks (Priority: P3)

**Goal**: Family administrators can create, edit, and delete recurring tasks with rotation and icons

**Independent Test**: Log in as admin, create task with rotation, verify it appears on dashboard, edit task, delete task

### Tests for User Story 3

- [ ] T061 [P] [US3] Integration test for task CRUD workflow in tests/test_integration/test_task_management.py
- [ ] T062 [P] [US3] Route test for task list endpoint in tests/test_routes/test_admin.py
- [ ] T063 [P] [US3] Route test for task create endpoint in tests/test_routes/test_admin.py
- [ ] T064 [P] [US3] Route test for task edit endpoint in tests/test_routes/test_admin.py
- [ ] T065 [P] [US3] Route test for task delete endpoint in tests/test_routes/test_admin.py
- [ ] T066 [P] [US3] Form validation test for TaskForm in tests/test_forms/test_task.py
- [ ] T067 [P] [US3] Test image upload validation and storage in tests/test_utils/test_images.py

### Implementation for User Story 3

- [ ] T068 [P] [US3] Create TaskForm in dinkydash/forms/task.py with name, dashboard_id, rotation (FieldList), icon_type (RadioField), emoji, image (FileField), custom validators
- [ ] T069 [P] [US3] Create task list template in dinkydash/templates/admin/tasks.html
- [ ] T070 [P] [US3] Create task form template in dinkydash/templates/admin/task_form.html with dynamic rotation entries, icon type toggle JavaScript
- [ ] T071 [US3] Implement task list route GET /admin/tasks in dinkydash/routes/admin.py with tenant filtering
- [ ] T072 [US3] Implement task create routes GET/POST /admin/tasks/new in dinkydash/routes/admin.py with image upload handling, rotation JSON serialization
- [ ] T073 [US3] Implement task edit routes GET/POST /admin/tasks/<id>/edit in dinkydash/routes/admin.py with image replacement, tenant validation
- [ ] T074 [US3] Implement task delete route POST /admin/tasks/<id>/delete in dinkydash/routes/admin.py with image file deletion
- [ ] T075 [US3] Register admin blueprint in dinkydash/__init__.py
- [ ] T076 [US3] Add CSS styling for admin tables and forms in dinkydash/static/css/style.css

**Checkpoint**: At this point, User Stories 1, 2, AND 3 work. Users can manage tasks and see them on dashboard.

---

## Phase 6: User Story 4 - Manage Countdown Events (Priority: P4)

**Goal**: Family administrators can create, edit, and delete countdown events with dates and icons

**Independent Test**: Log in as admin, create countdown with date, verify countdown appears on dashboard with correct days remaining, edit countdown, delete countdown

### Tests for User Story 4

- [ ] T077 [P] [US4] Integration test for countdown CRUD workflow in tests/test_integration/test_countdown_management.py
- [ ] T078 [P] [US4] Route test for countdown list endpoint in tests/test_routes/test_admin.py
- [ ] T079 [P] [US4] Route test for countdown create endpoint in tests/test_routes/test_admin.py
- [ ] T080 [P] [US4] Route test for countdown edit endpoint in tests/test_routes/test_admin.py
- [ ] T081 [P] [US4] Route test for countdown delete endpoint in tests/test_routes/test_admin.py
- [ ] T082 [P] [US4] Form validation test for CountdownForm in tests/test_forms/test_countdown.py
- [ ] T083 [P] [US4] Test countdown date validation (prevent Feb 31) in tests/test_forms/test_countdown.py

### Implementation for User Story 4

- [ ] T084 [P] [US4] Create CountdownForm in dinkydash/forms/countdown.py with name, dashboard_id, date_month (SelectField), date_day (IntegerField), icon_type, emoji, image, date validation
- [ ] T085 [P] [US4] Create countdown list template in dinkydash/templates/admin/countdowns.html sorted by days remaining
- [ ] T086 [P] [US4] Create countdown form template in dinkydash/templates/admin/countdown_form.html with icon type toggle JavaScript
- [ ] T087 [US4] Implement countdown list route GET /admin/countdowns in dinkydash/routes/admin.py with tenant filtering, days remaining calculation
- [ ] T088 [US4] Implement countdown create routes GET/POST /admin/countdowns/new in dinkydash/routes/admin.py with image upload handling, date validation
- [ ] T089 [US4] Implement countdown edit routes GET/POST /admin/countdowns/<id>/edit in dinkydash/routes/admin.py with image replacement
- [ ] T090 [US4] Implement countdown delete route POST /admin/countdowns/<id>/delete in dinkydash/routes/admin.py with image file deletion

**Checkpoint**: All core management features work. Users can manage tasks, countdowns, and view dashboard.

---

## Phase 7: User Story 5 - Manage Multiple Dashboards (Priority: P5)

**Goal**: Family administrators can create multiple named dashboards, assign tasks/countdowns to specific dashboards, and navigate between them

**Independent Test**: Log in as admin, create "Kitchen Dashboard", move tasks to it, view Kitchen dashboard separately from default dashboard, delete a dashboard

### Tests for User Story 5

- [ ] T091 [P] [US5] Integration test for dashboard CRUD workflow in tests/test_integration/test_dashboard_management.py
- [ ] T092 [P] [US5] Integration test for default dashboard auto-creation on registration in tests/test_integration/test_auth_flow.py
- [ ] T093 [P] [US5] Route test for dashboard management list endpoint in tests/test_routes/test_admin.py
- [ ] T094 [P] [US5] Route test for dashboard create endpoint in tests/test_routes/test_admin.py
- [ ] T095 [P] [US5] Route test for dashboard edit endpoint in tests/test_routes/test_admin.py
- [ ] T096 [P] [US5] Route test for dashboard delete endpoint with prevention of last dashboard deletion in tests/test_routes/test_admin.py
- [ ] T097 [P] [US5] Form validation test for DashboardForm in tests/test_forms/test_dashboard.py

### Implementation for User Story 5

- [ ] T098 [P] [US5] Create DashboardForm in dinkydash/forms/dashboard.py with name, layout_size (RadioField with small/medium/large choices)
- [ ] T099 [P] [US5] Create dashboard management list template in dinkydash/templates/admin/dashboards.html
- [ ] T100 [P] [US5] Create dashboard form template in dinkydash/templates/admin/dashboard_form.html
- [ ] T101 [US5] Update registration route to auto-create "Family Dashboard" with is_default=True in dinkydash/routes/auth.py
- [ ] T102 [US5] Implement dashboard management list route GET /admin/dashboards in dinkydash/routes/admin.py
- [ ] T103 [US5] Implement dashboard create routes GET/POST /admin/dashboards/new in dinkydash/routes/admin.py
- [ ] T104 [US5] Implement dashboard edit routes GET/POST /admin/dashboards/<id>/edit in dinkydash/routes/admin.py
- [ ] T105 [US5] Implement dashboard delete route POST /admin/dashboards/<id>/delete in dinkydash/routes/admin.py with prevention of last dashboard deletion, task/countdown reassignment
- [ ] T106 [US5] Update TaskForm and CountdownForm to populate dashboard_id choices dynamically in routes

**Checkpoint**: Full dashboard organization working. Multiple dashboards can be created and managed.

---

## Phase 8: User Story 6 - Customize Dashboard Layout (Priority: P6)

**Goal**: Family administrators can adjust dashboard element sizes (small, medium, large) per dashboard and preferences persist

**Independent Test**: Log in as admin, change layout from default to "large" for Kitchen Dashboard, log out and back in, verify layout persists, check different dashboards have independent layouts

### Tests for User Story 6

- [ ] T107 [P] [US6] Integration test for layout preference persistence in tests/test_integration/test_layout_customization.py
- [ ] T108 [P] [US6] Test layout size validation in DashboardForm in tests/test_forms/test_dashboard.py
- [ ] T109 [P] [US6] Test CSS layout classes render correctly in tests/test_routes/test_dashboard.py

### Implementation for User Story 6

- [ ] T110 [US6] Add layout size CSS classes (layout-small, layout-medium, layout-large) to dinkydash/static/css/style.css with responsive card sizing, emoji sizing, image sizing
- [ ] T111 [US6] Update dashboard view template to use layout-{{ dashboard.layout_size }} class in dinkydash/templates/dashboard/view.html
- [ ] T112 [US6] Verify DashboardForm includes layout_size field with correct choices (already created in Phase 7)
- [ ] T113 [US6] Verify dashboard model saves and retrieves layout_size correctly (already created in Phase 2)

**Checkpoint**: Layout customization complete. Each dashboard can have independent layout size.

---

## Phase 9: User Story 7 - Multi-Family Tenant Isolation (Priority: P7)

**Goal**: Multiple families use the system securely with complete data isolation, no cross-tenant data access

**Independent Test**: Create two family accounts, add distinct data to each, log in as Family A and verify only Family A's data appears, attempt URL manipulation to access Family B's data and confirm denial

### Tests for User Story 7

- [ ] T114 [P] [US7] Integration test for tenant isolation across all entities in tests/test_integration/test_tenant_isolation.py
- [ ] T115 [P] [US7] Test Family A cannot access Family B's dashboards via URL in tests/test_integration/test_tenant_isolation.py
- [ ] T116 [P] [US7] Test Family A cannot access Family B's tasks via URL in tests/test_integration/test_tenant_isolation.py
- [ ] T117 [P] [US7] Test Family A cannot access Family B's countdowns via URL in tests/test_integration/test_tenant_isolation.py
- [ ] T118 [P] [US7] Test SQLAlchemy tenant filter applies automatically in tests/test_utils/test_tenant.py
- [ ] T119 [P] [US7] Test image uploads are tenant-scoped and inaccessible cross-tenant in tests/test_integration/test_tenant_isolation.py

### Implementation for User Story 7

- [ ] T120 [US7] Verify tenant isolation filter works correctly for Dashboard queries (already implemented in Phase 2)
- [ ] T121 [US7] Verify tenant isolation filter works correctly for Task queries via dashboard relationship (already implemented in Phase 2)
- [ ] T122 [US7] Verify tenant isolation filter works correctly for Countdown queries via dashboard relationship (already implemented in Phase 2)
- [ ] T123 [US7] Verify image upload paths are tenant-scoped (uploads/{tenant_id}/) in dinkydash/utils/images.py (already implemented in Phase 2)
- [ ] T124 [US7] Add 403 Forbidden response for cross-tenant access attempts in all admin routes in dinkydash/routes/admin.py

**Checkpoint**: Full tenant isolation verified. Multiple families can safely use the system.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T125 [P] Create quickstart.md deployment guide for SQLite (Raspberry Pi) in specs/001-multitenant-rewrite/quickstart.md
- [ ] T126 [P] Create quickstart.md deployment guide for PostgreSQL (cloud) in specs/001-multitenant-rewrite/quickstart.md
- [ ] T127 [P] Update CLAUDE.md with v2.0.0 architecture documentation in /Users/wrede/repos/dinkydash/CLAUDE.md
- [ ] T128 [P] Add model unit tests in tests/test_models/ for Family, User, Dashboard, Task, Countdown
- [ ] T129 [P] Add coverage reporting to pytest configuration in setup.cfg or pytest.ini
- [ ] T130 Code cleanup and remove unused imports across all modules
- [ ] T131 Performance optimization: Add eager loading (joinedload) to dashboard queries in dinkydash/routes/dashboard.py
- [ ] T132 Security review: Verify CSRF protection on all POST routes
- [ ] T133 Security review: Verify password hashing uses bcrypt via Werkzeug
- [ ] T134 Security review: Verify file upload validation in dinkydash/utils/images.py
- [ ] T135 Run quickstart.md validation on both SQLite and PostgreSQL
- [ ] T136 Create migration rollback test (downgrade and re-upgrade)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5 → P6 → P7)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Requires US2 for authentication
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Requires US2 for authentication
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Requires US2 for authentication, integrates with US3/US4
- **User Story 6 (P6)**: Can start after Foundational (Phase 2) - Requires US5 (layout_size field on Dashboard)
- **User Story 7 (P7)**: Can start after Foundational (Phase 2) - Tests isolation across all stories

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services/utilities
- Forms before routes
- Templates before routes (routes render templates)
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- Phase 1 Setup: T003, T004, T005, T006, T008, T009 can run in parallel
- Phase 2 Foundational:
  - Models: T010, T011, T012, T013, T014 can run in parallel
  - Utilities: T023, T024, T025 can run in parallel
  - Error templates: T026, T027, T028 can run in parallel
- Within each user story:
  - All tests marked [P] can run in parallel
  - All models/forms/templates marked [P] can run in parallel
- Once Foundational completes, all user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 3

```bash
# Launch all tests for User Story 3 together:
T061: "Integration test for task CRUD workflow"
T062: "Route test for task list endpoint"
T063: "Route test for task create endpoint"
T064: "Route test for task edit endpoint"
T065: "Route test for task delete endpoint"
T066: "Form validation test for TaskForm"
T067: "Test image upload validation"

# Launch all parallel implementation tasks for User Story 3:
T068: "Create TaskForm"
T069: "Create task list template"
T070: "Create task form template"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T009)
2. Complete Phase 2: Foundational (T010-T030) - CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T031-T042)
4. **STOP and VALIDATE**: Test User Story 1 independently with seeded data
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (Authentication added)
4. Add User Story 3 → Test independently → Deploy/Demo (Task management added)
5. Add User Story 4 → Test independently → Deploy/Demo (Countdown management added)
6. Add User Story 5 → Test independently → Deploy/Demo (Multiple dashboards added)
7. Add User Story 6 → Test independently → Deploy/Demo (Layout customization added)
8. Add User Story 7 → Test independently → Deploy/Demo (Full tenant isolation verified)
9. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Dashboard viewing)
   - Developer B: User Story 2 (Authentication)
   - Developer C: Start User Story 3 (depends on US2, may need to wait or coordinate)
3. Stories complete and integrate independently

---

## Summary Statistics

- **Total tasks**: 136
- **Setup tasks**: 9 (T001-T009)
- **Foundational tasks**: 21 (T010-T030)
- **User Story 1 (P1) tasks**: 12 (T031-T042) - 5 tests, 7 implementation
- **User Story 2 (P2) tasks**: 18 (T043-T060) - 8 tests, 10 implementation
- **User Story 3 (P3) tasks**: 16 (T061-T076) - 7 tests, 9 implementation
- **User Story 4 (P4) tasks**: 14 (T077-T090) - 7 tests, 7 implementation
- **User Story 5 (P5) tasks**: 16 (T091-T106) - 7 tests, 9 implementation
- **User Story 6 (P6) tasks**: 7 (T107-T113) - 3 tests, 4 implementation
- **User Story 7 (P7) tasks**: 11 (T114-T124) - 6 tests, 5 implementation
- **Polish tasks**: 12 (T125-T136)

**Parallel opportunities identified**: 47 tasks marked [P] can run concurrently

**MVP scope** (User Story 1 only): 42 tasks total (Setup + Foundational + US1)
- T001-T030: Setup and Foundational (30 tasks)
- T031-T042: User Story 1 implementation (12 tasks)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Tests included for tenant isolation (US7), auth flows (US2), and migrations (Phase 2) as requested in spec.md
- File paths follow Flask structure from plan.md: dinkydash/ package, templates/, static/, routes/, forms/, models/, utils/
