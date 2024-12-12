# RAG Annotation Tool

Very brief readme. Ping Eugene for any questions.

## Get Started

```bash
pip install -r requirements.txt
```

Running this app at port 9988.
```bash
streamlit run entry.py --server.port 9988 -- --user_db_path=user_db.db --task_configs ./mini-test_config.json
```

For the Streamlit runtime configuration, please refer to https://docs.streamlit.io/develop/concepts/configuration/options. 

Flags after `--` are app sepcific configurations. Right now, you can pass mulitple files to `--task_configs` to load multiple config files. 

The `--user_db_path` points to a sqlite database that contains user log in information with passwords stored with salts. 

## Config File

Config files are `json` files that define the task.
The dictionary is loadded to the Python class `task_resources.TaskConfig`. 

There are several particularly important fields:
- `name`: the unique name of the task severing as the unique identifier of the task.
- `task_assignment`: a dictionary that define the assignment of the topic to the assessors. 
- `topic_file`: a jsonl file where the topic are stored with fields used defined by the `topic_id_field` and `topic_fields`. 
- `cited_sentences_path`: a json file containing all report sentences that cite some document in the collection. It is meant to be used to judge the supportness of the reference and constructing/revising the nuggets. The file should have four levels -- topic_id, doc_id, run_id, and sent_id. 
- `report_runs_path` a json file containing all the reports. The file should contain three levels -- topic_id, run_id, sent_id. 

Other fields should be self-explanatory by the field name. 
Please refer to the `mini-test_config.json` as an example.
`mini-test.citation-to-sentences.json` and `mini-test.report-sentences.json` are two example resource files referred in the `mini-test_config.json` config file. 
The two files are generaed by the utility script `prepare_utils.py`. 

## Preload Nuggets

In order to preload nuggets before the first stage citation support assessment, simply put a json file in the output directory defined in the config file with the file name in the format of `nuggets_{topic_id}.preload.json`. 

The json file has the same format of the output nugget file, which contains two high level fields -- `nugget_dict` and `group_assignment`. 

`nugget_dict` contains a dictionary of nugget questions to a dictionary of nugget answer to a list of document id supporting the question-answer pair. The preload nugget can have empty doucment id list, which is meant to be assigned during the nugget support stage. 

`group_assignment` contains a dictionar of nugget question to its assigned group. The dictionary can also be empty in the preload file. 
