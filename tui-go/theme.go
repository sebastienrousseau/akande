// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/glamour"
	"github.com/charmbracelet/lipgloss"
)

// Theme centralises every Lipgloss style + render helper.  Chat
// history is printed into the terminal scrollback (no alt-screen,
// no viewport) so the styles here cover one-shot blocks rather
// than full-frame panels.
type Theme struct {
	BgPanel     lipgloss.Color
	TextPrimary lipgloss.Color
	TextMuted   lipgloss.Color
	TextDim     lipgloss.Color
	AccentUser  lipgloss.Color
	AccentAI    lipgloss.Color
	AccentInfo  lipgloss.Color
	AccentOK    lipgloss.Color
	AccentWarn  lipgloss.Color
	AccentError lipgloss.Color
}

func newTheme() Theme {
	return Theme{
		BgPanel:     "#1a1a1d",
		TextPrimary: "#f5f5f7",
		TextMuted:   "#98989d",
		TextDim:     "#636366",
		// Apple HIG system blue for the assistant accent
		// (banner title, ❯ akande prefix, status dot, help
		// key labels).  User accent is a lighter sky blue so
		// `❯ you` and `❯ akande` stay distinguishable when
		// both turns scroll past in the history.
		AccentUser:  "#64d2ff",
		AccentAI:    "#0a84ff",
		AccentInfo:  "#5ac8fa",
		AccentOK:    "#32d74b",
		AccentWarn:  "#ff9f0a",
		AccentError: "#ff453a",
	}
}

// dot renders the live "online" marker for the status bar.
func (t Theme) dot() string {
	return lipgloss.NewStyle().
		Foreground(t.AccentAI).
		Bold(true).
		Render("●")
}

func (t Theme) warn(s string) string {
	return lipgloss.NewStyle().
		Foreground(t.AccentWarn).
		Render("⚠ " + s)
}

// banner is the one-time welcome string printed into scrollback
// before the first prompt.
func (t Theme) banner(cfg Config) string {
	title := lipgloss.NewStyle().
		Bold(true).
		Foreground(t.AccentAI).
		Render(" Àkàndé ")
	sub := lipgloss.NewStyle().
		Foreground(t.TextMuted).
		Render(" Executive briefing assistant ")
	meta := lipgloss.NewStyle().
		Foreground(t.TextDim).
		Render(fmt.Sprintf(
			"   provider · %s   model · %s   %s",
			cfg.Provider, cfg.Model, cfg.ServerURL))
	hint := lipgloss.NewStyle().
		Foreground(t.TextDim).
		Render("   Enter to send · Esc to quit · " +
			"/help for commands")
	return strings.Join([]string{
		"",
		title,
		sub,
		meta,
		hint,
		"",
	}, "\n")
}

// renderUser is the bubble printed into scrollback when the user
// submits a question.  Minimal, single coloured glyph + text.
func (t Theme) renderUser(text string) string {
	label := lipgloss.NewStyle().
		Foreground(t.AccentUser).
		Bold(true).
		Render("❯ you ")
	body := lipgloss.NewStyle().
		Foreground(t.TextPrimary).
		Render(text)
	return label + body
}

// renderAssistant is the bubble printed into scrollback once the
// assistant's stream completes.  We render the markdown with
// glamour so headings, code blocks, lists, tables and inline
// styles land fully styled in scrollback.
func (t Theme) renderAssistant(
	r *glamour.TermRenderer, markdown string,
) string {
	label := lipgloss.NewStyle().
		Foreground(t.AccentAI).
		Bold(true).
		Render("❯ akande")
	var body string
	if r != nil {
		rendered, err := r.Render(markdown)
		if err == nil && rendered != "" {
			body = strings.TrimRight(rendered, "\n")
		}
	}
	if body == "" {
		body = lipgloss.NewStyle().
			Foreground(t.TextPrimary).
			Render(markdown)
	}
	return label + "\n" + body
}

// renderStreamingPreview is what shows above the composer while
// a stream is in flight.  We re-render with glamour every refresh
// so the partial markdown stays legible.
func (t Theme) renderStreamingPreview(
	r *glamour.TermRenderer, partial string, width int,
) string {
	if partial == "" {
		return lipgloss.NewStyle().
			Foreground(t.TextDim).
			Padding(0, 1).
			Render("⠋ thinking…")
	}
	var body string
	if r != nil {
		rendered, err := r.Render(partial)
		if err == nil && rendered != "" {
			body = strings.TrimRight(rendered, "\n")
		}
	}
	if body == "" {
		body = lipgloss.NewStyle().
			Foreground(t.TextPrimary).
			Render(partial)
	}
	// Clamp the live preview to a few lines so the composer +
	// status stay visible.  Long previews trim to the last ~8
	// lines; the full response lands in scrollback at end.
	lines := strings.Split(body, "\n")
	if len(lines) > 8 {
		lines = append([]string{
			lipgloss.NewStyle().
				Foreground(t.TextDim).
				Render(fmt.Sprintf(
					"  ⋯ (%d lines above)",
					len(lines)-8)),
		}, lines[len(lines)-8:]...)
		body = strings.Join(lines, "\n")
	}
	border := lipgloss.NewStyle().
		Foreground(t.AccentAI).
		Bold(true).
		Render("❯ akande")
	return border + "\n" + body
}

// renderComposer wraps the textarea view in a rounded border.
func (t Theme) renderComposer(view string, width int) string {
	style := lipgloss.NewStyle().
		Padding(0, 1).
		Margin(1, 0, 0, 0).
		Foreground(t.TextPrimary).
		BorderStyle(lipgloss.RoundedBorder()).
		BorderForeground(t.TextDim)
	if width > 4 {
		style = style.Width(width - 2)
	}
	return style.Render(view)
}

// renderStatus renders the one-line status bar at the bottom of
// the program's footer.
func (t Theme) renderStatus(left, right string, width int) string {
	if width < 4 {
		return left + "  " + right
	}
	gap := width - lipgloss.Width(left) - lipgloss.Width(right) - 2
	if gap < 1 {
		gap = 1
	}
	combined := left + strings.Repeat(" ", gap) + right
	return lipgloss.NewStyle().
		Padding(0, 1).
		Foreground(t.TextMuted).
		Render(combined)
}

// renderHelp is the dim shortcut row below the status bar.
func (t Theme) renderHelp(width int) string {
	keyStyle := lipgloss.NewStyle().
		Foreground(t.AccentAI).
		Bold(true)
	descStyle := lipgloss.NewStyle().
		Foreground(t.TextDim)
	pairs := []struct{ k, d string }{
		{"Enter", "send"},
		{"Esc", "quit / cancel"},
		{"Ctrl+C", "quit"},
	}
	var parts []string
	for _, p := range pairs {
		parts = append(parts,
			keyStyle.Render(p.k)+" "+descStyle.Render(p.d))
	}
	return lipgloss.NewStyle().
		Padding(0, 2).
		Render(strings.Join(parts, "   "))
}

// renderNote is a labelled scrollback note (e.g. for AI
// disclosures or tool-call events).
func (t Theme) renderNote(label, content string) string {
	tag := lipgloss.NewStyle().
		Foreground(t.AccentInfo).
		Bold(true).
		Render("• " + label)
	body := lipgloss.NewStyle().
		Foreground(t.TextMuted).
		Render(content)
	return tag + "\n" + body
}

// helpTitle is the section heading inside the `/help` block.
func (t Theme) helpTitle(s string) string {
	return lipgloss.NewStyle().
		Foreground(t.AccentAI).
		Bold(true).
		Render(s)
}

// helpRow is a `  /name      description` row inside `/help`.
func (t Theme) helpRow(left, right string) string {
	pad := 18 - lipgloss.Width(left)
	if pad < 1 {
		pad = 1
	}
	return "  " + lipgloss.NewStyle().
		Foreground(t.TextPrimary).
		Bold(true).
		Render(left) +
		strings.Repeat(" ", pad) +
		lipgloss.NewStyle().
			Foreground(t.TextMuted).
			Render(right)
}

// renderError prints a labelled error block into scrollback.
func (t Theme) renderError(msg string) string {
	tag := lipgloss.NewStyle().
		Foreground(t.AccentError).
		Bold(true).
		Render("✗ error")
	body := lipgloss.NewStyle().
		Foreground(t.AccentError).
		Render(msg)
	return tag + "\n" + body
}
