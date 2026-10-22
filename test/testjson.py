import json
bob = True

settings = f'{{"isOn":"{bob}" }}'

y = json.loads(settings)
print(y["isOn"])
b = eval(y["isOn"])

if b == True:
    print("yes it works")
    print(b)
else:
    print("no")
    print(b)
