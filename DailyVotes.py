"""
DailyVotes: POSTs the day's votes according to ProPublica
"""

from FiveThreeFive import Vote, RedditClient, PP_KEY, REDDIT_PWD, REDDIT_USN
import requests
import datetime

"""Client"""
alien = RedditClient(REDDIT_PWD, REDDIT_USN)

""""Gather votes in a 24-hr period"""
month = datetime.datetime.now().strftime("%m")
# month = '02'
year = datetime.datetime.now().strftime("%Y")
updated_votes = requests.get("https://api.propublica.org/congress/v1/house/votes/{}/{}.json".format(year, month),
                             headers={"X-API-Key": PP_KEY})
print "Got the votes"
uv_json = updated_votes.json()['results']

votes = []

for vote in uv_json['votes']:
    print "Building Vote object"
    votes.append(Vote(vote['congress'], 'house', vote['roll_call'], key=PP_KEY))

for vote in votes:
    if vote.datetime > (datetime.datetime.now() - datetime.timedelta(days=1)):
        print "Attempting post"
        r = vote.post(alien)

        print r.status_code
        print r.text
        print r.headers

"""Sample Response:

{"jquery": [[0, 1, "call", ["body"]], [1, 2, "attr", "find"], [2, 3, "call", [".status"]], [3, 4, "attr", "hide"], [4, 5, "call", []], [5, 6, "attr", "html"], [6, 7, "call", [""]], [7, 8, "attr", "end"], [8, 9, "call", []], [1, 10, "attr", "redirect"], [10, 11, "call", ["https://www.reddit.com/r/535/comments/5x82ot/senate_vote_nonbill_measure_on_the_motion_to/"]], [1, 12, "attr", "find"], [12, 13, "call", ["*[name=url]"]], [13, 14, "attr", "val"], [14, 15, "call", [""]], [15, 16, "attr", "end"], [16, 17, "call", []], [1, 18, "attr", "find"], [18, 19, "call", ["*[name=text]"]], [19, 20, "attr", "val"], [20, 21, "call", [""]], [21, 22, "attr", "end"], [22, 23, "call", []], [1, 24, "attr", "find"], [24, 25, "call", ["*[name=title]"]], [25, 26, "attr", "val"], [26, 27, "call", [" "]], [27, 28, "attr", "end"], [28, 29, "call", []]], "success": true}
{'Content-Length': '354', 'X-Cache-Hits': '0', 'x-xss-protection': '1; mode=block', 'x-content-type-options': 'nosniff', 'X-Moose': 'majestic', 'x-ua-compatible': 'IE=edge', 'cache-control': 'private, s-maxage=0, max-age=0, must-revalidate, max-age=0, must-revalidate', 'Date': 'Fri, 03 Mar 2017 03:31:08 GMT', 'x-ratelimit-remaining': '599.0', 'Strict-Transport-Security': 'max-age=15552000; includeSubDomains; preload', 'X-Cache': 'MISS', 'Set-Cookie': 'loid=IZrrI4HGukZ9T5pZ7x; Domain=reddit.com; Max-Age=63071999; Path=/;  secure, loidcreated=1488511868000; Domain=reddit.com; Max-Age=63071999; Path=/;  secure', 'Accept-Ranges': 'bytes', 'expires': '-1', 'Server': 'snooserv', 'Connection': 'keep-alive', 'X-Served-By': 'cache-iad2628-IAD', 'x-ratelimit-used': '1', 'Via': '1.1 varnish', 'Content-Encoding': 'gzip', 'X-Timer': 'S1488511868.400515,VS0,VE95', 'Vary': 'accept-encoding', 'x-frame-options': 'SAMEORIGIN', 'Content-Type': 'application/json; charset=UTF-8', 'x-ratelimit-reset': '532'}
200


"""
