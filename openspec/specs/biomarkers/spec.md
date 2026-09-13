# biomarkers Specification

## Purpose
Turns GokuCam from a live-control tool into a health record: automatic
periodic snapshots, a feeding log, and calibrated photo measurements, all
indexed in a durable store so growth and habits can be tracked over time.

## Requirements

### Requirement: Snapshots are captured automatically on a schedule
The system SHALL take a snapshot at a configurable interval without manual
action, in addition to the existing manual snapshot button, and SHALL
record each captured snapshot (scheduled or manual) in the datastore with
its file path, timestamp, and capture reason (scheduled vs. manual).

#### Scenario: Scheduled capture occurs
- **WHEN** the configured snapshot interval elapses since the last capture
- **THEN** the system takes a new snapshot, saves it under the existing
  capture directory, and records a corresponding entry in the datastore

#### Scenario: Manual snapshot is also recorded
- **WHEN** a user triggers a snapshot via the existing manual snapshot
  control
- **THEN** the resulting file is recorded in the datastore the same way a
  scheduled one is, marked as manually triggered

#### Scenario: Camera unavailable when a scheduled capture is due
- **WHEN** the scheduled interval elapses but the camera is degraded or
  unavailable
- **THEN** the system skips that capture without crashing or blocking other
  functionality, and tries again at the next interval

### Requirement: Feeding events are logged
The system SHALL let an authenticated user record a feeding event with a
food description, portion, optional note, and timestamp, and SHALL persist
it in the datastore.

#### Scenario: Log a feeding event
- **WHEN** an authenticated user submits a feeding-log entry with at least a
  food description
- **THEN** the system stores the entry with a server-recorded timestamp
  (defaulting to now, unless the user specifies another time) and it
  appears in the feeding history

#### Scenario: Missing required field
- **WHEN** an authenticated user submits a feeding-log entry with no food
  description
- **THEN** the system rejects the submission with an error and does not
  create a record

### Requirement: Growth can be measured from a stored photo
The system SHALL let an authenticated user select two points on a stored
snapshot and record the corresponding real-world distance, using a
previously established pixel-to-centimeter calibration for that camera
position, and SHALL persist the resulting measurement with a reference to
the source snapshot and timestamp.

#### Scenario: Calibration is established
- **WHEN** an authenticated user marks two points on a snapshot known to
  contain the physical reference marker and enters the real-world distance
  between them
- **THEN** the system stores a pixel-to-centimeter calibration value for
  future measurements

#### Scenario: Measurement using an existing calibration
- **WHEN** an authenticated user marks two points on a snapshot after a
  calibration has been established
- **THEN** the system computes and records the real-world distance between
  those points using the stored calibration

#### Scenario: Measurement attempted with no calibration set
- **WHEN** an authenticated user attempts to record a measurement before any
  calibration has been established
- **THEN** the system rejects the attempt and directs the user to calibrate
  first, without recording an uncalibrated measurement

### Requirement: Biomarker history is viewable
The system SHALL provide an authenticated view listing recorded snapshots,
feeding-log entries, and measurements in chronological order.

#### Scenario: View recent history
- **WHEN** an authenticated user opens the biomarker dashboard
- **THEN** the system displays recent snapshots, feeding-log entries, and
  measurements, most recent first

### Requirement: Biomarker routes require authentication
The system SHALL require a valid, non-expired session (per the `auth`
capability) before serving the biomarker dashboard or accepting a
feeding-log or measurement submission.

#### Scenario: Anonymous request to a biomarker route
- **WHEN** a client with no session requests the biomarker dashboard or
  submits a feeding-log or measurement entry
- **THEN** the system denies the request the same way it denies any other
  protected route
