import json, sys, glob, os, csv
root=sys.argv[1]; out=sys.argv[2]
rows=[]
for d in sorted(os.listdir(root)):
    for p in glob.glob(os.path.join(root,d,'**','*.json'),recursive=True):
        try: e=json.load(open(p,encoding='utf-8'))
        except Exception: continue
        if 'episode_id' not in e: continue
        s=e.get('submission') or {}
        rows.append(dict(arm_dir=d, episode_id=e['episode_id'], condition=e['condition'], rollout=e['rollout'],
                         submitted=bool(e['env_final_state'].get('submitted')),
                         recommendation=s.get('recommendation',''), justification=s.get('justification','')))
with open(out,'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows),'episodes')
