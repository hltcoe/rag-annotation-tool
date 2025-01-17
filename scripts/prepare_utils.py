from argparse import ArgumentParser
import json
from pathlib import Path
from tqdm import tqdm

import pandas as pd
import ir_measures as irms

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--name', type=str, required=True)
    parser.add_argument('--input_reports', type=str, nargs='+', required=True)
    parser.add_argument('--output_dir', type=str, default='./resources')

    parser.add_argument('--qrels', nargs='+', type=str, default=[])

    parser.add_argument('--add_rel_docs', action='store_true', default=False)
    parser.add_argument('--construct_doc_pool', action='store_true', default=False)

    args = parser.parse_args()

    print(f"Got {len(args.input_reports)} reports.")

    all_runs = {
        (f.stem if f.suffix == ".jsonl" else f.name): [ json.loads(l) for l in f.open() ]
        for f in map(Path, args.input_reports)
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assert not (output_dir / f"{args.name}.citation-to-sentences.json").exists()
    assert not (output_dir / f"{args.name}.report-sentences.json").exists()

    if args.construct_doc_pool:
        assert not (output_dir / f"{args.name}.document_pool.json").exists()

    data = {}
    for run_id, run in all_runs.items():
        for topic_run in run:
            request_id = topic_run['request_id']

            if request_id not in data:
                data[ request_id ] = {}
            
            data[ request_id ][ run_id ] = {
                i: s['text'] for i, s in enumerate(topic_run['sentences'])
            }

    with (output_dir / f"{args.name}.report-sentences.json").open('w') as fw:
        json.dump(data, fw)
    
    data = {}
    for run_id, run in all_runs.items():
        for topic_run in run:
            request_id = topic_run['request_id']

            if request_id not in data:
                data[ request_id ] = {}
            
            for i, sent in enumerate(topic_run['sentences']):
                for doc_id in sent['citations']:
                    if doc_id not in data[ request_id ]:
                        data[ request_id ][ doc_id ] = {}

                    if run_id not in data[ request_id ][ doc_id ]:
                        data[ request_id ][ doc_id ][ run_id ] = {}
                    
                    data[ request_id ][ doc_id ][ run_id ][ i ] = sent['text']
    
    if args.add_rel_docs:
        for fn in args.qrels:
            qrel = pd.DataFrame(irms.read_trec_qrels(fn)).set_index(['query_id', 'relevance']).doc_id
            if 0 in qrel.index.get_level_values('relevance').unique():
                qrel = qrel.drop(0, level='relevance')

            
            for request_id in data:
                counter = 0
                if request_id not in qrel.index:
                    continue
                for doc_id in qrel.loc[request_id]:
                    if doc_id not in data[request_id]:
                        data[request_id][doc_id] = {}
                        counter += 1

                if counter > 0:
                    print(f"[{request_id}] {fn} adds {counter} additional rel docs.")

    with (output_dir / f"{args.name}.citation-to-sentences.json").open('w') as fw:
        json.dump(data, fw)

    if args.construct_doc_pool:
        with (output_dir / f"{args.name}.document_pool.json").open('w') as fw:
            json.dump({
                topic_id: list(d.keys())
                for topic_id, d in data.items()
            }, fw)