import pathlib 
lines = pathlib.Path('utility.py').read_text().splitlines() 
for i in range(1120, 1200): 
    print(f'{i+1:04d}: {lines[i]}') 
