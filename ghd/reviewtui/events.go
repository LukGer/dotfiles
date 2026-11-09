package main

import (
	"encoding/json"
	"fmt"
	"strings"
)

// Event is what one line of a harness's JSON stream means for the transcript.
type Event struct {
	Text  string  // assistant text to append
	Tool  string  // a top-level tool call line, e.g. "review_pass: security"
	Cost  float64 // cumulative cost of a finished assistant message
	Error string  // provider or agent error ending the run
	Done  bool    // agent_settled
}

var detailKeys = []string{"specialist", "description", "title", "path", "command", "pattern", "code"}

// Parse interprets one JSON line from a harness. Lines that are not JSON are shown verbatim.
func Parse(line string) Event {
	var raw struct {
		Type string `json:"type"`
		Part struct {
			Text  string  `json:"text"`
			Tool  string  `json:"tool"`
			Cost  float64 `json:"cost"`
			State struct {
				Input map[string]any `json:"input"`
			} `json:"state"`
		} `json:"part"`
		Error struct {
			Message string `json:"message"`
			Data    struct {
				Message string `json:"message"`
			} `json:"data"`
		} `json:"error"`
	}
	if err := json.Unmarshal([]byte(line), &raw); err != nil {
		return Event{Text: line + "\n"}
	}
	switch raw.Type {
	case "text":
		return Event{Text: raw.Part.Text + "\n"}
	case "tool_use":
		return Event{Tool: fmt.Sprintf("%s: %s", raw.Part.Tool, detail(raw.Part.State.Input))}
	case "step_finish":
		return Event{Cost: raw.Part.Cost}
	case "error":
		message := raw.Error.Message
		if message == "" {
			message = raw.Error.Data.Message
		}
		if message == "" {
			message = "OpenCode reported an error"
		}
		return Event{Error: message}
	case "agent_settled":
		return Event{Done: true}
	}
	return Event{}
}

func detail(args map[string]any) string {
	for _, key := range detailKeys {
		if value, ok := args[key].(string); ok && value != "" {
			first := strings.SplitN(strings.TrimSpace(value), "\n", 2)[0]
			if len(first) > 100 {
				return first[:100] + "…"
			}
			return first
		}
	}
	return ""
}
