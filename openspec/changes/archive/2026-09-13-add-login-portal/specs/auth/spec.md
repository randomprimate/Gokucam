## Purpose

Restricts GokuCam's live view, gallery, media, and control endpoints to
authenticated household users via a session-based login, while keeping the
health-check endpoint open for monitoring.

## ADDED Requirements

### Requirement: Protected routes require an authenticated session
The system SHALL require a valid, non-expired session before serving the
live view, the gallery, media download/delete, or any pan/tilt/snapshot/
record API.

#### Scenario: Anonymous request to a protected page
- **WHEN** a client with no session requests `/`, `/gallery`, or any
  `/api/*` control endpoint (other than `/health`)
- **THEN** the system denies access and redirects browser requests to the
  login page, or returns a 401 JSON error for XHR/API requests, without
  performing the requested action

#### Scenario: Authenticated request to a protected page
- **WHEN** a client with a valid session requests a protected page or API
- **THEN** the system serves the request normally

### Requirement: Health check remains unauthenticated
The system SHALL serve `/health` without requiring a session, so external
monitors and the systemd watchdog can check liveness without credentials.

#### Scenario: Health check without a session
- **WHEN** a client with no session requests `/health`
- **THEN** the system returns the health payload as normal

### Requirement: Login with correct credentials starts a session
The system SHALL allow a client to authenticate by submitting a username
and password, and SHALL start a session on success.

#### Scenario: Successful login
- **WHEN** a client submits the correct configured username and password to
  the login endpoint
- **THEN** the system establishes a session for that client and subsequent
  requests are treated as authenticated

#### Scenario: Failed login
- **WHEN** a client submits an incorrect username or password
- **THEN** the system does not establish a session, and returns an error
  that does not reveal whether the username or the password was wrong

### Requirement: Logout ends the session
The system SHALL allow an authenticated client to end its own session.

#### Scenario: Logout
- **WHEN** an authenticated client requests logout
- **THEN** the system invalidates that session, and subsequent requests
  from that client are treated as unauthenticated

### Requirement: Sessions expire after inactivity
The system SHALL expire a session after a configurable period of
inactivity, so a browser left open indefinitely does not grant indefinite
access.

#### Scenario: Session expires
- **WHEN** a session has had no activity for longer than the configured
  session lifetime
- **THEN** the next request from that client is treated as unauthenticated

### Requirement: Repeated failed logins are throttled
The system SHALL limit the rate of login attempts from a single source, to
resist password-guessing.

#### Scenario: Too many failed attempts
- **WHEN** a client has exceeded the configured number of failed login
  attempts within the configured window
- **THEN** the system rejects further login attempts from that client until
  the window passes, even if the correct credentials are supplied
