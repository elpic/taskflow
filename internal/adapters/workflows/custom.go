package workflows

import (
	"os"
	"path/filepath"
)

// customFS_ReadDir lists entries in a directory on disk.
func customFS_ReadDir(dir string) ([]os.DirEntry, error) {
	return os.ReadDir(dir)
}

// readFile reads a file from a directory on disk.
func readFile(dir, name string) ([]byte, error) {
	return os.ReadFile(filepath.Join(dir, name))
}
