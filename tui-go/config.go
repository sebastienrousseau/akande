// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"fmt"
	"os"
	"path/filepath"
)

// Config holds the runtime parameters resolved from env + flags.
//
// All fields are immutable after loadConfig returns; the Bubble
// Tea model takes a copy so concurrent updates from streaming
// goroutines are race-free.
type Config struct {
	// ServerURL is the akande server's HTTP base.  Used for /stream
	// + /health.  Defaults to http://127.0.0.1:8080.
	ServerURL string

	// PythonBin is the interpreter used to launch the akande server
	// when no instance is already running.  Defaults to the
	// $VIRTUAL_ENV/bin/python if set, then the first `python` on
	// $PATH.
	PythonBin string

	// Provider + Model display in the header.  Sourced from env;
	// the launcher script sets these.
	Provider string
	Model    string

	// LogFile is the path appended to with streaming events for
	// debugging.  Empty disables logging.
	LogFile string
}

func loadConfig() (Config, error) {
	cfg := Config{
		ServerURL: getenvDefault("AKANDE_SERVER_URL",
			"http://127.0.0.1:8080"),
		Provider: getenvDefault("LLM_PROVIDER", "openai"),
		Model:    getenvDefault("OPENAI_DEFAULT_MODEL", "default"),
		LogFile:  os.Getenv("AKANDE_TUI_LOG"),
	}

	// Pick the Python interpreter: prefer the active venv, fall
	// back to the system python.
	if venv := os.Getenv("VIRTUAL_ENV"); venv != "" {
		cfg.PythonBin = filepath.Join(venv, "bin", "python")
		if _, err := os.Stat(cfg.PythonBin); err != nil {
			cfg.PythonBin = ""
		}
	}
	if cfg.PythonBin == "" {
		cfg.PythonBin = getenvDefault("AKANDE_PYTHON", "python3")
	}

	if cfg.ServerURL == "" {
		return cfg, fmt.Errorf("AKANDE_SERVER_URL is empty")
	}
	return cfg, nil
}

func getenvDefault(key, def string) string {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	return v
}
