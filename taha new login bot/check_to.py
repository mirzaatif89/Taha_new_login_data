from pathlib import Path 
txt=Path('utility.py').read_text(errors='ignore') 
print(txt.count('TimeoutException')) 
