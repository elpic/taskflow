package app

import "github.com/google/uuid"

// UUIDGen implements domain.IDGen using the first 8 chars of a UUID v4.
type UUIDGen struct{}

// NewID returns a new 8-character ID (first 8 chars of a UUID v4, no hyphens).
func (UUIDGen) NewID() string {
	return uuid.NewString()[:8]
}
