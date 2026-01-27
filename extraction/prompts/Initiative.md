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
- `description`: Initiative description or summary (REQUIRED) - extract the action description, objectives, or any text that describes what the initiative does
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence) - ALL OPTIONAL:
  - `startYear`: Start year as 4-digit integer (OPTIONAL)
  - `startYear_quote`: Verbatim quote from document (OPTIONAL)
  - `startYear_confidence`: Confidence score 0.0-1.0 (OPTIONAL)
  - `endYear`: End year as 4-digit integer (OPTIONAL)
  - `endYear_quote`: Verbatim quote from document (OPTIONAL)
  - `endYear_confidence`: Confidence score 0.0-1.0 (OPTIONAL)
  - `totalEstimatedCost`: Total cost as integer (OPTIONAL)
  - `totalEstimatedCost_quote`: Verbatim quote from document (OPTIONAL)
  - `totalEstimatedCost_confidence`: Confidence score 0.0-1.0 (OPTIONAL)
  - `status`: Project status (e.g., "planned", "in progress", "completed") (OPTIONAL)
  - `status_quote`: Verbatim quote from document (OPTIONAL)
  - `status_confidence`: Confidence score 0.0-1.0 (OPTIONAL)
- `currency`: Currency code (REQUIRED) - extract if explicitly mentioned (e.g., "EUR", "USD"), if costs are mentioned without explicit currency, use "EUR" as default for European cities
- `notes`: Additional context and insights (REQUIRED) - Extract any valuable information about the initiative including: expected outcomes, implementation details, co-benefits, risks, interdependencies, funding status, or any other meaningful context not covered by other fields. If no additional context is available, write "No additional details provided"
- `misc`: Any extra relevant data as JSON object - optional

**Verified Field Rules**:

For verified fields (`startYear`, `endYear`, `totalEstimatedCost`, `status`):

- Each verified field requires THREE fields in your output: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document
- The `_confidence` must be a number between 0.0 and 1.0
- Set confidence based on clarity of the information
- If a field is not mentioned in the source document, OMIT ALL THREE related fields (value, _quote, _confidence)

**Example**:
```json
{
  "title": "Solar power plant expansion",
  "description": "Installation of additional solar panels on municipal buildings to increase renewable energy generation capacity",
  "startYear": "2024",
  "startYear_quote": "starting 2024",
  "startYear_confidence": 0.95,
  "totalEstimatedCost": "40000000",
  "totalEstimatedCost_quote": "40 million EUR",
  "totalEstimatedCost_confidence": 0.95,
  "currency": "EUR",
  "notes": "Project aims to reduce CO2 emissions by 500 tonnes annually. Funded through municipal budget and EU grants."
}
```

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
- **ALWAYS provide `description`, `currency`, and `notes` fields - they are REQUIRED**
- If the description is brief, expand it with any available context from the document
- For currency: extract if mentioned explicitly, otherwise use "EUR" for European cities
- For notes: include any relevant context; if truly no details exist, write "No additional details provided"
- If timing or costs are "not quantifiable" or missing, omit those verified fields (startYear, endYear, totalEstimatedCost are optional)
- Capture as many initiatives as present in the document - there may be dozens
- Do not invent numeric values; only extract what is explicitly stated in the source
