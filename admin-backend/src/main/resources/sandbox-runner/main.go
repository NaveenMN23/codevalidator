package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type ExecuteRequest struct {
	Files   map[string]string `json:"files"`
	Command string            `json:"command"`
}

type ExecuteResponse struct {
	Success  bool   `json:"success"`
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	ExitCode int    `json:"exit_code"`
}

func main() {
	port := flag.String("port", "8080", "Port to listen on")
	flag.Parse()

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	http.HandleFunc("/execute", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var req ExecuteRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request body", http.StatusBadRequest)
			return
		}

		// Ensure /app directory exists
		appDir := "/app"
		if err := os.MkdirAll(appDir, 0755); err != nil {
			log.Printf("Failed to create %s: %v", appDir, err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
			return
		}

		// Write user files
		for relPath, content := range req.Files {
			// Prevent path traversal
			fullPath := filepath.Clean(filepath.Join(appDir, relPath))
			if !strings.HasPrefix(fullPath, appDir+string(filepath.Separator)) && fullPath != appDir {
				http.Error(w, "Invalid file path", http.StatusBadRequest)
				return
			}

			dir := filepath.Dir(fullPath)
			if err := os.MkdirAll(dir, 0755); err != nil {
				log.Printf("Failed to create dir %s: %v", dir, err)
				http.Error(w, "Internal server error", http.StatusInternalServerError)
				return
			}

			if err := os.WriteFile(fullPath, []byte(content), 0644); err != nil {
				log.Printf("Failed to write file %s: %v", fullPath, err)
				http.Error(w, "Internal server error", http.StatusInternalServerError)
				return
			}
		}

		// Execute the requested test command
		var stdout, stderr bytes.Buffer
		cmd := exec.Command("sh", "-c", req.Command)
		cmd.Dir = appDir
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr

		err := cmd.Run()

		exitCode := 0
		if err != nil {
			if exitError, ok := err.(*exec.ExitError); ok {
				exitCode = exitError.ExitCode()
			} else {
				exitCode = -1
				// If it wasn't an exit error, we failed to even run the command properly
				if stderr.Len() == 0 {
					stderr.WriteString(err.Error())
				}
			}
		}

		resp := ExecuteResponse{
			Success:  exitCode == 0,
			Stdout:   stdout.String(),
			Stderr:   stderr.String(),
			ExitCode: exitCode,
		}

		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			log.Printf("Failed to encode response: %v", err)
		}
	})

	addr := fmt.Sprintf("0.0.0.0:%s", *port)
	log.Printf("Starting sandbox-runner on %s...", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
