**TASK**: Extract all **{class_name}** objects from the Markdown and use tools to communicate results.

**REQUIRED ACTION**: You MUST call tools to respond. Do NOT output any plain text or reasoning.

Class-specific guidance:

```
{class_context}
```

JSON schema for {class_name}:

```
{json_schema}
```

Previously extracted {class_name} instances (avoid duplicates):

```
{existing_summary}
```

**EXTRACTION INSTRUCTIONS**:

1. Scan the entire Markdown for all mentions matching {class_name} (tables, lists, paragraphs, inline mentions).
2. For each instance: populate an object using the exact schema aliases as JSON keys.
3. **For VerifiedField objects** (fields with `value`, `quote`, `confidence`):
   - Extract the value from the source
   - Provide a verbatim quote from the document that supports the value
   - Assign a confidence score (0.0-1.0) based on clarity
   - Example: `"targetYear": {{"value": "2030", "quote": "by 2030", "confidence": 0.95}}`
4. Call `record_instances` with the `items` array containing all extracted objects.
   - Example: `record_instances({{"items": [...], "source_notes": "Found X instances"}})`
5. If you find zero instances, call `record_instances` with an empty items array OR call `all_extracted` with a reason.
6. After extracting all instances, call `all_extracted` with a reason explaining the extraction result.

**IMPORTANT**: Every response must contain tool calls. No plain text responses.

**VerifiedField Examples**:

For a target year field in the schema (quote MUST be verbatim from source):
```json
{{
  "targetYear": {{
    "value": "2030",
    "quote": "by 2030",
    "confidence": 0.95
  }}
}}
```

For an amount field (quote MUST be verbatim from source):
```json
{{
  "totalAmount": {{
    "value": "5000000",
    "quote": "5 million euros",
    "confidence": 0.9
  }}
}}
```

For a field not found in source (ONLY use null if you can find explicit absence text in document):
```json
{{
  "status": {{
    "value": null,
    "quote": "status not mentioned",
    "confidence": 0.85
  }}
}}
```
⚠️ **ONLY VALID IF** "status not mentioned" or similar text appears verbatim in the source document. Otherwise, OMIT this field entirely.

**CRITICAL: null Values with Quotes**:
- Use `value: null` ONLY when the document explicitly states the absence (e.g., "not specified", "not available", "N/A")
- The quote MUST be found verbatim in the source document
- If the document is silent (just doesn't mention the field), do NOT create a null entry—omit the field instead
- Example valid: `"quote": "baseline not specified"` (if this exact text is in source)
- Example invalid: `"quote": "no baseline information found"` (if this exact text is NOT in source)

**CRITICAL**: All quotes MUST be verbatim text from the source document. Paraphrased or inferred quotes will cause record rejection.

Markdown to parse:

```
{markdown}
```
