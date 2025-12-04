# Feature Specification: Multi-Tenant Web Application Rewrite

**Feature Branch**: `001-multitenant-rewrite`
**Created**: 2025-12-04
**Status**: Draft
**Input**: User description: "Complete rewrite of DinkyDash as a multi-tenant web application. Transform from single-family config-file-based Raspberry Pi dashboard to web app supporting multiple families with authentication. Core features remain: recurring tasks (daily rotations like "whose turn for dishes") and countdowns to important dates (birthdays, holidays). New requirements: database backend (SQLite for Pi deployment, PostgreSQL for cloud), user authentication and registration, family/tenant isolation for data security, web-based admin UI to manage tasks and countdowns (replacing config.yaml editing). Traditional server-side rendering with Flask templates, minimal JavaScript. Must support both Raspberry Pi deployment (lightweight, SQLite) and optional cloud deployment (PostgreSQL, scalable)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Family Dashboard (Priority: P1)

A family member opens the dashboard to see today's recurring task assignments and upcoming event countdowns. The dashboard displays whose turn it is for chores (dishes, trash, etc.) based on daily rotation, and shows countdowns to upcoming birthdays and holidays. The dashboard automatically updates every 30 seconds to show the latest information without requiring manual page refresh.

**Why this priority**: This is the core value proposition - delivering at-a-glance family information. Without this, there is no product. This must work before any authentication or management features.

**Independent Test**: Can be fully tested by seeding a database with sample family data (recurring tasks, countdowns) and verifying the dashboard displays correct rotations based on current date and accurate countdown calculations. Delivers immediate value as a read-only family information display.

**Acceptance Scenarios**:

1. **Given** a family has 3 children (Alice, Bob, Charlie) with a "Dishes" task that rotates daily, **When** a family member views the dashboard on day N, **Then** the correct child's name/photo appears for today's rotation based on (day_of_year % 3)
2. **Given** there is a birthday countdown for "Mom's Birthday" on March 15, **When** viewing the dashboard on March 10, **Then** the countdown shows "5 days until Mom's Birthday"
3. **Given** multiple recurring tasks (dishes, trash, pet feeding) and multiple countdowns exist, **When** viewing the dashboard, **Then** all items display simultaneously in an organized, readable format
4. **Given** today's date changes to the next day, **When** refreshing the dashboard, **Then** recurring task assignments rotate to the next person in sequence and countdowns decrement by 1 day
5. **Given** an admin adds a new task while a family member is viewing the dashboard, **When** the auto-refresh occurs (within 30 seconds), **Then** the new task appears without requiring manual page reload
6. **Given** JavaScript is disabled in the browser, **When** viewing the dashboard, **Then** the dashboard still displays correctly and refreshes every 60 seconds via fallback mechanism

---

### User Story 2 - User Registration and Authentication (Priority: P2)

A family administrator creates an account for their family by registering with email and password. After registration, they can log in to access their family's dashboard and management features. Other family members can also be given login credentials to view the dashboard.

**Why this priority**: Multi-tenant support requires authentication to separate family data. This is the prerequisite for tenant isolation and admin features. Must be in place before families can manage their own data.

**Independent Test**: Can be tested independently by attempting to register a new family account, logging in, logging out, and verifying session management works correctly. Delivers value by enabling secure access to personalized dashboards.

**Acceptance Scenarios**:

1. **Given** a new family administrator visits the registration page, **When** they provide email, password, and family name, **Then** a new family account is created and they are logged in automatically
2. **Given** a registered family administrator, **When** they log in with correct credentials, **Then** they gain access to their family's dashboard
3. **Given** a logged-in user, **When** they log out, **Then** their session ends and they cannot access the dashboard without re-authenticating
4. **Given** a user enters incorrect login credentials, **When** attempting to log in, **Then** login fails with an appropriate error message
5. **Given** a user attempts to access the dashboard without being logged in, **When** navigating to the dashboard URL, **Then** they are redirected to the login page

---

### User Story 3 - Manage Recurring Tasks (Priority: P3)

A family administrator logs into the management interface and adds, edits, or removes recurring task assignments (like dishes, trash, pet care). They define the task name, who is in the rotation, and optionally add a display icon (emoji text or uploaded image). Changes appear immediately on the family dashboard.

**Why this priority**: This replaces the config.yaml editing workflow with a user-friendly web interface. Requires authentication (P2) but is independently testable as a CRUD interface for task management.

**Independent Test**: After authentication is working (P2), test by logging in as an admin, creating a new recurring task, verifying it appears on the dashboard, editing the task, and deleting it. Delivers value by enabling non-technical families to self-manage their dashboard content.

**Acceptance Scenarios**:

1. **Given** an authenticated family admin, **When** they create a new recurring task "Take out trash" with rotation [Alice, Bob], **Then** the task appears on the dashboard with today's assigned person
2. **Given** an existing recurring task, **When** the admin edits the rotation to add another family member, **Then** the updated rotation sequence applies immediately
3. **Given** an existing recurring task, **When** the admin deletes it, **Then** it no longer appears on the family dashboard
4. **Given** an admin is creating a task, **When** they enter an emoji "🍽" in the icon field, **Then** the emoji appears alongside the task on the dashboard
5. **Given** an admin is creating a task, **When** they upload an image file (JPG/PNG) via file picker, **Then** the uploaded image appears alongside the task on the dashboard after upload completes
6. **Given** an admin uploads an invalid file type (e.g., .exe), **When** attempting to save, **Then** validation error prevents upload with message about accepted formats
7. **Given** multiple recurring tasks exist, **When** the admin views the management interface, **Then** all tasks are listed with their icons and edit/delete options

---

### User Story 4 - Manage Countdown Events (Priority: P4)

A family administrator logs into the management interface and adds, edits, or removes countdown events (birthdays, holidays, special occasions). They define the event name, date, and optionally add a display icon (emoji text or uploaded image). The dashboard automatically calculates and displays days remaining until each event.

**Why this priority**: Completes the management interface by enabling families to maintain their countdown events without editing configuration files. Requires authentication (P2) and builds on the task management patterns from P3.

**Independent Test**: After authentication is working, test by logging in as an admin, creating a new countdown "Christmas - 12/25", verifying the countdown appears on the dashboard with correct days remaining, editing the event, and deleting it.

**Acceptance Scenarios**:

1. **Given** an authenticated family admin, **When** they create a new countdown "Mom's Birthday - 03/15", **Then** the countdown appears on the dashboard showing correct days remaining from today
2. **Given** an existing countdown event, **When** the admin edits the date or name, **Then** the dashboard reflects the updated information immediately
3. **Given** an existing countdown, **When** the admin deletes it, **Then** it no longer appears on the family dashboard
4. **Given** an admin is creating a countdown, **When** they enter an emoji "🎂" in the icon field, **Then** the emoji appears alongside the countdown on the dashboard
5. **Given** an admin is creating a countdown, **When** they upload a person's photo via file picker, **Then** the uploaded image appears alongside the countdown on the dashboard after upload completes
6. **Given** multiple countdowns exist, **When** the admin views the management interface, **Then** all countdowns are listed sorted by proximity with their icons and edit/delete options
7. **Given** a countdown date passes, **When** viewing the dashboard the next day, **Then** the countdown automatically calculates for next year's occurrence

---

### User Story 5 - Manage Multiple Dashboards (Priority: P5)

A family administrator can create multiple named dashboards to organize tasks and countdowns by room or purpose (e.g., "Kitchen", "Kids Room", "Living Room"). When registering, families automatically get their first dashboard named "Family Dashboard". Admins can create additional dashboards, give them meaningful names, and assign specific tasks/countdowns to each dashboard. Family members can navigate between dashboards to see location-specific information. Admins can also delete dashboards they no longer need.

**Why this priority**: Room-based organization allows families to mount different displays in different locations showing relevant information. Dashboard names also provide valuable usage data about how families organize their spaces. This builds on task/countdown management (P3/P4) but is needed before layout customization (which applies per-dashboard).

**Independent Test**: After authentication and task/countdown management work, test by logging in as admin, creating a new dashboard "Kitchen Dashboard", moving some tasks to it, viewing the Kitchen dashboard separately from the default dashboard, and deleting a dashboard. Verify default dashboard is created automatically on registration.

**Acceptance Scenarios**:

1. **Given** a family registers a new account, **When** registration completes, **Then** a dashboard named "Family Dashboard" is automatically created for them
2. **Given** an authenticated family admin, **When** they create a new dashboard with name "Kitchen Dashboard", **Then** the new dashboard appears in the dashboard list and can be viewed separately
3. **Given** multiple dashboards exist (Family Dashboard, Kitchen Dashboard), **When** an admin creates a task, **Then** they can choose which dashboard to assign it to
4. **Given** a task is assigned to "Kitchen Dashboard", **When** viewing the "Kitchen Dashboard", **Then** the task appears there but not on other dashboards
5. **Given** multiple dashboards exist, **When** a family member views the dashboard list, **Then** they can navigate between dashboards and each shows only its assigned tasks/countdowns
6. **Given** an admin wants to delete "Kitchen Dashboard", **When** they delete it, **Then** the dashboard and its assignments are removed (but tasks/countdowns remain and can be reassigned)
7. **Given** a family has only one dashboard remaining, **When** attempting to delete it, **Then** deletion is prevented with a message requiring at least one dashboard to exist

---

### User Story 6 - Customize Dashboard Layout (Priority: P6)

A family administrator adjusts the size and layout of dashboard elements (recurring tasks and countdown cards) to optimize the display for their screen. They can choose from preset sizes (small, medium, large) or adjust spacing to make elements fill available space. Layout preferences are saved per dashboard (so Kitchen Dashboard can have large layout while Kids Room has small layout).

**Why this priority**: Different deployment scenarios have different screen sizes (small tablet, large wall display, Pi touchscreen). Customizable layouts ensure the dashboard looks good and is readable on any screen without requiring CSS knowledge. This enhances the core viewing experience (P1) but requires authentication (P2) and dashboard management (P5) to be in place.

**Independent Test**: After authentication and dashboard viewing work, test by logging in as admin, changing layout size from default to "large" for a specific dashboard, verifying dashboard elements resize, logging out and back in to confirm preference persists. Can also test on different screen sizes/devices.

**Acceptance Scenarios**:

1. **Given** an authenticated family admin viewing a dashboard, **When** they access layout settings and select "Large" size for that dashboard, **Then** all dashboard cards (tasks and countdowns) increase in size to fill more screen space
2. **Given** layout size is set to "Large" for "Kitchen Dashboard", **When** the admin logs out and back in, **Then** the Kitchen Dashboard maintains the "Large" size setting
3. **Given** layout preferences are saved per dashboard, **When** "Kitchen Dashboard" has "Large" and "Kids Room" has "Small", **Then** each dashboard displays with its own layout size
4. **Given** an admin selects "Small" size for a dashboard, **When** viewing that dashboard with many items, **Then** more items fit on screen without scrolling
5. **Given** different families with different layout preferences, **When** each family views their dashboards, **Then** each sees their own configured layout sizes

---

### User Story 7 - Multi-Family Tenant Isolation (Priority: P7)

Multiple families use the same DinkyDash deployment. Each family sees only their own recurring tasks and countdowns. Family A cannot access or view Family B's dashboard or management interface. All data is securely isolated by tenant identifier.

**Why this priority**: Enables true multi-tenancy with secure data isolation. This is the final piece that transforms DinkyDash from a single-family tool to a multi-family platform. Requires authentication (P2) and builds on management features (P3, P4).

**Independent Test**: Create two family accounts, add distinct data to each (different tasks, countdowns), log in as Family A and verify only Family A's data appears, then log in as Family B and verify only Family B's data appears. Attempt to access another family's data by manipulating URLs/requests and confirm access is denied.

**Acceptance Scenarios**:

1. **Given** Family A and Family B both have accounts, **When** Family A logs in, **Then** they see only their own recurring tasks and countdowns
2. **Given** Family A is logged in, **When** they attempt to access Family B's dashboard via URL manipulation, **Then** access is denied
3. **Given** multiple families share the same deployment, **When** Family B creates a new task, **Then** it does not appear on Family A's dashboard
4. **Given** Family A deletes a task, **When** checking Family B's dashboard, **Then** Family B's tasks remain unaffected
5. **Given** a new family registers, **When** they log in for the first time, **Then** they see an empty dashboard ready for them to add their own tasks and countdowns

---

### Edge Cases

- What happens when a recurring task rotation has only 1 person? (Dashboard shows the same person every day)
- What happens when a countdown date is in the past and hasn't rolled over to next year? (System automatically calculates next occurrence)
- What happens when an admin tries to create a task with an empty rotation list? (Validation error prevents creation)
- What happens when two family members try to edit the same task simultaneously? (Last save wins, no conflict detection in MVP)
- What happens when a user forgets their password? (Password reset functionality via email - standard flow)
- What happens when SQLite database grows very large on Raspberry Pi? (System continues to work; performance may degrade over time - monitoring recommended)
- What happens when a family has no tasks or countdowns configured? (Dashboard displays empty state with prompt to add items)
- How does the system handle invalid dates (e.g., February 30)? (Validation prevents invalid date entry)
- What happens when admin deletes their own account? (Account deletion disabled for sole admin; must transfer ownership first)
- What happens when a dashboard hasn't had layout preferences set? (System uses default medium size)
- What happens when layout is set to "large" but screen is very small? (Elements may require scrolling; responsive design handles gracefully)
- What happens when polling fails due to network issues? (Dashboard continues showing last known state; polling retries automatically when connection restored)
- What happens when multiple browser tabs show the same dashboard? (Each tab polls independently; all stay synchronized within 30 seconds)
- What happens when an admin deletes a dashboard that has tasks/countdowns assigned to it? (Tasks/countdowns become unassigned and admin must reassign them to another dashboard or they won't display)
- What happens when a family only has one dashboard and tries to delete it? (Deletion prevented with error message requiring at least one dashboard)
- What happens when an admin creates a dashboard with a duplicate name? (Allowed - dashboard names don't need to be unique within a family)
- What happens when navigating between dashboards while admin is making changes? (Each dashboard polls independently; changes appear within 30 seconds on the respective dashboard)
- What happens when an admin uploads an image larger than 5MB? (Validation error prevents upload with message about size limit)
- What happens when an admin uploads a PDF or other non-image file? (Validation error prevents upload with message about accepted formats: JPG, PNG, GIF)
- What happens when a task or countdown has both an emoji and an uploaded image? (Only one icon type allowed - UI presents choice between emoji or image, not both)
- What happens when an admin deletes a task that has an uploaded image? (Image file is deleted from storage to prevent orphaned files)
- What happens when the same family photo is used for multiple countdowns? (Image is uploaded separately for each countdown - file duplication acceptable for MVP simplicity)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store all family data (recurring tasks, countdowns, user accounts) in a relational database
- **FR-002**: System MUST support both SQLite database (for Raspberry Pi deployment) and PostgreSQL database (for cloud deployment) using the same codebase
- **FR-003**: Users MUST be able to register a new family account with email, password, and family name
- **FR-004**: System MUST validate email format and password strength (minimum 8 characters) during registration
- **FR-005**: Users MUST be able to log in with email and password credentials
- **FR-006**: System MUST maintain secure user sessions with appropriate timeout and CSRF protection
- **FR-007**: System MUST log out users and invalidate sessions when they click logout
- **FR-008**: Dashboard MUST display all recurring tasks with today's assigned person based on daily rotation algorithm (day_of_year % rotation_length)
- **FR-009**: Dashboard MUST display all countdown events with calculated days remaining until each event
- **FR-010**: Dashboard MUST automatically refresh content every 30 seconds via polling to show current task assignments and updated countdowns
- **FR-010a**: Dashboard MUST provide fallback auto-refresh mechanism (60 second full page refresh) when JavaScript is disabled
- **FR-011**: System MUST automatically create a default dashboard named "Family Dashboard" when a new family registers
- **FR-012**: Authenticated family administrators MUST be able to create new dashboards with custom names
- **FR-013**: Authenticated family administrators MUST be able to edit dashboard names
- **FR-014**: Authenticated family administrators MUST be able to delete dashboards (except when only one remains)
- **FR-015**: System MUST prevent deletion of the last remaining dashboard for a family
- **FR-016**: System MUST provide navigation UI to switch between multiple dashboards
- **FR-017**: Authenticated family administrators MUST be able to create new recurring tasks with task name, rotation list (people), optional display icon (emoji or uploaded image), and dashboard assignment
- **FR-018**: Authenticated family administrators MUST be able to edit existing recurring tasks (name, rotation, icon, dashboard assignment)
- **FR-019**: Authenticated family administrators MUST be able to delete recurring tasks
- **FR-020**: Authenticated family administrators MUST be able to create new countdown events with event name, date (MM/DD format), optional display icon (emoji or uploaded image), and dashboard assignment
- **FR-021**: Authenticated family administrators MUST be able to edit existing countdown events (name, date, icon, dashboard assignment)
- **FR-022**: Authenticated family administrators MUST be able to delete countdown events
- **FR-022a**: System MUST provide separate input mechanisms for emoji (text field) and image upload (file picker) when adding icons to tasks or countdowns
- **FR-022b**: System MUST display preview of uploaded image or entered emoji before saving task or countdown
- **FR-023**: System MUST enforce tenant isolation - families can only access their own data
- **FR-024**: System MUST prevent cross-tenant data leakage through database queries (all queries filtered by tenant_id)
- **FR-025**: System MUST prevent unauthorized access to dashboard - redirect unauthenticated users to login page
- **FR-026**: System MUST use server-side rendering (Flask templates) for all primary UI pages with HTML responses
- **FR-027**: System MUST function with JavaScript disabled for core operations (viewing dashboard, managing tasks) using progressive enhancement approach
- **FR-028**: System MAY use lightweight JavaScript library (HTMX) for enhanced user experience (polling, partial updates) while maintaining full functionality without JavaScript
- **FR-029**: System MUST hash all passwords using bcrypt or argon2 (never store plain text)
- **FR-030**: System MUST validate all user input to prevent SQL injection attacks
- **FR-031**: System MUST support direct image uploads via file picker for recurring tasks and countdowns with validation (file type: JPG/PNG/GIF only, size limit: 5MB maximum)
- **FR-032**: Uploaded images MUST be stored with tenant-isolated file paths (Family A cannot access Family B's images via URL manipulation or direct access)
- **FR-032a**: System MUST validate image file type and size on upload and reject invalid files with clear error messages
- **FR-033**: System MUST use database migrations for schema version control
- **FR-034**: Countdown dates MUST automatically roll over to next year after the event passes
- **FR-035**: System MUST display appropriate error messages for failed operations (login errors, validation errors, etc.)
- **FR-036**: Authenticated family administrators MUST be able to configure dashboard layout size with preset options (small, medium, large)
- **FR-037**: System MUST persist layout preferences per dashboard in the database
- **FR-038**: Dashboard MUST apply saved layout preferences when rendering that specific dashboard
- **FR-039**: Layout preferences MUST be tenant-isolated (Family A's layout settings do not affect Family B)
- **FR-040**: Dashboards MUST be tenant-isolated (Family A cannot access Family B's dashboards)

### Key Entities

- **Family/Tenant**: Represents a family unit using the system. Attributes: unique tenant_id, family name, registration date. Relationships: has many users, has many dashboards
- **User**: Represents an individual with login credentials. Attributes: user_id, email, hashed password, associated tenant_id. Relationships: belongs to one family/tenant
- **Dashboard**: Represents a named view/organization of tasks and countdowns. Attributes: dashboard_id, tenant_id, dashboard name, layout preferences (size setting: small/medium/large), creation date, is_default (boolean for first dashboard). Relationships: belongs to one family/tenant, has many recurring tasks, has many countdowns
- **Recurring Task**: Represents a daily rotating chore/responsibility. Attributes: task_id, dashboard_id, task name, rotation order (ordered list of people), optional icon (either emoji text or image file path), creation date. Relationships: belongs to one dashboard
- **Countdown Event**: Represents an important date to track. Attributes: countdown_id, dashboard_id, event name, event date (MM/DD), optional icon (either emoji text or image file path), creation date. Relationships: belongs to one dashboard. Behavior: calculates days remaining from current date, auto-advances to next year after date passes

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Families can view their dashboard and see correct daily task assignments in under 3 seconds from page load
- **SC-002**: Dashboard countdown calculations are accurate to within 1 day of actual date difference
- **SC-003**: System supports at least 50 concurrent family accounts with isolated data and no performance degradation
- **SC-004**: New families can complete registration and add their first task in under 5 minutes
- **SC-005**: 95% of families successfully create their first recurring task without errors or confusion
- **SC-006**: Zero cross-tenant data leaks during security testing (families cannot access other families' data)
- **SC-007**: System operates continuously on Raspberry Pi for 30 days without crashes or restarts
- **SC-008**: Database migrations complete successfully on both SQLite and PostgreSQL without data loss
- **SC-009**: Dashboard remains functional with JavaScript disabled for core viewing operations
- **SC-010**: Password authentication prevents unauthorized access in 100% of test cases (no false positives)
- **SC-011**: Families report increased satisfaction with web UI compared to config file editing (measured via survey or feedback)
- **SC-012**: Layout preferences persist correctly across sessions (login/logout) in 100% of test cases
- **SC-013**: Dashboard elements scale appropriately for small (phone), medium (tablet), and large (wall display) preset sizes without breaking layout
- **SC-014**: Admin changes (new tasks, countdowns, layout) appear on viewing dashboards within 30 seconds when JavaScript enabled, 60 seconds when disabled
- **SC-015**: Dashboard polling maintains performance with multiple concurrent families (50+) without server degradation
- **SC-016**: Default dashboard is automatically created within 1 second of family registration completing
- **SC-017**: Families successfully create additional dashboards with custom names in under 30 seconds
- **SC-018**: Dashboard names collected from users provide actionable insights into room-based usage patterns (measured via data analysis)
- **SC-019**: Image uploads complete and display preview within 5 seconds for files under 5MB on standard broadband connection
- **SC-020**: Image validation correctly rejects 100% of invalid file types and oversized files before storage

## Assumptions

- Families will have between 2-10 members in typical rotation scenarios
- Average family will have 3-10 recurring tasks
- Average family will track 5-15 countdown events annually
- Raspberry Pi deployments will have sufficient storage for SQLite database growth (multi-year usage)
- Email-based password reset follows standard time-limited token pattern (30-minute expiration)
- Session timeout will be set to industry standard (30 minutes of inactivity)
- Image uploads use direct upload pattern (upload per item, not shared library) for MVP simplicity
- Image uploads limited to 5MB per file, common formats (JPG, PNG, GIF)
- Image file duplication (same photo uploaded multiple times) is acceptable trade-off for simpler implementation
- Emoji icons are stored as text (Unicode characters), not as image files
- Each task or countdown can have either emoji OR image, not both (UI enforces single icon type choice)
- Uploaded images are stored with tenant-scoped file paths (e.g., uploads/{tenant_id}/{item_id}_icon.jpg) for security
- Orphaned image files are deleted when associated task/countdown is deleted to prevent storage bloat
- Mobile access will be via responsive web design (no native mobile apps in initial version)
- Admin role is assigned to the account creator; future versions may support multiple admins or role management
- Dashboard uses progressive enhancement: HTMX for 30-second polling when JavaScript enabled, meta refresh (60 seconds) as fallback
- HTMX library (~14kb) is acceptable dependency for progressive enhancement while maintaining server-side rendering architecture
- Polling interval of 30 seconds balances freshness with server load for typical family usage patterns
- Default layout size is "medium" for new dashboards
- Layout customization uses preset sizes (small/medium/large) rather than pixel-perfect controls to maintain simplicity
- Admin changes propagate to all viewing devices within 30-60 seconds depending on JavaScript availability
- Typical families will create 2-5 dashboards (e.g., Kitchen, Kids Room, Living Room, Family)
- First dashboard is automatically named "Family Dashboard" to provide a sensible default
- Dashboard names will be analyzed for common patterns (kitchen, bedroom, kids, office) to inform future feature development
- When deleting a dashboard with assigned items, tasks/countdowns become orphaned and must be manually reassigned
- Layout preferences are stored per dashboard, not per family, allowing different screens to have different sizes
