from pathlib import Path 
text=Path('utility.py').read_text().splitlines() 
start=600; end=900 
for i in range(start,end): 
    print(f'{i+1:04d}: {text[i]}') 
