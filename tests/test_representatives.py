from datetime import datetime, timedelta
from types import SimpleNamespace
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

def run(ident, score=None, status='completed', days=0):
    return SimpleNamespace(id=ident, summary_json={'strategy.summary':{'sharpe':score}},status=status,created_at=datetime(2026,1,1),updated_at=datetime(2026,1,1)+timedelta(days=days))

@pytest.mark.parametrize('score',[None,'',True,float('nan'),float('inf'),'n/a'])
def test_nonfinite_values_do_not_beat_zero(score):
    from blackbox_server.representatives import choose_representative
    assert choose_representative([run('invalid',score,days=2),run('zero',0),run('negative',-1)]).id=='zero'

def test_manual_highest_latest_priority():
    from blackbox_server.representatives import choose_representative
    candidates=[run('manual',-1),run('highest',2),run('latest',None,'running',3)]
    assert choose_representative(candidates,{'manual'}).id=='manual'
    assert choose_representative(candidates).id=='highest'
    assert choose_representative([run('old'),candidates[2]]).id=='latest'
    assert choose_representative([]) is None

def test_manual_baseline_is_consistent_across_apis(tmp_path: Path, monkeypatch):
    monkeypatch.setenv('BLACKBOX_DATABASE_URL',f'sqlite:///{tmp_path / "blackbox.db"}')
    monkeypatch.setenv('BLACKBOX_ARTIFACT_ROOT',str(tmp_path/'artifacts'))
    from blackbox_server.main import create_app
    with TestClient(create_app()) as c:
        def call(method,path,**kwargs):
            payload=c.request(method,path,**kwargs).json(); assert payload['ok'],payload; return payload['data']
        p=call('POST','/api/v1/projects',json={'key':'p','title':'P'})
        r=call('POST','/api/v1/researches',json={'project_key':'p','key':'r','title':'R'})
        b=call('POST','/api/v1/branches',json={'research_id':r['id'],'key':'b','title':'B'})
        runs=[]
        for score in [0,2]:
            item=call('POST','/api/v1/runs',json={'branch_id':b['id'],'name':str(score)})
            call('POST',f"/api/v1/runs/{item['id']}/metrics",json={'namespace':'strategy.summary','values':{'sharpe':score}})
            call('POST',f"/api/v1/runs/{item['id']}/finish",params={'skip_quality_gate':'true'});runs.append(item)
        m=call('POST','/api/v1/research-maps',json={'project':'p','research':'r','key':'m','title':'M'})
        call('POST',f"/api/v1/research-maps/{m['id']}/nodes",json={'key':'base','title':'Base','binding':{'kind':'run','id':runs[0]['id']}})
        call('POST',f"/api/v1/research-maps/{m['id']}/baseline",json={'node_key':'base'})
        call('POST',f"/api/v1/research-maps/{m['id']}/nodes",json={'key':'branch','title':'Branch','binding':{'kind':'branch','id':b['id']}})
        dashboard=call('GET','/api/v1/dashboard')
        assert dashboard['researches'][0]['champion_run']['id']==runs[0]['id']
        assert next(x for x in dashboard['runs'] if x['id']==runs[0]['id'])['is_manual_baseline'] is True
        project=call('GET',f"/api/v1/projects/{p['id']}")
        assert project['researches'][0]['champion_run']['id']==runs[0]['id']
        search=call('POST','/api/v1/search/researches',json={})
        assert search[0]['champion_run']['id']==runs[0]['id']
        quick=call('POST','/api/v1/quick-compare',json={'targets':[{'type':'branch','id':b['id']}]})
        assert quick['runs'][0]['id']==runs[0]['id']
        nodes=call('GET',f"/api/v1/research-maps/{m['id']}")['nodes']
        assert next(n for n in nodes if n['key']=='branch')['binding']['run']['id']==runs[0]['id']
