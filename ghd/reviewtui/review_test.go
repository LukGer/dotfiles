package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestPreselectedAndCommentText(t *testing.T) {
	for _, tc := range []struct {
		finding  Finding
		selected bool
		comment  string
	}{
		{Finding{Category: "security", Severity: "P0", Comment: "Exposed."}, true, "[P0] 🔒 Exposed.\n\n(added by AI)"},
		{Finding{Category: "bug", Severity: "P1", Comment: "Null here."}, true, "[P1] 🐛 Null here.\n\n(added by AI)"},
		{Finding{Category: "quality", Severity: "P3", Comment: "Rename."}, false, "[P3] 🧹 nit: Rename.\n\n(added by AI)"},
		{Finding{Category: "completeness", Severity: "P1", Comment: "Missing."}, false, "[P1] 📋 Missing.\n\n(added by AI)"},
		{Finding{Category: "other", Severity: "P2", Comment: "Hm."}, true, "[P2] • Hm.\n\n(added by AI)"},
	} {
		if got := Preselected(tc.finding); got != tc.selected {
			t.Errorf("%+v preselected %v", tc.finding, got)
		}
		if got := CommentText(tc.finding); got != tc.comment {
			t.Errorf("%+v comment %q", tc.finding, got)
		}
	}
}

func TestOrderAndPointerAndPicks(t *testing.T) {
	findings := []Finding{
		{File: "a", Line: 5, Severity: "P3"}, {File: "b", Line: 9, StartLine: 7, Severity: "P1"}, {File: "c", Line: 1, Severity: "P1"}, {File: "d", Line: 2, Severity: "P0"},
	}
	if got := Order(findings); !reflect.DeepEqual(got, []int{3, 1, 2, 0}) {
		t.Fatalf("order %v", got)
	}
	if got := Pointer(findings[1]); got != "b:7-9" {
		t.Fatalf("pointer %q", got)
	}
	if got := Pointer(findings[0]); got != "a:5" {
		t.Fatalf("pointer %q", got)
	}
	if got := Picks(map[int]bool{2: true, 0: true, 1: false}); got != "1,3" {
		t.Fatalf("picks %q", got)
	}
	if got := Picks(map[int]bool{}); got != "" {
		t.Fatalf("picks %q", got)
	}
}

func TestSaveReviewKeepsUnknownKeys(t *testing.T) {
	path := filepath.Join(t.TempDir(), "r.findings")
	os.WriteFile(path, []byte(`{"tldr":"T","findings":[{"file":"a","line":1,"anchor":"x","category":"bug","severity":"P1","title":"t","comment":"old"}],"dropped":[{"candidate":"c","reason":"r"}]}`), 0o644)
	review, err := LoadReview(path)
	if err != nil {
		t.Fatal(err)
	}
	review.Findings[0].Comment = "new"
	if err := SaveReview(path, review); err != nil {
		t.Fatal(err)
	}
	var whole map[string]any
	data, _ := os.ReadFile(path)
	json.Unmarshal(data, &whole)
	if whole["dropped"] == nil || whole["findings"].([]any)[0].(map[string]any)["comment"] != "new" || whole["tldr"] != "T" {
		t.Fatalf("got %s", data)
	}
}

func TestVerificationSelectionAndRoundTrip(t *testing.T) {
	for _, tc := range []struct {
		verdicts []string
		selected bool
	}{
		{[]string{"confirmed"}, true}, {[]string{"uncertain"}, false}, {[]string{"refuted"}, false},
		{[]string{"uncertain", "confirmed"}, true}, {[]string{"refuted", "confirmed"}, false},
		{[]string{"confirmed", "uncertain"}, false},
	} {
		t.Run(fmt.Sprint(tc.verdicts), func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "review.findings")
			votes := []map[string]string{}
			for _, verdict := range tc.verdicts {
				votes = append(votes, map[string]string{"model": "luna", "verdict": verdict, "reason": "Evidence."})
			}
			data, _ := json.Marshal(map[string]any{"tldr": "Review", "findings": []any{map[string]any{"file": "a", "line": 1, "category": "bug", "severity": "P1", "verification": votes}}})
			os.WriteFile(path, data, 0o644)
			review, err := LoadReview(path)
			if err != nil {
				t.Fatal(err)
			}
			if got := Preselected(review.Findings[0]); got != tc.selected {
				t.Fatalf("preselected %v, want %v", got, tc.selected)
			}
			if err := SaveReview(path, review); err != nil {
				t.Fatal(err)
			}
			saved, _ := os.ReadFile(path)
			var whole map[string]any
			json.Unmarshal(saved, &whole)
			finding := whole["findings"].([]any)[0].(map[string]any)
			savedVotes, ok := finding["verification"].([]any)
			if !ok || len(savedVotes) != len(votes) {
				t.Fatalf("lost verdicts: %s", saved)
			}
		})
	}
}
