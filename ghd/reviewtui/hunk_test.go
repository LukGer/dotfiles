package main

import (
	"reflect"
	"testing"
)

const diff = `diff --git a/a.txt b/a.txt
index 1..2 100644
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,4 @@
 first
-second
+changed
+added
 third
diff --git a/b.txt b/b.txt
@@ -10,2 +12,2 @@ func x()
 keep
-old
+new
`

func TestHunksTrackNewLineNumbers(t *testing.T) {
	files := Hunks(diff)
	want := map[string][][]DiffLine{
		"a.txt": {{{1, " first"}, {0, "-second"}, {2, "+changed"}, {3, "+added"}, {4, " third"}}},
		"b.txt": {{{12, " keep"}, {0, "-old"}, {13, "+new"}}},
	}
	if !reflect.DeepEqual(files, want) {
		t.Fatalf("got %#v", files)
	}
}

func TestContext(t *testing.T) {
	files := Hunks(diff)
	for _, tc := range []struct {
		path         string
		line, around int
		want         []string
	}{
		{"a.txt", 2, 1, []string{"      -second", "   2 ▶+changed", "   3  +added"}},
		{"a.txt", 4, 0, []string{"   4 ▶ third"}},
		{"b.txt", 13, 5, []string{"  12   keep", "      -old", "  13 ▶+new"}},
		{"b.txt", 99, 5, nil},
		{"missing", 1, 5, nil},
	} {
		if got := Context(files, tc.path, tc.line, tc.around); !reflect.DeepEqual(got, tc.want) {
			t.Errorf("%s:%d around %d: got %q want %q", tc.path, tc.line, tc.around, got, tc.want)
		}
	}
}

func TestPacketDiff(t *testing.T) {
	packet := "# o/r#1 T\n\n## Diff\n```diff\n" + diff + "```\n"
	if got := PacketDiff(packet); got != diff[:len(diff)-1] {
		t.Fatalf("got %q", got)
	}
	if PacketDiff("no diff here") != "" {
		t.Fatal("expected empty")
	}
}
