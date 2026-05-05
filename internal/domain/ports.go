package domain

// TaskRepository is the persistence port for tasks.
type TaskRepository interface {
	// Task CRUD
	CreateTask(name, description string, parentID *string, verificationCriteria *string, metadata map[string]any, idempotencyKey *string) (*Task, error)
	GetTask(id string) (*Task, error)
	GetChildren(parentID string) ([]*Task, error)
	GetAllTasks() ([]*Task, error)
	SearchTasks(query string) ([]*Task, error)
	GetTasksFiltered(status *string, parentID *string) ([]*Task, error)
	UpdateTask(id string, fields map[string]any) (*Task, error)
	ResetTask(id string) error
	DeleteTask(id string) error

	// Hierarchy
	MoveTask(id string, newParentID *string) error
	GetAllDescendants(rootID string) ([]*Task, error)

	// Idempotency
	FindByIdempotencyKey(key string) (*Task, error)

	// Current task tracking
	SetCurrentTask(id *string) error
	GetCurrentTaskID() (*string, error)

	// Dependencies
	AddDependencies(taskID string, blockedByIDs []string) error
	GetBlockers(taskID string) ([]*Task, error)
	GetDependents(taskID string) ([]*Task, error)
	GetReadyTasks(parentID *string) ([]*Task, error)

	// Events
	LogEvent(taskID, eventType string, details map[string]any) error
	GetTaskHistory(taskID string, recursive bool) ([]map[string]any, error)

	// Utilities
	HasTasks() (bool, error)
	CleanupDoneRoots(days int) (int, error)
	FindActiveRoot() (*Task, error)
}

// WorkflowSource provides workflow definitions.
type WorkflowSource interface {
	GetWorkflow(taskType string) (*Workflow, error)
	ListTypes() []string
}

// Logger is an interface for structured logging from the app layer.
type Logger interface {
	Info(msg string)
	Warn(msg string)
	Error(msg string)
}

// Clock provides time functions (injectable for testing).
type Clock interface {
	NowUTC() string
}

// IDGen generates unique IDs.
type IDGen interface {
	NewID() string
}
