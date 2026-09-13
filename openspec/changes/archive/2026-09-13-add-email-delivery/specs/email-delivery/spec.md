## Purpose

Delivers Goku's draft captions and video recordings straight to the
household's inbox as they're produced, so they can be posted to Instagram
by hand — without any Instagram API integration or account linking.

## ADDED Requirements

### Requirement: A new draft caption triggers an email
The system SHALL send an email to the configured recipient whenever a new
caption draft (roundup or highlight) is created, containing the draft's
photo as an attachment and the caption text in a form ready to copy into a
post.

#### Scenario: Draft created with email configured
- **WHEN** the insights scheduler creates a new caption draft and email
  delivery is configured
- **THEN** an email is sent to the configured recipient with the draft's
  photo attached and its caption text in the body

#### Scenario: Draft created with email not configured
- **WHEN** the insights scheduler creates a new caption draft but email
  delivery is not configured (no recipient or SMTP credentials set)
- **THEN** the draft is still created and visible on the insights page; no
  email is attempted and no error is raised

### Requirement: A manual recording triggers an email
The system SHALL send an email to the configured recipient whenever a
manual video recording completes successfully, with the recording
attached.

#### Scenario: Recording completes with email configured
- **WHEN** a manual recording is saved and email delivery is configured
- **THEN** an email is sent to the configured recipient with the recording
  attached

#### Scenario: Recording completes with email not configured
- **WHEN** a manual recording is saved but email delivery is not
  configured
- **THEN** the recording is still saved and available in the gallery; no
  email is attempted and no error is raised

### Requirement: Automatic and manual snapshots are not individually emailed
The system SHALL NOT send an email for a routine scheduled snapshot or a
manually triggered still-photo snapshot — only for caption drafts and
recordings, per the requirements above.

#### Scenario: Scheduled snapshot occurs
- **WHEN** the phase-3 snapshot scheduler captures a routine snapshot
- **THEN** no email is sent for that snapshot on its own

### Requirement: Email failures never block the underlying action
The system SHALL NOT fail or delay creating a draft or saving a recording
because sending the associated email failed or timed out.

#### Scenario: SMTP send fails
- **WHEN** sending the notification email fails (bad credentials, network
  error, SMTP server error)
- **THEN** the draft or recording that triggered it is still created and
  saved successfully, and the failure is logged rather than raised to the
  caller
