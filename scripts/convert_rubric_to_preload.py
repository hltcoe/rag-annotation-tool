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

    rubric_data = {
        d['query_id']: d['items']
        for d in map(json.loads, (gzip.open if input_fn.suffix == ".gz" else open)(input_fn, 'rt'))
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    file_suffix = "revised" if args.already_revised else "preload"

    for query_id, items in rubric_data.items():
        output_fn = output_dir / f"nuggets_{query_id}.{file_suffix}.json"

        if output_fn.exists():
            print(f"[{query_id}] file {output_fn} already exists, skipped.")
            continue
    
        # merge 
        nugget_list = []
        q_idx = {}
        for item in items:
            a_dict = { answer: [] for answer in item['gold_answers'] }
            if item['question_text'] in q_idx:
                nugget_list[ q_idx[item['question_text']] ][1].update(a_dict)
            else:
                nugget_list.append((item['question_text'], a_dict))
                q_idx[item['question_text']] = len(nugget_list) - 1

        with output_fn.open('w') as fw:
            json.dump({
                "nugget_list": nugget_list
            }, fw)
        
        print(f"[{query_id}] file {output_fn} done")
        
    
    

    
    

