from pathlib import Path 
lines=Path('utility.py').read_text('utf-8').splitlines()  
for i,l in enumerate(lines):  
    if 'selenium-wire' in l or 'Proxy settings supplied' in l:  
        for j in range(max(0,i-5), min(len(lines), i+5)):  
            print(str(j+1) + ': ' + lines[j])  
        print('-'*60)  
