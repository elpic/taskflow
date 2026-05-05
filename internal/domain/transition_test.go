package domain

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestValidateTransition_ValidEdges(t *testing.T) {
	validCases := []struct {
		from TaskStatus
		to   TaskStatus
	}{
		{StatusPending, StatusInProgress},
		{StatusPending, StatusFailed},
		{StatusInProgress, StatusVerifying},
		{StatusInProgress, StatusDone},
		{StatusInProgress, StatusFailed},
		{StatusVerifying, StatusDone},
		{StatusVerifying, StatusInProgress},
		{StatusVerifying, StatusFailed},
		{StatusFailed, StatusInProgress},
	}

	for _, tc := range validCases {
		t.Run(string(tc.from)+"->"+string(tc.to), func(t *testing.T) {
			err := ValidateTransition(tc.from, tc.to)
			require.NoError(t, err, "expected valid transition from %s to %s", tc.from, tc.to)
		})
	}
}

func TestValidateTransition_InvalidEdges(t *testing.T) {
	invalidCases := []struct {
		from TaskStatus
		to   TaskStatus
	}{
		// pending cannot go directly to done or verifying
		{StatusPending, StatusDone},
		{StatusPending, StatusVerifying},
		// in_progress cannot go back to pending
		{StatusInProgress, StatusPending},
		// done is terminal
		{StatusDone, StatusPending},
		{StatusDone, StatusInProgress},
		{StatusDone, StatusVerifying},
		{StatusDone, StatusFailed},
		{StatusDone, StatusDone},
		// failed cannot go to pending, done, or verifying
		{StatusFailed, StatusPending},
		{StatusFailed, StatusDone},
		{StatusFailed, StatusVerifying},
		{StatusFailed, StatusFailed},
		// verifying cannot go to pending
		{StatusVerifying, StatusPending},
	}

	for _, tc := range invalidCases {
		t.Run(string(tc.from)+"->"+string(tc.to), func(t *testing.T) {
			err := ValidateTransition(tc.from, tc.to)
			require.Error(t, err, "expected invalid transition from %s to %s", tc.from, tc.to)
			assert.Contains(t, err.Error(), "Cannot transition from")
			assert.Contains(t, err.Error(), string(tc.from))
			assert.Contains(t, err.Error(), string(tc.to))
		})
	}
}

func TestTransitionError_Message(t *testing.T) {
	err := ValidateTransition(StatusDone, StatusPending)
	require.Error(t, err)

	te, ok := err.(*TransitionError)
	require.True(t, ok, "error should be *TransitionError")
	assert.Equal(t, StatusDone, te.From)
	assert.Equal(t, StatusPending, te.To)
	// Done has no valid transitions
	assert.Contains(t, te.Error(), "none")
}

func TestValidTransitions_Coverage(t *testing.T) {
	// Ensure every status has an entry in ValidTransitions
	allStatuses := []TaskStatus{
		StatusPending, StatusInProgress, StatusVerifying, StatusDone, StatusFailed,
	}
	for _, s := range allStatuses {
		_, ok := ValidTransitions[s]
		assert.True(t, ok, "ValidTransitions should contain entry for %s", s)
	}
}
