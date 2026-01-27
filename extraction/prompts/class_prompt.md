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

Table context (same-table only; avoid duplicates):

```
{table_context}
```

**EXTRACTION INSTRUCTIONS**:

1. Scan the entire Markdown for all mentions matching {class_name} (tables, lists, paragraphs, inline mentions).
2. For each instance: populate an object using the exact schema aliases as JSON keys.
3. **For verified fields** (fields with accompanying `_quote` and `_confidence` fields):
   - Set the main field to the extracted value (e.g., `"targetYear": "2030"`)
   - Set the `_quote` field with a verbatim quote from the document (e.g., `"targetYear_quote": "by 2030"`)
   - Set the `_confidence` field with a score 0.0-1.0 (e.g., `"targetYear_confidence": 0.95`)
4. Call `record_instances` with the `items` array containing all extracted objects.
   - Example: `record_instances({{"items": [...], "source_notes": "Found X instances"}})`
5. If you find zero instances, call `record_instances` with an empty items array OR call `all_extracted` with a reason.
6. After extracting all instances, call `all_extracted` with a reason explaining the extraction result.

**IMPORTANT**: Every response must contain tool calls. No plain text responses.

**Verified Field Examples**:

For a target year field (quote MUST be verbatim from source):
```json
{{
  "targetYear": "2030",
  "targetYear_quote": "by 2030",
  "targetYear_confidence": 0.95
}}
```

For an amount field (quote MUST be verbatim from source):
```json
{{
  "totalAmount": "5000000",
  "totalAmount_quote": "5 million euros",
  "totalAmount_confidence": 0.9
}}
```

For an optional field not found in source (ONLY if document explicitly states absence):
```json
{{
  "status": null,
  "status_quote": "status not mentioned",
  "status_confidence": 0.85
}}
```
⚠️ **ONLY VALID IF** "status not mentioned" or similar text appears verbatim in the source document. Otherwise, OMIT all three fields (status, status_quote, status_confidence) entirely.

**CRITICAL: null Values with Quotes**:
- Use `null` value ONLY when the document explicitly states the absence (e.g., "not specified", "not available", "N/A")
- The quote MUST be found verbatim in the source document
- If the document is silent (just doesn't mention the field), OMIT all three related fields (value, _quote, _confidence)
- Example valid: `"baselineYear_quote": "baseline not specified"` (if this exact text is in source)
- Example invalid: `"baselineYear_quote": "no baseline information found"` (if this exact text is NOT in source)

**CRITICAL**: All quotes MUST be verbatim text from the source document. Paraphrased or inferred quotes will cause record rejection.

Markdown to parse:

```
{markdown}
```
