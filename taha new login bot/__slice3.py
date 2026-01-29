import pathlib 
lines = pathlib.Path('utility.py').read_text().splitlines() 
for i in range(860, 940): 
    print(f'{i+1:04d}: {lines[i]}') 
