## MODIFIED Requirements

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
