from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def make_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("BLACKBOX_DATABASE_URL", f"sqlite:///{tmp_path / 'blackbox.db'}")
    monkeypatch.setenv("BLACKBOX_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    from blackbox_server.main import create_app

    return TestClient(create_app())


def call(client: TestClient, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    payload = response.json()
    assert payload["ok"], payload
    return payload["data"]


def expect_error(response: Any, code: str) -> dict[str, Any]:
    payload = response.json()
    assert payload["ok"] is False, payload
    assert payload["error"]["code"] == code, payload
    return payload["error"]


def bootstrap(client: TestClient) -> dict[str, Any]:
    project = call(client, "POST", "/api/v1/projects", json={"key": "alpha-lab", "title": "Alpha Lab"})
    research = call(client, "POST", "/api/v1/researches", json={"project_key": "alpha-lab", "key": "quadrant-options", "title": "Quadrant Options"})
    branch = call(client, "POST", "/api/v1/branches", json={"research_id": research["id"], "key": "s2", "title": "S2"})
    runs = {}
    for name, sharpe, annual, mdd in (("hold", 1.55, 65.01, -29.85), ("h20", 1.29, 45.1, -30.1)):
        run = call(client, "POST", "/api/v1/runs", json={"project_key": "alpha-lab", "research_key": "quadrant-options", "branch_key": "s2", "name": name, "mode": "backtest"})
        call(client, "POST", f"/api/v1/runs/{run['id']}/metrics", json={"namespace": "strategy.summary", "values": {"sharpe": sharpe, "annual_return": annual, "max_drawdown": mdd, "periods_per_year": 252}})
        call(client, "POST", f"/api/v1/runs/{run['id']}/finish", params={"skip_quality_gate": "true"})
        runs[name] = run
    running = call(client, "POST", "/api/v1/runs", json={"project_key": "alpha-lab", "research_key": "quadrant-options", "branch_key": "s2", "name": "tail10", "mode": "paper"})
    assert running["mode"] == "paper"
    return {"project": project, "research": research, "branch": branch, "runs": runs, "running": running}


def test_research_map_two_axis_lifecycle(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        research_map = call(client, "POST", "/api/v1/research-maps", json={"project": "alpha-lab", "research": "quadrant-options", "key": "options-tree", "title": "Options Tree", "created_by_id": "agent-alpha"})
        map_id = research_map["id"]
        assert research_map["project_key"] == "alpha-lab"
        assert research_map["research_key"] == "quadrant-options"
        assert research_map["primary_metric"] == "strategy.summary.sharpe"
        assert research_map["created_by_type"] == "agent"
        assert research_map["node_count"] == 0

        # create is idempotent on key
        assert call(client, "POST", "/api/v1/research-maps", json={"project": ctx["project"]["id"], "key": "options-tree", "title": "ignored"})["id"] == map_id

        root = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes", json={"key": "root", "title": "Turtle CTA", "stage": "live", "decision": "accepted", "binding": {"kind": "research", "id": ctx["research"]["id"]}, "created_by_id": "agent-alpha"})
        assert root["stage"] == "live" and root["decision"] == "accepted" and root["family"] == "accepted"
        assert root["binding"]["kind"] == "research" and root["binding"]["research"]["key"] == "quadrant-options"
        assert root["updated_by_id"] == "agent-alpha"

        s2 = call(client, "PUT", f"/api/v1/research-maps/{map_id}/nodes/s2", json={"title": "S2 + CTA sizing", "parent_key": "root", "stage": "experiment", "binding": {"kind": "branch", "id": ctx["branch"]["id"]}, "created_by_id": "agent-alpha"})
        assert s2["created"] is True and s2["parent_key"] == "root" and s2["stage"] == "experiment" and s2["decision"] is None
        assert s2["binding"]["branch"]["run_count"] == 3
        assert s2["binding"]["run"]["name"] == "hold"  # champion = best sharpe among completed runs
        assert s2["binding"]["run"]["metrics"]["sharpe"] == 1.55

        hold = call(client, "PUT", f"/api/v1/research-maps/{map_id}/nodes/hold", json={
            "title": "HOLD", "parent_key": "s2", "stage": "experiment",
            "hypothesis": "Never exit on volatility expansion.",
            "change": [{"what": "exit", "from": "leave state", "to": "only on valuation flip"}, "no minimum holding period"],
            "binding": {"kind": "run", "id": ctx["runs"]["hold"]["id"]}, "created_by_id": "agent-alpha",
        })
        assert hold["change"] == [{"what": "exit", "to": "only on valuation flip", "from": "leave state"}, "no minimum holding period"]
        assert hold["flags"] == ["ready"]  # bound run completed, no decision yet
        assert hold["binding"]["run"]["quality"]["severity"] in {"ok", "warning", "error"}

        # decide: decision + verdict + decision note on the bound run
        decided = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes/hold/decide", json={"decision": "accepted", "verdict": "Accept as baseline: right tail fully kept.", "reading": ["2025 +167%"], "caveats": ["2024/25 concentration"], "note": True, "created_by_id": "human:jiang", "created_by_type": "human"})
        assert decided["decision"] == "accepted" and decided["family"] == "accepted" and decided["flags"] == []
        assert decided["note"]["run_id"] == ctx["runs"]["hold"]["id"]
        notes = call(client, "GET", f"/api/v1/runs/{ctx['runs']['hold']['id']}/notes")
        assert [n["kind"] for n in notes] == ["decision"]
        assert notes[0]["summary"] == "Accept as baseline: right tail fully kept."
        assert notes[0]["author_type"] == "human"
        assert notes[0]["structured_json"]["node"] == "hold"
        assert decided["binding"]["run"]["notes"][0]["kind"] == "decision"

        # baseline pointer + derived mainline
        base = call(client, "POST", f"/api/v1/research-maps/{map_id}/baseline", json={"node_key": "hold", "reason": "user picked", "created_by_id": "human:jiang"})
        assert base["baseline_node_key"] == "hold"
        assert base["baseline"]["run"]["metrics"]["primary"] == {"metric": "strategy.summary.sharpe", "value": 1.55}
        assert base["mainline_keys"] == ["hold", "root", "s2"]
        expect_error(client.post(f"/api/v1/research-maps/{map_id}/baseline", json={"node_key": "missing"}), "NOT_FOUND")

        h20 = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes", json={"key": "h20", "title": "HOLD20", "parent_key": "hold", "stage": "experiment", "binding": {"kind": "run", "id": ctx["runs"]["h20"]["id"]}})
        call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes/h20/decide", json={"decision": "rejected", "verdict": "Reject: 2025 lags."})
        tail10 = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes", json={"key": "tail10", "title": "10d put", "parent_key": "hold", "stage": "experiment", "binding": {"kind": "run", "id": ctx["running"]["id"]}})
        assert tail10["flags"] == [] and tail10["binding"]["run"]["status"] == "running" and tail10["binding"]["run"]["metrics"] is None
        idea = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes", json={"key": "ivrv", "title": "IV-RV gate", "parent_key": "hold"})
        assert idea["stage"] == "idea" and idea["family"] == "active" and idea["binding"] is None

        # stage only advances unless a reason is given
        adv = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes/hold/advance", json={"stage": "validation", "date_label": "09-14"})
        assert adv["stage"] == "validation" and adv["date_label"] == "09-14"
        expect_error(client.post(f"/api/v1/research-maps/{map_id}/nodes/hold/advance", json={"stage": "experiment"}), "VALIDATION_ERROR")
        back = call(client, "POST", f"/api/v1/research-maps/{map_id}/nodes/hold/advance", json={"stage": "experiment", "reason": "validation not run yet"})
        assert back["stage"] == "experiment"

        # binding must exist; cycles rejected; missing parent
        expect_error(client.patch(f"/api/v1/research-maps/{map_id}/nodes/h20", json={"binding": {"kind": "run", "id": "run_missing"}}), "NOT_FOUND")
        expect_error(client.patch(f"/api/v1/research-maps/{map_id}/nodes/root", json={"parent_key": "hold"}), "VALIDATION_ERROR")
        expect_error(client.post(f"/api/v1/research-maps/{map_id}/nodes", json={"key": "x", "title": "X", "parent_key": "nope"}), "NOT_FOUND")

        detail = call(client, "GET", f"/api/v1/research-maps/{map_id}")
        assert detail["counts"]["families"] == {"accepted": 2, "ended": 1, "active": 3}
        assert detail["counts"]["stages"] == {"live": 1, "experiment": 4, "idea": 1}
        assert detail["counts"]["undecided"] == 3
        assert [n["key"] for n in detail["recent"]][:1] == ["hold"] or detail["recent"][0]["key"] in {"hold", "ivrv", "tail10", "h20"}
        tree = detail["tree"]
        assert tree[0]["key"] == "root" and tree[0]["children"][0]["key"] == "s2"
        assert [c["key"] for c in tree[0]["children"][0]["children"][0]["children"]] == ["h20", "tail10", "ivrv"]
        hold_row = next(n for n in detail["nodes"] if n["key"] == "hold")
        assert hold_row["is_baseline"] is True and hold_row["is_mainline"] is True and hold_row["parent_key"] == "s2"
        assert next(n for n in detail["nodes"] if n["key"] == "h20")["is_mainline"] is False

        status = call(client, "GET", f"/api/v1/research-maps/{map_id}/status")
        assert status["baseline"] == "hold" and status["mainline"] == 3
        assert [n["key"] for n in status["results_without_decision"]] == ["s2"]
        assert [n["key"] for n in status["unbound"]] == ["ivrv"]
        assert status["runs_without_node"] == []  # all completed runs of the research are bound

        lint = call(client, "GET", f"/api/v1/research-maps/{map_id}/lint")
        assert lint["severity"] in {"ok", "warning", "error"}  # accepted node bound to a run without a curve fails the quality gate
        assert all(issue["code"] != "accepted_without_note" or issue["node_key"] != "hold" for issue in lint["issues"])
        call(client, "PATCH", f"/api/v1/research-maps/{map_id}/nodes/ivrv", json={"title": "a very long title that goes far beyond fourteen characters", "decision": "kept"})
        lint = call(client, "GET", f"/api/v1/research-maps/{map_id}/lint")
        codes = {(i["node_key"], i["code"]) for i in lint["issues"]}
        assert ("ivrv", "title_too_long") in codes and ("ivrv", "decision_without_verdict") in codes

        revisions = call(client, "GET", f"/api/v1/research-maps/{map_id}/revisions", params={"node_key": "hold"})
        actions = [r["action"] for r in revisions]
        assert "node.create" in actions and "node.decide" in actions and "node.advance" in actions and "map.baseline" in actions
        decide_rev = next(r for r in revisions if r["action"] == "node.decide")
        assert decide_rev["changes"]["decision"] == {"from": None, "to": "accepted"} and decide_rev["by_id"] == "human:jiang"

        # research lists include maps bound to its entities; research-map list filter too
        assert [m["id"] for m in call(client, "GET", f"/api/v1/researches/{ctx['research']['id']}/research-maps")] == [map_id]
        assert [m["id"] for m in call(client, "GET", "/api/v1/research-maps", params={"research": "quadrant-options"})] == [map_id]
        assert [m["id"] for m in call(client, "GET", "/api/v1/research-maps", params={"project": "alpha-lab", "key": "options-tree"})] == [map_id]

        # export round-trips, delete cascades and clears the baseline
        exported = call(client, "GET", f"/api/v1/research-maps/{map_id}/export")
        assert exported["baseline"] == "hold" and exported["nodes"][0]["children"][0]["children"][0]["binding"] == {"kind": "run", "id": ctx["runs"]["hold"]["id"]}
        roundtrip = call(client, "POST", "/api/v1/research-maps/import", json={**exported, "mode": "replace"})
        assert roundtrip["nodes"]["created"] == 0 and roundtrip["nodes"]["deleted"] == 0
        assert call(client, "GET", f"/api/v1/research-maps/{map_id}/export") == exported
        expect_error(client.delete(f"/api/v1/research-maps/{map_id}/nodes/hold"), "STATE_ERROR")
        deleted = call(client, "DELETE", f"/api/v1/research-maps/{map_id}/nodes/hold", params={"cascade": "true"})
        assert sorted(deleted["deleted"]) == ["h20", "hold", "ivrv", "tail10"]
        after = call(client, "GET", f"/api/v1/research-maps/{map_id}")
        assert after["baseline_node_key"] is None and [n["key"] for n in after["nodes"]] == ["root", "s2"]

        db = call(client, "GET", "/api/v1/system/db-status")
        assert {"research_maps", "research_map_nodes", "research_map_revisions"} <= set(db["tables"]) and db["needs_migration"] is False


def test_research_map_document_import(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        document = {
            "project": "alpha-lab", "research": "quadrant-options", "key": "options-tree", "title": "Options Tree", "baseline": "hold",
            "created_by_id": "agent-alpha",
            "nodes": [{
                "key": "root", "title": "Turtle CTA", "stage": "live", "decision": "accepted",
                "children": [
                    {"key": "exec", "title": "Execution", "stage": "experiment", "decision": "rejected", "verdict": "Reject."},
                    {"key": "s2", "title": "S2", "stage": "experiment", "decision": "superseded", "binding": {"kind": "branch", "id": ctx["branch"]["id"]},
                     "children": [{"key": "hold", "title": "HOLD", "stage": "experiment", "decision": "accepted", "verdict": "Accept.", "binding": {"kind": "run", "id": ctx["runs"]["hold"]["id"]}}]},
                ],
            }],
        }
        result = call(client, "POST", "/api/v1/research-maps/import", json=document)
        assert result["map_created"] is True
        assert result["nodes"] == {"created": 4, "updated": 0, "unchanged": 0, "deleted": 0, "total": 4}
        assert result["map"]["baseline_node_key"] == "hold" and result["map"]["mainline_keys"] == ["hold", "root", "s2"]
        by_key = {n["key"]: n for n in result["map"]["nodes"]}
        assert by_key["s2"]["family"] == "ended" and by_key["s2"]["decision"] == "superseded"
        assert by_key["exec"]["position"] == 0 and by_key["s2"]["position"] == 1
        map_id = result["map"]["id"]

        # merge: update one, add one, keep others; unchanged count reported
        document["nodes"][0]["children"][1]["children"][0]["caveats"] = ["capacity unverified"]
        document["nodes"][0]["children"].append({"key": "drift", "title": "Drift", "stage": "hypothesis"})
        merged = call(client, "POST", "/api/v1/research-maps/import", json=document)
        assert merged["nodes"] == {"created": 1, "updated": 1, "unchanged": 3, "deleted": 0, "total": 5}

        # replace prunes; duplicate keys and unknown bindings rejected
        document["nodes"][0]["children"] = [document["nodes"][0]["children"][1]]
        replaced = call(client, "POST", "/api/v1/research-maps/import", json={**document, "mode": "replace"})
        assert replaced["nodes"]["deleted"] == 2 and sorted(n["key"] for n in replaced["map"]["nodes"]) == ["hold", "root", "s2"]
        expect_error(client.post("/api/v1/research-maps/import", json={**document, "nodes": [{"key": "d", "title": "A"}, {"key": "d", "title": "B"}]}), "VALIDATION_ERROR")
        expect_error(client.post("/api/v1/research-maps/import", json={**document, "nodes": [{"key": "bad", "title": "B", "binding": {"kind": "run", "id": "run_missing"}}]}), "NOT_FOUND")
        expect_error(client.post("/api/v1/research-maps/import", json={**document, "baseline": "nope"}), "NOT_FOUND")

        revisions = call(client, "GET", f"/api/v1/research-maps/{map_id}/revisions")
        assert any(r["action"] == "map.import" for r in revisions) and any(r["action"] == "map.baseline" for r in revisions)


def test_cli_map_commands_build_expected_requests(monkeypatch, tmp_path: Path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")
    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> Any:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        if method == "GET" and path == "/api/v1/research-maps":
            return [{"id": "rmap_1", "key": "options-tree"}]
        if method == "GET" and path.endswith("/export"):
            return {"project": "alpha-lab", "key": "options-tree", "title": "T", "nodes": []}
        return {"id": "rmap_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    run = lambda argv: cli_main.dispatch(cli_main.build_parser().parse_args(argv))  # noqa: E731

    run(["map", "init", "--project", "alpha-lab", "--research", "quadrant-options", "--key", "options-tree", "--title", "Options Tree", "--primary-metric", "strategy.summary.calmar", "--created-by-id", "agent-alpha"])
    assert calls[-1]["method"] == "POST" and calls[-1]["path"] == "/api/v1/research-maps"
    assert calls[-1]["json"] == {"project": "alpha-lab", "key": "options-tree", "title": "Options Tree", "primary_metric": "strategy.summary.calmar", "created_by_type": "agent", "created_by_id": "agent-alpha", "research": "quadrant-options"}

    run(["map", "get", "--map", "alpha-lab/options-tree"])
    assert calls[-2]["params"] == {"project": "alpha-lab", "key": "options-tree"} and calls[-1]["path"] == "/api/v1/research-maps/rmap_1"

    run(["map", "baseline", "--map", "rmap_1", "--key", "hold", "--reason", "user picked", "--created-by-id", "human:jiang", "--created-by-type", "human"])
    assert calls[-1] == {"method": "POST", "path": "/api/v1/research-maps/rmap_1/baseline", "json": {"node_key": "hold", "reason": "user picked", "created_by_type": "human", "created_by_id": "human:jiang"}}
    run(["map", "baseline", "--map", "rmap_1", "--key", ""])
    assert calls[-1]["json"]["node_key"] is None

    run(["map", "node", "set", "--map", "rmap_1", "--key", "hold", "--parent", "s2", "--title", "HOLD", "--stage", "experiment", "--date", "09-07",
         "--hypothesis", "h", "--change", "exit|leave state|only on flip", "--change", "min hold|none", "--change", "free text", "--reading", "2025 +167%",
         "--verdict", "v", "--caveat", "c1", "--next", "n", "--run", "run_1", "--ref", "compare_set:cmp_1:theta variants", "--ref", "url:https://x.y|report", "--position", "3", "--created-by-id", "agent-alpha"])
    body = calls[-1]["json"]
    assert calls[-1]["method"] == "PUT" and calls[-1]["path"] == "/api/v1/research-maps/rmap_1/nodes/hold"
    assert body["parent_key"] == "s2" and body["stage"] == "experiment" and body["date_label"] == "09-07" and body["position"] == 3
    assert body["change"] == [{"what": "exit", "to": "only on flip", "from": "leave state"}, {"what": "min hold", "to": "none"}, "free text"]
    assert body["reading"] == ["2025 +167%"] and body["caveats"] == ["c1"] and body["next"] == "n"
    assert body["binding"] == {"kind": "run", "id": "run_1"}
    assert body["refs"] == [{"kind": "compare_set", "id": "cmp_1", "label": "theta variants"}, {"kind": "url", "href": "https://x.y", "label": "report"}]
    assert body["created_by_type"] == "agent"

    run(["map", "node", "update", "--map", "rmap_1", "--key", "hold", "--decision", "none", "--unbind", "--parent", ""])
    assert calls[-1]["method"] == "PATCH" and calls[-1]["json"] == {"decision": None, "parent_key": None, "binding": None}

    run(["map", "node", "decide", "--map", "rmap_1", "--key", "h20", "--decision", "rejected", "--verdict", "Reject.", "--reading", "r1", "--note", "--created-by-id", "codex"])
    assert calls[-1]["path"] == "/api/v1/research-maps/rmap_1/nodes/h20/decide"
    assert calls[-1]["json"] == {"decision": "rejected", "verdict": "Reject.", "reading": ["r1"], "note": True, "created_by_type": "agent", "created_by_id": "codex"}

    run(["map", "node", "advance", "--map", "rmap_1", "--key", "hold", "--stage", "validation", "--date", "09-14"])
    assert calls[-1]["json"] == {"stage": "validation", "date_label": "09-14"}

    run(["map", "node", "move", "--map", "rmap_1", "--key", "tail", "--parent", "hold", "--position", "2"])
    assert calls[-1]["method"] == "PATCH" and calls[-1]["json"] == {"parent_key": "hold", "position": 2}

    run(["map", "node", "delete", "--map", "rmap_1", "--key", "x", "--cascade", "--created-by-id", "codex"])
    assert calls[-1]["method"] == "DELETE" and calls[-1]["params"] == {"cascade": "true", "created_by_type": "agent", "created_by_id": "codex"}

    for action in ("status", "lint"):
        run(["map", action, "--map", "rmap_1"])
        assert calls[-1]["path"] == f"/api/v1/research-maps/rmap_1/{action}"
    run(["map", "revisions", "--map", "rmap_1", "--key", "hold", "--limit", "5"])
    assert calls[-1]["params"] == {"node_key": "hold", "limit": 5}

    doc_path = tmp_path / "map.yaml"
    doc_path.write_text("project: alpha-lab\nkey: options-tree\ntitle: T\nbaseline: hold\nnodes:\n  - key: root\n    title: Root\n    stage: live\n    children:\n      - key: hold\n        title: HOLD\n        stage: experiment\n        decision: accepted\n", encoding="utf-8")
    run(["map", "import", "--file", str(doc_path), "--replace", "--created-by-id", "agent-alpha"])
    assert calls[-1]["path"] == "/api/v1/research-maps/import" and calls[-1]["json"]["mode"] == "replace"
    assert calls[-1]["json"]["nodes"][0]["children"][0]["decision"] == "accepted"

    out_path = tmp_path / "out.json"
    run(["map", "export", "--map", "rmap_1", "--output-file", str(out_path)])
    assert json.loads(out_path.read_text(encoding="utf-8"))["key"] == "options-tree"

    run(["run", "start", "--project", "alpha-lab", "--research", "r", "--branch", "b", "--name", "n", "--mode", "paper"])
    assert calls[-1]["json"]["mode"] == "paper"


def test_map_list_skips_quality_and_detail_reuses_evidence(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        project = ctx["project"]
        research = ctx["research"]
        run = next(iter(ctx["runs"].values()))
        m = call(client, "POST", "/api/v1/research-maps", json={"project": project["id"], "research": research["id"], "key": "perf", "title": "Performance"})
        for key in ["base", "same"]:
            call(client, "POST", f"/api/v1/research-maps/{m['id']}/nodes", json={"key": key, "title": key, "binding": {"kind": "run", "id": run["id"]}})
        call(client, "POST", f"/api/v1/research-maps/{m['id']}/baseline", json={"node_key": "base"})
        module = importlib.import_module("blackbox_server.main")
        checked = []
        def report(db, item):
            checked.append(item.id)
            return {"severity": "ok"}
        monkeypatch.setattr(module, "run_quality_gate_report", report)
        for url in ["/api/v1/research-maps", f"/api/v1/projects/{project['id']}/research-maps", f"/api/v1/researches/{research['id']}/research-maps"]:
            rows = call(client, "GET", url, params={"include_evidence": "false"})
            assert rows[0]["baseline"]["run"]["id"] == run["id"]
            assert "metrics" in rows[0]["baseline"]["run"]
        assert checked == []
        full = call(client, "GET", f"/api/v1/research-maps/{m['id']}")
        assert checked == [run["id"]]
        assert all(n["binding"]["run"]["quality"]["severity"] == "ok" for n in full["nodes"])
        call(client, "GET", f"/api/v1/research-maps/{m['id']}")
        assert checked == [run["id"], run["id"]]  # no cross-request stale quality cache
