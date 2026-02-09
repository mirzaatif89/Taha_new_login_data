lines=open('utility.py',encoding='utf-8').read().splitlines()  
start=930  
end=990  
for i,line in enumerate(lines[start:end], start=start+1):  
    print(f'{i}: {line}')  
