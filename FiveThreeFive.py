"""
The 535 Library
A library designed to do the backend work for /r/535 by leveraging the APIs of nonprofits (like PeoPublica) into
informational posts organized by the Reddit API.
Author: James C. Lynch
Code: Python 2
"""
import re
import cStringIO
import codecs
import csv
import datetime
import time
import requests
import requests.auth
import deepdiff
import os
import json
from configparser import ConfigParser
from warnings import warn
from dateutil import parser, tz
from cPickle import HIGHEST_PROTOCOL, dump, load

"""Global Variables"""
CURRENT_CONGRESS = '115'
BILL_FLAIR_ID = "db59d2b0-10df-11e7-9495-0ee45a3eb946"

"""Config-derrived Globals"""

config = ConfigParser()
config.read('config.ini')

REDDIT_USN = config.get('reddit', 'username')
REDDIT_PWD = config.get('reddit', 'password')
USER_AGENT = config.get('reddit', 'user_agent')
_BOT_SECRET = config.get('reddit', 'app_secret')
_BOT_ID = config.get('reddit', 'app_id')
PP_KEY = config.get('propublica', 'key')

# ======================================================================================================================


def main():
    pass


# ----------------------------------------------------------------------------------------------------------------------
def authorize(username, password, user_agent=USER_AGENT, app_id=_BOT_ID,
              app_secret=_BOT_SECRET):
    """
    Secure a temporary OAuth token from the Reddit API. This is good for 3600 seconds
    :param app_id: Public ID for the Reddit app
    :param username: Reddit account username
    :param password: Reddit account password
    :param user_agent: Name of the Reddit app, should be modeled for "CongressionalRobot"
    :param app_secret: the secret key for the app. DO NOT SHARE THIS WITH ANYONE OUTSIDE OF THE 535 PROJECT

    :return: a dictionary header for requests that includes the OAuth token
    :rtype: dict
    """

    url = "https://www.reddit.com/api/v1/access_token"

    client_auth = requests.auth.HTTPBasicAuth(app_id, app_secret)
    post_data = {"grant_type": "password", "username": username, "password": password}
    headers = {"User-Agent": "{} (by /u/{})".format(user_agent, username)}
    response = requests.post(url, auth=client_auth, data=post_data,
                             headers=headers)

    # Sample response JSON:
    #  {u'access_token': u'XXXXXXXXXXXXXXXXX', u'token_type': u'bearer', u'expires_in': 3600, u'scope': u'*'}

    header = {"Authorization": "bearer {}".format(response.json()["access_token"]),
              "User-Agent": "python:CongressionalRobot:v0.0.1 (by /u/theChuck-Truck)"}

    return header


# ----------------------------------------------------------------------------------------------------------------------
def reddit_ini(filename):
    """
    Opens the .ini file at *filename* and returns a tuple with the reddit usn and pwd
    :param filename: the path to the file, to be opened by open()
    :return: tuple of the username and password
    :rtype: tuple of str
    """

    reader = ConfigParser()

    reader.read(filename)

    username = reader.get('reddit', 'username')
    password = reader.get('reddit', 'password')

    return username, password

# ----------------------------------------------------------------------------------------------------------------------
def update_house_csv():
    """
    Updates the CSV file of the US House of Representatives in the local directory
    :return: None
    """

    """Set headers"""
    headers = {"X-API-Key": "PP_KEY"}

    """Generate list of house members"""
    houser = requests.get("https://api.propublica.org/congress/v1/115/house/members.json", headers=headers)
    assert houser.status_code == 200  # Just so we don't blow up our current CSV without a replacement.
    reps = houser.json()['results'][0]['members']  # Isolate representatives themselves

    """Open/Generate the CSV file"""
    with open("house.csv", "wb+") as csvfile:
        f = UnicodeWriter(csvfile)
        # Headers
        headers = ["first_name", "middle_name", "last_name", "state", "district", "party", "next_election", "id",
                   "api_uri", "domain",
                   "url", "facebook_account", "facebook_id", "twitter_account", "google_entity_id", "rss_url",
                   "total_votes", "missed_votes", "missed_votes_pct",
                   "total_present", "votes_with_party_pct", "dw_nominate", "seniority", "ideal_point"]
        f.writerow(headers)
        for rep in reps:

            """Ensure all fields in 'headers' is represented"""

            for entry in headers:
                if entry not in rep or rep[entry] == u'' or not rep[entry]:
                    rep[entry] = u'null'

            """Write row"""
            f.writerow([rep[entry] for entry in headers])

    return


# ----------------------------------------------------------------------------------------------------------------------
def update_senate_csv():
    """
    Same as update_house_csv, but with the upper house
    :return: None
    """

    """Set headers"""
    headers = {"X-API-Key": "PP_KEY"}

    """Generate list of house members"""
    senate_response = requests.get("https://api.propublica.org/congress/v1/115/senate/members.json", headers=headers)
    assert senate_response.status_code == 200  # Just so we don't blow up our current CSV without a replacement.
    senators = senate_response.json()['results'][0]['members']  # Isolate representatives themselves

    """Open/Generate the CSV file"""
    with open("senate.csv", "wb+") as csvfile:
        f = UnicodeWriter(csvfile)
        # Headers
        headers = ["first_name", "middle_name", "last_name", "state", "district", "party", "next_election", "id",
                   "api_uri", "domain",
                   "url", "facebook_account", "facebook_id", "twitter_account", "google_entity_id", "rss_url",
                   "total_votes", "missed_votes", "missed_votes_pct",
                   "total_present", "votes_with_party_pct", "dw_nominate", "seniority", "ideal_point"]
        f.writerow(headers)
        for senator in senators:

            """Ensure all fields in 'headers' is represented"""

            for entry in headers:
                if entry not in senator or senator[entry] == u'' or not senator[entry]:
                    senator[entry] = u'null'

            """Write row"""
            f.writerow([senator[entry] for entry in headers])

    return


# ----------------------------------------------------------------------------------------------------------------------
def moc_lookup(name, chamber):
    """
    Looks up the name of a MOC in the local csv and returns its info.
    :param name:
    :param chamber:
    :return:
    """
    steve = csv.DictReader('{}.csv'.format(chamber.lower))
    row = steve.next()

    while row[0] + ' ' + row[2] != name:
        row = steve.next()

    return row


# ----------------------------------------------------------------------------------------------------------------------

def load_with_datetime(pairs):
    """Handles deserialization of Bill objects.
    credit to: http://stackoverflow.com/questions/14995743/how-to-deserialize-the-datetime-in-a-json-object-in-python
    """
    d = {}
    for k, v in pairs:
        if isinstance(v, basestring):

            if k == 'votes':
                d[k] = Vote(file_path=v[1:-1])

            try:
                d[k] = parser.parse(v)
            except ValueError:
                d[k] = v

        elif isinstance(v, dict):  # For dealing with Bill.timeline()
            for key in v.keys():
                try:
                    v[parser.parse(key)] = v.pop(key)
                except ValueError:
                    pass
            d[k] = v
        else:
            d[k] = v
    return d


# ----------------------------------------------------------------------------------------------------------------------

def date_handler(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, Vote):
        obj.save()
        return "<{}>".format(obj.json_file)
    elif isinstance(obj, str):
        pass
    elif isinstance(obj, unicode):
        pass
    else:
        raise TypeError(
            "Unserializable object {} of type {}".format(obj, type(obj))
        )


# ----------------------------------------------------------------------------------------------------------------------

def billtime(vote, raw=False):  # TODO: Nest this in Vote as a static
    """
    Strips datetime object from vote JSON
    :param vote: the vote json from ProPublica GET
    :param raw: the option to return a raw datetime object
    """
    bt = datetime.datetime.strptime('{}T{}'.format(vote['date'], vote['time']), "%Y-%m-%dT%H:%M:%S")

    if raw:
        return bt
    else:
        return bt.strftime('%A, %B %d, %Y at %X')

# ----------------------------------------------------------------------------------------------------------------------
"""From https://docs.python.org/2/library/csv.html"""
"""Provides unicode-compatible csv ops"""


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")


class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self


class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ----------------------------------------------------------------------------------------------------------------------
"""What follows is the class hierarchy for the 535 project, currently including Bills, MOCs, and Votes"""


class Bill:
    def __init__(self, url=None, file_path=None):
        """
        A Bill object that can store amendments, updates, and a time-line. All these arguments are optional, because you
        :param str url: The ProPublica URL. The class can be created manually via the from_params class
        """

        """Initialize vars - more for clarity's sake. Most of the actual __init__ assigning will be done via GET or deserialization"""

        self.chamber = self.session = self.bill_id = self.votes = self.timeline = self.subjects = self.title = \
            self.name = self.official_link = self.birthday = self.cosponsors = self.sponsor_party = self.sponsor = \
                self.sponsor_state = self.sparknotes = self.last_action = self.committees = self.passed = \
            self.passed_house = self.passed_senate = self.vetoed = self.status = self.raw_type = self.type = \
            self.post_body = self.tracking = None

        """Deserializing method"""
        if file_path:
            with open(file_path, 'r') as json_file:
                try:
                    self.__dict__.update(json.loads(json_file.read(), object_pairs_hook=load_with_datetime))
                    return
                except ValueError:
                    print '{} FILE:'.format(file_path) + json_file.read()
                    raise
        else:
            self.tracking = True  # If constructing from url (not reloading), assume we want to track it.
            self.url = url  # This shouldn't be overwritten because the filepath option will return before reassignment
            self.propublica_pull()

        """Fullname Placeholder"""
        self.fullname = None

        """JSON settings"""
        self.json_file = './bills/' + self.bill_id + '.json'

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def needs_update(self, other):
        """
        Different from __eq__ in that this comparison function only checks what we care about - that is, the data that
        we publish to Reddit. Because most bills we pull down don't have serialization info, they won't be equivalent.
        :param Bill other: Bill object that has NOT been serialized
        :return: True if all the following fields match up:
                    self.title, self.name, self.type, self.birthday, self.status, self.official_link, self.subjects,
                    self.votes, self.sparknotes, self.timeline(.items())
        """

        if self.title != other.title:
            print self.title
            print other.title
            return True
        if self.name != other.name:
            print self.name
            print other.name
            return True
        if self.type != other.type:
            print self.type
            print other.type
            return True
        if self.birthday != other.birthday:
            print self.birthday
            print other.birthday
            return True
        if self.status != other.status:
            print self.status
            print other.status
            return True
        if self.official_link != other.official_link:  # We just want there to be a source there
            print self.official_link
            print other.official_link
            return True
        if self.sparknotes != other.sparknotes:
            return True
        if self.timeline != other.timeline:
            return True
        if self.votes != other.votes:
            return True
        return False

    @classmethod
    def from_params(cls, chamber, bill_id):
        """
        Generates the class with parameters instead of a url, constructing the url along the way
        :param key:
        :param chamber:
        :param congress:
        :param bill_type:
        :param bill_id:
        :return:
        """

        new_bill = cls("https://api.propublica.org/congress/v1/{}/bills/{}.json"
                                .format(chamber, bill_id), PP_KEY)

        return new_bill

    @staticmethod
    def _parse_actions(actions_list):
        """
        Parses the ProPublica JSON object in format list dict (containing a datestamp entry and a description entry)
        into a dictionary with the format {[timestamp string]: [string desctiption]}
        :param actions_list:
        :return: dctionary of actions
        :rtype: dict
        """

        actions_dict = {}

        for action in actions_list:
            dt = parser.parse(action['datetime'])  # Strip datetime literal in UTC
            dt.astimezone(tz.tzlocal())  # Convert to local timezone
            actions_dict.update({dt: action['description']})

        return actions_dict

    def get_subjects(self, key):

        # Define authentication headers
        headers = {"X-API-Key": key}

        # API call parameters
        url = "https://api.propublica.org/congress/v1/{session}/bills/{bill_id}/subjects.json".format(**self.__dict__)

        subject_r = requests.get(url, headers=headers)

        # If for any reason we encounter an error getting the subjects, construct a dummy list and return it.

        if subject_r.status_code != 200:
            return ['No subjects found.']
        subject_json = subject_r.json()
        if subject_json['status'] == u'ERROR':
            return ['No subjects found.']
        subject_dicts = subject_json['results']['subjects']  # list of dict objects

        # We return subjects, instead of mutating self.votes in get_votes, because subjects *should* be static
        return [subject['name'] for subject in subject_dicts]

    def get_votes(self, votes_json, key):
        """
        Gets the detailed vote objects (roll calls) by iterating through the less thorough list included in bill JSON
        :param votes_json: The section of the bill's JSON that pertains to the votes
        :param key: the ProPublica API key
        :return: None
        """

        votes = []

        if self.votes:
            # We do not want to overwrite votes that already have a post
            for vote in self.votes[:]:
                if type(vote) == unicode:
                    self.votes[self.votes.index(vote)] = Vote(file_path=str(vote[1:-1]))  # Convert a filepath string to Vote

            stored_ids = [stored_vote.id for stored_vote in self.votes]
            for vote in votes_json:
                url = vote['api_url']
                if url[url.rindex('/') + 1: url.rindex('.')] in stored_ids:  # i.e., if we have the vote logged already
                    continue
                else:
                    # If this is a new vote, we're going to update
                    self.votes.append(Vote(url, key))


        else:
            self.votes = []
            for vote in votes_json:
                self.votes.append(Vote(vote['api_url'], key)) # Votes are only to be created in bills, NOT MOCs.

    def gen_post_body(self, client):
        """
        Generates a markdown-formatted post in unicode.
        :param RedditClient client: Reddit Client to handle vote updates
        :return: body
        :rtype: str
        """

        body = u''  # We will store our markdown body for the post in this variable as the function progresses.

        """Bill headers"""
        body += u'#{}\n####{}\n\n'.format(self.title, self.name)  # Title of the bill, and the designator as a subtitle
        body += u'Type: *{}*\n\n'.format(self.type.title())  # String title method (confused me!)
        body += u'Date Created: {}\n\n'.format(self.birthday)  # Date of creation right under the title
        body += u'Status: {}\n\n'.format(self.status.replace('_', ' ').title())
        body += u'######[Link]({})\n'.format(self.official_link)  # Link to official bill info site
        body += u'\n*****\n\n'  # This string makes a horizontal line

        """Subjects"""
        body += u'####Subjects: '
        for subject in self.subjects:
            body += u'{}, '.format(subject)
        body = body[:-2]  # strip away final ", "
        body += u'\n\n'

        """Sponsors"""
        body += u'####Sponsor: {} ({}-{})\n\n'.format(self.sponsor, self.sponsor_party, self.sponsor_state)
        # TODO: Add cosponsor names? PP API only gives the name of the main sponsor up-front

        """Summary"""
        body += u'####Summary:\n>{}\n\n'.format(self.sparknotes)

        """Actions"""
        body += u'##Actions:\nTime|Action\n:---|:---\n'  # Table headers and alignment (both aligned left)
        for dt, desc in self.timeline.items():
            body += u'**{}**|{}\n'.format(dt.strftime('%a, %B %m'), desc)
        body += u'*All times are in U.S. Eastern.*\n\n'

        """Votes"""
        body += u'##Roll Call Votes:\n'

        # Most of what the chambers pass are not roll call votes - let's catch and reflect this in the post.
        if len(self.votes) == 0:
            body += u'**No roll call vote data available**\n'
        else:
            for vote in self.votes:

                if not vote.fullname:
                    # If the vote's fullname is not present, that means the vote needs to be posted
                    vote.fullname = vote.unicode_post(client)
                if not vote.fullname:  # Another failure means that the post failed, and the linking needs to be skipped
                    body += u'{}({})\n\n'.format(vote.question, vote.result)
                else:
                    # Post a link for each vote that we just posted
                    body += u'[{}](https://reddit.com/r/535/comments/{})\n\n'.format(vote.question, vote.fullname[3:])

        self.post_body = body  # For ease-of-access in append_post

    def post(self, client):
        """
        Initially post the vote to Reddit.
        For updates, use "edit_post".
        :param RedditClient client: a RedditClient
        :return: response from the reddit API call.
        :rtype: requests.Response
        """

        self.gen_post_body(client)

        # Reddit's max title length is 300
        if len(self.title) > 250:
            self.title = self.title[:247] + '...'

        """Construct the request"""
        params = {
            "kind": "self",
            "text": self.post_body,
            "sendreplies": "true",
            # Capitalize the chamber in the title
            "title": '[{}]: {}'.format(self.type.upper(), self.title),
            "sr": "535"
        }

        url = "https://oauth.reddit.com/api/submit"

        post_r = client.request('POST', url, params=params)
        """Calmly tell Chuck he's an idiot if he messed something up."""
        if post_r.status_code != 200:
            warn("Vote post request returned {}".format(post_r.status_code))
            return False
        print post_r.text
        fullname = 't3_' + re.search('comments\/([a-zA-Z0-9_]*)\/', post_r.text).group(1)  # For future comment+/flair

        self.fullname = fullname

        return fullname

    def save(self, retry=True):
        """
        Serialize the object as a json object
        :return: None
        """

        try:
            """Convert datetime keys into isoformat() - they will be re-parsed by the load() pair-catcher"""
            self.last_action = self.last_action.isoformat()
            for key, value in self.timeline.items():
                if type(key) not in (str, unicode):
                    self.timeline[key.isoformat()] = self.timeline.pop(key)

            """Write File"""
            with open(self.json_file, 'w') as data_file:
                json.dump(self.__dict__, data_file, default=date_handler)

            print "{} saved at {}".format(self.name, self.json_file)
        except AttributeError:
            if retry:
                self.last_action = parser.parse(self.last_action)
                self.save(retry=False)
            else:
                raise

    def load(self):
        """
        Deserializes the object's json file at json_file and updates the object's __dict__ directly
        :return:
        """
        with open(self.json_file, 'r') as data_file:
            self.__dict__ = json.load(data_file)

    def propublica_pull(self):
        """
        Assigns most self variables based on a new json call. Does not edit post-related attrs
        :return:
        """

        """Attributes defined via API call below"""
        r = requests.get(self.url, headers={"X-API-Key": PP_KEY})
        pp_json = r.json()['results'][0]

        self.chamber = 'house' if pp_json['number'] == 'H' else 'senate'
        self.session = 2 if datetime.datetime.now().year % 2 == 0 else 1
        self.bill_id = pp_json['bill_id']

        # Update self.votes
        self.get_votes(pp_json['votes'], PP_KEY)

        self.timeline = self._parse_actions(pp_json['actions'])
        self.subjects = self.get_subjects(PP_KEY)
        self.title = pp_json['title']

        # Reddit's max title length is 300
        if len(self.title) > 250:
            self.title = self.title[:247] + '...'

        try:
            self.name = pp_json['bill']
        except KeyError:  # Catches resolutions, I think.
            self.name = pp_json['number']
        self.official_link = pp_json['gpo_pdf_uri']

        if self.official_link == "":
            self.official_link = pp_json['congressdotgov_url']

        self.birthday = parser.parse(pp_json['introduced_date'])
        self.cosponsors = int(pp_json['cosponsors'])
        self.sponsor = pp_json['sponsor']
        self.sponsor_party = pp_json['sponsor_party']
        self.sponsor_state = pp_json['sponsor_state']
        # TODO: Pull the full summary using some sort of HTML-to-Markdown conversion scheme
        self.sparknotes = pp_json['summary_short']
        self.last_action = datetime.datetime.strptime(pp_json["latest_major_action_date"], "%Y-%m-%d")
        self.committees = []  # TODO: fill in later when Committee class is complete

        """Boolean statuses based on passage dates"""
        self.passed_house = True if pp_json['house_passage_vote'] else False
        self.passed_senate = True if pp_json['senate_passage_vote'] else False
        self.passed = pp_json['enacted'] != ""
        self.vetoed = pp_json['vetoed'] != ""

        """Status Logic"""
        if self.passed:
            self.status = 'passed'
        if self.vetoed:
            self.status = 'vetoed'
        elif self.passed_house and self.passed_senate:
            self.status = 'passed_congress'
        elif self.passed_house:
            self.status = 'passed_house'
        elif self.passed_senate:
            self.status = 'passed_senate'
        else:
            self.status = 'new'

        """Bill Type Logic"""
        self.raw_type = pp_json['bill_type']
        if self.raw_type == 's':
            self.type = 'senate bill'
        elif self.raw_type == 'sres':
            self.type = 'senate res'
        elif 'jres' in self.raw_type:
            self.type = 'joint res'
        elif self.raw_type == 'hr':
            self.type = 'house bill'
        else:
            self.type = 'misc'

    def edit_post(self, client, markdown=None):
        """
        Updates the Reddit post identified by self.fullname with additional information.
            Any string argued in str markdown will be appended directly to the end of the Reddit Post with string
            '**Update**: ' as a header
        :param str markdown: A string representing the markdown-formatted text we're going to append the post with.
        :param RedditClient client: a RedditClient object to handle the POST.
        :return: fullname
        """

        if markdown:
            text = self.post_body + '\n\n**Update**: ' + markdown
        else:
            text = self.post_body

        params = {
            'api_type': 'json',
            'text': text,
            'thing_id': self.fullname
        }

        append_r = client.request('POST', url='https://oauth.reddit.com/api/editusertext', params=params)

        if append_r.status_code == 200:
            self.post_body = text
        else:
            warn("Bill append_post POST request returned {}".format(append_r.status_code))
            return False

        """We're going to check here if the bill's flair can change"""
        self.title_flair(client)

    def decommission(self):
        """
        Remove this bill from tracking status. When higher-level parsers load this bill, it will be flagged as inactive
        :return: None
        """

        self.tracking = False

    def title_flair(self, client):
        if len(self.title) < 64:
            f_params = {
                'api_type': 'json',
                'link': self.fullname,
                'flair_template_id': BILL_FLAIR_ID,
                'text': self.title
            }
            client.request('POST', "https://oauth.reddit.com/r/535/api/selectflair", params=f_params)
        else:
            print "title too long"


class MOC:
    def __init__(self, key, member_id):
        """
        An object to represent a Member of Congress, to include both house reps and senators.
        :param key: the ProPublica API key, which is not stored in the MOC class
        :param member_id: the member ID, gained from either a local csv (recommended) or this GET call:
            GET https://api.propublica.org/congress/v1/{congress}/{chamber}/members.json
        """

        self.id = member_id

        """Attributes below are derivative of this API call"""
        # Define authentication headers
        headers = {"X-API-Key": key}
        pp_json = requests.get("https://api.propublica.org/congress/v1/members/{}.json"
                                  .format(self.id), headers=headers).json()['results]']

        self.firstname = pp_json['first_name']
        self.lastname = pp_json['last name']
        self.middle_name = pp_json['middle_name']

        self.party = pp_json['current_party']
        self.birthday = pp_json['date_of_birth']
        self.website = pp_json['url']
        self.rss = pp_json['rss_url']
        self.cspan_id = pp_json['cspan_id']
        self.icpsr_id = pp_json['icpsr_id']
        self.thomas_id = pp_json['thomas_id']

        """Social Media"""
        self.twitter = pp_json['twitter_account']
        self.facebook = pp_json['facebook_account']
        self.youtube = pp_json['youtube_account']

        """Congressional Positions"""
        self.committees = {entry['congress']: entry['committees'] for entry in pp_json['roles']}
        # TODO: Fill self.committees with find_committee function
        self.roles = pp_json['roles']
        self.total_votes = 0  # Set in get_votes
        self.votes = self.get_votes(key)

    def get_votes(self, key):
        """
        Generates and returns a list of Vote objects
        :param key:
        :return: a list of vote-summary dictionaries in the format:
                {
                    "member_id": str,
                    "chamber": house/senate,
                    "congress": str of int,
                    "session": str of int,
                    "roll_call": str of int,
                    "bill": {},
                    "description": str
                    "question": str,
                    "datetime": datetime.datetime object
                    "position": "Yes" or "No" or "Not Voting"
                }
        """
        headers = {"X-API-Key": key}

        pp_json = requests.get("https://api.propublica.org/congress/v1/members/{}/votes.json"
                               .format(self.id), headers=headers).json()['results']

        self.total_votes = pp_json['total_votes']
        votes = pp_json['votes']

        """Adjust the format to match Python datetime object"""
        for vote in votes:
            vote.update({'datetime': billtime(vote, raw=True)})
            del vote['date']
            del vote['time']

        return votes


class Vote:
    def __init__(self, url=None, key=None, file_path=None):
        """
        Generates a Vote object
        :param congress: The string representing the current congress - i.e.'115' for the current one (2017)
        :param chamber: The stirng 'house' or 'senate'
        :param rc_id: A ProPublica roll-call ID
        :param file_path: a filepath to a JSON-serialized Vote object
        :param key:
        """

        """Deserialize a JSON if file_path exists"""
        if file_path:
            with open(file_path, 'r') as json_file:
                self.__dict__ = json.load(json_file)
                return

        self.session = 2 if datetime.datetime.now().year % 2 == 0 else 1
        self.id = url[url.rindex('/') + 1: url.rindex('.')]

        # Define authentication headers
        headers = {"X-API-Key": key}

        pp_json = requests.get(url, headers=headers).json()['results']
        vote_json = pp_json['votes']['vote']

        self.question = vote_json['question']
        self.description = vote_json['description']
        self.type = vote_json['vote_type']
        self.datetime = billtime(vote_json, raw=True)
        self.result = vote_json['result']
        self.chamber = vote_json['chamber'][0].lower() + vote_json['chamber'][1:]
        self.positions = vote_json['positions']
        self.republican_summary = vote_json['republican']
        self.democratic_summary = vote_json['democratic']
        self.independent_summary = vote_json['independent']
        self.fullname = None

        """JSON settings"""
        self.json_file = './votes/' + self.chamber + self.id + '.json'

        try:
            self.title = vote_json['bill']['bill_id'].upper()
            self.bill_name = vote_json['bill']['title']
        except KeyError:
            self.bill_name = "Non-Bill Measure"
            self.title = self.question

    @classmethod
    def from_params(cls, congress, chamber, rc_id, key):
        session = 2 if datetime.datetime.now().year % 2 == 0 else 1
        new_vote = cls("https://api.propublica.org/congress/v1/{}/{}/sessions/{}/votes/{}.json" \
            .format(congress, chamber, session, rc_id))
        return new_vote

    def __getitem__(self, key):
        return self.__dict__[key]

    def save(self):
        """
        Serialize the object as a json object
        :return: None
        """

        if type(self.datetime) not in (str, unicode):
            self.datetime = self.datetime.isoformat()  # To allow serialization of datetime objects

        with open(self.json_file, 'w') as data_file:
            json.dump(self.__dict__, data_file)

    def json_dump(self):
        """
        Serialize the object as a json object. Dump it instead of saving it to a file
        :return: None
        """

        with open(self.json_file, 'w') as data_file:
            json.dumps(self.__dict__, default=date_handler)

    def load(self):
        """
        Deserializes the object's json file at json_file and updates the object's __dict__ directly
        :return:
        """
        with open(self.json_file, 'r') as data_file:
            self.__dict__ = json.load(data_file, object_pairs_hook=load_with_datetime)

    # TODO: Move the reddit functions we do here (comment, flair, and hide) to the client object.
    def unicode_post(self, client):
        """
        post...but in unicode! yay.
        :param client:
        :return: the fullname of the link, or False if an error prevented completion.
                Note that an error will not raise; this function only warns() as of now.
        """

        text = u""""""

        text += u'#Subject: "{}"\n'.format(self.description)
        text += u'**Time: {}**\n\n'.format(self.datetime)
        text += u'**Result: {}**\n\n'.format(self.result)
        text += u'###Vote Summary:\n\n'

        """Add rollcall by party"""
        for party in ['independent', 'democratic', 'republican']:
            text += u"**{}:**\n\n".format(party.title())
            for position, count in self['{}_summary'.format(party)].items():
                if position in ['majority_position', 'present']:
                    continue  # Not neccessary to convey this information
                text += '*{}*: {}\n'.format(position.replace('_', ' ').title(), count)
            text += '\n'

        """Read internal CSV to determine who voted on what side"""
        roll = {'Yes': [], 'No': [], 'Not Voting': []}

        with open('{}.csv'.format(self.chamber), 'r') as f:
            r = UnicodeReader(f)

            # TODO: Create a soft-copy of the chamber's csv to cut down on search time as members are found

            for member in self.positions:
                """Get to our desired entry. Error will kill loop if EOF reached"""
                while True:
                    line = r.next()
                    if member['member_id'] in line:
                        if self.chamber == 'senate':
                            try:
                                roll[member['vote_position']].append(u'{2}, {0} ({5}-{3})'.format(*line))
                            except KeyError:
                                roll[member['vote_position']] = u'{2}, {0} ({5}-{3})'.format(*line)
                        else:  # Shortened string for house
                            try:
                                roll[member['vote_position']].append(u'{2} ({5}-{3}/{4})'.format(*line))
                            except KeyError:
                                roll[member['vote_position']] = [u'{2} ({5}-{3}/{4})'.format(*line)]
                        break
                f.seek(0)

        """Add our roll to the bottom of the file"""

        if self.chamber == 'house':  # Request sizes made with the entire house are typically too large, so we'll put that in a comment.
            comment = {}
            for position, members in sorted(roll.items(), key=lambda x: x[1]):  # Sorts by popularity of position
                comment[position] = u'**{}({}):**\n\n'.format(position, len(members))
                for member in members:
                    comment[position] += u'{}; \n'.format(member)
                comment[position] += u'\n\n'
        else:
            comment = False
            text += u"###Votes by Member\n\n"
            for position, members in sorted(roll.items(), key=lambda x: x[1]):  # Sorts by popularity of position
                text += u'**{}({}):**\n\n'.format(position, len(members))
                for member in members:
                    text += u'{}; \n'.format(member)
                text += u'\n\n'

        url = "https://oauth.reddit.com/api/submit"

        # Reddit's max title length is 300
        if len(self.bill_name) > 200:
            billname = self.bill_name[197:] + '...'
        else:
            billname = self.bill_name
        if self.question > 50:
            question = self.question[47:] + '...'
        else:
            question = self.question

        params = {
            "kind": "self",
            "text": text,
            "sendreplies": "true",
            # Capitalize the chamber in the title
            "title": '{} Vote: {}; {}'.format(
                self.chamber[:1].upper() + self.chamber[1:], billname, question
            ),
            "sr": "535"
        }
        post_r = client.request('POST', url, params=params)


        """Calmly tell Chuck he's an idiot if he messed something up."""
        if post_r.status_code != 200:
            warn("Vote post request returned {}".format(post_r.status_code))
            print post_r.text()
            return None
        fn_search = re.search('comments\/([a-zA-Z0-9_]*)\/', post_r.text)
        if not fn_search:
            print "No fullname regexed, retrying"
            print self.question
            print post_r.text
            return None
        else:
            fullname = 't3_' + fn_search.group(1)  # For future comment+/flair

        """If we are dealing with a House of Representatives post, we are going to post the positions as comments"""
        if comment:
            # General comment params:
            c_params = {
                'api_type': 'json',
                'thing_id': fullname
            }
            for pos, data in comment.iteritems():
                c_params.update(text=data)
                comment_r = client.request('POST', 'https://oauth.reddit.com/api/comment', params=c_params)
                if comment_r.status_code != 200:
                    warn("House comment follow-up POST returned {}".format(comment_r.status_code))

        """FLAIR THE VOTE"""

        # Hardcoded values; if something flair-related breaks, it'll probably be this.
        pass_flair_id = "72c210b8-eee9-11e6-a5ae-0eaf4dbf6b74"
        fail_flair_id = "76cdad02-eee9-11e6-8acb-0e942a836e52"
        furl = "https://oauth.reddit.com/r/535/api/selectflair"
        f_params = {
            'api_type': 'json',
            'link': fullname,
        }

        # Determine which flair to apply

        if len(roll['Yes']) > len(roll['No']):
            f_params.update(flair_template_id=pass_flair_id)

        elif len(roll['No']) > len(roll['Yes']):
            f_params.update(flair_template_id=fail_flair_id)

        # Apply the flair
        flair_r = client.request('POST', furl, params=f_params)

        # Warn Chuck if he is an idiot
        if flair_r.status_code != 200:
            warn("Vote flair POST returned {}".format(flair_r.status_code))

        """Finally, remove the post so it only shows up in links"""
        h_params = {
            'id': fullname,
            'spam': 'false'
        }
        hurl = 'https://oauth.reddit.com/api/remove'

        hide_r = client.request('POST', hurl, params=h_params)

        if hide_r.status_code != 200:
            warn("Abnormal code {} for hide POST".format(hide_r.status_code))

        return fullname


class Committee:
    def __init__(self):
        pass


class RedditClient:
    """
    Class representing a Reddit Client for the CongressionalRobot
    """
    def __init__(self, usn, pw, limit=60, **agents_and_ids):
        """"""

        self.header = {}
        self.header_exp = datetime.datetime.now()  # set as "expired" by default
        self.authorize(usn, pw, **agents_and_ids)

        self.requests_made = 0  # Requests made in the past minute
        self.limit = limit  # Reddit standard is 60 requests/min
        self.requests_remaining = self.limit - self.requests_made

        self.cycle_start = datetime.datetime.now()

        # This Client needs to store its credentials to ensure constant service
        self.username = usn
        self.password = pw

    def authorize(self, username, password, user_agent="python:CongressionalRobot:v0.0.1", app_id="BQ6EuAzmCd3JkQ",
                  app_secret="0_DiQkyZssMwE2mw-nHP-aswWek"):
        """
        Secure a temporary OAuth token from the Reddit API. This is good for 3600 seconds
        :param app_id: Public ID for the Reddit app
        :param username: Reddit account username
        :param password: Reddit account password
        :param user_agent: Name of the Reddit app, should be modeled for "CongressionalRobot"
        :param app_secret: the secret key for the app. DO NOT SHARE THIS WITH ANYONE OUTSIDE OF THE 535 PROJECT

        :return: a dictionary header for requests that includes the OAuth token
        :rtype: dict
        """

        url = "https://www.reddit.com/api/v1/access_token"

        client_auth = requests.auth.HTTPBasicAuth(app_id, app_secret)
        post_data = {"grant_type": "password", "username": username, "password": password}
        headers = {"User-Agent": "{} (by /u/{})".format(user_agent, username)}
        response = requests.post(url, auth=client_auth, data=post_data,
                                 headers=headers)

        # Sample response JSON:
        #  {u'access_token': u'XXXXXXXXXXXXXXXXX', u'token_type': u'bearer', u'expires_in': 3600, u'scope': u'*'}

        self.header = {"Authorization": "bearer {}".format(response.json()["access_token"]),
                  "User-Agent": "python:CongressionalRobot:v0.0.2 (by /u/theChuck-Truck)"}

        self.header_exp = datetime.datetime.now() + datetime.timedelta(minutes=36)

    def wait(self, seconds):
        """
        Waits a certain number of seconds then resets the request counter
        :return:
        """
        print "[CLIENT]: Waiting for next minute"
        self.requests_made = 0  # Reset requests counter since we will wait out the rest of the period
        self.requests_remaining = self.limit - self.requests_made

        time.sleep(seconds)  # Wait that many seconds

    def seconds_in_cycle(self):
        """
        Returns time (in seconds) remaining in the current cycle.
        :return: seconds left
        :rtype: int
        """

        return (datetime.datetime.now() - self.cycle_start).seconds

    def cycle_expired(self):
        """
        Checks if a cycle has passed since the last request
        :return: True if cycle
        """

        return self.seconds_in_cycle > 60

    def request(self, verb, url, **options):
        """
        Makes a requests.get request with the argued options.
        Note that the OAuth headers are automatically passed and don't need to be argued
        :param verb: one of these RESTful verbs:
                GET, PUT, POST, DELETE
        :param url: the url to GET from
        :param options: key/value pairs of requests
        :return:
        """

        """Validate Inputs"""
        verb = verb.upper()
        assert verb in ['GET', 'POST', 'PUT', 'DELETE']

        """Check auth"""
        if self.header_exp < (datetime.datetime.now() - datetime.timedelta(minutes=36)):
            self.authorize(self.username, self.password)

        """Check if the request count can be reset, or if we need to wait before making a call"""

        if self.cycle_expired():
            self.cycle_start = datetime.datetime.now()

        elif self.requests_remaining == 0:
            self.wait(self.seconds_in_cycle())

        if verb == 'GET':
            r = requests.get(url, headers=self.header, **options)
        elif verb == 'POST':
            r = requests.post(url, headers=self.header, **options)
        elif verb == 'PUT':
            r = requests.put(url, headers=self.header, **options)
        elif verb == 'DELETE':
            r = requests.delete(url, headers=self.header, **options)

        else:
            raise ValueError("Invalid verb argument: {}".format(verb))

        return r


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
# ======================================================================================================================
'./votes/house76.json'
'./votes/house76.json'