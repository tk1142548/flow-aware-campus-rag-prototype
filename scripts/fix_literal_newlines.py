from pathlib import Path
p=Path('data/research/process_records.jsonl');s=p.read_text(encoding='utf8');print(s.count(r'\n'));s=s.replace(r'\n','\n');p.write_text(s,encoding='utf8');print(s.count(r'\n'))
