Context: Stakeholders mentioned in the Climate City Contract (e.g., municipal bodies, utilities, NGOs, industry partners, citizen groups).

**Available fields ONLY** (no other fields are permitted):

- `stakeholderId`: UUID identifier (auto-generated if missing)
- `name`: Stakeholder name (REQUIRED) - extract exactly as written in document
- `type`: Stakeholder type/category (e.g., "NGO", "government_agency", "utility") - only if explicitly stated
- `description`: Brief description of the stakeholder (REQUIRED) - extract their role, function, or any descriptive text about the organization. If no description is provided in the document, infer from context or write "Stakeholder mentioned in climate action context"
- `notes`: Additional context and details (REQUIRED) - Extract any valuable information including: role in initiatives, contact details, organizational focus, relationships with other stakeholders, or any other relevant context. If no additional context is available, write "No additional details provided"

**Rules**:

- ONLY populate the fields listed above. NO other fields (city, contact_email, phone, address, etc.)
- **ALWAYS provide `description` and `notes` fields - they are REQUIRED**
- `name`, `description`, and `notes` are required fields
- For `type`, use natural categories from the document (e.g., "municipality", "NGO", "business", "university")
- Skip stakeholders when names are ambiguous or not explicitly listed
- Put additional info in `notes` or `misc` field, NOT in extra fields
