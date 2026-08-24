// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"os"
	"strings"
)

// ProviderCandidate is one entry in the in-TUI picker that
// replaces the launcher's bare `Choice (1-N):` shell prompt.
//
// The launcher script (.git/v0.0.7-run.sh) detects which
// providers are usable on the host — env vars set, CLIs
// installed, local servers reachable — and exports them as
// `AKANDE_PROVIDER_CANDIDATES="name1:reason1|name2:reason2"`.
// The TUI parses that envelope and shows the list.
type ProviderCandidate struct {
	Name        string // e.g. "claude_cli"
	Description string // why it is available (env var, CLI, …)
	Model       string // recommended default model for this provider
}

// defaultModelFor mirrors the launcher's `pick_default_model`
// helper so the TUI can preselect a sensible model.  Callers can
// still override via `/model <name>` once they are in the chat.
func defaultModelFor(provider string) string {
	switch provider {
	case "openai":
		return "gpt-4o-mini"
	case "anthropic":
		return "claude-3-5-haiku-latest"
	case "google":
		return "gemini-1.5-flash"
	case "mistral":
		return "mistral-small-latest"
	case "cohere":
		return "command-r"
	case "groq":
		return "llama-3.1-8b-instant"
	case "huggingface":
		return "mistralai/Mistral-7B-Instruct-v0.2"
	case "azure_openai":
		return "gpt-35-turbo"
	case "claude_cli":
		return "sonnet"
	case "codex_cli":
		return "gpt-5-codex"
	case "copilot_cli":
		return "auto"
	case "antigravity_cli":
		return "gemini-2.5-pro"
	case "ollama":
		return "llama3.2:1b"
	case "lmstudio":
		return "local-model"
	}
	return ""
}

// loadProviderCandidates parses the `AKANDE_PROVIDER_CANDIDATES`
// env var the launcher exports for the `go` mode.  Returns nil
// when nothing was passed; callers should fall back to whatever
// LLM_PROVIDER is in env in that case.
func loadProviderCandidates() []ProviderCandidate {
	raw := os.Getenv("AKANDE_PROVIDER_CANDIDATES")
	if raw == "" {
		return nil
	}
	var out []ProviderCandidate
	for _, entry := range strings.Split(raw, "|") {
		entry = strings.TrimSpace(entry)
		if entry == "" {
			continue
		}
		name, desc, _ := strings.Cut(entry, ":")
		name = strings.TrimSpace(name)
		desc = strings.TrimSpace(desc)
		if name == "" {
			continue
		}
		out = append(out, ProviderCandidate{
			Name:        name,
			Description: desc,
			Model:       defaultModelFor(name),
		})
	}
	return out
}
