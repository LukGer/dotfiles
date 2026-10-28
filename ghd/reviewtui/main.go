// ghd's review screen: watches a running reviewer, then lets you read, tick,
// edit and post its findings.
//
//	ghd tui <review prefix> [--dry]         read a saved review
//	ghd tui <review prefix> -- <command>    run the reviewer, then read its review
//	ghd tui menu <result file>              choose a reviewer and its instructions
//	ghd tui screen <request> <result>       show a picker or message from JSON
//
// The prefix is the path of a review without its extension; its .json, .findings,
// .md, .progress and .packet.md files live next to it. GHD_LIB names the ghd
// directory, for post.py and mcp.json.
package main

import (
	"fmt"
	"os"
	"slices"

	tea "github.com/charmbracelet/bubbletea"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: ghd tui <review prefix> [--dry] [-- command...] | menu <result> | screen <request> <result>")
		os.Exit(2)
	}
	if os.Args[1] == "menu" && len(os.Args) == 3 {
		if err := runMenu(os.Args[2]); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	if os.Args[1] == "screen" && len(os.Args) == 4 {
		if err := runScreen(os.Args[2], os.Args[3]); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	var command []string
	if at := slices.Index(os.Args, "--"); at > 0 {
		command = os.Args[at+1:]
	}
	m, err := newModel(os.Args[1], os.Getenv("GHD_LIB"), command)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	m.dry = slices.Contains(os.Args[2:], "--dry")
	if _, err := tea.NewProgram(m, tea.WithAltScreen(), tea.WithMouseCellMotion()).Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if m.mode == failed {
		fmt.Fprintln(os.Stderr, m.exitErr)
	}
	os.Exit(m.exitCode)
}
