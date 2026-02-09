lines=open('utility.py',encoding='utf-8').read().splitlines()  
start=961  
end=1005  
for i,line in enumerate(lines[start:end], start=start+1):  
    print(f'{i}: {line}')  
