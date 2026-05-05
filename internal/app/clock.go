package app

import "time"

// SystemClock implements domain.Clock using the real system time.
type SystemClock struct{}

// NowUTC returns the current UTC time formatted to match Python's isoformat().
// Example: "2024-01-15T10:30:00.123456+00:00"
func (SystemClock) NowUTC() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.999999-07:00")
}
