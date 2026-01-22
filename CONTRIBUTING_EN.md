# Contributing Guide

Thank you for your interest in the Work-by-Roles project! We welcome all forms of contributions.

## 🤝 How to Contribute

### Reporting Issues

If you find a bug or have a feature suggestion, please:

1. Search [GitHub Issues](https://github.com/puppyfront-web/work-by-roles/issues) to see if a similar issue already exists
2. If not, create a new issue including:
   - Clear problem description
   - Reproduction steps (if it's a bug)
   - Expected behavior and actual behavior
   - Environment information (Python version, operating system, etc.)

### Submitting Code

1. **Fork the Project**
   ```bash
   git clone https://github.com/your-username/work-by-roles.git
   cd work-by-roles
   ```

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run Tests**
   ```bash
   pytest
   ```

5. **Commit Code**
   ```bash
   git add .
   git commit -m "feat: Add new feature description"
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Create a Pull Request on GitHub
   - Describe your changes and reasons
   - Ensure all tests pass

## 📝 Code Standards

### Code Style

- Follow PEP 8 Python code standards
- Use type hints (Type Hints)
- Follow SOLID principles
- Keep code concise and readable

### Commit Message Standards

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation update
- `style:` Code formatting (doesn't affect functionality)
- `refactor:` Code refactoring
- `test:` Test related
- `chore:` Build process or auxiliary tool changes

Examples:
```
feat: Add SOP import functionality
fix: Fix memory leak in skill selector
docs: Update README.md usage instructions
```

## 🧪 Testing

Before submitting code, please ensure:

1. All existing tests pass
2. Add test cases for new features
3. Test coverage is not lower than current level

Run tests:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific.py

# View coverage
pytest --cov=work_by_roles
```

## 📚 Documentation

If you modify functionality, please also update relevant documentation:

- `README.md` - Main documentation
- `QUICKSTART.md` - Quick start guide
- `docs/ARCHITECTURE.md` - Architecture documentation (if architecture changes are involved)
- `docs/API.md` - API documentation (if API changes are involved)

## 🎯 Contribution Areas

We particularly welcome contributions in the following areas:

- 🐛 Bug fixes
- ✨ New feature implementation
- 📖 Documentation improvements
- 🧪 Test case additions
- 🎨 Code optimization and refactoring
- 🌐 Internationalization support
- 🔌 Plugins and extensions

## ❓ Questions

If you have any questions, you can:

- Ask in [GitHub Discussions](https://github.com/puppyfront-web/work-by-roles/discussions)
- Create a [GitHub Issue](https://github.com/puppyfront-web/work-by-roles/issues)
- Send an email to puppy.front@gmail.com

## 📄 License

By contributing code, you agree that your contributions will be licensed under the MIT License.

---

Thank you again for your contributions! 🎉
