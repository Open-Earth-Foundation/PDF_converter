Context: TEF (Taxonomy for Economic Activities) categories defined or referenced in Climate City Contract documents.

**Available fields ONLY** (no other fields are permitted):

- `tefId`: UUID identifier (auto-generated if missing)
- `parentId`: Parent TEF category UUID reference (optional, for hierarchical relationships)
- `code`: TEF category code (e.g., "1.1", "1.2.1", "1.1.1.1") (REQUIRED)
- `name`: TEF category name (REQUIRED) - exactly as written in document
- `description`: Category description or definition - only if explicitly provided
- `misc`: Any extra relevant data (e.g., applicability scope, examples of activities) as JSON object - optional

**Rules**:

- Extract TEF codes and names exactly as stated in document
- Only include categories that are explicitly mentioned or referenced
- Leave parentId blank if hierarchical relationship is not stated
- Do NOT invent TEF codes or categories
- Preserve formatting and naming exactly as written
