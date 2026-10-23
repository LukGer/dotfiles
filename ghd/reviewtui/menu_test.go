package main

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func press(m *menuModel, keys ...tea.KeyMsg) (quit bool) {
	for _, key := range keys {
		_, cmd := m.Update(key)
		if cmd != nil {
			if _, ok := cmd().(tea.QuitMsg); ok {
				return true
			}
		}
	}
	return false
}

func runes(text string) tea.KeyMsg { return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(text)} }

var (
	enter    = tea.KeyMsg{Type: tea.KeyEnter}
	esc      = tea.KeyMsg{Type: tea.KeyEsc}
	down     = tea.KeyMsg{Type: tea.KeyDown}
	newline  = tea.KeyMsg{Type: tea.KeyEnter, Alt: true}
	cancelCC = tea.KeyMsg{Type: tea.KeyCtrlC}
)

func TestMenuChoices(t *testing.T) {
	for _, tc := range []struct {
		name string
		keys []tea.KeyMsg
		want *menuResult
	}{
		{"number picks a model, enter starts without instructions", []tea.KeyMsg{runes("1"), enter},
			&menuResult{Action: "review", Model: "openai-codex/gpt-6.1-sol:high"}},
		{"arrows and enter pick a model", []tea.KeyMsg{down, enter, enter},
			&menuResult{Action: "review", Model: "anthropic/claude-opus-5-5:high"}},
		{"typed instructions travel with the model, q included", []tea.KeyMsg{runes("2"), runes("quality only"), newline, runes("skip gen/"), enter},
			&menuResult{Action: "review", Model: "anthropic/claude-opus-5-5:high", Instructions: "quality only\nskip gen/"}},
		{"surrounding blank space is dropped", []tea.KeyMsg{runes("1"), runes("  "), newline, runes("a.go only "), enter},
			&menuResult{Action: "review", Model: "openai-codex/gpt-6.1-sol:high", Instructions: "a.go only"}},
		{"esc returns to the list and keeps the draft", []tea.KeyMsg{runes("1"), runes("x"), esc, runes("2"), enter},
			&menuResult{Action: "review", Model: "anthropic/claude-opus-5-5:high", Instructions: "x"}},
		{"past reviews need no instructions", []tea.KeyMsg{runes("3")}, &menuResult{Action: "past"}},
		{"posting needs no instructions", []tea.KeyMsg{down, down, down, enter}, &menuResult{Action: "post"}},
		{"q cancels the list", []tea.KeyMsg{runes("q")}, nil},
		{"esc cancels the list", []tea.KeyMsg{esc}, nil},
		{"ctrl+c cancels while writing instructions", []tea.KeyMsg{runes("1"), runes("x"), cancelCC}, nil},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m := newMenuModel()
			m.Update(tea.WindowSizeMsg{Width: 70, Height: 14})
			if !press(m, tc.keys...) {
				t.Fatalf("menu did not quit; view:\n%s", m.View())
			}
			if (tc.want == nil) != (m.result == nil) || tc.want != nil && *tc.want != *m.result {
				t.Fatalf("got %+v want %+v", m.result, tc.want)
			}
		})
	}
}

func TestMenuShowsTheInstructionsStepForTheChosenModel(t *testing.T) {
	m := newMenuModel()
	m.Update(tea.WindowSizeMsg{Width: 70, Height: 14})
	for _, label := range []string{"GPT-6.1 Sol", "Opus 5.5", "pi", "Past reviews of this PR", "Post to GitHub (pending)"} {
		if !strings.Contains(m.View(), label) {
			t.Fatalf("list lacks %q:\n%s", label, m.View())
		}
	}
	if press(m, runes("2")) {
		t.Fatal("choosing a model quit before asking for instructions")
	}
	view := m.View()
	for _, text := range []string{"Opus 5.5", "Instructions", "enter start"} {
		if !strings.Contains(view, text) {
			t.Fatalf("instructions step lacks %q:\n%s", text, view)
		}
	}
}
