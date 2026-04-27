import dotenv
vals = dotenv.dotenv_values('.env')
for k, v in vals.items():
    print(f"'{k}': {v!r}")
