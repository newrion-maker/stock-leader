import json
data = json.load(open('data.json', encoding='utf-8'))
print('TOP60 전체 종목:')
for s in data['top60']:
    print(s['ticker'], s['name'], s['change'])
