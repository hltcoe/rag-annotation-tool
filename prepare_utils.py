from argparse import ArgumentParser
import json
from pathlib import Path
from tqdm import tqdm

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--name', type=str, required=True)
    parser.add_argument('--input_reports', type=str, nargs='+', required=True)
    parser.add_argument('--output_dir', type=str, default='./resources')

    args = parser.parse_args()

    all_runs = {
        f.stem: [ json.loads(l) for l in f.open() ]
        for f in map(Path, args.input_reports)
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assert not (output_dir / f"{args.name}.citation-to-sentences.json").exists()
    assert not (output_dir / f"{args.name}.report-sentences.json").exists()

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

    with (output_dir / f"{args.name}.citation-to-sentences.json").open('w') as fw:
        json.dump(data, fw)
