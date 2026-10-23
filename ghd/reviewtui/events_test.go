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
		{`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"Hi"}}`, Event{Text: "Hi"}},
		{`{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","delta":"hm"}}`, Event{}},
		{`{"type":"tool_execution_start","toolCallId":"1","toolName":"bash","args":{"command":"git log\n--oneline"}}`, Event{Tool: "bash: git log"}},
		{`{"type":"tool_execution_start","toolCallId":"1/1","parentToolCallId":"1","toolName":"read","args":{"path":"a"}}`, Event{}},
		{`{"type":"tool_execution_start","toolCallId":"2","toolName":"review_pass","args":{"specialist":"risk","scope":"s"}}`, Event{Tool: "review_pass: risk"}},
		{`{"type":"tool_execution_start","toolCallId":"3","toolName":"finish_review","args":{"tldr":"x"}}`, Event{Tool: "finish_review: "}},
		{`{"type":"message_end","message":{"role":"assistant","stopReason":"stop","usage":{"cost":{"total":0.25}}}}`, Event{Cost: 0.25}},
		{`{"type":"message_end","message":{"role":"assistant","stopReason":"error","errorMessage":"boom"}}`, Event{Error: "boom"}},
		{`{"type":"message_end","message":{"role":"assistant","stopReason":"error"}}`, Event{Error: "pi reported an error"}},
		{`{"type":"message_end","message":{"role":"user"}}`, Event{}},
		{`{"type":"agent_settled","aborted":false}`, Event{Done: true}},
		{`Warning: plain text`, Event{Text: "Warning: plain text\n"}},
	} {
		if got := Parse(tc.line); !reflect.DeepEqual(got, tc.want) {
			t.Errorf("%s: got %+v want %+v", tc.line, got, tc.want)
		}
	}
}
