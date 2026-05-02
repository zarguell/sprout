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
    """All template files must exist, load, and render valid HTML with correctly embedded data."""

    def test_templates_load(self):
        from fastapi.templating import Jinja2Templates

        templates = Jinja2Templates(directory=str(APP_DIR.parent / "templates"))
        env = templates.env

        for name in ["base.html", "login.html", "dashboard.html", "archive.html", "plant_detail.html"]:
            template = env.get_template(name)
            assert template is not None, f"Missing template: {name}"

    def test_dashboard_renders_valid_html(self):
        """Dashboard template must output parseable JSON script tags and valid Alpine init."""
        from fastapi.templating import Jinja2Templates
        import json

        templates = Jinja2Templates(directory=str(APP_DIR.parent / "templates"))
        env = templates.env
        template = env.get_template("dashboard.html")

        plant_data = [
            {
                "id": 1, "name": "Monstera", "species": "Monstera deliciosa",
                "location": "Living Room", "notes": None, "archived": False,
                "archived_at": None, "archived_reason": None,
                "thumbnail_url": None, "next_task": None,
            }
        ]
        result = template.render(plants=plant_data)

        # Must use function-call pattern (not inline JSON that breaks HTML attribute)
        assert 'x-data="dashData()"' in result or "x-data='dashData()'" in result, \
            "x-data must be a function call, not inline JSON"

        # Script data tag must contain valid parseable JSON
        import re
        m = re.search(
            r'<script id="dash-data" type="application/json">(.*?)</script>',
            result, re.DOTALL
        )
        assert m, "Missing dash-data script tag"
        data = json.loads(m.group(1))
        assert len(data) == 1
        assert data[0]["name"] == "Monstera"

        # dashData() function must be present in scripts block
        assert "function dashData()" in result, "Missing dashData() function"

    def test_plant_detail_renders_valid_html(self):
        """Plant detail template must embed all four data sources correctly."""
        from fastapi.templating import Jinja2Templates
        import json
        import re

        templates = Jinja2Templates(directory=str(APP_DIR.parent / "templates"))
        env = templates.env
        template = env.get_template("plant_detail.html")

        plant = {
            "id": 1, "name": "Monstera", "species": "Monstera", "location": "LR",
            "notes": "Test note with 'single quotes' and \"double quotes\"",
            "archived": False, "archived_at": None, "archived_reason": None,
        }
        tasks = [
            {"id": 1, "type": "water", "label": "Water", "due_date": "2026-06-01", "plant_id": 1}
        ]
        photos = []
        activity = [
            {"id": 1, "type": "note", "notes": "Watered today", "created_at": "2026-05-02T12:00:00Z"}
        ]

        result = template.render(plant=plant, tasks=tasks, photos=photos, activity=activity)

        # Must use function-call pattern
        assert 'x-data="plantDetailData()"' in result or "x-data='plantDetailData()'" in result

        # All four data sources must be parseable
        for sid in ["plant-data", "tasks-data", "photos-data", "activity-data"]:
            m = re.search(
                rf'<script id="{sid}" type="application/json">(.*?)</script>',
                result, re.DOTALL
            )
            assert m, f"Missing {sid} script tag"
            json.loads(m.group(1))  # Must be valid JSON

        # Data with special characters must survive round-trip
        plant_parsed = json.loads(
            re.search(
                r'<script id="plant-data" type="application/json">(.*?)</script>',
                result, re.DOTALL
            ).group(1)
        )
        assert plant_parsed["notes"] == plant["notes"], \
            "Special characters in notes must survive JSON serialization"

        # plantDetailData() function must be present
        assert "function plantDetailData()" in result

    def test_archive_renders_valid_html(self):
        """Archive template must render parseable JSON data."""
        from fastapi.templating import Jinja2Templates
        import json
        import re

        templates = Jinja2Templates(directory=str(APP_DIR.parent / "templates"))
        env = templates.env
        template = env.get_template("archive.html")

        plants = [
            {
                "id": 1, "name": "Dead Plant", "species": None,
                "archived": True, "archived_at": "2026-04-01T00:00:00Z",
                "archived_reason": "Died",
            }
        ]
        result = template.render(plants=plants)

        assert 'x-data="archiveData()"' in result or "x-data='archiveData()'" in result

        m = re.search(
            r'<script id="archive-data" type="application/json">(.*?)</script>',
            result, re.DOTALL
        )
        assert m, "Missing archive-data script tag"
        data = json.loads(m.group(1))
        assert len(data) == 1
        assert data[0]["name"] == "Dead Plant"

        assert "function archiveData()" in result
