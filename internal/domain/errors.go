package domain

import "errors"

// Sentinel errors for domain operations.
var (
	ErrNotFound        = errors.New("not found")
	ErrCycleDetected   = errors.New("cycle detected")
	ErrSelfDependency  = errors.New("task cannot depend on itself")
	ErrInProgress      = errors.New("cannot delete in-progress task")
	ErrPendingRequired = errors.New("can only add dependencies to pending tasks")
)
