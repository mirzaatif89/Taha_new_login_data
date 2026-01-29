import pathlib 
lines = pathlib.Path('utility.py').read_text().splitlines() 
for i in range(300, 450): 
    print(f'{i+1:04d}: {lines[i]}') 
