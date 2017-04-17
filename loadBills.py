from FiveThreeFive import Bill, Vote, RedditClient, PP_KEY
import requests
import datetime
import os
test = []
os.chdir('./bills')
for f in [f for f in os.listdir(os.getcwd())]:
    print f
    test.append(Bill(file_path=f))

for bill in test:
    print 'this bill is at index ' + str(test.index(bill))

