package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/charmbracelet/bubbles/cursor"
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/textarea"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type menuItem struct {
	label, detail, action, model string
}

var modelItems = []menuItem{
	{"GPT-6.1 Sol", "high · OpenCode", "review", "openai/gpt-6.1-sol#high"},
	{"Opus (Claude Code)", "high · OpenCode", "review", "claude-agent/opus#high"},
}

var menuItems = append(modelItems, []menuItem{
	{"Past reviews of this PR", "", "past", ""},
	{"Post to GitHub (pending)", "", "post", ""},
	{"Chat with PR", "", "chat", ""},
}...)

// menuResult is what `ghd review` reads back from the menu's result file.
type menuResult struct {
	Action       string `json:"action"`
	Model        string `json:"model,omitempty"`
	Instructions string `json:"instructions,omitempty"`
}

type menuModel struct {
	items  []menuItem
	chat   bool
	cursor int
	picked *menuItem
	input  textarea.Model
	result *menuResult
}

var (
	menuPage = lipgloss.NewStyle().Padding(1, 2)
	inputBox = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("6")).Padding(0, 1)
)

func newMenuModel() *menuModel {
	input := textarea.New()
	input.Placeholder = "e.g. only review src/api/, skip generated files, focus on concurrency"
	input.ShowLineNumbers = false
	input.Prompt = ""
	input.CharLimit = 0
	input.SetHeight(5)
	input.Cursor.SetMode(cursor.CursorStatic)
	input.FocusedStyle.CursorLine = lipgloss.NewStyle()
	input.FocusedStyle.Placeholder = dim
	input.KeyMap.InsertNewline = key.NewBinding(key.WithKeys("alt+enter", "ctrl+j"))
	return &menuModel{items: menuItems, input: input}
}

func (m *menuModel) Init() tea.Cmd { return nil }

func (m *menuModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.input.SetWidth(max(msg.Width-menuPage.GetHorizontalFrameSize()-inputBox.GetHorizontalFrameSize(), 20))
	case tea.KeyMsg:
		if m.picked != nil {
			return m.instructionsKey(msg)
		}
		return m.listKey(msg)
	}
	return m, nil
}

func (m *menuModel) listKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch key := msg.String(); key {
	case "q", "esc", "ctrl+c":
		return m, tea.Quit
	case "up", "k":
		m.cursor = (m.cursor + len(m.items) - 1) % len(m.items)
	case "down", "j":
		m.cursor = (m.cursor + 1) % len(m.items)
	case "enter":
		return m.choose(m.cursor)
	default:
		if n, err := strconv.Atoi(key); err == nil && n >= 1 && n <= len(m.items) {
			return m.choose(n - 1)
		}
	}
	return m, nil
}

func (m *menuModel) choose(i int) (tea.Model, tea.Cmd) {
	m.cursor = i
	item := m.items[i]
	if m.chat {
		m.result = &menuResult{Action: "chat", Model: item.model}
		return m, tea.Quit
	}
	if item.action != "review" {
		m.result = &menuResult{Action: item.action}
		return m, tea.Quit
	}
	m.picked = &item
	return m, m.input.Focus()
}

func (m *menuModel) instructionsKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c":
		return m, tea.Quit
	case "esc":
		m.picked = nil
		m.input.Blur()
		return m, nil
	case "enter":
		m.result = &menuResult{Action: "review", Model: m.picked.model, Instructions: strings.TrimSpace(m.input.Value())}
		return m, tea.Quit
	}
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	return m, cmd
}

func (m *menuModel) View() string {
	if m.picked != nil {
		return menuPage.Render(strings.Join([]string{
			accent.Bold(true).Render(m.picked.label) + dim.Render(" · "+m.picked.detail),
			bold.Render("Instructions") + dim.Render(" for this review (optional)"),
			inputBox.Render(m.input.View()),
			dim.Render("enter start review · alt+enter newline · esc back"),
		}, "\n"))
	}
	labelWidth := 0
	for _, item := range m.items {
		if item.detail != "" {
			labelWidth = max(labelWidth, lipgloss.Width(item.label))
		}
	}
	var rows []string
	if m.chat {
		rows = append(rows, bold.Render("Chat with PR"), dim.Render("Choose a model · diff only, no checkout"), "")
	}
	for i, item := range m.items {
		if i > 0 && m.items[i-1].action == "review" && item.action != "review" {
			rows = append(rows, "")
		}
		pointer, number, label := "  ", dim, lipgloss.NewStyle()
		if i == m.cursor {
			pointer, number, label = accent.Render("› "), accent, accent.Bold(true)
		}
		row := pointer + number.Render(fmt.Sprint(i+1)) + "  " + label.Render(item.label)
		if item.detail != "" {
			row += strings.Repeat(" ", labelWidth-lipgloss.Width(item.label)+2) + dim.Render(item.detail)
		}
		rows = append(rows, row)
	}
	rows = append(rows, "", dim.Render(fmt.Sprintf("1–%d choose · ↑/↓ move · enter select · esc/q cancel", len(m.items))))
	return menuPage.Render(strings.Join(rows, "\n"))
}

// runMenu shows the menu and writes the choice to result as JSON; a cancelled
// menu leaves result untouched.
func runMenu(result string, chat bool) error {
	m := newMenuModel()
	if chat {
		m.items, m.chat = modelItems, true
	}
	if _, err := tea.NewProgram(m, tea.WithAltScreen()).Run(); err != nil {
		return err
	}
	if m.result == nil {
		return nil
	}
	choice, err := json.Marshal(m.result)
	if err != nil {
		return err
	}
	return os.WriteFile(result, choice, 0o600)
}
