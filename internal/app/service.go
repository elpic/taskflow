package app

import (
	"github.com/elpic/taskflow/internal/domain"
)

// Service is the application service that orchestrates domain operations.
type Service struct {
	repo      domain.TaskRepository
	workflows domain.WorkflowSource
	hooks     domain.HookRunner
	logger    domain.Logger
}

// NewService constructs an application Service.
func NewService(
	repo domain.TaskRepository,
	workflows domain.WorkflowSource,
	hooks domain.HookRunner,
	logger domain.Logger,
) *Service {
	return &Service{
		repo:      repo,
		workflows: workflows,
		hooks:     hooks,
		logger:    logger,
	}
}
