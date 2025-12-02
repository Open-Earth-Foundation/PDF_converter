Context: Climate actions, projects, measures, or interventions described in the Climate City Contract.

An Initiative is any concrete action, project, or measure that the city or stakeholders are implementing to reduce emissions or advance climate neutrality. Look for:

- Numbered actions in portfolio tables (e.g., "B-2.1 Description of action portfolios")
- Individual project descriptions with titles like "Action name" or measure names
- Infrastructure projects (solar plants, district heating, hydrogen systems, etc.)
- Mobility measures (tram extensions, cycling infrastructure, etc.)
- Building/renovation programmes
- Circular economy and waste initiatives
- Green infrastructure projects

**Available fields ONLY** (no other fields are permitted):

- `initiativeId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID (optional, auto-linked if context available)
- `title`: Initiative name (REQUIRED) - exactly as written
- `description`: Initiative description or summary
- `startYear`: Start year as 4-digit integer (e.g., "starting 2024" → 2024) - only if explicitly stated
- `endYear`: End year as 4-digit integer (e.g., "completed by 2027" → 2027) - only if explicitly stated
- `totalEstimatedCost`: Total cost as integer in smallest currency unit (e.g., "40 million EUR" → 40000000) - only if explicitly stated
- `currency`: Currency code (e.g., "EUR", "USD") - only if mentioned
- `status`: Project status (e.g., "planned", "in progress", "completed") - only if explicitly stated
- `notes`: Catch-all field for any valuable insights or additional data about the initiative (e.g., expected outcomes, stakeholders involved, co-benefits, risks, interdependencies, funding status) - USE THIS FIELD for anything meaningful not covered by other fields
- `misc`: Any extra relevant data as JSON object - optional

**Field mapping examples**:

- "Action name" or project title → `title`
- "Action description" or project summary → `description`
- Year references like "starting 2024", "2025-2030" → extract just the 4-digit year as integer
- "Total costs" or investment amounts → `totalEstimatedCost`

Rules:

- Extract each discrete action/project as a separate Initiative
- If timing or costs are "not quantifiable" or missing, leave those fields null
- Capture as many initiatives as present in the document - there may be dozens
- Do not invent numeric values; only extract what is explicitly stated
