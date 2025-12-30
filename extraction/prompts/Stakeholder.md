Context: Stakeholders mentioned in the Climate City Contract (e.g., municipal bodies, utilities, NGOs, industry partners, citizen groups).

**Available fields ONLY** (no other fields are permitted):

- `stakeholderId`: UUID identifier (auto-generated if missing)
- `name`: Stakeholder name (REQUIRED) - extract exactly as written in document
- `type`: Stakeholder type/category (e.g., "NGO", "government_agency", "utility") - only if explicitly stated
- `description`: Brief description of the stakeholder - only if present
- `notes`: Catch-all field for any valuable insights or additional data about the stakeholder (e.g., role, contact details mentioned, organizational focus, relationships) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- ONLY populate the fields listed above. NO other fields (city, contact_email, phone, address, etc.)
- `name` is the only required field - extract it exactly as written
- For `type`, use natural categories from the document (e.g., "municipality", "NGO", "business", "university")
- Skip stakeholders when names are ambiguous or not explicitly listed
- Put additional info in `notes` or `misc` field, NOT in extra fields
