#!/usr/bin/env python3
"""51 distinct synthetic tasks x two Pi arms; standard library only. NOT EdgeBench."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import queue
import random
import shutil
import subprocess
import threading
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

N=51
FLAGS=('actionFusion','observationPack','evidencePreservingReducer','onlineContextCompact')
FIELDS=('task_id','family','arm','order','verified','input','output','cacheRead','cacheWrite','total','cost_estimate','tool_calls','status','error')

def log(message): print(f'[{time.strftime("%H:%M:%S")}] {message}',flush=True)
def dump(p,data): p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()

def make_task(task_id, home):
    """Three independent task families, 17 datasets each; exact-output verification."""
    rng=random.Random(54011+task_id); family=('logs','csv','jsonl')[(task_id-1)//17]
    home.mkdir(parents=True,exist_ok=True)
    if family=='logs':
        tags=['AUTH','RATE','DISK','NET','TIMEOUT','CACHE']; rows=[];counts={}
        for i in range(250+(task_id%7)*37):
            code=rng.choice(tags);level=rng.choice(['ERROR','INFO','WARN'])
            if level=='ERROR':counts[code]=counts.get(code,0)+1
            rows.append(f'2026-09-23T09:{i%60:02d}:00Z level={level} code={code} id={i:05d} detail='+('trace-%06d'%i+'x'*82))
        (home/'events.log').write_text('\n'.join(rows)+'\n')
        expected={'counts':dict(sorted(counts.items()))}
        instruction='Read events.log fully. Count ERROR records grouped by code; output {"counts": {code: count}}. Include only codes with a positive count.'
    elif family=='csv':
        services=['api','worker','gateway','search','scheduler','billing'];rows=[];counts={}
        for i in range(290+(task_id%7)*41):
            service=rng.choice(services);status=rng.choice(['ok','fail','retry'])
            if status=='fail':counts[service]=counts.get(service,0)+1
            rows.append(f'{i},{service},{status},payload-'+('x'*90))
        (home/'requests.csv').write_text('id,service,status,detail\n'+'\n'.join(rows)+'\n')
        expected={'counts':dict(sorted(counts.items()))}
        instruction='Read requests.csv fully. Count rows whose status is fail, grouped by service; output {"counts": {service: count}}. Include only services with a positive count.'
    else:
        groups=['red','blue','green','yellow','white','black']; rows=[];counts={}
        for i in range(230+(task_id%7)*43):
            group=rng.choice(groups);valid=rng.choice([True,True,False])
            if valid:counts[group]=counts.get(group,0)+1
            rows.append(json.dumps({'id':i,'group':group,'valid':valid,'payload':'x'*100}))
        (home/'records.jsonl').write_text('\n'.join(rows)+'\n')
        expected={'counts':dict(sorted(counts.items()))}
        instruction='Read records.jsonl fully. Count records whose boolean valid is true, grouped by group; output {"counts": {group: count}}. Include only groups with a positive count.'
    dump(home/'expected.json',expected)
    return family,instruction,sha(json.dumps(expected,sort_keys=True).encode())

def read_thread(stream,q):
    for line in stream:q.put(line)
    q.put(None)

def pi_rpc(project,case,prompt,provider,model,timeout,label):
    session=case/'sessions';session.mkdir(exist_ok=True)
    proc=subprocess.Popen(['pi','--mode','rpc','--provider',provider,'--model',model,
        '--session-dir',str(session),'--approve'],cwd=project,stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    events=queue.Queue();errors=queue.Queue()
    threading.Thread(target=read_thread,args=(proc.stdout,events),daemon=True).start()
    threading.Thread(target=read_thread,args=(proc.stderr,errors),daemon=True).start()
    stats=None;settled=False;tool_calls=0;deadline=time.monotonic()+timeout;heartbeat=time.monotonic()
    def send(x):proc.stdin.write(json.dumps(x)+'\n');proc.stdin.flush()
    try:
        with (case/'pi.jsonl').open('w') as raw,(case/'pi.stderr').open('w') as err:
            send({'id':'prompt-1','type':'prompt','message':prompt})
            while time.monotonic()<deadline:
                while True:
                    try:line=errors.get_nowait()
                    except queue.Empty:break
                    if line is not None:err.write(line);err.flush()
                try:line=events.get(timeout=.5)
                except queue.Empty:
                    if proc.poll() is not None:raise RuntimeError('Pi exited early; inspect pi.stderr')
                    if time.monotonic()-heartbeat>15:
                        log(f'{label} waiting for agent/provider...');heartbeat=time.monotonic()
                    continue
                if line is None:raise RuntimeError('Pi closed RPC output; inspect pi.stderr')
                raw.write(line);raw.flush()
                try:e=json.loads(line)
                except json.JSONDecodeError:continue
                kind=e.get('type')
                if kind=='agent_start':log(f'{label} agent started')
                elif kind=='tool_execution_start':
                    tool_calls+=1;log(f'{label} tool #{tool_calls}: {e.get("toolName","unknown")}')
                elif kind=='tool_execution_end' and e.get('isError'):
                    log(f'{label} tool error: {e.get("toolName","unknown")}')
                elif kind=='agent_settled' and not settled:
                    settled=True;log(f'{label} settled; requesting stats');send({'id':'stats-1','type':'get_session_stats'})
                elif kind=='response' and e.get('id')=='prompt-1' and e.get('success') is False:
                    raise RuntimeError('RPC prompt rejected; inspect pi.jsonl')
                elif kind=='response' and e.get('id')=='stats-1':
                    if e.get('success') is False:raise RuntimeError('RPC statistics failed; inspect pi.jsonl')
                    stats=e.get('data');break
            if stats is None:raise TimeoutError('Timed out before agent_settled/stats')
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        with (case/'pi.stderr').open('a') as err:
            while True:
                try:line=errors.get_nowait()
                except queue.Empty:break
                if line is not None:err.write(line)
    return stats,tool_calls

def verify(case):
    work=case/'workspace'
    actual=json.loads((work/'result.json').read_text())
    expected=json.loads((work/'expected.json').read_text())
    return actual==expected

def record(case,task_id,family,arm,order,stats,tools):
    dump(case/'stats.json',stats)
    u=stats.get('tokens') if isinstance(stats,dict) else None
    if not isinstance(u,dict) or any(not isinstance(u.get(k),(int,float)) for k in ('input','output','total')):
        raise ValueError('No numeric input/output/total in stats.tokens; see stats.json')
    return dict(task_id=task_id,family=family,arm=arm,order=order,verified=verify(case),
        input=u['input'],output=u['output'],cacheRead=u.get('cacheRead',''),
        cacheWrite=u.get('cacheWrite',''),total=u['total'],cost_estimate=stats.get('cost',''),
        tool_calls=tools,status='ok',error='')

def write_results(run,rows):
    with (run/'results.csv').open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=FIELDS);w.writeheader();w.writerows(rows)

def report(run,rows):
    by={(int(r['task_id']),r['arm']):r for r in rows if r['status']=='ok' and r['verified'] is True}
    pairs=[(by[(i,'A')],by[(i,'B')]) for i in range(1,N+1) if (i,'A') in by and (i,'B') in by]
    summary={'paired_verified_tasks':len(pairs),'attempted_runs':len(rows),'expected_runs':N*2,
             'note':'Synthetic suite, NOT EdgeBench. Session tokens reported by Pi; not network/billed tokens.'}
    if pairs:
        for metric in ('input','output','cacheRead','cacheWrite','total'):
            valid=[(float(a[metric]),float(b[metric])) for a,b in pairs
                   if isinstance(a[metric],(int,float)) and isinstance(b[metric],(int,float))]
            if not valid:continue
            aa=sum(a for a,b in valid);bb=sum(b for a,b in valid)
            savings=[(a-b)/a for a,b in valid if a>0]
            if not savings:continue
            mean=sum(savings)/len(savings)
            ordered=sorted(savings);median=ordered[len(ordered)//2] if len(ordered)%2 else (ordered[len(ordered)//2-1]+ordered[len(ordered)//2])/2
            rng=random.Random(20260923);boot=[]
            for _ in range(5000):
                sample=[savings[rng.randrange(len(savings))] for _ in savings]
                boot.append(sum(sample)/len(sample))
            boot.sort()
            summary[metric]={'n':len(savings),'arm_a_sum':aa,'arm_b_sum':bb,
                'pooled_reduction_pct':100*(aa-bb)/aa if aa else None,
                'mean_paired_reduction_pct':100*mean,'median_paired_reduction_pct':100*median,
                'bootstrap_95_ci_mean_pct':[100*boot[125],100*boot[4874]]}
    dump(run/'report.json',summary)
    log(f"Paired verified tasks: {len(pairs)}/{N}; completed rows: {len(rows)}/{2*N}")
    for metric in ('input','total'):
        if metric in summary:
            v=summary[metric];log(f'{metric}: mean paired reduction {v["mean_paired_reduction_pct"]:.2f}% (95% bootstrap CI {v["bootstrap_95_ci_mean_pct"][0]:.2f}% to {v["bootstrap_95_ci_mean_pct"][1]:.2f}%)')
    if len(pairs)<N:log('INCOMPLETE: do not report 51-task result yet.')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',default='.',help='trusted project with SoL-Pi installed as a Pi package')
    ap.add_argument('--provider',default='regolo');ap.add_argument('--model',default='qwen3.5-122b')
    ap.add_argument('--timeout',type=int,default=600,help='seconds per arm')
    ap.add_argument('--max-tasks',type=int,default=51,help='pilot: 1..51; default 51')
    ap.add_argument('--dry-run',action='store_true',help='make 51-task manifest; spend no API credits')
    ap.add_argument('--resume',type=Path,help='existing run directory; skip completed arms')
    args=ap.parse_args()
    if not 1<=args.max_tasks<=51:ap.error('--max-tasks must be 1..51')
    project=Path(args.project).resolve();config=project/'.pi'/'sol-pi.json'
    if not (project/'.pi').is_dir():ap.error('missing project .pi/ directory')
    if not args.dry_run and not shutil.which('pi'):ap.error('pi not found in PATH')
    if not args.dry_run and args.provider=='regolo' and not os.getenv('REGOLO_API_KEY'):
        for env_path in (project/'.env', Path('.env')):
            if env_path.exists():
                for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and line.startswith('REGOLO_API_KEY='):
                        val = line.split('=', 1)[1].strip().strip('"').strip("'")
                        if val and val != 'your-regolo-api-key-here':
                            os.environ['REGOLO_API_KEY'] = val
                            break
            if os.getenv('REGOLO_API_KEY'):break
    if not args.dry_run and args.provider=='regolo' and not os.getenv('REGOLO_API_KEY'):
        ap.error('REGOLO_API_KEY is not set. Please add it to .env or export REGOLO_API_KEY')
    if args.timeout<=0:ap.error('--timeout must be positive')
    old=config.read_bytes() if config.exists() else None
    base=json.loads(old) if old else {'version':1}
    if not isinstance(base,dict):ap.error('sol-pi.json must be a JSON object')
    if args.resume:
        run=args.resume.resolve()
        if not (run/'manifest.json').exists():ap.error('missing manifest.json in --resume directory')
        manifest=json.loads((run/'manifest.json').read_text())
        if manifest['project']!=str(project) or manifest['model']!=args.model or manifest['provider']!=args.provider:
            ap.error('resume project/model/provider differs from original run')
        if manifest['config_base_sha256']!=sha(json.dumps(base,sort_keys=True).encode()):
            ap.error('original SoL-Pi configuration changed; restore it before resuming')
    else:
        run=project/('sol-pi-51-'+time.strftime('%Y%m%d-%H%M%S'));run.mkdir(exist_ok=False)
        order=list(range(1,52));random.Random(20260923).shuffle(order)
        manifest={'project':str(project),'provider':args.provider,'model':args.model,
            'config_base_sha256':sha(json.dumps(base,sort_keys=True).encode()),
            'order':order,'seed':20260923,'suite':'51 synthetic tasks, three families; NOT EdgeBench',
            'profiles':{'A':'all four mechanisms OFF','B':'Action Fusion + ObservationPack ON; EPR and OCC OFF'}}
        dump(run/'manifest.json',manifest)
    rows=[]
    if (run/'results.csv').exists():
        with (run/'results.csv').open(newline='') as file:
            rows=list(csv.DictReader(file))
        for r in rows:r['verified']=str(r['verified']).lower()=='true'
    done={(int(r['task_id']),r['arm']) for r in rows if r['status']=='ok' and r['verified'] is True}
    if args.dry_run:
        for i in range(1,52):make_task(i,run/'fixtures'/f'task-{i:02d}')
        log('Dry run: 51 synthetic fixtures created; no API calls. Artifacts: '+str(run));return
    try:
        for i in manifest['order'][:args.max_tasks]:
            for arm in (('A','B') if i%2 else ('B','A')):
                if (i,arm) in done:continue
                # Do not repeat a failed arm automatically: avoid unintended extra charges.
                if any(int(r['task_id'])==i and r['arm']==arm for r in rows):
                    log(f'Task {i:02d} {arm}: previously failed; inspect logs, no automatic paid retry');continue
                enabled=arm=='B';cfg=dict(base)
                cfg.update({k:(enabled if k in ('actionFusion','observationPack') else False) for k in FLAGS})
                cfg['version']=1
                config.write_text(json.dumps(cfg,indent=2)+'\n')
                case=run/f'task-{i:02d}'/f'arm-{arm}';case.mkdir(parents=True,exist_ok=True)
                work=case/'workspace';family,instruction,digest=make_task(i,work)
                dump(case/'config.json',cfg)
                prompt=(f'In {work}, {instruction} Write only the JSON object to result.json in that '
                    'directory. Create a Python standard-library script solve.py to compute it; run '
                    'solve.py and then read result.json to verify your result. Do not open or edit '
                    'expected.json. Do not modify the input dataset. Reply briefly when finished.')
                label=f'Task {i:02d}/51 Arm {arm} ({family})';log(label+' START')
                try:
                    stats,tools=pi_rpc(project,case,prompt,args.provider,args.model,args.timeout,label)
                    row=record(case,i,family,arm,'AB' if i%2 else 'BA',stats,tools)
                    log(label+f' END verified={row["verified"]} input={row["input"]} output={row["output"]} total={row["total"]}')
                except Exception as exc:
                    row={key:'' for key in FIELDS};row.update(task_id=i,family=family,arm=arm,
                        order='AB' if i%2 else 'BA',verified=False,status='failed',error=str(exc))
                    log(label+' FAILED: '+str(exc)+' (check saved logs; may contain sensitive content)')
                rows.append(row);write_results(run,rows);report(run,rows)
        log('Saved run: '+str(run))
    finally:
        if old is None:config.unlink(missing_ok=True)
        else:config.write_bytes(old)
        log('Original .pi/sol-pi.json restored')

if __name__=='__main__':main()
