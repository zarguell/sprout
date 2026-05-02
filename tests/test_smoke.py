"""Syntax and import smoke tests — catch broken files before they ship."""

import importlib
import py_compile
import subprocess
from pathlib import Path

import pytest

APP_DIR = Path(__file__).parent.parent / "app"


class TestSyntax:
    """Every .py file in app/ must compile cleanly."""

    def test_all_app_files_compile(self):
        for path in APP_DIR.rglob("*.py"):
            py_compile.compile(path, doraise=True)


class TestImports:
    """All app modules must be importable."""

    @pytest.mark.parametrize(
        "module",
        [
            "app.database",
            "app.models",
            "app.auth",
            "app.schemas",
            "app.images",
            "app.background",
            "app.main",
            "app.routers.users",
            "app.routers.plants",
            "app.routers.tasks",
            "app.routers.photos",
            "app.routers.activity",
        ],
    )
    def test_module_imports(self, module):
        importlib.import_module(module)


class TestNoGarbage:
    """Catch stray XML/tool artifacts that break Python files."""

    @pytest.mark.parametrize("pattern", ["</content>", "<parameter ", "</parameter>"])
    def test_no_xml_garbage_in_app(self, pattern):
        for path in APP_DIR.rglob("*.py"):
            content = path.read_text()
            assert pattern not in content, f"{path}: found '{pattern}'"


class TestAlembic:
    """Alembic config must be valid and migrations must load."""

    def test_alembic_config_loads(self):
        from alembic.config import Config

        cfg = Config(str(APP_DIR.parent / "alembic.ini"))
        assert cfg.get_main_option("script_location") is not None

    def test_alembic_env_imports(self):
        from alembic import context
        from app.models import Base

        # Just verify the metadata has tables
        assert len(Base.metadata.tables) > 0


class TestTemplates:
    """All template files must exist and be loadable."""

    def test_templates_load(self):
        from fastapi.templating import Jinja2Templates

        templates = Jinja2Templates(directory=str(APP_DIR.parent / "templates"))
        env = templates.env

        for name in ["base.html", "login.html", "dashboard.html", "archive.html", "plant_detail.html"]:
            template = env.get_template(name)
            assert template is not None, f"Missing template: {name}"
