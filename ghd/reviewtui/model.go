package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/glamour"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
)

type mode int

const (
	running mode = iota
	failed
	reviewing
	posting
	postResult
)

type pass struct {
	Label string
	Done  bool
}

type (
	lineMsg     string
	exitMsg     struct{ err error }
	tickMsg     time.Time
	editDoneMsg struct {
		path string
		err  error
	}
	actionDoneMsg struct{ err error }
	postDoneMsg   struct {
		output string
		posted []int
		err    error
	}
)

var (
	bold    = lipgloss.NewStyle().Bold(true)
	dim     = lipgloss.NewStyle().Faint(true)
	accent  = lipgloss.NewStyle().Foreground(lipgloss.Color("6"))
	warn    = lipgloss.NewStyle().Foreground(lipgloss.Color("3"))
	bad     = lipgloss.NewStyle().Foreground(lipgloss.Color("1"))
	good    = lipgloss.NewStyle().Foreground(lipgloss.Color("2"))
	cursorS = lipgloss.NewStyle().Reverse(true)
	border  = lipgloss.NewStyle().Border(lipgloss.NormalBorder(), false, false, false, true).BorderForeground(lipgloss.Color("8")).PaddingLeft(1)
)

type model struct {
	out  string
	lib  string
	meta Meta
	mode mode

	// running
	cmd        *exec.Cmd
	lines      chan string
	stderr     *bytes.Buffer
	transcript strings.Builder
	log        viewport.Model
	follow     bool
	cost       float64
	started    time.Time
	passes     []pass
	exitErr    string

	// reviewing
	review     Review
	order      []int
	cursor     int
	selected   map[int]bool
	detail     viewport.Model
	showMD     bool
	dry        bool
	postOutput string
	files      map[string][][]DiffLine
	status     string
	width      int
	height     int
	exitCode   int
	dragging   bool
	dragGrab   int
}

func newModel(out, lib string, command []string) (*model, error) {
	m := &model{out: out, lib: lib, follow: true, started: time.Now(), selected: map[int]bool{}}
	if err := readJSON(out+".json", &m.meta); err != nil {
		return nil, fmt.Errorf("no review metadata at %s.json: %w", out, err)
	}
	if len(command) > 0 {
		m.cmd = exec.Command(command[0], command[1:]...)
		m.stderr = &bytes.Buffer{}
		m.cmd.Stderr = m.stderr
		m.cmd.Stdin = nil
		return m, nil
	}
	return m, m.loadReview()
}

func (m *model) loadReview() error {
	review, err := LoadReview(m.out + ".findings")
	if err != nil {
		return err
	}
	m.review, m.order, m.mode = review, Order(review.Findings), reviewing
	m.cursor, m.selected = 0, map[int]bool{}
	for i, f := range review.Findings {
		m.selected[i] = Preselected(f)
	}
	if packet, err := os.ReadFile(m.out + ".packet.md"); err == nil {
		m.files = Hunks(PacketDiff(string(packet)))
	}
	m.layout()
	return nil
}

func (m *model) Init() tea.Cmd {
	if m.cmd == nil {
		return nil
	}
	stdout, err := m.cmd.StdoutPipe()
	if err != nil {
		m.fail(err.Error())
		return nil
	}
	if err := m.cmd.Start(); err != nil {
		m.fail(err.Error())
		return nil
	}
	m.lines = make(chan string, 256)
	go func() {
		scanner := bufio.NewScanner(stdout)
		scanner.Buffer(make([]byte, 1<<20), 64<<20)
		for scanner.Scan() {
			m.lines <- scanner.Text()
		}
		close(m.lines)
	}()
	return tea.Batch(m.nextLine(), tick())
}

func tick() tea.Cmd { return tea.Tick(time.Second, func(t time.Time) tea.Msg { return tickMsg(t) }) }

func (m *model) nextLine() tea.Cmd {
	return func() tea.Msg {
		line, ok := <-m.lines
		if !ok {
			return exitMsg{m.cmd.Wait()}
		}
		return lineMsg(line)
	}
}

func (m *model) fail(reason string) {
	m.mode, m.exitErr, m.exitCode = failed, reason, 1
}

func (m *model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		m.layout()
	case tea.KeyMsg:
		return m.key(msg)
	case tea.MouseMsg:
		m.mouse(msg)
	case lineMsg:
		event := Parse(string(msg))
		switch {
		case event.Text != "":
			m.transcript.WriteString(event.Text)
		case event.Tool != "":
			m.transcript.WriteString("\n" + accent.Render(event.Tool) + "\n")
		case event.Error != "":
			m.exitErr = event.Error
		}
		if event.Cost > 0 {
			m.cost += event.Cost
		}
		m.refreshLog()
		return m, m.nextLine()
	case exitMsg:
		if m.exitErr != "" || msg.err != nil {
			reason := m.exitErr
			if reason == "" {
				reason = msg.err.Error()
			}
			if tail := strings.TrimSpace(m.stderr.String()); tail != "" {
				reason += "\n\n" + lastLines(tail, 12)
			}
			m.fail(reason)
			return m, nil
		}
		return m, tea.Quit
	case tickMsg:
		if m.mode == running {
			m.passes = readPasses(m.out + ".progress")
			if review, err := LoadReview(m.out + ".findings"); err == nil {
				m.review = review
			}
			return m, tick()
		}
	case editDoneMsg:
		if msg.err == nil {
			if text, err := os.ReadFile(msg.path); err == nil {
				m.review.Findings[m.order[m.cursor]].Comment = strings.TrimSpace(string(text))
				if err := SaveReview(m.out+".findings", m.review); err != nil {
					m.status = err.Error()
				} else {
					m.status = "comment saved"
				}
			}
		}
		os.Remove(msg.path)
		m.renderDetail()
	case actionDoneMsg:
		if msg.err != nil {
			m.status = msg.err.Error()
		}
		if m.cmd == nil || m.mode == reviewing {
			m.loadReview()
		}
	case postDoneMsg:
		m.mode = postResult
		m.postOutput = strings.TrimSpace(msg.output)
		if msg.err != nil {
			m.postOutput += "\n\nPosting failed: " + msg.err.Error()
		}
		for _, position := range msg.posted {
			m.selected[position-1] = false
		}
		m.renderPostResult()
	}
	return m, nil
}

func (m *model) key(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	k := msg.String()
	switch m.mode {
	case running:
		switch k {
		case "ctrl+c":
			if m.cmd != nil && m.cmd.Process != nil {
				m.cmd.Process.Kill()
			}
			m.exitCode = 130
			return m, tea.Quit
		case "G", "end":
			m.follow = true
			m.log.GotoBottom()
		default:
			before := m.log.YOffset
			m.log, _ = m.log.Update(msg)
			if m.log.YOffset != before {
				m.follow = m.log.AtBottom()
			}
		}
	case failed:
		return m, tea.Quit
	case posting:
		return m, nil
	case postResult:
		switch k {
		case "enter", "esc":
			m.mode = reviewing
			m.layout()
		case "q", "ctrl+c":
			return m, tea.Quit
		default:
			m.detail, _ = m.detail.Update(msg)
		}
	case reviewing:
		switch k {
		case "q", "esc", "ctrl+c":
			return m, tea.Quit
		case "j", "down":
			m.move(1)
		case "k", "up":
			m.move(-1)
		case " ":
			if len(m.order) == 0 {
				return m, nil
			}
			i := m.order[m.cursor]
			m.selected[i] = !m.selected[i]
		case "a":
			for i := range m.review.Findings {
				m.selected[i] = true
			}
		case "n":
			for i := range m.review.Findings {
				m.selected[i] = false
			}
		case "tab":
			m.showMD = !m.showMD
			m.renderDetail()
		case "e":
			return m, m.edit()
		case "p":
			return m, m.post()
		case "c":
			return m, m.resume()
		default:
			m.detail, _ = m.detail.Update(msg)
		}
	}
	return m, nil
}

func (m *model) move(delta int) {
	if len(m.order) == 0 {
		return
	}
	m.cursor = (m.cursor + delta + len(m.order)) % len(m.order)
	m.renderDetail()
}

func (m *model) edit() tea.Cmd {
	if len(m.order) == 0 {
		return nil
	}
	editor := os.Getenv("VISUAL")
	if editor == "" {
		editor = os.Getenv("EDITOR")
	}
	if editor == "" {
		editor = "vi"
	}
	file, err := os.CreateTemp("", "ghd-comment-*.md")
	if err != nil {
		m.status = err.Error()
		return nil
	}
	file.WriteString(m.review.Findings[m.order[m.cursor]].Comment + "\n")
	file.Close()
	cmd := exec.Command("sh", "-c", editor+` "$1"`, "ghd", file.Name())
	return tea.ExecProcess(cmd, func(err error) tea.Msg { return editDoneMsg{file.Name(), err} })
}

func (m *model) post() tea.Cmd {
	cmd, status := m.postCommand()
	if cmd == nil {
		m.status = status
		return nil
	}
	m.mode, m.status = posting, ""
	return func() tea.Msg {
		output, err := cmd.CombinedOutput()
		var report struct {
			Message string `json:"message"`
			Posted  []int  `json:"posted"`
		}
		if decodeErr := json.Unmarshal(output, &report); decodeErr != nil {
			if err == nil {
				err = fmt.Errorf("invalid posting report: %w", decodeErr)
			}
			return postDoneMsg{output: string(output), err: err}
		}
		return postDoneMsg{report.Message, report.Posted, err}
	}
}

func (m *model) resume() tea.Cmd { return m.run(m.resumeCommand()) }

// run hands the terminal to a command, or shows why there is none.
func (m *model) run(cmd *exec.Cmd, status string) tea.Cmd {
	if cmd == nil {
		m.status = status
		return nil
	}
	return tea.ExecProcess(cmd, func(err error) tea.Msg { return actionDoneMsg{err} })
}

// postCommand posts the ticked findings through ghd post without its picker.
func (m *model) postCommand() (*exec.Cmd, string) {
	picks := Picks(m.selected)
	if picks == "" {
		return nil, "nothing selected"
	}
	cmd := exec.Command("python3", filepath.Join(m.lib, "post.py"), m.meta.Repo, fmt.Sprint(m.meta.PR), "--json", "--review", m.out+".findings", "--pick", picks)
	if m.dry {
		cmd.Args = append(cmd.Args, "--dry")
	}
	return cmd, ""
}

// resumeCommand reopens the reviewer's conversation in its worktree.
func (m *model) resumeCommand() (*exec.Cmd, string) {
	if m.meta.Session == "" || m.meta.Cwd == "" {
		return nil, "no conversation to continue: this review was saved by hand"
	}
	if _, err := os.Stat(m.meta.Cwd); err != nil {
		return nil, "no conversation to continue: its worktree is gone"
	}
	var cmd *exec.Cmd
	switch m.meta.Tool {
	case "pi":
		cmd = exec.Command("pi", "--session", m.meta.Session)
	case "claude":
		cmd = exec.Command("claude", "--resume", m.meta.Session, "--setting-sources", "user", "--mcp-config", filepath.Join(m.lib, "mcp.json"), "--add-dir", filepath.Dir(m.out))
	case "opencode":
		cmd = exec.Command("opencode", "--session", m.meta.Session)
	default:
		return nil, "no conversation to continue for " + m.meta.Tool
	}
	cmd.Dir = m.meta.Cwd
	return cmd, ""
}

func (m *model) layout() {
	if m.width == 0 {
		return
	}
	body := max(m.height-5, 3)
	m.log = viewport.New(max(m.width-m.sideWidth()-3, 1), body)
	m.detail = viewport.New(max(m.width-m.listWidth()-3, 1), body)
	m.dragging = false
	m.refreshLog()
	if m.mode == reviewing {
		m.renderDetail()
	} else if m.mode == postResult {
		m.renderPostResult()
	}
}

func (m *model) renderPostResult() {
	m.detail = viewport.New(max(m.width-3, 1), max(m.height-5, 3))
	m.detail.SetContent(ansi.Wrap(m.postOutput, m.detail.Width, ""))
}

func (m *model) sideWidth() int { return min(36, m.width/3) }
func (m *model) listWidth() int { return min(64, m.width*45/100) }

func (m *model) refreshLog() {
	m.log.SetContent(lipgloss.NewStyle().Width(m.log.Width).Render(m.transcript.String()))
	if m.follow {
		m.log.GotoBottom()
	}
}

func (m *model) renderDetail() {
	if m.detail.Width == 0 {
		return
	}
	var text string
	switch {
	case m.showMD:
		md, err := os.ReadFile(m.out + ".md")
		if err != nil {
			md = []byte(m.review.TLDR)
		}
		text = markdown(string(md), m.detail.Width)
	case len(m.order) == 0:
		text = markdown(m.review.TLDR+"\n\nNo findings.", m.detail.Width)
	default:
		f := m.review.Findings[m.order[m.cursor]]
		var b strings.Builder
		b.WriteString(bold.Render(fmt.Sprintf("%s %s  %s", f.Severity, f.Category, Pointer(f))) + "\n")
		b.WriteString(bold.Render(f.Title) + "\n\n")
		b.WriteString(CommentText(f) + "\n")
		if lines := Context(m.files, f.File, f.Line, 8); lines != nil {
			b.WriteString("\n" + dim.Render("diff at head") + "\n")
			for _, line := range lines {
				switch {
				case strings.Contains(line, "▶"):
					b.WriteString(cursorS.Render(line) + "\n")
				case len(line) > 6 && line[6] == '+':
					b.WriteString(good.Render(line) + "\n")
				case len(line) > 6 && line[6] == '-':
					b.WriteString(bad.Render(line) + "\n")
				default:
					b.WriteString(line + "\n")
				}
			}
		}
		if f.Detail != "" {
			b.WriteString("\n" + dim.Render("evidence") + "\n" + markdown(f.Detail, m.detail.Width))
		}
		text = b.String()
	}
	m.detail.SetContent(ansi.Wrap(text, m.detail.Width, ""))
	m.detail.GotoTop()
}

func markdown(text string, width int) string {
	renderer, err := glamour.NewTermRenderer(glamour.WithAutoStyle(), glamour.WithWordWrap(max(width, 20)))
	if err != nil {
		return text
	}
	out, err := renderer.Render(text)
	if err != nil {
		return text
	}
	return out
}

func (m *model) View() string {
	if m.width == 0 {
		return ""
	}
	header := ansi.Truncate(bold.Render(fmt.Sprintf("%s#%d  %s", m.meta.Repo, m.meta.PR, m.meta.Title)), m.width, "…")
	switch m.mode {
	case running:
		return m.runView(header)
	case failed:
		return header + "\n\n" + bad.Render("Review failed") + "\n\n" + m.exitErr + "\n\n" + dim.Render("press any key")
	case posting:
		return m.frame(header, "Posting selected findings…", "", dim.Render("Adding comments to your pending GitHub review…"))
	case postResult:
		return m.frame(header, "Posting result", paneView(m.detail), dim.Render("↑/↓/pgup/pgdn scroll · enter/esc findings · q close"))
	}
	return m.reviewView(header)
}

func (m *model) runView(header string) string {
	elapsed := time.Since(m.started).Round(time.Second)
	info := fmt.Sprintf("%s %s  ·  %s  ·  $%.2f  ·  %s", m.meta.Tool, m.meta.Model, elapsed, m.cost, m.phase())
	var side []string
	side = append(side, bold.Render("Passes"))
	if len(m.passes) == 0 {
		side = append(side, dim.Render("none yet"))
	}
	for _, p := range m.passes {
		mark := accent.Render("●")
		if p.Done {
			mark = good.Render("✓")
		}
		side = append(side, mark+" "+p.Label)
	}
	side = append(side, "", bold.Render(fmt.Sprintf("Findings %d", len(m.review.Findings))))
	for _, i := range Order(m.review.Findings) {
		f := m.review.Findings[i]
		side = append(side, lipgloss.NewStyle().Width(m.sideWidth()).Render(fmt.Sprintf("%s %s", f.Severity, f.Title)))
	}
	left := lipgloss.NewStyle().Width(m.sideWidth()).MaxWidth(m.sideWidth()).Height(m.log.Height).MaxHeight(m.log.Height).Render(strings.Join(side, "\n"))
	right := paneView(m.log)
	footer := dim.Render("↑/↓ scroll · G follow · ctrl+c cancel")
	return m.frame(header, info, lipgloss.JoinHorizontal(lipgloss.Top, left, right), footer)
}

// frame stacks a screen; the line under the info shows the human's instructions, if any.
func (m *model) frame(header, info, body, footer string) string {
	instructions := ""
	if m.meta.Instructions != "" {
		instructions = lipgloss.NewStyle().MaxWidth(m.width).Render(accent.Render("Instructions: ") + dim.Render(strings.Join(strings.Fields(m.meta.Instructions), " ")))
	}
	return strings.Join([]string{header, ansi.Truncate(dim.Render(info), m.width, "…"), instructions, body, ansi.Truncate(footer, m.width, "…")}, "\n")
}

func (m *model) phase() string {
	running, done := 0, 0
	for _, p := range m.passes {
		if p.Done {
			done++
		} else {
			running++
		}
	}
	switch {
	case running > 0:
		return fmt.Sprintf("review (%d/%d passes)", done, done+running)
	case done > 0 && len(m.review.Findings) == 0:
		return "verify"
	case done > 0:
		return "write"
	}
	return "gather"
}

func (m *model) reviewView(header string) string {
	var rows []string
	start := max(0, m.cursor-m.detail.Height+1)
	for row := start; row < min(len(m.order), start+m.detail.Height); row++ {
		i := m.order[row]
		f := m.review.Findings[i]
		box := "[ ]"
		if m.selected[i] {
			box = "[x]"
		}
		mark := emoji[f.Category]
		if mark == "" {
			mark = "•"
		}
		text := fmt.Sprintf("%s %s %s %s  %s", box, f.Severity, mark, Pointer(f), f.Title)
		line := lipgloss.NewStyle().Width(m.listWidth()).MaxHeight(1).Render(text)
		if row == m.cursor {
			line = cursorS.Render(line)
		}
		rows = append(rows, line)
	}
	if len(rows) == 0 {
		rows = append(rows, dim.Render("No findings."))
	}
	picked := 0
	for _, on := range m.selected {
		if on {
			picked++
		}
	}
	info := fmt.Sprintf("%s %s  ·  %s  ·  %d of %d selected", m.meta.Tool, m.meta.Model, shortSHA(m.meta.SHA), picked, len(m.review.Findings))
	left := lipgloss.NewStyle().Width(m.listWidth()).Height(m.detail.Height).Render(strings.Join(rows, "\n"))
	right := paneView(m.detail)
	keys := "q close · pgup/dn scroll · space select · a/n all/none · e edit · p post · c continue · tab review/finding"
	footer := dim.Render(keys)
	if m.status != "" {
		footer = warn.Render(m.status) + "  " + footer
	}
	return m.frame(header, info, lipgloss.JoinHorizontal(lipgloss.Top, left, right), footer)
}

func shortSHA(sha string) string {
	if len(sha) > 7 {
		return sha[:7]
	}
	return sha
}

func readPasses(path string) []pass {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var passes []pass
	index := map[string]int{}
	for _, line := range strings.Split(string(data), "\n") {
		var event struct {
			Kind  string `json:"kind"`
			Label string `json:"label"`
		}
		if json.Unmarshal([]byte(line), &event) != nil {
			continue
		}
		switch event.Kind {
		case "agent_start":
			if _, seen := index[event.Label]; !seen {
				index[event.Label] = len(passes)
				passes = append(passes, pass{Label: event.Label})
			}
		case "agent_end":
			if i, seen := index[event.Label]; seen {
				passes[i].Done = true
			}
		}
	}
	return passes
}

func lastLines(text string, n int) string {
	lines := strings.Split(text, "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}
