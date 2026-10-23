package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

// Finding mirrors one entry of a ghd findings file.
type Finding struct {
	File      string `json:"file"`
	Line      int    `json:"line"`
	StartLine int    `json:"start_line,omitempty"`
	Anchor    string `json:"anchor"`
	Category  string `json:"category"`
	Severity  string `json:"severity"`
	Title     string `json:"title"`
	Comment   string `json:"comment"`
	Detail    string `json:"detail,omitempty"`
}

// Review is a ghd findings file. Unknown keys survive a round trip through Extra.
type Review struct {
	TLDR     string          `json:"tldr"`
	Findings []Finding       `json:"findings"`
	Extra    json.RawMessage `json:"-"`
}

// Meta is a review's metadata file.
type Meta struct {
	Repo    string `json:"repo"`
	PR      int    `json:"pr"`
	Tool    string `json:"tool"`
	Model   string `json:"model"`
	SHA     string `json:"sha"`
	Title   string `json:"title"`
	Session string `json:"session"`
	Cwd     string `json:"cwd"`
}

var (
	severities = []string{"P0", "P1", "P2", "P3"}
	emoji      = map[string]string{"bug": "🐛", "security": "🔒", "risk": "⚠️", "quality": "🧹", "design": "🎨", "completeness": "📋"}
)

const aiSuffix = "(added by AI)"

// Preselected says whether a finding starts ticked, as ghd post does.
func Preselected(f Finding) bool {
	return f.Severity != "P3" && f.Category != "completeness"
}

// CommentText is the exact text ghd post publishes for a finding.
func CommentText(f Finding) string {
	mark, ok := emoji[f.Category]
	if !ok {
		mark = "•"
	}
	nit := ""
	if f.Severity == "P3" {
		nit = "nit: "
	}
	return fmt.Sprintf("%s %s%s\n\n%s", mark, nit, f.Comment, aiSuffix)
}

// Pointer renders file:line or file:start-line.
func Pointer(f Finding) string {
	if f.StartLine > 0 {
		return fmt.Sprintf("%s:%d-%d", f.File, f.StartLine, f.Line)
	}
	return fmt.Sprintf("%s:%d", f.File, f.Line)
}

// Order returns finding indices sorted by severity, stable within a severity.
func Order(findings []Finding) []int {
	rank := func(s string) int {
		for i, severity := range severities {
			if severity == s {
				return i
			}
		}
		return len(severities)
	}
	order := make([]int, len(findings))
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(a, b int) bool { return rank(findings[order[a]].Severity) < rank(findings[order[b]].Severity) })
	return order
}

// Picks renders the 1-based positions of the selected findings for `ghd post --pick`.
func Picks(selected map[int]bool) string {
	var numbers []int
	for index, on := range selected {
		if on {
			numbers = append(numbers, index+1)
		}
	}
	sort.Ints(numbers)
	parts := make([]string, len(numbers))
	for i, n := range numbers {
		parts[i] = fmt.Sprint(n)
	}
	return strings.Join(parts, ",")
}

func readJSON(path string, into any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, into)
}

// LoadReview reads a findings file, keeping the keys this program does not model.
func LoadReview(path string) (Review, error) {
	var review Review
	data, err := os.ReadFile(path)
	if err != nil {
		return review, err
	}
	if err := json.Unmarshal(data, &review); err != nil {
		return review, err
	}
	review.Extra = data
	return review, nil
}

// SaveReview writes the findings back, preserving the other keys of the file.
func SaveReview(path string, review Review) error {
	whole := map[string]json.RawMessage{}
	if len(review.Extra) > 0 {
		json.Unmarshal(review.Extra, &whole)
	}
	tldr, _ := json.Marshal(review.TLDR)
	findings, _ := json.Marshal(review.Findings)
	whole["tldr"], whole["findings"] = tldr, findings
	data, err := json.MarshalIndent(whole, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}
