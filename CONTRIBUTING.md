## Contributing code

### Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)**
- **Mod Organizer 2** (v2.5.2+)

### Setting Up the Dev Environment

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/modorganizer2-nxm-collection-dl.git
   cd modorganizer2-nxm-collection-dl
   ```

2. **Install dependencies with uv:**

   ```bash
   uv sync
   ```

   This creates a virtual environment (`.venv`) and installs all dependencies including `mobase-stubs`, `PyQt6`, and development tools.

3. **Activate the virtual environment:**

   ```bash
   source .venv/bin/activate
   ```

### Pre-commit Hooks

The project uses [pre-commit](https://pre-commit.com/) to enforce code quality. Install the hooks with:

```bash
uv run pre-commit install
```

The hooks will run automatically on every commit and will:

- Check for private keys, trailing whitespace, YAML validity, and large files.
- Run [Ruff](https://docs.astral.sh/ruff/) (linter and formatter) with auto-fix.
- Ensure the `uv.lock` file is up to date.
- Block commits to `master`, `prerelease`, `v6`, and `v1` branches.

You can also run the hooks manually at any time:

```bash
uv run pre-commit run --all-files
```

---

Thank you for contributing! 🚀
