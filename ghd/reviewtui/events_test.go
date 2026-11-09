package main

import (
	"reflect"
	"testing"
)

func TestParse(t *testing.T) {
	for _, tc := range []struct {
		line string
		want Event
	}{
		{`{"type":"text","part":{"text":"Reading the packet"}}`, Event{Text: "Reading the packet\n"}},
		{`{"type":"tool_use","part":{"tool":"subagent","state":{"input":{"description":"Security pass"},"status":"completed"}}}`, Event{Tool: "subagent: Security pass"}},
		{`{"type":"step_finish","part":{"cost":0.12}}`, Event{Cost: 0.12}},
		{`{"type":"error","error":{"name":"APIError","data":{"message":"Token expired"}}}`, Event{Error: "Token expired"}},
		{`{"type":"error","error":{"name":"UnknownError"}}`, Event{Error: "OpenCode reported an error"}},
		{`{"type":"agent_settled","aborted":false}`, Event{Done: true}},
		{`Warning: plain text`, Event{Text: "Warning: plain text\n"}},
	} {
		if got := Parse(tc.line); !reflect.DeepEqual(got, tc.want) {
			t.Errorf("%s: got %+v want %+v", tc.line, got, tc.want)
		}
	}
}
