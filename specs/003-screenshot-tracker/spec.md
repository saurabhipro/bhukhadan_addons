# Feature Specification: Screenshot Tracker

**Feature Branch**: `003-screenshot-tracker`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "I WANT TO IMPMENT THE SCREENSHOT tRACKER IN ODOO wEB ui AND MOBIEL APP SO PLS MAKE PLAN..THE WEB ui VIVLE TOAD DMIN CAN SHOW WHO TRACJED WHAT ATE TIME AND ip SO I CAN TRACK"

## Clarifications

### Session 2026-07-22

- Q: Offline screenshot reporting behavior → A: Queue locally and retry when online
- Q: Which screens get screenshot blocking → A: Block screenshots on all app screens
- Q: Should the user be told when a screenshot is logged → A: Show a brief notice that the screenshot was recorded
- Q: Who can open the Screenshot Audit Log in Odoo → A: Administrator + System only
- Q: Can admins delete screenshot audit rows → A: Admins may delete rows
- Q: Odoo web browser screenshots cannot be detected — what instead? → A: Visible identity watermark on Odoo web UI (trace leaked images; do not pretend to log Print Screen)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin reviews screenshot audit trail (Priority: P1)

As a BhuKhadan administrator, I open an audit screen in the Odoo backend and see a list of screenshot events showing **who** took (or attempted) a screenshot, **what screen/page** they were on, **when** it happened, and from which **IP address**, so I can investigate data-leak risk.

**Why this priority**: This is the core business need — visibility and accountability for administrators.

**Independent Test**: With sample audit records present, an admin-only user can open the screenshot log, filter by user/date/IP, open a row, and see who / what / when / IP without using the mobile app.

**Acceptance Scenarios**:

1. **Given** an administrator is signed into Odoo, **When** they open the Screenshot Audit Log menu, **Then** they see a list of events with user, time, IP, platform, and screen/page.
2. **Given** audit events exist for multiple users, **When** the admin filters by user or IP or today’s date, **Then** only matching events remain visible.
3. **Given** a non-administrator user (including District Administrator / field roles) is signed into Odoo, **When** they look for Screenshot Audit Log, **Then** the menu/action is not available to them.
4. **Given** an admin opens one event, **When** they view the detail, **Then** they see user identity (name/login/mobile/role when available), IP, screen/page, related survey if any, device info, and timestamp.
5. **Given** an Administrator or System user views the audit list, **When** they delete a row, **Then** the event is removed and no longer appears in the list.

---

### User Story 2 - Mobile app reports screenshot events (Priority: P1)

As a signed-in mobile field user, when the device detects a screenshot while I am using the BhuKhadan app, the app silently reports the event so administrators can later see who, which screen, when, and the connection IP.

**Why this priority**: Without mobile reporting, the admin view stays empty for real field activity.

**Independent Test**: While logged into the mobile app on a screen such as Survey Details, trigger a detectable screenshot (or a test report action in debug); an admin then sees a new audit row with that user, screen, time, and IP.

**Acceptance Scenarios**:

1. **Given** a field user is logged into the mobile app, **When** a screenshot is detected on a supported platform, **Then** an audit event is recorded with that user’s identity and the current screen name.
2. **Given** the user is viewing a specific survey, **When** a screenshot is detected, **Then** the audit event links to that survey when known.
3. **Given** the report is sent over the network, **When** the server stores the event, **Then** the client IP observed by the server is stored on the audit record.
4. **Given** the user’s session is invalid or expired, **When** a screenshot report is attempted, **Then** no trusted audit row is created for an anonymous/unknown actor, and the app does not crash.
5. **Given** a screenshot is detected while the user is signed in, **When** the app records/queues the event, **Then** the user sees a brief on-screen notice that the screenshot was recorded (no acknowledgment required to continue).

---

### User Story 3 - Reduce silent leakage on hard-to-detect platforms (Priority: P2)

As an administrator, on platforms where screenshot detection is unreliable, the entire mobile app window still reduces leakage risk (blocked or blank screenshots wherever the OS allows) while any detectable events continue to be logged.

**Why this priority**: Improves protection where detection alone is incomplete; secondary to having a working admin trail.

**Independent Test**: On a device where screenshots can be blocked for an app window, open any app screen (including home/login/survey) and attempt a screenshot; content is not usefully captured, and any detectable events still appear in the admin log.

**Acceptance Scenarios**:

1. **Given** a user is on any screen of the mobile app on a platform that supports screenshot blocking, **When** they attempt a system screenshot, **Then** the captured image does not clearly expose app content (blocked/blank/obscured per platform capability).
2. **Given** detection is available on another platform (e.g. iOS), **When** a screenshot occurs on any app screen, **Then** the event is still logged for admin review.

---

### User Story 4 - Odoo web identity watermark (Priority: P2)

As an administrator, when someone uses the Odoo web UI and later shares a screenshot or photo of the screen, the captured image should show a visible watermark with that signed-in user’s identity so we can still attribute the leak even though the browser cannot report “screenshot taken”.

**Why this priority**: Complements mobile detection where web Print Screen cannot be logged; secondary to mobile audit trail.

**Independent Test**: Sign into Odoo backend as a normal user; take a browser/OS screenshot of any backend screen; the image clearly shows a non-blocking watermark with that user’s name/login (and uid or similar).

**Acceptance Scenarios**:

1. **Given** a signed-in user is on the Odoo backend, **When** they view any backend screen, **Then** a subtle repeating watermark shows their display name and login (and user id when available).
2. **Given** the watermark is present, **When** the user clicks menus/forms/buttons, **Then** the watermark does not block clicks or obscure critical form fields beyond light opacity.
3. **Given** User A and User B are signed in on different sessions, **When** each takes a screenshot, **Then** each capture shows that session’s own identity text (not a shared generic label).
4. **Given** no web screenshot detection exists, **When** Print Screen occurs, **Then** no new `bhu.screenshot.log` row is required from the browser; attribution relies on the watermark in the image.

---

### Edge Cases

- Screenshot detected while offline: the app MUST queue the event locally and retry upload when connectivity returns (must not crash; must not permanently drop without retry).
- User photographs the screen with another camera: cannot be detected; out of scope for automated logging; watermark still helps if the photo includes the on-screen overlay.
- Browser / Odoo web Print Screen: not reliably detectable; do **not** create fake screenshot-log rows from the browser; apply a **visible identity watermark** on Odoo backend for post-leak attribution.
- Shared office IP / NAT: multiple users may share one public IP; identity fields (user/login/mobile) remain the primary “who”.
- Missing screen name or survey: event is still stored with available fields; screen may show as unknown/blank.
- Very high volume of events: list remains searchable/filterable; oldest events may be retained per Assumptions.
- Watermark crop / heavy editing of a screenshot: may remove attribution; accepted limitation of visual watermarks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an administrator-only Odoo backend view listing screenshot audit events.
- **FR-002**: Each audit event MUST show at least: who (user), when (timestamp), IP address, and what (screen/page label).
- **FR-003**: Each audit event SHOULD also capture platform, device info, user login/mobile/role when available, and related survey when known.
- **FR-004**: Only BhuKhadan Administrator and System administrators MUST be able to access the screenshot audit list or detail screens; District Administrators and other roles MUST NOT.
- **FR-005**: Administrators MUST be able to search/filter audit events by user, IP, screen, and date.
- **FR-006**: The mobile app MUST report screenshot events for signed-in users when the platform can detect them.
- **FR-007**: Screenshot reports MUST be accepted only from authenticated mobile sessions.
- **FR-008**: The server MUST record the client IP associated with each accepted screenshot report.
- **FR-009**: The mobile app MUST identify the current screen/page in the report when known.
- **FR-010**: The mobile app MUST apply best-effort screenshot blocking/obscuring on **all** app screens where the OS allows (not limited to survey screens).
- **FR-011**: Failed screenshot reports MUST NOT crash the mobile app or block the user from continuing their work.
- **FR-012**: Odoo web UI MUST NOT claim to detect browser Print Screen / OS screenshots; the admin audit list remains for **mobile-reported** events. Web leakage mitigation MUST use a visible identity watermark instead (FR-016).
- **FR-013**: When a screenshot is detected while offline, the mobile app MUST queue the event locally and retry delivery when connectivity is restored until accepted or a bounded retry policy is exhausted (without data loss on transient failures).
- **FR-014**: When a screenshot is detected for a signed-in user, the mobile app MUST show a brief notice that the screenshot was recorded; the user MUST NOT be required to acknowledge it before continuing work.
- **FR-015**: BhuKhadan Administrator and System users MUST be able to delete screenshot audit rows; other roles MUST NOT.
- **FR-016**: Signed-in Odoo backend sessions MUST show a non-interactive identity watermark (at least display name + login; uid when available) over the main backend UI so screenshots/photos of the screen carry attribution.

### Key Entities

- **Screenshot Audit Event**: A single recorded occurrence of a screenshot (or detectable screenshot attempt) while using the mobile app. Attributes include actor (user), time, IP, screen/page, optional survey reference, platform/device context.
- **Administrator**: Backend role allowed to view and manage audit events.
- **Field User**: Authenticated mobile user whose screenshot activity may generate audit events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can open the screenshot audit view and identify who / what screen / when / IP for a known test event in under 1 minute.
- **SC-002**: 100% of successfully reported, authenticated mobile screenshot events appear in the admin list with user and IP populated.
- **SC-003**: District Administrators and field roles have 0 successful access paths to the screenshot audit screens in role testing; only BhuKhadan Administrator and System succeed.
- **SC-004**: On at least one supported mobile platform with detection, a controlled screenshot during survey viewing produces a visible admin audit row within 30 seconds of connectivity.
- **SC-006**: After a detectable screenshot while signed in, the mobile user sees a brief recorded notice without being forced to dismiss a blocking dialog before continuing.
- **SC-007**: A controlled OS/browser screenshot of the Odoo backend shows the signed-in user’s watermark text readable enough for attribution in under 10 seconds of visual inspection.

## Assumptions

- “Administrator” for this feature means **BhuKhadan Administrator** and **System** only (not District Administrator).
- Mobile app means the existing BhuKhadan Flutter field app used with OTP login.
- iOS can detect screenshots more reliably than Android; Android relies on best-effort detection and/or screenshot blocking.
- Screenshot blocking applies to the **entire mobile app** (all screens), not survey-only.
- Photographing the device with another camera is out of scope for automated logging; web watermark still helps when the photo includes the overlay.
- Detecting screenshots inside the Odoo web browser remains out of scope; web mitigation is a **visible identity watermark**, not audit-log rows from Print Screen.
- Existing mobile authentication is reused; no new login method is required.
- Audit retention has no automatic purge in v1; Administrator/System may manually delete rows.
- Offline screenshot events are queued on device and retried when online (not dropped on first failure).
- Users receive a brief notice when a screenshot is recorded; no blocking acknowledgment dialog.
- IP may reflect NAT/proxy; user identity fields are authoritative for “who”.
- Partial backend foundations for audit logging may already exist and MUST be completed to match this full Odoo + mobile scope rather than inventing a parallel product.
- Watermark uses session identity already available to the web client; no new ACL model is required for watermark-only.
