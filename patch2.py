with open("/Volumes/algsoch/magicpin-ai-challenge/backend/app/routes/context.py", "r") as f:
    text = f.read()

text = "import json\n" + text
with open("/Volumes/algsoch/magicpin-ai-challenge/backend/app/routes/context.py", "w") as f:
    f.write(text)
