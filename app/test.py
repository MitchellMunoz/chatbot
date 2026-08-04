#request library is great for getting, not meant to parse
#beatiful soup is good to parse
#requests-html is a new parser.

#REST APIs → GET to read, POST to create, PUT to update, DELETE to delete.
#SOAP APIs → POST for everything, always. The XML envelope carries the meaning instead.
#banco de guatemala is using SOAP API
import requests
#banco do guatemala uses xml, requests doesnt have a library to handle xml



r = requests.post("https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?op=TipoCambioDia", data=BODY.encode("utf-8"), )


#r = requests.get('https://xkcd.com/353/')
#r = requests.get('http://127.0.0.1:8000/get', params=payload)
#img = requests.get('https://imgs.xkcd.com/comics/python.png')
#print(r.text)
#print(img.content) gives content in bytes
#this saves it
# with open('comic.png', 'wb') as f:
#     f.write(r.content)

print(r.text)
