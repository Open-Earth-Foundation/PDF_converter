Context: Climate actions, projects, measures, or interventions described in the Climate City Contract.

An Initiative is any concrete action, project, or measure that the city or stakeholders are implementing to reduce emissions or advance climate neutrality. Look for:

- Numbered actions in portfolio tables (e.g., "B-2.1 Description of action portfolios")
- Individual project descriptions with titles like "Action name" or measure names
- Infrastructure projects (solar plants, district heating, hydrogen systems, etc.)
- Mobility measures (tram extensions, cycling infrastructure, etc.)
- Building/renovation programmes
- Circular economy and waste initiatives
- Green infrastructure projects

Field mapping guidance:

- "Action name" or project title → title
- "Action description" or project summary → description
- Year references like "starting 2024", "completed by 2027", "2025-2030" → startYear / endYear (extract just the 4-digit year as integer)
- "Total costs" or investment amounts → totalEstimatedCost (as integer, e.g., "40 million euros" → 40000000)
- Currency mentioned → currency (e.g., "EUR", "euros")
- Project phase or timeline status → status (e.g., "planned", "in progress", "completed")
- Any other useful information not covered by specific fields → misc (as a JSON object)

Rules:

- Extract each discrete action/project as a separate Initiative
- If timing or costs are "not quantifiable" or missing, leave those fields null
- Capture as many initiatives as present in the document - there may be dozens
- Do not invent numeric values; only extract what is explicitly stated
