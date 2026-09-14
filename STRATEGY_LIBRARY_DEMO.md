# Strategy Library Demo (real execution)

GET /strategies -> seeds present: ['black-b0', 'black-b1', 'black-b2', 'black-b3', 'white-w5', 'white-w6']
GET /strategies?side=white -> ['white-w5', 'white-w6']
GET /strategies/white-w6 -> White Harness W6, status=completed
GET /strategies/black-b3 -> 200
POST demo-test-strategy -> 201
GET /strategies/demo-test-strategy -> Demo Test
DELETE demo-test-strategy -> 204
GET /strategies/demo-test-strategy after delete -> 404
