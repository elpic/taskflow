package domain

import "fmt"

// ValidTransitions maps each status to the set of valid target statuses.
var ValidTransitions = map[TaskStatus]map[TaskStatus]bool{
	StatusPending:    {StatusInProgress: true, StatusFailed: true},
	StatusInProgress: {StatusVerifying: true, StatusDone: true, StatusFailed: true},
	StatusVerifying:  {StatusDone: true, StatusInProgress: true, StatusFailed: true},
	StatusDone:       {},
	StatusFailed:     {StatusInProgress: true},
}

// TransitionError is returned when a status transition is not allowed.
type TransitionError struct {
	From TaskStatus
	To   TaskStatus
}

func (e *TransitionError) Error() string {
	valid := ""
	sep := ""
	for s := range ValidTransitions[e.From] {
		valid += sep + string(s)
		sep = ", "
	}
	if valid == "" {
		valid = "none"
	}
	return fmt.Sprintf(
		"Cannot transition from '%s' to '%s'. Valid transitions: %s",
		e.From, e.To, valid,
	)
}

// ValidateTransition returns a TransitionError if the transition is not allowed.
func ValidateTransition(current, target TaskStatus) error {
	targets, ok := ValidTransitions[current]
	if !ok || !targets[target] {
		return &TransitionError{From: current, To: target}
	}
	return nil
}
