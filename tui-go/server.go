// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"syscall"
	"time"
)

// ServerHandle tracks an akande server we launched ourselves so
// we can shut it down when the TUI exits.  A nil-receiver Stop is
// safe — the server was already running before we started.
type ServerHandle struct {
	cmd *exec.Cmd
}

// Stop terminates the server we spawned.  Idempotent.
func (s *ServerHandle) Stop() {
	if s == nil || s.cmd == nil || s.cmd.Process == nil {
		return
	}
	// SIGINT triggers the CherryPy graceful shutdown path; the
	// server has its own atexit hook for the SQLite cache.
	_ = s.cmd.Process.Signal(syscall.SIGINT)
	done := make(chan error, 1)
	go func() { done <- s.cmd.Wait() }()
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		_ = s.cmd.Process.Kill()
	}
}

// ensureServer returns a handle to a running akande server.  If
// the configured URL is already serving requests, we return an
// empty handle (no shutdown needed at exit).  Otherwise we spawn
// `python -m akande server --host … --port …` and wait for
// /health to respond.
func ensureServer(cfg Config) (*ServerHandle, error) {
	if reachable(cfg.ServerURL) {
		return &ServerHandle{}, nil
	}

	host, port := splitHostPort(cfg.ServerURL)
	cmd := exec.Command(cfg.PythonBin, "-m", "akande", "server",
		"--host", host, "--port", port)
	cmd.Stdout = nil
	cmd.Stderr = os.Stderr
	cmd.Env = os.Environ()
	// Detach into its own process group so a stray Ctrl+C in the
	// TUI does not double-signal the server.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("spawn akande server: %w", err)
	}

	deadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(deadline) {
		if reachable(cfg.ServerURL) {
			return &ServerHandle{cmd: cmd}, nil
		}
		time.Sleep(250 * time.Millisecond)
	}
	_ = cmd.Process.Kill()
	return nil, fmt.Errorf(
		"akande server did not become reachable at %s within 20s",
		cfg.ServerURL,
	)
}

// reachable returns true when /health responds 200 within 1 s.
func reachable(base string) bool {
	ctx, cancel := context.WithTimeout(
		context.Background(), 1*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(
		ctx, http.MethodGet, base+"/health", nil)
	if err != nil {
		return false
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// splitHostPort decomposes "http://host:port" or "http://host"
// into (host, port).  Falls back to ("127.0.0.1", "8080").
func splitHostPort(url string) (string, string) {
	if i := indexOf(url, "://"); i >= 0 {
		url = url[i+3:]
	}
	if j := indexOf(url, "/"); j >= 0 {
		url = url[:j]
	}
	if k := indexOf(url, ":"); k >= 0 {
		return url[:k], url[k+1:]
	}
	return url, "8080"
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
