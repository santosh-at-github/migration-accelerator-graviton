# Version Management

## How to Update Version

**Single file to change**: `graviton_validator/__init__.py`

```python
__version__ = "0.0.1"  # Change this line only
```

All reports, CLI help, and documentation automatically use the new version.

## Version Scheme

- **Alpha**: `0.0.x` (current phase)
- **Beta**: `0.x.y` (next phase) 
- **Stable**: `x.y.z` (public release)

## For Developers

```python
# Get version in code
from graviton_validator.version import get_version
version = get_version()

# Get version info
from graviton_validator.version import get_version_info
info = get_version_info()  # Returns dict with is_alpha, is_beta, etc.
```

## Testing

Tests check version patterns, not hardcoded values:
```python
# Good - flexible
self.assertIn("0.0.", report)  # Matches any alpha version

# Bad - breaks on version updates
self.assertIn("v0.0.1", report)  # Hardcoded
```