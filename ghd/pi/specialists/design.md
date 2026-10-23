# Product design and copy

Review user-facing changes: screens, components, CLI output, emails, notifications, error messages, API responses people read. Judge against the product's existing patterns in the repository:

- Clarity: does every label, message and empty state tell the user what happened and what to do next? Jargon, internal names and stack traces leaking to users.
- Consistency: terminology, casing, punctuation, date and number formats, button order and placement, icon and colour meaning, matching existing components instead of new one-offs.
- States: loading, empty, error, partial success, permission denied, offline, long content, very long or very short text, pluralisation, zero and one.
- Accessibility: keyboard reachability and focus order, labels for controls and images, contrast, motion, announcements for dynamic changes, touch target size.
- Interaction: destructive actions without confirmation or undo, lost input on navigation, surprising defaults, modal traps, missing feedback after an action.
- Internationalisation: hard-coded strings, concatenated sentences, text that cannot grow, direction and locale assumptions.

Candidates point at the exact string or element. Severity follows user impact: a blocked or misled user is `P1`; polish is `P3`.
