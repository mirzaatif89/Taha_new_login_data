from pathlib import Path 
lines=Path('utility.py').read_text(errors='ignore').splitlines() 
for i,l in enumerate(lines,1): 
    if 'TimeoutException' in l: 
        print(i, l) 
