from app.database import RunRepository


def test_project_and_entries_lifecycle(tmp_path):
    repository = RunRepository(tmp_path / "phase3.db")
    repository.initialize()
    project = repository.create_project({
        "name": "TimeLogger", "aliases": ["TL"], "domains": ["github.com"],
        "keywords": ["ActivityWatch"], "active": True,
    })
    assert repository.list_projects()[0]["aliases"] == ["TL"]
    updated = repository.update_project(project["id"], {
        **project, "name": "TimeLogger 3000", "keywords": ["LM Studio"]
    })
    assert updated["name"] == "TimeLogger 3000"
    assert repository.delete_project(project["id"]) is True
