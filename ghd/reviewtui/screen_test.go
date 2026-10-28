package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestScreenSelectionAndCancellation(t *testing.T) {
	for _, tc := range []struct {
		name string
		keys []string
		want int
	}{
		{"first", []string{"enter"}, 0},
		{"second", []string{"j", "enter"}, 1},
		{"wrap", []string{"k", "enter"}, 2},
		{"filter", []string{"/", "s", "e", "c", "enter", "enter"}, 1},
		{"clear filter", []string{"/", "x", "esc", "enter"}, 0},
		{"cancel", []string{"esc"}, -1},
		{"quit", []string{"q"}, -1},
		{"interrupt while filtering", []string{"/", "ctrl+c"}, -1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m := newScreen(screenRequest{Title: "Pick", Items: []screenItem{{Label: "first"}, {Label: "second"}, {Label: "third"}}})
			m.Update(tea.WindowSizeMsg{Width: 100, Height: 20})
			for _, key := range tc.keys {
				msg := tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(key)}
				switch key {
				case "enter":
					msg = tea.KeyMsg{Type: tea.KeyEnter}
				case "esc":
					msg = tea.KeyMsg{Type: tea.KeyEsc}
				case "ctrl+c":
					msg = tea.KeyMsg{Type: tea.KeyCtrlC}
				}
				m.Update(msg)
			}
			if tc.want < 0 {
				if m.result != nil {
					t.Fatalf("cancelled picker selected %+v", m.result)
				}
			} else if m.result == nil || m.result.Index != tc.want {
				t.Fatalf("got %+v, want %d", m.result, tc.want)
			}
		})
	}
}

func TestScreenPreviewsAndCopiesTheSelectedReview(t *testing.T) {
	directory := t.TempDir()
	path := filepath.Join(directory, "review.md")
	text := "# Saved review\n\n" + strings.Repeat("Evidence.\n\n", 100)
	os.WriteFile(path, []byte(text), 0o600)
	clipboard := filepath.Join(directory, "clipboard")
	os.WriteFile(filepath.Join(directory, "pbcopy"), []byte("#!/bin/sh\ncat > '"+clipboard+"'\n"), 0o700)
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	m := newScreen(screenRequest{Copy: true, Items: []screenItem{{Label: "review", PreviewFile: path}}})
	m.Update(tea.WindowSizeMsg{Width: 100, Height: 12})
	if !strings.Contains(m.View(), "Saved review") {
		t.Fatalf("no preview: %s", m.View())
	}
	m.Update(tea.KeyMsg{Type: tea.KeyPgDown})
	if m.detail.YOffset == 0 {
		t.Fatal("preview did not scroll")
	}
	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyCtrlY})
	m.Update(cmd())
	got, err := os.ReadFile(clipboard)
	if err != nil || string(got) != text || !strings.Contains(m.View(), "Copied to clipboard") {
		t.Fatalf("copy failed: %v, %s", err, m.View())
	}
}

func TestMessageScreenScrollsAndCloses(t *testing.T) {
	for _, key := range []tea.KeyType{tea.KeyEnter, tea.KeyEsc, tea.KeyCtrlC} {
		t.Run(fmt.Sprint(key), func(t *testing.T) {
			m := newScreen(screenRequest{Message: strings.Repeat("Details\n\n", 100)})
			m.Update(tea.WindowSizeMsg{Width: 80, Height: 12})
			m.Update(tea.KeyMsg{Type: tea.KeyDown})
			if m.detail.YOffset == 0 {
				t.Fatal("message did not scroll")
			}
			_, cmd := m.Update(tea.KeyMsg{Type: key})
			if cmd == nil {
				t.Fatal("message did not close")
			}
			if _, ok := cmd().(tea.QuitMsg); !ok {
				t.Fatal("message did not quit")
			}
		})
	}
}
