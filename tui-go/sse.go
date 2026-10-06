// Copyright (C) 2026 Sebastien Rousseau.
// Licensed under the Apache License, Version 2.0.

package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// StreamEvent is one decoded SSE record from the /stream endpoint.
type StreamEvent struct {
	Type           string `json:"type"` // delta|done|error|meta|disclosure|tool_call
	Content        string `json:"content,omitempty"`
	Message        string `json:"message,omitempty"`
	ConversationID string `json:"conversation_id,omitempty"`
	// tool_call extras
	Name string `json:"name,omitempty"`
}

// openStream POSTs the question to /stream and pushes every
// decoded SSE event onto ch until EOF or ctx cancellation.  The
// channel is always closed before openStream returns.
func openStream(
	ctx context.Context,
	cfg Config,
	question string,
	conversationID string,
	ch chan<- StreamEvent,
) {
	defer close(ch)

	body := map[string]string{"question": question}
	if conversationID != "" {
		body["conversation_id"] = conversationID
	}
	buf, _ := json.Marshal(body)

	req, err := http.NewRequestWithContext(
		ctx, http.MethodPost,
		cfg.ServerURL+"/stream",
		bytes.NewReader(buf),
	)
	if err != nil {
		ch <- StreamEvent{Type: "error",
			Message: fmt.Sprintf("request: %v", err)}
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Requested-With", "AkandeApp")
	req.Header.Set("Accept", "text/event-stream")

	// Streaming has no overall deadline — ctx controls cancellation.
	client := &http.Client{Timeout: 0}
	resp, err := client.Do(req)
	if err != nil {
		ch <- StreamEvent{Type: "error",
			Message: fmt.Sprintf("connect: %v", err)}
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		ch <- StreamEvent{Type: "error",
			Message: fmt.Sprintf(
				"server returned %s",
				resp.Status,
			)}
		return
	}

	reader := bufio.NewReader(resp.Body)
	var data strings.Builder
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		line, err := reader.ReadString('\n')
		if err != nil {
			if err == io.EOF && data.Len() > 0 {
				dispatch(data.String(), ch)
			}
			return
		}
		line = strings.TrimRight(line, "\n")
		// Blank line ends an event.
		if line == "" {
			if data.Len() == 0 {
				continue
			}
			dispatch(data.String(), ch)
			data.Reset()
			continue
		}
		if strings.HasPrefix(line, "data:") {
			payload := strings.TrimSpace(strings.TrimPrefix(
				line, "data:"))
			if data.Len() > 0 {
				data.WriteByte('\n')
			}
			data.WriteString(payload)
		}
		// SSE comments / other fields are ignored.
	}
}

func dispatch(raw string, ch chan<- StreamEvent) {
	var ev StreamEvent
	if err := json.Unmarshal([]byte(raw), &ev); err != nil {
		ch <- StreamEvent{Type: "error",
			Message: fmt.Sprintf(
				"decode: %v (%q)", err, raw),
		}
		return
	}
	ch <- ev
}
