package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
)

type screenItem struct {
	Label       string `json:"label"`
	Preview     string `json:"preview"`
	PreviewFile string `json:"preview_file"`
}

type screenRequest struct {
	Title   string       `json:"title"`
	Message string       `json:"message"`
	Items   []screenItem `json:"items"`
	Copy    bool         `json:"copy"`
}

type screenResult struct {
	Index int `json:"index"`
}

type copiedMsg struct{ err error }

type screenModel struct {
	request screenRequest
	result  *screenResult
	matches []int
	cursor  int
	filter  textinput.Model
	detail  viewport.Model
	width   int
	height  int
	status  string
}

func newScreen(request screenRequest) *screenModel {
	input := textinput.New()
	input.Prompt = "/ "
	m := &screenModel{request: request, filter: input}
	m.match()
	return m
}

func (m *screenModel) Init() tea.Cmd { return nil }

func (m *screenModel) match() {
	m.matches = nil
	for i, item := range m.request.Items {
		if strings.Contains(strings.ToLower(ansi.Strip(item.Label)), strings.ToLower(m.filter.Value())) {
			m.matches = append(m.matches, i)
		}
	}
	m.cursor = 0
	m.preview()
}

func (m *screenModel) text() string {
	if len(m.matches) == 0 {
		return m.request.Message
	}
	item := m.request.Items[m.matches[m.cursor]]
	if item.PreviewFile != "" {
		data, err := os.ReadFile(item.PreviewFile)
		if err != nil {
			return err.Error()
		}
		return string(data)
	}
	return item.Preview
}

func (m *screenModel) preview() {
	if m.detail.Width > 0 {
		m.detail.SetContent(ansi.Wrap(markdown(m.text(), m.detail.Width), m.detail.Width, ""))
		m.detail.GotoTop()
	}
}

func (m *screenModel) listWidth() int { return m.width / 2 }

func (m *screenModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		width := max(m.width-3, 1)
		if len(m.request.Items) > 0 {
			width = max(m.width-m.listWidth()-3, 1)
		}
		m.detail = viewport.New(width, max(m.height-4, 1))
		m.filter.Width = max(m.width-4, 1)
		m.preview()
	case copiedMsg:
		m.status = "Copied to clipboard."
		if msg.err != nil {
			m.status = "Copy failed: " + msg.err.Error()
		}
	case tea.KeyMsg:
		if msg.String() == "ctrl+c" {
			return m, tea.Quit
		}
		if m.filter.Focused() {
			switch msg.String() {
			case "enter":
				m.filter.Blur()
			case "esc":
				m.filter.Blur()
				m.filter.SetValue("")
				m.match()
			default:
				var cmd tea.Cmd
				m.filter, cmd = m.filter.Update(msg)
				m.match()
				return m, cmd
			}
			return m, nil
		}
		switch msg.String() {
		case "q", "esc":
			return m, tea.Quit
		case "enter":
			if len(m.request.Items) == 0 {
				return m, tea.Quit
			}
			if len(m.matches) > 0 {
				m.result = &screenResult{Index: m.matches[m.cursor]}
				return m, tea.Quit
			}
		case "/":
			if len(m.request.Items) > 0 {
				return m, m.filter.Focus()
			}
		case "up", "k", "down", "j":
			if len(m.request.Items) == 0 {
				m.detail, _ = m.detail.Update(msg)
			} else if len(m.matches) > 0 {
				delta := 1
				if msg.String() == "up" || msg.String() == "k" {
					delta = -1
				}
				m.cursor = (m.cursor + delta + len(m.matches)) % len(m.matches)
				m.preview()
			}
		case "ctrl+y":
			if m.request.Copy && len(m.matches) > 0 {
				text := m.text()
				return m, func() tea.Msg {
					cmd := exec.Command("pbcopy")
					cmd.Stdin = strings.NewReader(text)
					return copiedMsg{cmd.Run()}
				}
			}
		default:
			m.detail, _ = m.detail.Update(msg)
		}
	case tea.MouseMsg:
		m.detail, _ = m.detail.Update(msg)
	}
	return m, nil
}

func (m *screenModel) View() string {
	if m.width == 0 {
		return ""
	}
	body := paneView(m.detail)
	footer := "↑/↓/pgup/pgdn scroll · enter/esc/q close"
	if len(m.request.Items) > 0 {
		var rows []string
		start := max(0, m.cursor-m.detail.Height+1)
		for row := start; row < min(len(m.matches), start+m.detail.Height); row++ {
			label := ansi.Truncate(m.request.Items[m.matches[row]].Label, m.listWidth()-2, "…")
			if row == m.cursor {
				label = cursorS.Render("› " + label)
			} else {
				label = "  " + label
			}
			rows = append(rows, label)
		}
		if len(m.matches) == 0 {
			rows = []string{dim.Render("No matches.")}
		}
		left := lipgloss.NewStyle().Width(m.listWidth()).Height(m.detail.Height).Render(strings.Join(rows, "\n"))
		body = lipgloss.JoinHorizontal(lipgloss.Top, left, body)
		footer = "↑/↓ choose · enter select · / filter · pgup/pgdn preview · esc/q cancel"
		if m.request.Copy {
			footer += " · ctrl+y copy"
		}
	}
	filter := m.status
	if m.filter.Focused() || m.filter.Value() != "" {
		filter = m.filter.View()
	}
	return strings.Join([]string{bold.Render(m.request.Title), filter, body, dim.Render(ansi.Truncate(footer, m.width, "…"))}, "\n")
}

func runScreen(source, result string) error {
	var request screenRequest
	if err := readJSON(source, &request); err != nil {
		return fmt.Errorf("screen request: %w", err)
	}
	m := newScreen(request)
	if _, err := tea.NewProgram(m, tea.WithAltScreen(), tea.WithMouseCellMotion()).Run(); err != nil {
		return err
	}
	if m.result == nil {
		return nil
	}
	data, err := json.Marshal(m.result)
	if err != nil {
		return err
	}
	return os.WriteFile(result, data, 0o600)
}
