import pathlib 
lines = pathlib.Path('utility.py').read_text().splitlines() 
for i in range(980, 1060): 
    print(f'{i+1:04d}: {lines[i]}') 
