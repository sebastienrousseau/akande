// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import "github.com/charmbracelet/lipgloss"

// Theme centralises every Lipgloss style the TUI uses.  Tokens
// match the v0.0.6 design system shared with the Python TUI and
// the Web UI so the three surfaces stay visually consistent.
//
// Colours are adaptive — Lipgloss picks the dark variant when the
// terminal background is dark, the light variant otherwise.
type Theme struct {
	BgPage       lipgloss.AdaptiveColor
	BgPanel      lipgloss.AdaptiveColor
	Border       lipgloss.AdaptiveColor
	TextPrimary  lipgloss.AdaptiveColor
	TextMuted    lipgloss.AdaptiveColor
	TextDim      lipgloss.AdaptiveColor
	AccentUser   lipgloss.AdaptiveColor
	AccentAI     lipgloss.AdaptiveColor
	AccentInfo   lipgloss.AdaptiveColor
	AccentOK     lipgloss.AdaptiveColor
	AccentWarn   lipgloss.AdaptiveColor
	AccentError  lipgloss.AdaptiveColor

	// Composed styles
	Header     lipgloss.Style
	HeaderSub  lipgloss.Style
	StatusBar  lipgloss.Style
	StatusOk   lipgloss.Style
	StatusInfo lipgloss.Style
	BubbleUser lipgloss.Style
	BubbleAI   lipgloss.Style
	BubbleErr  lipgloss.Style
	BubbleFile lipgloss.Style
	RoleBadge  lipgloss.Style
	Composer   lipgloss.Style
	HelpKey    lipgloss.Style
	HelpDesc   lipgloss.Style
}

func newTheme() Theme {
	t := Theme{
		BgPage: lipgloss.AdaptiveColor{
			Light: "#fafafa", Dark: "#0f0f10"},
		BgPanel: lipgloss.AdaptiveColor{
			Light: "#ffffff", Dark: "#18181b"},
		Border: lipgloss.AdaptiveColor{
			Light: "#e5e5e7", Dark: "#2a2a2e"},
		TextPrimary: lipgloss.AdaptiveColor{
			Light: "#1d1d1f", Dark: "#f5f5f7"},
		TextMuted: lipgloss.AdaptiveColor{
			Light: "#86868b", Dark: "#98989d"},
		TextDim: lipgloss.AdaptiveColor{
			Light: "#aeaeb2", Dark: "#636366"},
		AccentUser: lipgloss.AdaptiveColor{
			Light: "#007aff", Dark: "#0a84ff"},
		AccentAI: lipgloss.AdaptiveColor{
			Light: "#af52de", Dark: "#bf5af2"},
		AccentInfo: lipgloss.AdaptiveColor{
			Light: "#5ac8fa", Dark: "#64d2ff"},
		AccentOK: lipgloss.AdaptiveColor{
			Light: "#34c759", Dark: "#32d74b"},
		AccentWarn: lipgloss.AdaptiveColor{
			Light: "#ff9500", Dark: "#ff9f0a"},
		AccentError: lipgloss.AdaptiveColor{
			Light: "#ff3b30", Dark: "#ff453a"},
	}

	base := lipgloss.NewStyle()

	t.Header = base.
		Bold(true).
		Padding(0, 2).
		Foreground(t.TextPrimary).
		Background(t.BgPanel).
		BorderStyle(lipgloss.NormalBorder()).
		BorderBottom(true).
		BorderForeground(t.Border)

	t.HeaderSub = base.
		Foreground(t.TextMuted).
		Background(t.BgPanel)

	t.StatusBar = base.
		Padding(0, 2).
		Foreground(t.TextMuted).
		Background(t.BgPanel).
		BorderStyle(lipgloss.NormalBorder()).
		BorderTop(true).
		BorderForeground(t.Border)

	t.StatusOk = base.Foreground(t.AccentOK).Bold(true)
	t.StatusInfo = base.Foreground(t.AccentAI).Bold(true)

	bubbleBase := base.
		Padding(0, 1).
		Margin(0, 0, 1, 0).
		Foreground(t.TextPrimary).
		BorderStyle(lipgloss.ThickBorder()).
		BorderLeft(true)

	t.BubbleUser = bubbleBase.BorderForeground(t.AccentUser)
	t.BubbleAI = bubbleBase.BorderForeground(t.AccentAI)
	t.BubbleErr = bubbleBase.BorderForeground(t.AccentError).
		Foreground(t.AccentError)
	t.BubbleFile = bubbleBase.BorderForeground(t.AccentOK).
		Foreground(t.TextMuted)

	t.RoleBadge = base.Bold(true).
		Margin(0, 0, 0, 1)

	t.Composer = base.
		Padding(0, 1).
		BorderStyle(lipgloss.RoundedBorder()).
		BorderForeground(t.Border)

	t.HelpKey = base.Foreground(t.AccentAI).Bold(true)
	t.HelpDesc = base.Foreground(t.TextMuted)

	return t
}
