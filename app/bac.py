import requests

url = "https://staging.ptranz.com/Api/Alive"

headers = {"accept": "application/json"}

response = requests.get(url, headers=headers)

print(response.text)
