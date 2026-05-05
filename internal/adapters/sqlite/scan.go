package sqlite

import (
	"database/sql"

	"github.com/elpic/taskflow/internal/domain"
)

// rowToTask scans a SQL row into a domain.Task.
// The query must SELECT all columns in the tasks table.
func rowToTask(row *sql.Row) (*domain.Task, error) {
	return scanTask(row.Scan)
}

// rowsToTask scans the current row of a sql.Rows into a domain.Task.
func rowsToTask(rows *sql.Rows) (*domain.Task, error) {
	return scanTask(rows.Scan)
}

type scanFunc func(dest ...any) error

func scanTask(scan scanFunc) (*domain.Task, error) {
	var t domain.Task
	var parentID sql.NullString
	var verificationCriteria sql.NullString
	var verificationResult sql.NullString
	var metadata sql.NullString
	var startedAt sql.NullString
	var completedAt sql.NullString
	var agentOutput sql.NullString
	var contextSummary sql.NullString
	var position sql.NullInt64
	var idempotencyKey sql.NullString

	err := scan(
		&t.ID,
		&t.Name,
		&t.Description,
		&t.Status,
		&parentID,
		&verificationCriteria,
		&verificationResult,
		&metadata,
		&t.CreatedAt,
		&startedAt,
		&completedAt,
		&agentOutput,
		&contextSummary,
		&position,
		&idempotencyKey,
	)
	if err != nil {
		return nil, err
	}

	if parentID.Valid {
		t.ParentID = &parentID.String
	}
	if verificationCriteria.Valid {
		t.VerificationCriteria = &verificationCriteria.String
	}
	if verificationResult.Valid {
		t.VerificationResult = &verificationResult.String
	}
	t.Metadata = metadata.String
	if t.Metadata == "" {
		t.Metadata = "{}"
	}
	if startedAt.Valid {
		t.StartedAt = &startedAt.String
	}
	if completedAt.Valid {
		t.CompletedAt = &completedAt.String
	}
	if agentOutput.Valid {
		t.AgentOutput = &agentOutput.String
	}
	if contextSummary.Valid {
		t.ContextSummary = &contextSummary.String
	}
	if position.Valid {
		pos := int(position.Int64)
		t.Position = &pos
	}
	if idempotencyKey.Valid {
		t.IdempotencyKey = &idempotencyKey.String
	}

	return &t, nil
}

const selectTaskCols = `id, name, description, status, parent_id,
    verification_criteria, verification_result, metadata,
    created_at, started_at, completed_at, agent_output, context_summary,
    position, idempotency_key`
