from __future__ import annotations

from sqlalchemy import event, select
from test_research_map import bootstrap, call, make_client


def test_context_and_run_pages_are_scoped(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        data = call(client, 'GET', '/api/v1/ui/context')
        assert data['runs'] == data['branches'] == data['researches'] == []
        assert 'champion_run' not in str(data)
        first = call(client, 'GET', '/api/v1/ui/runs?limit=1')
        second = call(client, 'GET', '/api/v1/ui/runs?limit=1&page=2')
        assert first['total'] == 3 and len(first['runs']) == 1
        assert first['runs'][0]['id'] != second['runs'][0]['id']
        assert 'config_json' not in first['runs'][0]
        scoped = call(client, 'GET', '/api/v1/ui/runs?project=missing')
        assert scoped['runs'] == []
        for section in ['summary', 'activity', 'projects', 'recent', 'quality', 'researches', 'decisions', 'system']:
            call(client, 'GET', '/api/v1/ui/overview?section=' + section)
        call(client, 'GET', '/api/v1/ui/researches?project=' + ctx['project']['id'])
        call(client, 'GET', '/api/v1/ui/branches/' + ctx['branch']['id'] + '/summary')
        running = call(client, 'POST', '/api/v1/runs', json={'branch_id': ctx['branch']['id'], 'name': 'failed-counter'})
        call(client, 'POST', '/api/v1/runs/' + running['id'] + '/fail', json={'error_message': 'fixture'})
        assert call(client, 'GET', '/api/v1/ui/scope-summary?research=' + ctx['research']['id'])['failed_run_count'] == 1
        call(client, 'GET', '/api/v1/ui/scope-summary?project=' + ctx['project']['id'])
        call(client, 'GET', '/api/v1/ui/lineage?research=' + ctx['research']['id'])
        call(client, 'GET', '/api/v1/ui/lineage?branch=' + ctx['branch']['id'])
        call(client, 'GET', '/api/v1/ui/branches/' + ctx['branch']['id'] + '/evolution')
        for kind in ['projects', 'researches', 'branches', 'workspaces', 'maps', 'compare_sets', 'search_views']:
            call(client, 'GET', '/api/v1/ui/catalog?kind=' + kind)


def test_run_tabs_do_not_read_other_content(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        import blackbox_server.main as main
        def forbidden(*args):
            raise AssertionError('Unrequested series read')
        monkeypatch.setattr(main, 'artifact_read_with_full_series', forbidden)
        ident = ctx['runs']['hold']['id']
        for section in ['summary', 'events', 'metrics', 'artifacts', 'notes', 'snapshots', 'config']:
            data = call(client, 'GET', f'/api/v1/ui/runs/{ident}?section={section}')
            assert ('config_json' in data) == (section == 'config')
            assert ('events' in data) == (section == 'events')


def test_ui_conditional_get_and_compression(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        bootstrap(client)
        first = client.get('/api/v1/ui/context')
        assert first.headers['etag']
        unchanged = client.get('/api/v1/ui/context', headers={'If-None-Match': first.headers['etag']})
        assert unchanged.status_code == 304 and not unchanged.content
        call(client, 'POST', '/api/v1/projects', json={'key': 'other', 'title': 'Other'})
        changed = client.get('/api/v1/ui/context', headers={'If-None-Match': first.headers['etag']})
        assert changed.status_code == 200 and changed.headers['etag'] != first.headers['etag']
        assert client.get('/api/v1/ui/runs', headers={'Accept-Encoding': 'gzip'}).headers['content-encoding'] == 'gzip'


def test_map_canvas_skips_quality_and_repeated_nodes(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        research_map = call(client, 'POST', '/api/v1/research-maps', json={'project': ctx['project']['id'], 'key': 'map', 'title': 'Map'})
        ident = research_map['id']
        for index in range(6):
            call(client, 'PUT', f'/api/v1/research-maps/{ident}/nodes/n{index}', json={'title': str(index), 'stage': 'experiment', 'binding': {'kind': 'run', 'id': ctx['runs']['hold']['id']}})
        import blackbox_server.main as main
        def forbidden(*args):
            raise AssertionError('Canvas must not perform quality checks')
        monkeypatch.setattr(main, 'run_quality_gate_report', forbidden)
        import blackbox_server.db as db
        statements = []
        def record(*args):
            statements.append(args[2])
        event.listen(db.engine, 'before_cursor_execute', record)
        try:
            data = call(client, 'GET', f'/api/v1/ui/maps/{ident}')
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        assert len(data['nodes']) == 6 and 'tree' not in data
        assert len(statements) <= 7
        assert data['nodes'][0]['binding']['run']['quality']['severity'] == 'not_loaded'
        assert 'artifacts' not in data['nodes'][0]['binding']['run']


def test_ui_representative_keeps_manual_priority(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        url = '/api/v1/ui/researches?project=' + ctx['project']['id']
        assert call(client, 'GET', url)['researches'][0]['champion_run']['id'] == ctx['runs']['hold']['id']
        research_map = call(client, 'POST', '/api/v1/research-maps', json={'project': ctx['project']['id'], 'key': 'map', 'title': 'Map'})
        ident = research_map['id']
        call(client, 'PUT', f'/api/v1/research-maps/{ident}/nodes/pin', json={'title': 'Pin', 'binding': {'kind': 'run', 'id': ctx['runs']['h20']['id']}})
        call(client, 'POST', f'/api/v1/research-maps/{ident}/baseline', json={'node_key': 'pin'})
        assert call(client, 'GET', url)['researches'][0]['champion_run']['id'] == ctx['runs']['h20']['id']


def test_quality_hint_reuses_only_unchanged_results(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        import blackbox_server.main as main
        import blackbox_server.db as dbmod
        from blackbox_server.models import Run
        from blackbox_server.research_maps import run_quality
        from sqlalchemy.orm import Session
        checks = []
        def check(db, run):
            checks.append(run.id)
            return {'severity': 'warning', 'error_count': 0, 'warning_count': 1}
        monkeypatch.setattr(main, 'run_quality_gate_report', check)
        ident = ctx['runs']['hold']['id']
        for _ in range(2):
            with Session(dbmod.engine) as db:
                db.info['ui_quality_cache'] = True
                assert run_quality(db, db.get(Run, ident))['severity'] == 'warning'
        assert checks == [ident]
        call(client, 'POST', f'/api/v1/runs/{ident}/metrics', json={'namespace': 'strategy.summary', 'values': {'sharpe': 0.5}})
        with Session(dbmod.engine) as db:
            db.info['ui_quality_cache'] = True
            run_quality(db, db.get(Run, ident))
        assert len(checks) == 2
        # Original API/write gates never use the display cache.
        with Session(dbmod.engine) as db:
            run_quality(db, db.get(Run, ident))
        assert len(checks) == 3


def test_slim_rows_omit_unrequested_payloads_and_filters_match_all_rows(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        ident = ctx['runs']['hold']['id']
        call(client, 'POST', f'/api/v1/runs/{ident}/metrics', json={'namespace': 'debug', 'values': {'blob': 'x' * 4000}})
        result = call(client, 'GET', '/api/v1/ui/runs?limit=1&sort=sharpe&direction=desc')
        assert result['runs'][0]['id'] == ident
        assert 'debug' not in result['runs'][0]['summary_json']
        assert call(client, 'GET', '/api/v1/ui/runs?artifact=none')['total'] == 3
        assert call(client, 'GET', '/api/v1/ui/runs?artifact=yes')['total'] == 0
        assert call(client, 'GET', '/api/v1/ui/runs?status=completed&limit=1')['total'] == 2
        detail = call(client, 'GET', f'/api/v1/ui/runs/{ident}?section=results')
        assert detail['summary_json']['debug']['blob'] == 'x' * 4000


def test_run_search_preserves_config_tags_and_explicit_config_columns(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        ctx = bootstrap(client)
        import blackbox_server.db as dbmod
        from blackbox_server.models import Run
        from sqlalchemy.orm import Session
        ident = ctx['runs']['hold']['id']
        with Session(dbmod.engine) as db:
            run = db.get(Run, ident)
            run.config_json = {'special_filter': 'config-needle'}
            run.context_json = {'sample': 'context-needle'}
            run.tags = ['tag-needle']
            db.commit()
        for term in ['config-needle', 'context-needle', 'tag-needle']:
            data = call(client, 'GET', '/api/v1/ui/runs?q=' + term)
            assert [r['id'] for r in data['runs']] == [ident]
            assert 'config_json' not in data['runs'][0]
        data = call(client, 'GET', '/api/v1/ui/runs?q=config-needle&with_config=true')
        assert data['runs'][0]['config_json'] == {'special_filter': 'config-needle'}
