# ai-insights Specification

## Purpose
Turns Goku's recorded snapshots and biomarker history into a periodic
Claude-generated health assessment and draft Instagram captions, delivered
by email (see `email-delivery`) for a person to post by hand.

## Requirements

### Requirement: Health is assessed on a schedule
The system SHALL periodically send Claude the most recent snapshot and a
summary of recent feeding and measurement history, and SHALL store the
resulting assessment (a summary and whether anything was flagged as
concerning) with a timestamp and reference to the snapshot used.

#### Scenario: Scheduled health check runs
- **WHEN** the configured health-check interval elapses and a recent
  snapshot is available
- **THEN** the system sends it and a recent-history summary to Claude,
  stores the returned assessment, and it appears in the health-note history

#### Scenario: No snapshot available yet
- **WHEN** the health-check interval elapses but no snapshot has been
  captured yet
- **THEN** the system skips that cycle without error and tries again at the
  next interval

### Requirement: A concerning assessment is visible without digging
The system SHALL make a health assessment flagged as concerning visibly
distinct from routine ones in the authenticated dashboard view.

#### Scenario: Concerning assessment recorded
- **WHEN** a stored health assessment is flagged as concerning
- **THEN** it is visually distinguished from non-flagged assessments
  wherever health history is displayed

### Requirement: Caption drafts are generated on a schedule
The system SHALL periodically ask Claude to draft an Instagram-style
caption from a selected recent snapshot and recent history, on two
independently configurable cadences (a roundup cadence and a
highlight-moment cadence), and SHALL store each draft with a
`pending_review` status, the chosen snapshot, the generated caption text,
and which cadence produced it.

#### Scenario: Roundup draft is generated
- **WHEN** the roundup-cadence interval elapses
- **THEN** the system selects a representative recent snapshot, requests a
  caption summarizing the recent period from Claude, and stores it as a
  `pending_review` draft

#### Scenario: Highlight draft is generated
- **WHEN** the highlight-cadence interval elapses
- **THEN** the system selects a recent snapshot, requests a caption about
  one specific moment from Claude, and stores it as a `pending_review`
  draft

### Requirement: Drafts require human approval before becoming postable
The system SHALL allow an authenticated user to mark a draft `approved` or
`rejected` for their own tracking of what has been posted, and SHALL NOT
have any automated behavior that depends on a draft's status — drafts are
delivered (see `email-delivery`) regardless of review status, and no
publishing step consumes `approved` drafts.

#### Scenario: Draft approved
- **WHEN** an authenticated user approves a `pending_review` draft
- **THEN** its status changes to `approved`, recorded purely for the
  user's own reference

#### Scenario: Draft rejected
- **WHEN** an authenticated user rejects a `pending_review` draft
- **THEN** its status changes to `rejected`, recorded purely for the
  user's own reference

#### Scenario: Unreviewed draft is never published
- **WHEN** a draft's status is still `pending_review`
- **THEN** the draft was already emailed to the user when it was created
  (per `email-delivery`); its review status does not affect that

### Requirement: AI calls degrade without disrupting the rest of the app
The system SHALL continue operating normally if a Claude API call fails
(network error, API error, timeout, or rate limit), skipping that cycle
and retrying at the next scheduled interval, and SHALL NOT exceed a
configurable maximum number of Claude API calls per day.

#### Scenario: API call fails
- **WHEN** a scheduled health-check or caption-draft call to Claude fails
- **THEN** the system logs the failure, does not record a result for that
  cycle, and continues serving all other functionality normally

#### Scenario: Daily call cap reached
- **WHEN** the configured maximum number of Claude API calls for the
  current day has already been reached
- **THEN** the system skips further scheduled AI calls until the cap
  resets, without error

### Requirement: AI dashboard routes require authentication
The system SHALL require a valid, non-expired session (per the `auth`
capability) before serving health-note or draft-queue views, or accepting
an approve/reject action.

#### Scenario: Anonymous request to an AI insights route
- **WHEN** a client with no session requests the health-note view, the
  draft queue, or submits an approve/reject action
- **THEN** the system denies the request the same way it denies any other
  protected route
