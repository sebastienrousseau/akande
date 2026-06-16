// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textarea"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/glamour"
	"github.com/charmbracelet/lipgloss"
)

// streamEvent / streamDone / errMsg / initServerReady are control
// messages dispatched by the SSE consumer goroutine and the
// initial health probe.
type streamEvent struct{ ev StreamEvent }
type streamDone struct {
	latency time.Duration
	err     error
}
type errMsg struct{ err error }
type initServerReady struct{}

// model owns the bubbletea state.  The chat history lives in the
// terminal's scrollback — we print it there via `tea.Println` —
// so this struct only tracks the in-flight response, the
// composer, and the bottom status strip.  The alt-screen is
// disabled so the user can scroll back through past turns with
// their terminal's normal scrollback gestures.
type model struct {
	cfg   Config
	theme Theme
	ctx   context.Context

	width, height int
	ready         bool

	textarea textarea.Model

	// In-flight streaming buffer.  Replaced by the final
	// glamour-rendered response (printed into scrollback) once
	// the stream completes.
	streamingBody   string
	streamingActive bool
	streamStart     time.Time
	streamCh        chan StreamEvent
	streamCtx       context.CancelFunc

	provider     string
	model        string
	conversation string
	totalTokens  int
	lastLatency  time.Duration
	statusNote   string

	mdRenderer *glamour.TermRenderer
}

func newModel(ctx context.Context, cfg Config) model {
	ta := textarea.New()
	ta.Placeholder = "Ask anything — /help for commands · Enter to send"
	ta.Focus()
	ta.Prompt = "▎ "
	ta.CharLimit = 4096
	ta.SetWidth(80)
	ta.SetHeight(1)
	ta.ShowLineNumbers = false
	ta.FocusedStyle.CursorLine = lipgloss.NewStyle()
	ta.BlurredStyle.CursorLine = lipgloss.NewStyle()

	r, _ := glamour.NewTermRenderer(
		glamour.WithStandardStyle("dark"),
		glamour.WithWordWrap(80),
	)

	return model{
		cfg:        cfg,
		theme:      newTheme(),
		ctx:        ctx,
		textarea:   ta,
		provider:   cfg.Provider,
		model:      cfg.Model,
		mdRenderer: r,
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(
		textarea.Blink,
		m.pollServer(),
		m.printBanner(),
	)
}

// printBanner emits the one-time welcome panel into the
// terminal's scrollback so the rest of the UI starts on a
// fresh line below it.
func (m model) printBanner() tea.Cmd {
	return tea.Println(m.theme.banner(m.cfg))
}

func (m model) pollServer() tea.Cmd {
	return func() tea.Msg {
		deadline := time.Now().Add(5 * time.Second)
		for time.Now().Before(deadline) {
			if reachable(m.cfg.ServerURL) {
				return initServerReady{}
			}
			time.Sleep(200 * time.Millisecond)
		}
		return errMsg{err: fmt.Errorf(
			"server unreachable at %s", m.cfg.ServerURL)}
	}
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		w := msg.Width - 4
		if w < 30 {
			w = 30
		}
		m.textarea.SetWidth(w)
		// Re-create the markdown renderer so wrapping matches
		// the new viewport.
		r, err := glamour.NewTermRenderer(
			glamour.WithStandardStyle("dark"),
			glamour.WithWordWrap(w),
		)
		if err == nil {
			m.mdRenderer = r
		}
		m.ready = true
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c":
			if m.streamingActive && m.streamCtx != nil {
				m.streamCtx()
				return m, nil
			}
			return m, tea.Quit
		case "esc":
			if m.streamingActive && m.streamCtx != nil {
				m.streamCtx()
				return m, nil
			}
			return m, tea.Quit
		case "enter":
			if m.streamingActive {
				return m, nil
			}
			q := strings.TrimSpace(m.textarea.Value())
			if q == "" {
				return m, nil
			}
			m.textarea.Reset()
			// Slash commands intercept BEFORE the LLM call.
			// They never hit the akande server — pure UI
			// affordances (status, model switch, log path,
			// clear screen, quit, …).
			if strings.HasPrefix(q, "/") {
				lines, follow, next, ok := dispatchSlash(m, q)
				if ok {
					var cmds []tea.Cmd
					cmds = append(cmds,
						tea.Println(m.theme.renderUser(q)))
					for _, l := range lines {
						cmds = append(cmds, tea.Println(l))
					}
					if follow != nil {
						cmds = append(cmds, follow)
					}
					return next, tea.Batch(cmds...)
				}
			}
			userLine := m.theme.renderUser(q)
			m.streamingBody = ""
			m.streamingActive = true
			m.streamStart = time.Now()
			ctx, cancel := context.WithCancel(m.ctx)
			m.streamCtx = cancel
			m.streamCh = make(chan StreamEvent, 64)
			go openStream(ctx, m.cfg, q, m.conversation,
				m.streamCh)
			return m, tea.Batch(
				tea.Println(userLine),
				readStreamEvent(m.streamCh, m.streamStart),
			)
		}

	case initServerReady:
		m.statusNote = ""
		return m, nil

	case streamEvent:
		return m.handleStreamEvent(msg.ev)

	case streamDone:
		m.streamingActive = false
		m.lastLatency = msg.latency
		// Final clean render with glamour so headings, code
		// blocks, lists land in scrollback in their fully
		// styled form.  Drop the partial preview that was
		// rendering above the composer.
		body := strings.TrimRight(m.streamingBody, "\n")
		m.streamingBody = ""
		var cmds []tea.Cmd
		if body != "" {
			cmds = append(cmds,
				tea.Println(m.theme.renderAssistant(
					m.mdRenderer, body)))
		}
		if msg.err != nil {
			m.statusNote = fmt.Sprintf("stream: %v", msg.err)
		}
		return m, tea.Batch(cmds...)

	case errMsg:
		m.statusNote = msg.err.Error()
		return m, nil
	}

	var cmd tea.Cmd
	m.textarea, cmd = m.textarea.Update(msg)
	return m, cmd
}

func (m *model) handleStreamEvent(ev StreamEvent) (tea.Model, tea.Cmd) {
	switch ev.Type {
	case "meta":
		if ev.ConversationID != "" {
			m.conversation = ev.ConversationID
		}
	case "disclosure":
		// Disclosures print into scrollback as a labelled note.
		return *m, tea.Batch(
			tea.Println(m.theme.renderNote(
				"disclosure", ev.Content)),
			readStreamEvent(m.streamCh, m.streamStart),
		)
	case "delta":
		m.streamingBody += ev.Content
		m.totalTokens++
	case "tool_call":
		return *m, tea.Batch(
			tea.Println(m.theme.renderNote(
				"tool", ev.Name)),
			readStreamEvent(m.streamCh, m.streamStart),
		)
	case "error":
		return *m, tea.Batch(
			tea.Println(m.theme.renderError(ev.Message)),
			readStreamEvent(m.streamCh, m.streamStart),
		)
	case "done":
		// streamDone follows when the goroutine returns.
	}
	return *m, readStreamEvent(m.streamCh, m.streamStart)
}

func readStreamEvent(
	ch <-chan StreamEvent, start time.Time,
) tea.Cmd {
	return func() tea.Msg {
		ev, ok := <-ch
		if !ok {
			return streamDone{latency: time.Since(start)}
		}
		return streamEvent{ev: ev}
	}
}

// View renders the bottom strip — the in-flight streaming
// preview (when active), the composer, and the status line.
// History prints into scrollback above this strip via
// `tea.Println`.
func (m model) View() string {
	if !m.ready {
		return ""
	}

	var preview string
	if m.streamingActive {
		preview = m.theme.renderStreamingPreview(
			m.mdRenderer, m.streamingBody, m.width)
	}

	composer := m.theme.renderComposer(
		m.textarea.View(), m.width)

	statusLeft := fmt.Sprintf(
		"%s %s · %s",
		m.theme.dot(),
		m.provider,
		m.model,
	)
	var statusRight string
	switch {
	case m.statusNote != "":
		statusRight = m.theme.warn(m.statusNote)
	case m.streamingActive:
		statusRight = fmt.Sprintf(
			"streaming · %d tokens",
			m.totalTokens,
		)
	case m.totalTokens > 0:
		statusRight = fmt.Sprintf(
			"%d tokens · %d ms",
			m.totalTokens, m.lastLatency.Milliseconds(),
		)
	default:
		statusRight = "ready"
	}
	status := m.theme.renderStatus(
		statusLeft, statusRight, m.width)

	help := m.theme.renderHelp(m.width)

	var parts []string
	if preview != "" {
		parts = append(parts, preview)
	}
	parts = append(parts, composer, status, help)

	return lipgloss.JoinVertical(lipgloss.Left, parts...)
}
