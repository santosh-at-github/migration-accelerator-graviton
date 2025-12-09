# Schemas and Templates

JSON schemas, templates, and validation utilities for the Graviton Compatibility Validator.

## Files

### Schemas (Validation)
- **`knowledge_base_schema.json`** - Validates knowledge base files
- **`deny_list_schema.json`** - Validates deny list files
- **`graviton_os_compatibility.json`** - OS compatibility configuration
- **`runtime_analysis_result_schema.json`** - Validates runtime analysis results

### Templates (Starting Points)
- **`knowledge_base_template.json`** - Template for creating custom knowledge bases
- **`deny_list_template.json`** - Template for creating deny lists

### Utilities
- **`system_package_scraper.py`** - Generates OS package knowledge bases (legacy - use `scripts/generate_docker_kb.sh` instead)

## Quick Usage

### Validate Files
```bash
# Validate knowledge base
jsonschema -i knowledge_bases/custom_kb.json schemas/knowledge_base_schema.json

# Validate deny list
jsonschema -i deny_lists/custom_deny.json schemas/deny_list_schema.json
```

### Create from Templates
```bash
# Copy template
cp schemas/knowledge_base_template.json my_kb.json

# Edit with your data
nano my_kb.json

# Validate
jsonschema -i my_kb.json schemas/knowledge_base_schema.json

# Test with validator
python graviton_validator.py -k my_kb.json sbom.json
```

## Schema Details

### Knowledge Base Schema

**Required fields:**
```json
{
  "software_compatibility": [
    {
      "name": "software-name",
      "compatibility": {
        "supported_versions": []
      }
    }
  ]
}
```

**Compatibility status values:**
- `compatible` - Full Graviton support
- `compatible_with_notes` - Works with limitations
- `incompatible` - Does not work on Graviton
- `unknown` - Status not determined

**Version range operators:**
- `>=1.0.0` - Greater than or equal
- `<=2.0.0` - Less than or equal
- `>`, `<`, `==`, `!=` - Standard comparisons
- `~1.0.0` - Patch compatible
- `^1.0.0` - Minor compatible
- `>=1.0.0,<2.0.0` - Combined ranges

### Deny List Schema

**Required fields:**
```json
{
  "deny_list": [
    {
      "name": "package-name",
      "reason": "Why this package is denied"
    }
  ]
}
```

## Common Validation Errors

```bash
# Missing required field
"'name' is a required property"
→ Add name field to entry

# Invalid status value
"'maybe_compatible' is not one of [...]"
→ Use: compatible, compatible_with_notes, incompatible, or unknown

# Invalid version range
"Version range '>=1.0.0 and <2.0.0' does not match pattern"
→ Use comma: '>=1.0.0,<2.0.0'
```

## See Also

- **[Knowledge Base Guide](../docs/KNOWLEDGE_BASE_GUIDE.md)** - Detailed KB creation guide with examples
- **[Scripts README](../scripts/README.md)** - Helper scripts for updating knowledge bases
- **[Knowledge Bases README](../knowledge_bases/README.md)** - KB directory structure and usage
