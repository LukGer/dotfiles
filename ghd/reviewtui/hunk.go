package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// DiffLine is one line of a unified diff hunk with its line number in the new file.
type DiffLine struct {
	New  int // 0 for removed lines
	Text string
}

var (
	fileHeader = regexp.MustCompile(`^diff --git a/(.*) b/(.*)$`)
	hunkHeader = regexp.MustCompile(`^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@`)
)

// Hunks parses a unified diff into hunks keyed by new path.
func Hunks(diff string) map[string][][]DiffLine {
	files := map[string][][]DiffLine{}
	var path string
	var hunk []DiffLine
	next := 0
	flush := func() {
		if path != "" && hunk != nil {
			files[path] = append(files[path], hunk)
		}
		hunk = nil
	}
	for _, raw := range strings.Split(diff, "\n") {
		if m := fileHeader.FindStringSubmatch(raw); m != nil {
			flush()
			path = m[2]
			continue
		}
		if m := hunkHeader.FindStringSubmatch(raw); m != nil {
			flush()
			next, _ = strconv.Atoi(m[1])
			hunk = []DiffLine{}
			continue
		}
		if hunk == nil || strings.HasPrefix(raw, "\\") {
			continue
		}
		switch {
		case strings.HasPrefix(raw, "-"):
			hunk = append(hunk, DiffLine{Text: raw})
		case strings.HasPrefix(raw, "+"), strings.HasPrefix(raw, " "):
			hunk = append(hunk, DiffLine{New: next, Text: raw})
			next++
		}
	}
	flush()
	return files
}

// Context returns the hunk lines around `line` of `path`, at most `around`
// lines each side of it, rendered with new-file line numbers and a marker.
func Context(files map[string][][]DiffLine, path string, line, around int) []string {
	for _, hunk := range files[path] {
		at := -1
		for i, l := range hunk {
			if l.New == line {
				at = i
			}
		}
		if at < 0 {
			continue
		}
		from, to := max(0, at-around), min(len(hunk), at+around+1)
		var out []string
		for i := from; i < to; i++ {
			number, mark := "    ", " "
			if hunk[i].New > 0 {
				number = fmt.Sprintf("%4d", hunk[i].New)
			}
			if i == at {
				mark = "▶"
			}
			out = append(out, fmt.Sprintf("%s %s%s", number, mark, hunk[i].Text))
		}
		return out
	}
	return nil
}

// PacketDiff extracts the fenced diff block from a review packet.
func PacketDiff(packet string) string {
	_, after, found := strings.Cut(packet, "\n```diff\n")
	if !found {
		return ""
	}
	body, _, _ := strings.Cut(after, "\n```")
	return body
}
