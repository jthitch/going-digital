from django.db import connection

c = connection.cursor()
c.execute('SELECT id, payment_gateway, internal_name, transaction_percentage FROM gd_payment_gateway ORDER BY id')
print('gateways:')
for r in c.fetchall():
    print(r)

c.execute(
    '''
    SELECT payment_gateway, COUNT(*)
    FROM gd_report__bookings_by_payment_gateway
    WHERE booking_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    GROUP BY payment_gateway
    ORDER BY COUNT(*) DESC
    '''
)
print('recent pg report:')
for r in c.fetchall():
    print(r)

c.execute(
    '''
    SELECT payment_gateway_id,
           AVG(transaction_percentage_on_creation),
           MIN(transaction_percentage_on_creation),
           MAX(transaction_percentage_on_creation),
           COUNT(*)
    FROM gd_booking
    WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
    GROUP BY payment_gateway_id
    '''
)
print('booking txn % on creation:')
for r in c.fetchall():
    print(r)
