package main

import (
	"strings"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

func scrollThumb(v viewport.Model) (top, size int) {
	if v.Height < 1 || v.TotalLineCount() <= v.Height {
		return 0, 0
	}
	size = max(1, v.Height*v.Height/v.TotalLineCount())
	top = v.YOffset * (v.Height - size) / (v.TotalLineCount() - v.Height)
	return top, size
}

func paneView(v viewport.Model) string {
	top, size := scrollThumb(v)
	rows := make([]string, v.Height)
	for i := range rows {
		switch {
		case size == 0:
			rows[i] = " "
		case i >= top && i < top+size:
			rows[i] = accent.Render("█")
		default:
			rows[i] = dim.Render("│")
		}
	}
	return border.Render(lipgloss.JoinHorizontal(lipgloss.Top, v.View(), strings.Join(rows, "\n")))
}

func (m *model) mouse(msg tea.MouseMsg) {
	if msg.Action == tea.MouseActionRelease {
		m.dragging = false
		return
	}
	v, left := &m.detail, m.listWidth()+2
	if m.mode == running {
		v, left = &m.log, m.sideWidth()+2
	} else if m.mode == postResult {
		left = 0
	} else if m.mode != reviewing {
		return
	}
	before := v.YOffset
	top, size := scrollThumb(*v)
	switch {
	case m.dragging && msg.Action == tea.MouseActionMotion:
		travel := v.Height - size
		if travel > 0 {
			y := min(max(msg.Y-3-m.dragGrab, 0), travel)
			v.SetYOffset(y * (v.TotalLineCount() - v.Height) / travel)
		}
	case msg.X < left || msg.X >= m.width || msg.Y < 3 || msg.Y >= 3+v.Height:
		return
	case msg.X == m.width-1 && msg.Button == tea.MouseButtonLeft && msg.Action == tea.MouseActionPress && size > 0:
		y := msg.Y - 3
		m.dragging, m.dragGrab = true, y-top
		if y < top || y >= top+size {
			m.dragGrab = size / 2
			travel := v.Height - size
			v.SetYOffset(min(max(y-m.dragGrab, 0), travel) * (v.TotalLineCount() - v.Height) / travel)
		}
	default:
		*v, _ = v.Update(msg)
	}
	if m.mode == running && before != v.YOffset {
		m.follow = v.AtBottom()
	}
}
