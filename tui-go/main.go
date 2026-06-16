// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.
//
// Package main is the entry point for `akande-tui`, the Bubble Tea
// TUI for the Àkàndé voice assistant.
//
// All LLM logic lives in the Python `akande` package; this binary
// owns rendering, input handling, and the SSE consumer.  It auto-
// launches `python -m akande server` in the background when no
// reachable instance is found, then drives every prompt through
// the existing /stream endpoint.
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"
)

func init() {
	// Pin the color profile so termenv does NOT issue OSC 10/11
	// (foreground/background) queries to the terminal at startup.
	// On Ghostty / iTerm2 / kitty the reply (e.g. `;rgb:1313/1616/
	// 1a1a`) leaks into Bubble Tea's stdin reader and shows up as
	// literal text in the textarea.
	lipgloss.SetColorProfile(termenv.TrueColor)
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "akande-tui: %v\n", err)
		os.Exit(2)
	}

	// Ensure the akande server is reachable; spawn it in the
	// background otherwise.  We deliberately swallow the spawn
	// failure path inside ensureServer — the user sees a clear
	// error in the TUI footer if /health stays unreachable.
	srv, err := ensureServer(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr,
			"akande-tui: server bootstrap failed: %v\n", err)
		os.Exit(1)
	}
	defer srv.Stop()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// SIGTERM / SIGINT → graceful exit even if Bubble Tea misses it.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
	}()

	model := newModel(ctx, cfg)

	p := tea.NewProgram(model,
		tea.WithAltScreen(),
		tea.WithMouseCellMotion(),
	)
	if _, err := p.Run(); err != nil {
		log.Fatalf("akande-tui: %v", err)
	}
}

// httpClient is the shared HTTP client for the akande server.
// Streaming responses set their own context; this default is for
// short health-check requests.
var httpClient = &http.Client{
	Timeout: 5 * time.Second,
}
