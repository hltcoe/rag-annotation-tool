import argparse
import gzip
import json
from pathlib import Path

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)

    parser.add_argument('--already_revised', action='store_true', default=False)

    args = parser.parse_args()

    input_fn: Path = args.input
    output_dir: Path = args.output_dir

    rubric_data = {}
    with (gzip.open if input_fn.suffix == ".gz" else open)(input_fn, 'rt') as fr:
        for l in fr:
            d = json.loads(l) 
            rubric_data[d['query_id']] = d['items']

    output_dir.mkdir(parents=True, exist_ok=True)

    file_suffix = "revised" if args.already_revised else "preload"

    for query_id, items in rubric_data.items():
        output_fn = output_dir / f"nuggets_{query_id}.{file_suffix}.json"

        if output_fn.exists():
            print(f"[{query_id}] file {output_fn} already exists, skipped.")
            continue

        with output_fn.open('w') as fw:
            json.dump({
                "nugget_list": [
                    (item['question_text'], { answer: [] for answer in item['gold_answers'] })
                    for item in items
                ]
            }, fw)
        
        print(f"[{query_id}] file {output_fn} done")
        
    
    

    
    

