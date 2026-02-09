from pathlib import Path 
lines=Path('utility.py').read_text('utf-8').splitlines()  
import sys  
import re  
for i,l in enumerate(lines):  
    if 'selenium-wire' in l or 'Proxy settings supplied' in l:  
        print(i+1, l)  
