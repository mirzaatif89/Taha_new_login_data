from pathlib import Path 
import json 
matches=[str(p) for p in Path('.').rglob('*.py') if 'TimeoutException' in p.read_text(errors='ignore')] 
print(json.dumps(matches, indent=2)) 
