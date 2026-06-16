// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	"github.com/charmbracelet/glamour"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Message is one entry in the conversation log.
type Message struct {
	Role      string // user|assistant|file|error|status|disclosure
	Body      string // raw markdown (or plain text for non-md bubbles)
	Markdown  bool   // body should be rendered as markdown
	Timestamp time.Time
}

// streamStart is a tea.Msg fired right before the SSE goroutine
// is spawned, so the model can pin the bubble it will append to.
type streamStart struct{}

// streamEvent wraps StreamEvent so the Bubble Tea Update loop can
// react to incoming SSE events as ordinary messages.
type streamEvent struct{ ev StreamEvent }

// streamDone signals the SSE goroutine has terminated (EOF or
// error).  Latency is the wall-clock from streamStart.
type streamDone struct {
	latency time.Duration
	err     error
}

// errMsg surfaces a non-fatal error in the footer.
type errMsg struct{ err error }

// initServerReady fires once the underlying HTTP server has been
// confirmed reachable on launch.
type initServerReady struct{}

// model is the Bubble Tea application state.
type model struct {
	cfg     Config
	theme   Theme
	ctx     context.Context

	// Layout
	width, height int
	ready         bool

	// Composer
	textarea textarea.Model

	// Chat
	viewport       viewport.Model
	messages       []Message
	streamingBody  string
	streamingActive bool

	// Status
	provider     string
	model        string
	conversation string
	totalTokens  int
	lastLatency  time.Duration
	streamStart  time.Time
	statusNote   string

	// Streaming
	streamCh    chan StreamEvent
	streamCtx   context.CancelFunc

	// Help overlay
	showHelp bool

	// Markdown renderer
	mdRenderer *glamour.TermRenderer
}

func newModel(ctx context.Context, cfg Config) model {
	ta := textarea.New()
	ta.Placeholder = "Ask me anything — Enter to send, Esc to quit"
	ta.Focus()
	ta.Prompt = "▌ "
	ta.CharLimit = 4096
	ta.SetWidth(80)
	ta.SetHeight(3)
	ta.ShowLineNumbers = false

	vp := viewport.New(80, 20)

	// Glamour with a dark-friendly theme.  Width is set per-render
	// once the terminal size is known.
	r, _ := glamour.NewTermRenderer(
		glamour.WithAutoStyle(),
		glamour.WithWordWrap(80),
	)

	m := model{
		cfg:        cfg,
		theme:      newTheme(),
		ctx:        ctx,
		textarea:   ta,
		viewport:   vp,
		provider:   cfg.Provider,
		model:      cfg.Model,
		mdRenderer: r,
		messages: []Message{
			{
				Role:      "assistant",
				Body:      welcomeMessage(cfg),
				Markdown:  true,
				Timestamp: time.Now(),
			},
		},
	}
	return m
}

func (m model) Init() tea.Cmd {
	return tea.Batch(textarea.Blink, m.pollServer())
}

// pollServer is a one-shot command that confirms the server is up
// before the user sees the prompt as enabled.
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
		m.layout()
		m.ready = true
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "esc":
			if m.streamingActive {
				// Esc cancels in-flight stream; first press only.
				if m.streamCtx != nil {
					m.streamCtx()
				}
				return m, nil
			}
			return m, tea.Quit
		case "ctrl+l":
			m.messages = m.messages[:0]
			m.renderViewport()
			return m, nil
		case "ctrl+h", "f1":
			m.showHelp = !m.showHelp
			m.renderViewport()
			return m, nil
		case "enter":
			if m.streamingActive {
				// Ignore Enter while streaming.
				return m, nil
			}
			q := strings.TrimSpace(m.textarea.Value())
			if q == "" {
				return m, nil
			}
			m.textarea.Reset()
			m.messages = append(m.messages, Message{
				Role:      "user",
				Body:      q,
				Markdown:  false,
				Timestamp: time.Now(),
			})
			m.streamingBody = ""
			m.streamingActive = true
			m.streamStart = time.Now()
			m.renderViewport()
			return m, m.startStream(q)
		}

	case initServerReady:
		m.statusNote = ""
		return m, nil

	case streamEvent:
		return m.handleStreamEvent(msg.ev)

	case streamDone:
		m.streamingActive = false
		if msg.err != nil {
			m.statusNote = fmt.Sprintf("stream: %v", msg.err)
		}
		m.lastLatency = msg.latency
		// Finalise the assistant bubble.
		if m.streamingBody != "" {
			m.messages = append(m.messages, Message{
				Role:      "assistant",
				Body:      m.streamingBody,
				Markdown:  true,
				Timestamp: time.Now(),
			})
		}
		m.streamingBody = ""
		m.renderViewport()
		return m, nil

	case errMsg:
		m.statusNote = msg.err.Error()
		return m, nil
	}

	var cmd tea.Cmd
	m.textarea, cmd = m.textarea.Update(msg)
	cmds := []tea.Cmd{cmd}
	m.viewport, cmd = m.viewport.Update(msg)
	cmds = append(cmds, cmd)
	return m, tea.Batch(cmds...)
}

func (m *model) handleStreamEvent(ev StreamEvent) (tea.Model, tea.Cmd) {
	switch ev.Type {
	case "meta":
		if ev.ConversationID != "" {
			m.conversation = ev.ConversationID
		}
	case "disclosure":
		m.messages = append(m.messages, Message{
			Role:      "status",
			Body:      ev.Content,
			Markdown:  false,
			Timestamp: time.Now(),
		})
		m.renderViewport()
	case "delta":
		m.streamingBody += ev.Content
		m.totalTokens++
		m.renderViewport()
	case "tool_call":
		m.messages = append(m.messages, Message{
			Role: "status",
			Body: fmt.Sprintf(
				"tool · %s", ev.Name),
			Markdown:  false,
			Timestamp: time.Now(),
		})
		m.renderViewport()
	case "error":
		m.messages = append(m.messages, Message{
			Role:      "error",
			Body:      ev.Message,
			Markdown:  false,
			Timestamp: time.Now(),
		})
		m.renderViewport()
	case "done":
		// streamDone follows when the goroutine returns; nothing
		// more to do here.
	}
	return *m, m.nextStreamEvent()
}

// startStream opens the SSE connection in a goroutine and returns
// a Cmd that waits for the first event.
func (m *model) startStream(question string) tea.Cmd {
	ctx, cancel := context.WithCancel(m.ctx)
	m.streamCtx = cancel
	m.streamCh = make(chan StreamEvent, 64)
	go openStream(ctx, m.cfg, question, m.conversation, m.streamCh)
	return tea.Batch(m.nextStreamEvent(), m.watchStreamCompletion())
}

// nextStreamEvent returns a Cmd that blocks on the next SSE event.
func (m model) nextStreamEvent() tea.Cmd {
	return func() tea.Msg {
		ev, ok := <-m.streamCh
		if !ok {
			return nil
		}
		return streamEvent{ev: ev}
	}
}

// watchStreamCompletion fires streamDone after the SSE channel
// closes — which `openStream` always does on EOF or error.
func (m model) watchStreamCompletion() tea.Cmd {
	return func() tea.Msg {
		// Drain the channel so we know the goroutine has exited.
		for range m.streamCh {
		}
		return streamDone{latency: time.Since(m.streamStart)}
	}
}

// layout recomputes child widget sizes based on the terminal size.
func (m *model) layout() {
	composerHeight := 5
	headerHeight := 2
	statusHeight := 2
	chatHeight := m.height - composerHeight - headerHeight - statusHeight
	if chatHeight < 3 {
		chatHeight = 3
	}
	m.viewport.Width = m.width
	m.viewport.Height = chatHeight
	m.textarea.SetWidth(m.width - 4)

	if m.mdRenderer != nil {
		_ = m.mdRenderer
	}
	// Re-create the renderer at the new width so wrapping matches.
	width := m.width - 6
	if width < 40 {
		width = 40
	}
	r, err := glamour.NewTermRenderer(
		glamour.WithAutoStyle(),
		glamour.WithWordWrap(width),
	)
	if err == nil {
		m.mdRenderer = r
	}
	m.renderViewport()
}

// renderViewport rebuilds the chat content + scrolls to bottom.
func (m *model) renderViewport() {
	if !m.ready {
		return
	}
	var parts []string
	for _, msg := range m.messages {
		parts = append(parts, m.renderMessage(msg))
	}
	if m.streamingActive {
		parts = append(parts, m.renderMessage(Message{
			Role:     "assistant",
			Body:     m.streamingBody + " ▌",
			Markdown: true,
		}))
	}
	if m.showHelp {
		parts = append(parts, m.helpPanel())
	}
	m.viewport.SetContent(
		lipgloss.JoinVertical(lipgloss.Left, parts...))
	m.viewport.GotoBottom()
}

func (m *model) renderMessage(msg Message) string {
	var bubbleStyle lipgloss.Style
	var roleStyle lipgloss.Style
	var label string
	switch msg.Role {
	case "user":
		bubbleStyle = m.theme.BubbleUser
		roleStyle = lipgloss.NewStyle().Bold(true).
			Foreground(m.theme.AccentUser)
		label = "you"
	case "assistant":
		bubbleStyle = m.theme.BubbleAI
		roleStyle = lipgloss.NewStyle().Bold(true).
			Foreground(m.theme.AccentAI)
		label = "akande"
	case "error":
		bubbleStyle = m.theme.BubbleErr
		roleStyle = lipgloss.NewStyle().Bold(true).
			Foreground(m.theme.AccentError)
		label = "error"
	case "file":
		bubbleStyle = m.theme.BubbleFile
		roleStyle = lipgloss.NewStyle().Bold(true).
			Foreground(m.theme.AccentOK)
		label = "files"
	default:
		bubbleStyle = m.theme.BubbleFile
		roleStyle = lipgloss.NewStyle().Bold(true).
			Foreground(m.theme.AccentInfo)
		label = msg.Role
	}

	bodyMaxWidth := m.width - 6
	if bodyMaxWidth < 40 {
		bodyMaxWidth = 40
	}

	var body string
	if msg.Markdown && m.mdRenderer != nil {
		rendered, err := m.mdRenderer.Render(msg.Body)
		if err != nil || rendered == "" {
			body = msg.Body
		} else {
			body = strings.TrimRight(rendered, "\n")
		}
	} else {
		body = lipgloss.NewStyle().Width(bodyMaxWidth).
			Render(msg.Body)
	}

	bubble := bubbleStyle.
		Width(m.width - 2).
		Render(body)

	role := roleStyle.Margin(0, 0, 0, 1).Render(label)

	return lipgloss.JoinVertical(lipgloss.Left, role, bubble)
}

func (m model) View() string {
	if !m.ready {
		return "  akande-tui starting…"
	}

	header := m.theme.Header.
		Width(m.width).
		Render(fmt.Sprintf(" Àkàndé · %s", m.cfg.ServerURL))

	subtitle := m.theme.HeaderSub.
		Width(m.width).
		Padding(0, 2).
		Render(fmt.Sprintf(
			"provider · %s   model · %s",
			m.provider, m.model,
		))

	chat := m.viewport.View()

	composer := m.theme.Composer.
		Width(m.width - 2).
		Render(m.textarea.View())

	statusLeft := fmt.Sprintf(
		"%s %s · %s",
		m.theme.StatusInfo.Render("●"),
		m.provider,
		m.model,
	)
	statusRight := ""
	if m.streamingActive {
		statusRight = fmt.Sprintf(
			"streaming · %d tokens",
			m.totalTokens,
		)
	} else if m.totalTokens > 0 {
		statusRight = fmt.Sprintf(
			"%d tokens · %d ms",
			m.totalTokens, m.lastLatency.Milliseconds(),
		)
	} else {
		statusRight = "ready"
	}
	if m.statusNote != "" {
		statusRight = m.theme.HelpKey.Render("⚠ ") +
			m.statusNote
	}

	statusWidth := m.width - 4
	statusBar := m.theme.StatusBar.
		Width(statusWidth).
		Render(joinSplit(statusLeft, statusRight, statusWidth))

	footer := m.helpHints()

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		subtitle,
		chat,
		composer,
		statusBar,
		footer,
	)
}

func (m model) helpHints() string {
	hints := []struct{ key, desc string }{
		{"Enter", "send"},
		{"Esc", "quit / cancel stream"},
		{"Ctrl+L", "clear chat"},
		{"F1", "help"},
	}
	var parts []string
	for _, h := range hints {
		parts = append(parts,
			m.theme.HelpKey.Render(h.key)+
				" "+m.theme.HelpDesc.Render(h.desc))
	}
	return lipgloss.NewStyle().
		Padding(0, 2).
		Render(strings.Join(parts, "   "))
}

func (m model) helpPanel() string {
	help := `**Keyboard**

- **Enter**   send message
- **Esc**     cancel active stream (or quit when idle)
- **Ctrl+L**  clear chat
- **Ctrl+H** / **F1**  toggle this help
- **Mouse**   scroll the chat region

**Environment**

- LLM_PROVIDER, OPENAI_DEFAULT_MODEL — pick provider + model
- AKANDE_SERVER_URL — point at a remote akande server
- AKANDE_PYTHON — interpreter used to launch the server`
	if m.mdRenderer != nil {
		if rendered, err := m.mdRenderer.Render(help); err == nil {
			return strings.TrimRight(rendered, "\n")
		}
	}
	return help
}

func welcomeMessage(cfg Config) string {
	return fmt.Sprintf(
		"# Àkàndé\n\n"+
			"_Executive briefing assistant_  ·  "+
			"`%s` · `%s`\n\n"+
			"Type a question below — answers stream in as "+
			"Markdown with code blocks, lists, and citations "+
			"rendered live.  Press **F1** for shortcuts.",
		cfg.Provider, cfg.Model,
	)
}

func joinSplit(left, right string, width int) string {
	gap := width - lipgloss.Width(left) - lipgloss.Width(right)
	if gap < 1 {
		gap = 1
	}
	return left + strings.Repeat(" ", gap) + right
}
