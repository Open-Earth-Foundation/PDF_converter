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
3. Call `record_instances` with the `items` array containing all extracted objects.
   - Example: `record_instances({{"items": [...], "source_notes": "Found X instances"}})`
4. If you find zero instances, call `record_instances` with an empty items array OR call `all_extracted` with a reason.
5. After extracting all instances, call `all_extracted` with a reason explaining the extraction result.

**IMPORTANT**: Every response must contain tool calls. No plain text responses.

Markdown to parse:

```
{markdown}
```
