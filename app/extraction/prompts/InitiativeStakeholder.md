Context: Relationships between initiatives and stakeholders within the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `initiativeStakeholderId`: UUID identifier (auto-generated if missing)
- `initiativeId`: Initiative UUID reference (optional, auto-linked if context available)
- `stakeholderId`: Stakeholder UUID reference (optional, auto-linked if context available)
- `role`: Stakeholder role in initiative (e.g., "lead", "partner", "funder", "advisor", "implementer") - only if explicitly stated
- `notes`: Catch-all field for any valuable insights (e.g., responsibilities, contribution level, engagement status, contact information) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Capture rows that pair a stakeholder to an initiative with a stated or implied role
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Skip only when NEITHER initiative NOR stakeholder can be identified
- Extract role descriptions exactly as stated in document
