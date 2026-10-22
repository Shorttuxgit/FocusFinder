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

name = "Bobby"
age = 22

o= open("timetable_cache.json", "r")
timetablelist = {o.read()}
print(timetablelist)

list = {
    "name": f"{name}",
    "age": f"{age}",
    "is_true": f"{bob}"
}

print(list["name"])

a = json.dumps(list)


with open("timetable_cache.json", "w") as f:
    f.write(a)

print(a)