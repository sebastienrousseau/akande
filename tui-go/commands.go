// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

// Command is one entry in the slash-command surface.  Each command
// is plain Go — no special UI affordances yet (autocomplete +
// inline suggestions would go in a follow-up).
//
// `Handler` returns:
//   - lines: zero or more strings to print into scrollback
//   - tea.Cmd: optional follow-up command (e.g. `tea.Quit`)
//   - updated `model` with any state mutations applied
type Command struct {
	Name        string
	Aliases     []string
	Args        string
	Description string
	Handler     func(m model, args []string) (
		lines []string, cmd tea.Cmd, next model)
}

// allCommands returns the registered slash commands, sorted for
// help display.  Mirrors the curated Claude Code surface as
// closely as makes sense for an executive-briefing assistant.
func allCommands() []Command {
	cmds := []Command{
		{
			Name:        "help",
			Aliases:     []string{"?"},
			Description: "Show available commands.",
			Handler:     cmdHelp,
		},
		{
			Name:        "clear",
			Description: "Clear the terminal scrollback.",
			Handler:     cmdClear,
		},
		{
			Name:        "quit",
			Aliases:     []string{"exit", "q"},
			Description: "Exit akande-tui.",
			Handler:     cmdQuit,
		},
		{
			Name:        "version",
			Description: "Print akande-tui version and runtime.",
			Handler:     cmdVersion,
		},
		{
			Name:        "status",
			Description: "Show provider, model, server, " +
				"and live counters.",
			Handler: cmdStatus,
		},
		{
			Name:        "model",
			Args:        "[name]",
			Description: "Show or switch the model for new " +
				"turns.  No restart required.",
			Handler: cmdModel,
		},
		{
			Name:        "provider",
			Args:        "[name]",
			Description: "Show the active provider " +
				"(read-only — switching needs a server " +
				"restart with LLM_PROVIDER set).",
			Handler: cmdProvider,
		},
		{
			Name:        "server",
			Description: "Show the akande server URL and " +
				"liveness.",
			Handler: cmdServer,
		},
		{
			Name:        "new",
			Aliases:     []string{"reset"},
			Description: "Start a new conversation (drop the " +
				"current conversation_id).",
			Handler: cmdNew,
		},
		{
			Name:        "cancel",
			Aliases:     []string{"stop"},
			Description: "Cancel the in-flight stream " +
				"(same as Esc).",
			Handler: cmdCancel,
		},
		{
			Name:        "tokens",
			Description: "Show the cumulative token / latency " +
				"counters for this session.",
			Handler: cmdTokens,
		},
		{
			Name:        "skills",
			Description: "List skills registered on the " +
				"akande server.",
			Handler: cmdSkills,
		},
		{
			Name:        "profile",
			Description: "Show the active AKANDE_PROFILE " +
				"(local / eu / strict / internal).",
			Handler: cmdProfile,
		},
		{
			Name:        "mode",
			Description: "Show the active AKANDE_MODE " +
				"(online / offline).",
			Handler: cmdMode,
		},
		{
			Name:        "config",
			Description: "Dump the resolved runtime config.",
			Handler: cmdConfig,
		},
		{
			Name:        "log",
			Description: "Print the path of the server log " +
				"file.",
			Handler: cmdLog,
		},
	}

	sort.Slice(cmds, func(i, j int) bool {
		return cmds[i].Name < cmds[j].Name
	})
	return cmds
}

// findCommand looks up a command by name or alias.
func findCommand(name string) (Command, bool) {
	name = strings.ToLower(strings.TrimPrefix(name, "/"))
	for _, c := range allCommands() {
		if c.Name == name {
			return c, true
		}
		for _, alias := range c.Aliases {
			if alias == name {
				return c, true
			}
		}
	}
	return Command{}, false
}

// matchCommands returns the slash commands whose name starts with
// the prefix in `input` (without the leading slash) — the list
// the inline autocomplete popup shows.  Returns nil when the
// input is past the command-name position (e.g. after a space)
// so user-supplied args don't keep the popup open.
func matchCommands(input string) []Command {
	input = strings.TrimSpace(input)
	if !strings.HasPrefix(input, "/") {
		return nil
	}
	body := strings.TrimPrefix(input, "/")
	// Once the user types a space, they are typing args; stop
	// suggesting command names.
	if strings.Contains(body, " ") {
		return nil
	}
	body = strings.ToLower(body)
	var hits []Command
	for _, c := range allCommands() {
		if strings.HasPrefix(c.Name, body) {
			hits = append(hits, c)
			continue
		}
		for _, alias := range c.Aliases {
			if strings.HasPrefix(alias, body) {
				hits = append(hits, c)
				break
			}
		}
	}
	return hits
}

// dispatchSlash parses a `/foo bar baz` line and runs the matching
// command.  Returns ok=false when the line is not a slash command
// (caller should send it to the LLM instead).
func dispatchSlash(
	m model, line string,
) (lines []string, cmd tea.Cmd, next model, ok bool) {
	line = strings.TrimSpace(line)
	if !strings.HasPrefix(line, "/") {
		return nil, nil, m, false
	}
	parts := strings.Fields(line)
	if len(parts) == 0 {
		return nil, nil, m, false
	}
	c, found := findCommand(parts[0])
	if !found {
		return []string{m.theme.renderError(
			fmt.Sprintf("unknown command: %s — try /help",
				parts[0]))}, nil, m, true
	}
	out, follow, n := c.Handler(m, parts[1:])
	return out, follow, n, true
}

// ── handlers ────────────────────────────────────────────────

func cmdHelp(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	cmds := allCommands()
	var rows []string
	rows = append(rows, m.theme.helpTitle("commands"))
	for _, c := range cmds {
		left := "/" + c.Name
		if c.Args != "" {
			left += " " + c.Args
		}
		rows = append(rows,
			m.theme.helpRow(left, c.Description))
	}
	rows = append(rows, "")
	rows = append(rows,
		m.theme.helpTitle("keys"))
	rows = append(rows,
		m.theme.helpRow("Enter", "send"))
	rows = append(rows,
		m.theme.helpRow("Esc", "quit / cancel stream"))
	rows = append(rows,
		m.theme.helpRow("Ctrl+C", "quit"))
	return []string{strings.Join(rows, "\n")}, nil, m
}

func cmdClear(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	// ANSI: clear scrollback (ESC [ 3 J) + reset screen
	// (ESC [ H + ESC [ 2 J).  This wipes the user's terminal
	// scrollback for the akande session without affecting the
	// rest of the tab.
	return nil, tea.ClearScreen, m
}

func cmdQuit(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	return []string{m.theme.renderNote(
		"bye", "akande-tui shutting down")}, tea.Quit, m
}

func cmdVersion(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	return []string{m.theme.renderNote("version",
		fmt.Sprintf(
			"akande-tui v0.0.7   "+
				"go %s   %s/%s",
			runtime.Version(),
			runtime.GOOS, runtime.GOARCH,
		))}, nil, m
}

func cmdStatus(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	live := "unreachable"
	if reachable(m.cfg.ServerURL) {
		live = "live"
	}
	lines := []string{
		fmt.Sprintf("provider          %s", m.provider),
		fmt.Sprintf("model             %s", m.model),
		fmt.Sprintf("server            %s   (%s)",
			m.cfg.ServerURL, live),
		fmt.Sprintf("conversation_id   %s",
			fallback(m.conversation, "—")),
		fmt.Sprintf("tokens            %d", m.totalTokens),
		fmt.Sprintf("last latency      %d ms",
			m.lastLatency.Milliseconds()),
	}
	return []string{m.theme.renderNote("status",
		strings.Join(lines, "\n"))}, nil, m
}

func cmdModel(m model, args []string) (
	[]string, tea.Cmd, model,
) {
	if len(args) == 0 {
		return []string{m.theme.renderNote(
			"model", m.model)}, nil, m
	}
	m.model = strings.Join(args, " ")
	return []string{m.theme.renderNote("model",
		"set to "+m.model+
			" — applies to the next turn")}, nil, m
}

func cmdProvider(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	return []string{m.theme.renderNote("provider",
		fmt.Sprintf(
			"%s   (switching providers requires "+
				"restarting the akande server with "+
				"LLM_PROVIDER set)", m.provider))}, nil, m
}

func cmdServer(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	live := "unreachable"
	if reachable(m.cfg.ServerURL) {
		live = "live"
	}
	return []string{m.theme.renderNote("server",
		fmt.Sprintf("%s   (%s)",
			m.cfg.ServerURL, live))}, nil, m
}

func cmdNew(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	m.conversation = ""
	return []string{m.theme.renderNote("conversation",
		"started a new conversation")}, nil, m
}

func cmdCancel(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	if m.streamingActive && m.streamCtx != nil {
		m.streamCtx()
		return []string{m.theme.renderNote("cancel",
			"in-flight stream cancelled")}, nil, m
	}
	return []string{m.theme.renderNote("cancel",
		"no active stream")}, nil, m
}

func cmdTokens(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	return []string{m.theme.renderNote("tokens",
		fmt.Sprintf("%d tokens · %d ms last turn",
			m.totalTokens,
			m.lastLatency.Milliseconds()))}, nil, m
}

func cmdSkills(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	// Best-effort: the akande server does not (yet) expose a
	// /skills endpoint, so list the built-in five from the
	// v0.0.6 surface.  Replace with a real fetch once the
	// server endpoint lands.
	body := "briefing       (default)\n" +
		"web_search     (consent required)\n" +
		"weather\n" +
		"finance\n" +
		"policy         (consent gate)"
	return []string{m.theme.renderNote(
		"skills", body)}, nil, m
}

func cmdProfile(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	p := os.Getenv("AKANDE_PROFILE")
	if p == "" {
		p = "local (default)"
	}
	return []string{m.theme.renderNote(
		"profile", p)}, nil, m
}

func cmdMode(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	p := os.Getenv("AKANDE_MODE")
	if p == "" {
		p = "online (default)"
	}
	return []string{m.theme.renderNote(
		"mode", p)}, nil, m
}

func cmdConfig(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	cfg := map[string]string{
		"server_url":  m.cfg.ServerURL,
		"python_bin":  m.cfg.PythonBin,
		"provider":    m.cfg.Provider,
		"model":       m.cfg.Model,
		"log_file":    fallback(m.cfg.LogFile, "—"),
		"COLORTERM":   os.Getenv("COLORTERM"),
		"TERM":        os.Getenv("TERM"),
	}
	b, _ := json.MarshalIndent(cfg, "", "  ")
	return []string{m.theme.renderNote("config",
		string(b))}, nil, m
}

func cmdLog(m model, _ []string) (
	[]string, tea.Cmd, model,
) {
	p := os.Getenv("AKANDE_TUI_SERVER_LOG")
	if p == "" {
		p = "$TMPDIR/akande-server.log"
	}
	return []string{m.theme.renderNote("log",
		p+"\n  tail -f "+p+
			"   to watch live")}, nil, m
}

// ── small helpers ────────────────────────────────────────────

func fallback(s, def string) string {
	if s == "" {
		return def
	}
	return s
}

// Ensure unused imports stay tied to the package so go vet is
// quiet even if a handler is later dropped.  (No-op at runtime.)
var (
	_ = http.MethodGet
	_ = context.Canceled
	_ = time.Now
)
