"""New K-only contained fault fixture. No engine, layout, Qt or old helper."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.random_expert_exhibition_process import verify_worker_scope
import live_k_policy as k
from live_policy_transport import message, read_next, write_once
from stage3_physical import load_timing_table


def publish_receipt(directory, name, data):
    path = Path(directory) / name
    staging = path.with_suffix('.part')
    staging.write_text(json.dumps(data), encoding='utf-8')
    os.link(staging, path)


def main(args):
    if args[0] == '--descendant':
        _, directory, scope = args
        verify_worker_scope(scope)
        publish_receipt(directory, 'k-descendant.json', {'pid': os.getpid(), 'membership_verified': True})
        time.sleep(60)
        return 0
    directory, run, scope, mode = args
    verify_worker_scope(scope)
    child = None
    if mode == 'tree_close':
        child = subprocess.Popen(
            [sys.executable, '-B', str(Path(__file__).resolve()), '--descendant', directory, scope],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    publish_receipt(directory, 'k-fixture.json', {
        'pid': os.getpid(), 'membership_verified': True, 'mode': mode,
        'fixture_descendant_starts': int(child is not None),
        'descendant_launcher_pid': child.pid if child else None})
    seq, owner = 0, None
    while True:
        value = read_next(directory, 'parent', seq, run)
        if value is None:
            time.sleep(.01)
            continue
        kind, payload = value['kind'], value['payload']
        if seq == 0:
            assert kind == 'START'
            start = k.from_dict(payload, k.KSnapshot)
            owner = k.KOwner(start, load_timing_table())
            outgoing = message(run, seq, 'PROPOSAL', k.to_dict(owner.propose(start)))
        elif kind == 'VALIDATE':
            if mode == 'slow_validation':
                time.sleep(60)
            permit = owner.validate(k.from_dict(payload, k.KValidation))
            if mode == 'tampered_permit':
                permit = replace(permit, nonce='f' * 32)
            outgoing = message(run, seq, 'ADMITTED', k.to_dict(permit))
        elif kind == 'ACK':
            ack = k.from_dict(payload, k.KAck)
            owner.acknowledge(ack)
            outgoing = message(run, seq, 'ACKED' if ack.status == 'PLAYING' else 'FINISHED', k.to_dict(ack))
            if ack.status != 'PLAYING':
                write_once(directory, 'worker', seq, outgoing)
                if mode == 'delayed_exit':
                    time.sleep(60)
                return 0
        else:
            raise ValueError('Unsupported fixture command')
        write_once(directory, 'worker', seq, outgoing)
        seq += 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
