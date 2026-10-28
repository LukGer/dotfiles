package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/ansi"
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
	if cmd.Args[1] != "/lib/post.py" || !strings.Contains(joined, "o/r 7 --json --review") || !strings.HasSuffix(joined, "--pick 2,3") {
		t.Fatalf("got %v", cmd.Args)
	}
	m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'n'}})
	if cmd, status := m.postCommand(); cmd != nil || status != "nothing selected" {
		t.Fatalf("expected nothing selected, got %q", status)
	}
}

func TestPostStaysInTheReviewScreen(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(fmt.Sprint(fail), func(t *testing.T) {
			m := savedReview(t, Meta{Repo: "o/r", PR: 7}, []Finding{{Severity: "P1", Category: "bug"}})
			m.lib = t.TempDir()
			positions := "[1]"
			if fail {
				positions = "[]"
			}
			script := "import sys\nassert sys.stdin.read() == ''\nprint('{\"message\": \"Result from Python\", \"posted\": " + positions + "}')\n"
			if fail {
				script += "sys.exit(1)\n"
			}
			os.WriteFile(filepath.Join(m.lib, "post.py"), []byte(script), 0o600)
			_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'p'}})
			if cmd == nil || !strings.Contains(m.View(), "Posting") {
				t.Fatal("post did not start inside the review screen")
			}
			if _, duplicate := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'p'}}); duplicate != nil {
				t.Fatal("posting twice started a duplicate request")
			}
			m.Update(cmd())
			if !strings.Contains(m.View(), "Result from Python") {
				t.Fatalf("post result is missing: %s", m.View())
			}
			if got := Picks(m.selected); (got != "") != fail {
				t.Fatalf("selection after posting: %q", got)
			}
			m.Update(tea.KeyMsg{Type: tea.KeyEnter})
			if m.mode != reviewing {
				t.Fatal("enter did not return to findings")
			}
		})
	}
}

func TestPartialPostKeepsOnlyUnpostedFindingsSelected(t *testing.T) {
	m := savedReview(t, Meta{}, []Finding{
		{Severity: "P1", Category: "bug"},
		{Severity: "P1", Category: "bug"},
		{Severity: "P1", Category: "bug"},
	})
	m.Update(postDoneMsg{output: "One thread failed", posted: []int{1, 3}, err: fmt.Errorf("exit status 1")})
	if got := Picks(m.selected); got != "2" {
		t.Fatalf("partial post left %q selected", got)
	}
	m.Update(tea.WindowSizeMsg{Width: 80, Height: 20})
	if !strings.Contains(m.View(), "One thread failed") {
		t.Fatal("resizing lost the posting report")
	}
	m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	if m.detail.Width != m.width-m.listWidth()-3 {
		t.Fatal("returning to findings did not restore the detail pane width")
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

func TestHeaderShowsTheInstructionsTheReviewRanWith(t *testing.T) {
	for _, tc := range []struct {
		instructions string
		want         string
	}{
		{"", ""},
		{"Only a.go.\n  Skip tests.", "Instructions: Only a.go. Skip tests."},
	} {
		m := savedReview(t, Meta{Repo: "o/r", PR: 1, Tool: "pi", Instructions: tc.instructions}, nil)
		if got := strings.Contains(m.View(), "Instructions:"); got != (tc.want != "") || !strings.Contains(m.View(), tc.want) {
			t.Fatalf("%q: view:\n%s", tc.instructions, m.View())
		}
	}
}

func TestMouseWheelScrollsReviewDetail(t *testing.T) {
	for _, fullReview := range []bool{false, true} {
		t.Run(fmt.Sprintf("fullReview=%t", fullReview), func(t *testing.T) {
			text := strings.Repeat("Review line\n\n", 80) + "last line"
			m := savedReview(t, Meta{}, []Finding{{Comment: text}})
			if fullReview {
				if err := os.WriteFile(m.out+".md", []byte(text), 0o644); err != nil {
					t.Fatal(err)
				}
				m.Update(tea.KeyMsg{Type: tea.KeyTab})
			}
			m.Update(tea.MouseMsg{X: 100, Y: 10, Button: tea.MouseButtonWheelDown, Action: tea.MouseActionPress})
			if m.detail.YOffset == 0 {
				t.Fatal("mouse wheel did not scroll the detail pane")
			}
			m.Update(tea.MouseMsg{X: 100, Y: 10, Button: tea.MouseButtonWheelUp, Action: tea.MouseActionPress})
			if m.detail.YOffset != 0 {
				t.Fatal("mouse wheel did not scroll back to the top")
			}
		})
	}
}

func TestReviewDetailWrapsWithoutLosingText(t *testing.T) {
	long := strings.Repeat("abcdefghijklmnop", 12) + "END"
	for _, tc := range []struct {
		name    string
		finding Finding
		md      string
	}{
		{name: "file", finding: Finding{File: long, Line: 1}},
		{name: "title", finding: Finding{Title: long}},
		{name: "comment", finding: Finding{Comment: long}},
		{name: "evidence", finding: Finding{Detail: "`" + long + "`"}},
		{name: "code", finding: Finding{Detail: "```go\n" + long + "\n```"}},
		{name: "review", md: "# Review\n\n" + long},
		{name: "table", md: "| Pointer | Comment |\n| --- | --- |\n| file.go | `" + long + "` |"},
	} {
		for _, width := range []int{80, 120} {
			t.Run(fmt.Sprintf("%s/%d", tc.name, width), func(t *testing.T) {
				m := savedReview(t, Meta{}, []Finding{tc.finding})
				m.Update(tea.WindowSizeMsg{Width: width, Height: 12})
				if tc.md != "" {
					if err := os.WriteFile(m.out+".md", []byte(tc.md), 0o644); err != nil {
						t.Fatal(err)
					}
					m.Update(tea.KeyMsg{Type: tea.KeyTab})
				}
				var pages strings.Builder
				pages.WriteString(ansi.Strip(m.detail.View()))
				for {
					before := m.detail.YOffset
					m.Update(tea.KeyMsg{Type: tea.KeyPgDown})
					if m.detail.YOffset == before {
						break
					}
					lines := strings.Split(ansi.Strip(m.detail.View()), "\n")
					pages.WriteString("\n" + strings.Join(lines[len(lines)-(m.detail.YOffset-before):], "\n"))
				}
				visible := strings.ReplaceAll(strings.Join(strings.Fields(pages.String()), ""), "|", "")
				if !strings.Contains(visible, long) {
					t.Fatalf("text was clipped instead of wrapped: %q", pages.String())
				}
			})
		}
	}
}

func TestScrollbarDragsPane(t *testing.T) {
	for _, pane := range []string{"finding", "review", "transcript"} {
		t.Run(pane, func(t *testing.T) {
			text := strings.Repeat("Review line\n\n", 80) + "last line"
			m := savedReview(t, Meta{}, []Finding{{Comment: text}})
			v := &m.detail
			switch pane {
			case "review":
				if err := os.WriteFile(m.out+".md", []byte(text), 0o644); err != nil {
					t.Fatal(err)
				}
				m.Update(tea.KeyMsg{Type: tea.KeyTab})
			case "transcript":
				m.mode, m.follow = running, false
				m.transcript.WriteString(text)
				m.layout()
				v = &m.log
			}
			view := strings.Split(ansi.Strip(m.View()), "\n")
			if !strings.HasSuffix(view[3], "█") {
				t.Fatal("scrollable pane has no scrollbar thumb at the top")
			}
			m.Update(tea.MouseMsg{X: m.width - 1, Y: 3, Button: tea.MouseButtonLeft, Action: tea.MouseActionPress})
			m.Update(tea.MouseMsg{X: m.width - 10, Y: 3 + v.Height - 1, Button: tea.MouseButtonLeft, Action: tea.MouseActionMotion})
			if !v.AtBottom() {
				t.Fatal("dragging the scrollbar did not reach the bottom")
			}
			view = strings.Split(ansi.Strip(m.View()), "\n")
			if !strings.HasSuffix(view[3+v.Height-1], "█") {
				t.Fatal("scrollbar thumb did not move to the bottom")
			}
			m.Update(tea.MouseMsg{X: 0, Y: 0, Action: tea.MouseActionRelease})
			m.Update(tea.MouseMsg{X: m.width - 1, Y: 3, Button: tea.MouseButtonLeft, Action: tea.MouseActionMotion})
			if !v.AtBottom() {
				t.Fatal("scrollbar kept dragging after release")
			}
			if pane == "transcript" && !m.follow {
				t.Fatal("scrolling to the bottom did not resume following")
			}
			m.Update(tea.MouseMsg{X: m.width - 1, Y: 3, Button: tea.MouseButtonLeft, Action: tea.MouseActionPress})
			if !v.AtTop() {
				t.Fatal("clicking the top of the track did not scroll to the top")
			}
			if pane == "transcript" && m.follow {
				t.Fatal("scrolling away from the bottom did not stop following")
			}
		})
	}
}

func TestReviewViewFitsTerminal(t *testing.T) {
	for _, width := range []int{60, 80, 120} {
		t.Run(fmt.Sprint(width), func(t *testing.T) {
			findings := make([]Finding, 50)
			for i := range findings {
				findings[i] = Finding{Title: fmt.Sprintf("finding%d", i), Comment: strings.Repeat("\tcode", 20)}
			}
			m := savedReview(t, Meta{Repo: "owner/repo", Title: strings.Repeat("Long PR title ", 20)}, findings)
			m.Update(tea.WindowSizeMsg{Width: width, Height: 20})
			m.Update(tea.KeyMsg{Type: tea.KeyUp})
			lines := strings.Split(m.View(), "\n")
			if len(lines) > m.height {
				t.Fatalf("view has %d rows in a %d-row terminal", len(lines), m.height)
			}
			var list strings.Builder
			for _, line := range lines {
				if ansi.StringWidth(line) > m.width {
					t.Fatalf("view has a %d-column row in a %d-column terminal", ansi.StringWidth(line), m.width)
				}
				list.WriteString(ansi.Strip(ansi.Cut(line, 0, m.listWidth())) + "\n")
			}
			if !strings.Contains(list.String(), "finding49") {
				t.Fatal("selected finding is outside the visible list")
			}
		})
	}
}
