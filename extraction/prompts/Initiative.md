Context: Climate actions, projects, measures, or interventions described in the Climate City Contract.

An Initiative is any concrete action, project, or measure that the city or stakeholders are implementing to reduce emissions or advance climate neutrality. Look for:

- Numbered actions in portfolio tables (e.g., "B-2.1 Description of action portfolios")
- Individual project descriptions with titles like "Action name" or measure names
- Infrastructure projects (solar plants, district heating, hydrogen systems, etc.)
- Mobility measures (tram extensions, cycling infrastructure, etc.)
- Building and renovation programmes
- Circular economy and waste initiatives
- Green infrastructure projects

**Available fields ONLY** (no other fields are permitted):

- `initiativeId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID (optional, auto-linked if context available)
- `title`: Initiative name (REQUIRED) - exactly as written
- `description`: Initiative description or summary
- `startYear`: **VERIFIED FIELD** - Start year as 4-digit integer (e.g., "starting 2024" -> {"value": "2024", "quote": "starting 2024", "confidence": 0.95}) - OPTIONAL, only if explicitly stated
- `endYear`: **VERIFIED FIELD** - End year as 4-digit integer (e.g., "completed by 2027" -> {"value": "2027", "quote": "completed by 2027", "confidence": 0.95}) - OPTIONAL, only if explicitly stated
- `totalEstimatedCost`: **VERIFIED FIELD** - Total cost as integer (e.g., "40 million EUR" -> {"value": "40000000", "quote": "40 million EUR", "confidence": 0.95}) - OPTIONAL, only if explicitly stated
- `currency`: Currency code (e.g., "EUR", "USD") - only if mentioned
- `status`: **VERIFIED FIELD** - Project status (e.g., "planned", "in progress", "completed") as VerifiedField - OPTIONAL, only if explicitly stated
- `notes`: Catch-all field for any valuable insights or additional data about the initiative (e.g., expected outcomes, stakeholders involved, co-benefits, risks, interdependencies, funding status) - USE THIS FIELD for anything meaningful not covered by other fields
- `misc`: Any extra relevant data as JSON object - optional

**Verified Field Rules**:

For `startYear`, `endYear`, `totalEstimatedCost`, and `status`:

- Each must be output as a VerifiedField object with `value`, `quote`, and `confidence` properties (only when field is present)
- The `quote` must be verbatim text from the document
- Set confidence based on clarity of the information
- Omit fields that are not mentioned in the source document

**Important: Quote Validation**

- Your quotes will be validated against the source document
- If a quote is NOT found in the source, the entire record will be REJECTED
- Use only exact verbatim text from the document as quotes

**Field mapping examples**:

- "Action name" or project title -> `title`
- "Action description" or project summary -> `description`
- Year references like "starting 2024", "2025-2030" -> extract just the 4-digit year as integer
- "Total costs" or investment amounts -> `totalEstimatedCost`

**Rules**:

- Extract each discrete action or project as a separate Initiative
- If timing or costs are "not quantifiable" or missing, omit those fields (they are optional)
- Capture as many initiatives as present in the document - there may be dozens
- Do not invent numeric values; only extract what is explicitly stated in the source
