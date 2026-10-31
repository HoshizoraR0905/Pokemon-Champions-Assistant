"""Portable checks of the browser's exact-set presentation, without a browser."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT=Path(__file__).resolve().parents[1]


def test_support_states_and_disjoint_integer_formatting():
    node=shutil.which('node')
    if not node:pytest.skip('Node is optional for browser presentation checks')
    program=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('scripts/templates/speed_replay.js','utf8');
const context={};vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function supportView('),source.indexOf('function statSummary(')),context);
const formatter=source.split('\n').find(line=>line.startsWith('const intervals='));
vm.runInContext(formatter.replace('const intervals=','globalThis.intervals='),context);
const cases=JSON.parse(fs.readFileSync('tests/fixtures/replay_ui/m345-support-states.json','utf8')).cases;
for(const spec of cases){
 const full={status:'exact',configuration_count:spec.reference_classes,speed:{count:spec.speed.length},offensive_stats:{},item_policy:{profile:spec.profile||'comprehensive',dormant:spec.dormant||[]}};
 if(spec.evaluated_classes!==undefined)full.offensive_stats.attack={configuration_classes:spec.reference_classes,evaluated_support:{configuration_classes:spec.evaluated_classes}};
 const result=context.supportView({full,observed:{}},{surviving_cores:spec.cores,eligible_records:spec.occurrences});
 assert.equal(result.available,spec.cores>0);assert.equal(result.noSample,spec.occurrences===0);
 assert.equal(result.unknown,spec.evaluated_classes===undefined?0:spec.reference_classes-spec.evaluated_classes);
 if(spec.id==='empty-empirical')assert.equal(result.state,'fallback');
 if(spec.id==='both-empty')assert.equal(result.state,'contradiction');
 if(spec.id==='no-sample')assert.equal(result.state,'no_sample');
 if(spec.id==='practical-empty')assert(result.qualified&&result.omitted===2);
 if(spec.id==='comprehensive')assert.equal(result.omitted,0);
}
assert.equal(context.intervals({count:42,intervals:[[80,100],[150,170]]}),'80–100 ∪ 150–170');
assert.equal(context.intervals({count:2,intervals:[[44,44],[89,89]]}),'44 ∪ 89');
assert.equal(context.intervals({count:0,intervals:[]}), '空集（无兼容配置）');
assert.equal(context.intervals(undefined),'未确定');
'''
    result=subprocess.run([node,'-e',program],cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
