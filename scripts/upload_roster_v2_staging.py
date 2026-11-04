"""Upload an approved v2 bundle to private staging only, after schema deployment.

The SQL proposal must be reviewed and deployed separately. This command never
creates accounts, activates a roster, or opens an evaluation period.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


FILES={"students.csv","teachers.csv","subject_loads.csv","homeroom.csv","programs.csv",
       "evaluation_allocations.csv","teacher_coverage.csv"}


def read_bundle(directory):
    raw=(directory/'manifest.json').read_bytes()
    manifest=json.loads(raw)
    if manifest.get('contract')!='roster-v2-validated' or manifest.get('errors')!=0:
        raise ValueError('A validated v2 bundle is required; review bundles cannot be uploaded')
    expected=set(manifest.get('files',{}))
    if expected not in (FILES,FILES|{'section_groups.csv'}):
        raise ValueError('Unexpected or missing bundle files')
    payload={}
    for name in sorted(expected):
        path=directory/name
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=manifest['files'][name]['sha256']:
            raise ValueError('Bundle checksum mismatch: '+name)
        with path.open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        if len(rows)!=manifest['files'][name]['rows']:
            raise ValueError('Bundle row count mismatch: '+name)
        payload[name.removesuffix('.csv')]=rows
    students=payload['students'];allocations=payload['evaluation_allocations']
    if len(allocations)!=4*len(students):
        raise ValueError('Expected exactly four evaluation targets per student')
    from collections import Counter,defaultdict
    kinds=defaultdict(Counter);subject_teachers=defaultdict(set)
    ids={s['student_number'] for s in students}
    if len(ids)!=len(students):
        raise ValueError('Duplicate student identities')
    for row in allocations:
        sid=row['student_number']
        if sid not in ids:
            raise ValueError('Unknown allocated student')
        kinds[sid][row['target_type']]+=1
        if row['target_type']=='subject_teacher':
            subject_teachers[sid].add(row['teacher_employee_number'])
    required=Counter(subject_teacher=2,homeroom_adviser=1,homeroom_program=1)
    if any(kinds[s]!=required or len(subject_teachers[s])!=2 for s in ids):
        raise ValueError('Invalid target distribution or repeated subject teacher')
    homes={r['section_code']:r for r in payload['homeroom']}
    subject_rows=[r for r in allocations if r['target_type']=='subject_teacher']
    basis_counts=Counter(r.get('allocation_basis','') for r in subject_rows)
    if basis_counts['regular_load']<=basis_counts['advisory_secondary']:
        raise ValueError('Regular-load subject invitations must remain the majority')
    for row in subject_rows:
        home=homes.get(row['teaching_section_code'])
        if home is None:
            raise ValueError('Subject allocation has no teaching-section adviser')
        is_adviser=(row['teacher_employee_number']==home['adviser_employee_number'])
        if is_adviser and row.get('allocation_basis')!='advisory_secondary':
            raise ValueError('Adviser subject targets must be labeled advisory_secondary')
        if not is_adviser and row.get('allocation_basis')!='regular_load':
            raise ValueError('Non-adviser subject targets must be labeled regular_load')
    return manifest,hashlib.sha256(raw).hexdigest(),payload


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle',type=Path)
    p.add_argument('--url',required=True)
    p.add_argument('--batch-code',required=True)
    p.add_argument('--period-code',required=True)
    args=p.parse_args()
    host=urlparse(args.url)
    if host.scheme!='https' or not (host.hostname or '').endswith('.supabase.co') or host.username or host.password:
        p.error('Use the HTTPS Supabase project URL')
    manifest,digest,payload=read_bundle(args.bundle)
    if args.period_code!=manifest.get('period_code'):
        p.error('Period code must match the reviewed bundle')
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions
    secret=getpass.getpass('Supabase secret key (hidden; never saved): ').strip()
    if not secret.startswith('sb_secret_'):
        p.error('Use a current secret key in this local operator process only')
    client=create_client(args.url,secret,options=SyncClientOptions(auto_refresh_token=False,persist_session=False))
    periods=client.table('evaluation_periods').select('id,status').eq('code',args.period_code).execute().data
    if len(periods)!=1 or periods[0]['status']!='draft':
        p.error('Exactly one existing draft production period is required')
    existing=client.table('roster_v2_batches').select('id,status,manifest_sha256,evaluation_period_id').eq('batch_code',args.batch_code).execute().data
    if existing:
        batch=existing[0]
        if batch['manifest_sha256']!=digest or batch['evaluation_period_id']!=periods[0]['id'] or batch['status']!='draft':
            p.error('Existing batch differs or is no longer draft; use a new batch code')
    else:
        batch=client.table('roster_v2_batches').insert({'batch_code':args.batch_code,
            'evaluation_period_id':periods[0]['id'],'manifest_sha256':digest,
            'source_sha256':manifest['source_sha256'],'counts':manifest['counts']}).execute().data[0]
    # Resume a partial upload without overwriting a previously staged payload.
    stored=client.table('roster_v2_payloads').select('batch_id').eq('batch_id',batch['id']).execute().data
    if not stored:
        client.table('roster_v2_payloads').insert({'batch_id':batch['id'],'payload':payload}).execute()
    confirmed=client.table('roster_v2_payloads').select('payload').eq('batch_id',batch['id']).execute().data
    if len(confirmed)!=1 or confirmed[0]['payload']!=payload:
        raise RuntimeError('Staging payload verification failed; no activation was attempted')
    print(f"Verified draft staging batch {args.batch_code}; no Auth, active roster, or period status changed.")


if __name__=='__main__':
    main()
