package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func savedReview(t *testing.T, meta Meta, findings []Finding) *model {
	t.Helper()
	out := filepath.Join(t.TempDir(), "review")
	metaJSON, _ := json.Marshal(meta)
	os.WriteFile(out+".json", metaJSON, 0o644)
	findingsJSON, _ := json.Marshal(Review{TLDR: "T", Findings: findings})
	os.WriteFile(out+".findings", findingsJSON, 0o644)
	m, err := newModel(out, "/lib", nil)
	if err != nil {
		t.Fatal(err)
	}
	m.Update(tea.WindowSizeMsg{Width: 120, Height: 40})
	return m
}

func TestResumeBuildsTheReviewerCommand(t *testing.T) {
	cwd := t.TempDir()
	for _, tc := range []struct {
		tool string
		want []string
	}{
		{"pi", []string{"pi", "--session", "s1"}},
		{"claude", []string{"claude", "--resume", "s1", "--setting-sources", "user", "--mcp-config", "/lib/mcp.json", "--add-dir"}},
		{"opencode", []string{"opencode", "--session", "s1"}},
	} {
		m := savedReview(t, Meta{Repo: "o/r", PR: 1, Tool: tc.tool, Session: "s1", Cwd: cwd}, nil)
		cmd, status := m.resumeCommand()
		if cmd == nil || status != "" || cmd.Dir != cwd {
			t.Fatalf("%s: cmd %v status %q", tc.tool, cmd, status)
		}
		for i, want := range tc.want {
			if i >= len(cmd.Args) || !strings.HasSuffix(cmd.Args[i], want) {
				t.Fatalf("%s: got %v want prefix %v", tc.tool, cmd.Args, tc.want)
			}
		}
	}
}

func TestResumeExplainsWhyItCannotContinue(t *testing.T) {
	for _, tc := range []struct {
		meta   Meta
		status string
	}{
		{Meta{Tool: "pi"}, "saved by hand"},
		{Meta{Tool: "pi", Session: "s", Cwd: "/nonexistent/worktree"}, "worktree is gone"},
		{Meta{Tool: "codex", Session: "s", Cwd: os.TempDir()}, "codex"},
	} {
		m := savedReview(t, tc.meta, nil)
		if cmd, status := m.resumeCommand(); cmd != nil || !strings.Contains(status, tc.status) {
			t.Fatalf("%+v: cmd %v status %q", tc.meta, cmd, status)
		}
	}
}

func TestPostPassesTheSelectedPositions(t *testing.T) {
	findings := []Finding{
		{File: "a", Line: 1, Category: "quality", Severity: "P3", Title: "nit"},
		{File: "b", Line: 2, Category: "bug", Severity: "P1", Title: "bug"},
		{File: "c", Line: 3, Category: "bug", Severity: "P2", Title: "bug2"},
	}
	m := savedReview(t, Meta{Repo: "o/r", PR: 7, Tool: "pi"}, findings)
	cmd, _ := m.postCommand()
	joined := strings.Join(cmd.Args, " ")
	if cmd.Args[1] != "/lib/post.py" || !strings.Contains(joined, "o/r 7 --review") || !strings.HasSuffix(joined, "--pick 2,3") {
		t.Fatalf("got %v", cmd.Args)
	}
	m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'n'}})
	if cmd, status := m.postCommand(); cmd != nil || status != "nothing selected" {
		t.Fatalf("expected nothing selected, got %q", status)
	}
}

func TestSelectionKeys(t *testing.T) {
	findings := []Finding{{Severity: "P3", Category: "quality"}, {Severity: "P1", Category: "bug"}}
	m := savedReview(t, Meta{Tool: "pi"}, findings)
	if Picks(m.selected) != "2" {
		t.Fatalf("preselection %q", Picks(m.selected))
	}
	press := func(r rune) { m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}}) }
	press(' ') // cursor is on the P1 finding (first in severity order)
	if Picks(m.selected) != "" {
		t.Fatalf("toggle off: %q", Picks(m.selected))
	}
	press('j')
	press(' ')
	if Picks(m.selected) != "1" {
		t.Fatalf("toggle P3 on: %q", Picks(m.selected))
	}
	press('a')
	if Picks(m.selected) != "1,2" {
		t.Fatalf("all: %q", Picks(m.selected))
	}
}

func TestReadPasses(t *testing.T) {
	path := filepath.Join(t.TempDir(), "p.progress")
	os.WriteFile(path, []byte(`{"kind":"agent_start","label":"risk"}
{"kind":"tool","label":"read"}
{"kind":"agent_start","label":"quality"}
{"kind":"agent_end","label":"risk"}
`), 0o644)
	passes := readPasses(path)
	if len(passes) != 2 || passes[0] != (pass{"risk", true}) || passes[1] != (pass{"quality", false}) {
		t.Fatalf("got %+v", passes)
	}
}
