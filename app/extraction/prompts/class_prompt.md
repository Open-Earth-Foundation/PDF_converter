Extract **{class_name}** objects from the Markdown below.

Class-specific guidance:
```
{class_context}
```

JSON schema for this class:
```
{json_schema}
```

Previously stored instances for this class (do not duplicate):
```
{existing_summary}
```

Guidance:
- Scan the entire Markdown for tables, bullet lists, or paragraphs that correspond to the schema fields.
- Use schema aliases exactly as keys when populating objects.
- Convert every applicable row; call `record_instances` as many times as needed.
- When no additional instances remain, call `all_extracted`.

Markdown to parse:
```
{markdown}
```
