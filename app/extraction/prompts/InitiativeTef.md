Context: TEF (Taxonomy for Economic Activities) category links to initiatives in Climate City Contract documents.

**Available fields ONLY** (no other fields are permitted):

- `initiativeTefId`: UUID identifier (auto-generated if missing)
- `initiativeId`: Initiative UUID reference (optional, auto-linked if context available)
- `tefId`: TEF category UUID reference (optional, auto-linked if context available)
- `notes`: Catch-all field for any valuable insights (e.g., TEF category name, classification rationale, applicability) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Only create an entry when a TEF identifier or category is explicitly tied to an initiative
- Skip vague or speculative mentions
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Do NOT fabricate TEF IDs or categories
- If TEF ID is missing but linkage is clear, still capture with blank tefId
