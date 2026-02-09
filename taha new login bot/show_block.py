from pathlib import Path 
lines=Path('utility.py').read_text('utf-8').splitlines()  
for i in range(480,520):  
    print(str(i+1).rjust(4) + ': ' + lines[i])  
