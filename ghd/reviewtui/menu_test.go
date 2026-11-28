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
			&menuResult{Action: "review", Model: "openai/gpt-6.2-sol#high"}},
		{"arrows and enter pick a model", []tea.KeyMsg{down, enter, enter},
			&menuResult{Action: "review", Model: "claude-agent/opus#high"}},
		{"typed instructions travel with the model, q included", []tea.KeyMsg{runes("2"), runes("quality only"), newline, runes("skip gen/"), enter},
			&menuResult{Action: "review", Model: "claude-agent/opus#high", Instructions: "quality only\nskip gen/"}},
		{"surrounding blank space is dropped", []tea.KeyMsg{runes("1"), runes("  "), newline, runes("a.go only "), enter},
			&menuResult{Action: "review", Model: "openai/gpt-6.2-sol#high", Instructions: "a.go only"}},
		{"esc returns to the list and keeps the draft", []tea.KeyMsg{runes("1"), runes("x"), esc, runes("2"), enter},
			&menuResult{Action: "review", Model: "claude-agent/opus#high", Instructions: "x"}},
		{"f switches GPT to its fast model", []tea.KeyMsg{runes("f"), runes("1"), enter},
			&menuResult{Action: "review", Model: "openai/gpt-6.2-sol-fast#high"}},
		{"f again switches fast mode off", []tea.KeyMsg{runes("f"), runes("f"), runes("1"), enter},
			&menuResult{Action: "review", Model: "openai/gpt-6.2-sol#high"}},
		{"fast mode leaves Opus as it is", []tea.KeyMsg{runes("f"), runes("2"), enter},
			&menuResult{Action: "review", Model: "claude-agent/opus#high"}},
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
	for _, label := range []string{"GPT-6.2 Sol", "Opus (Claude Code)", "OpenCode", "Past reviews of this PR", "Post to GitHub"} {
		if !strings.Contains(m.View(), label) {
			t.Fatalf("list lacks %q:\n%s", label, m.View())
		}
	}
	if press(m, runes("2")) {
		t.Fatal("choosing a model quit before asking for instructions")
	}
	view := m.View()
	for _, text := range []string{"Opus (Claude Code)", "Instructions", "enter start"} {
		if !strings.Contains(view, text) {
			t.Fatalf("instructions step lacks %q:\n%s", text, view)
		}
	}
}

func TestChatMenuOffersFastMode(t *testing.T) {
	m := newMenuModel()
	m.items, m.chat = modelItems, true
	if !press(m, runes("f"), runes("1")) {
		t.Fatal("choosing a chat model did not quit")
	}
	if want := (menuResult{Action: "chat", Model: "openai/gpt-6.2-sol-fast#high"}); *m.result != want {
		t.Fatalf("got %+v want %+v", m.result, want)
	}
}

func TestMenuShowsFastMode(t *testing.T) {
	for _, tc := range []struct {
		name string
		keys []tea.KeyMsg
		want []string
	}{
		{"off by default", nil, []string{"f fast mode: off"}},
		{"on after f, marked on GPT", []tea.KeyMsg{runes("f")}, []string{"f fast mode: on", "high · OpenCode · fast", "no fast mode"}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m := newMenuModel()
			press(m, tc.keys...)
			for _, text := range tc.want {
				if !strings.Contains(m.View(), text) {
					t.Fatalf("view lacks %q:\n%s", text, m.View())
				}
			}
		})
	}
}
