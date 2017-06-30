#!/usr/bin/evn python
"""
Python script for programmatically sending bitcoin via email
using blockonomics API
"""
import re
import os
import sys
import csv
import argparse
import requests
import time
from pycoin import ecdsa, encoding

"""
API Settings
"""
BASE_SERVER = "https://www.blockonomics.co"
SPLIT_KEY_API = BASE_SERVER + "/api/redeem_code"
SEND_MAIL_API = BASE_SERVER + "/api/send_redeem_code"
#Change this endpoint to point to your custom HTML
REDEEM_ENDPOINT = BASE_SERVER + "/btcmail#/redeem"
#Set API_KEY to relax API limits if needed
API_KEY = ""
#Time in days after refund happens
REFUND_TIME = 1

"""
A custom type for argparse, to facilitate validation of email addresses.
"""
class EmailType(object):
  """
  Supports checking email agains different patterns. The current available patterns is:
  RFC5322 (http://www.ietf.org/rfc/rfc5322.txt)
  """

  patterns = {
    'RFC5322': re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
  }

  def __init__(self, pattern):
    if pattern not in self.patterns:
      raise KeyError('{} is not a supported email pattern, choose from:'
                     ' {}'.format(pattern, ','.join(self.patterns)))
    self._rules = pattern
    self._pattern = self.patterns[pattern]

  def __call__(self, value):
    if not self._pattern.match(value):
      raise argparse.ArgumentTypeError(
        "'{}' is not a valid email - does not match {} rules".format(value, self._rules))
    return value


def generate_redeem_link(email):

  #Generate (Public, Private) key pair
  rand = os.urandom(32).encode('hex')
  secret_exponent= int("0x"+rand, 0) % ecdsa.secp256k1._r
  private_key = encoding.secret_exponent_to_wif(secret_exponent, compressed=True)
  public_pair = ecdsa.public_pair_for_secret_exponent(ecdsa.secp256k1.generator_secp256k1,secret_exponent)
  public_key1 = "04" + format(public_pair[0], '064x') + format(public_pair[1], '064x')

  #Only submit public_key/email to server
  post_request_data = { "public_key1" : public_key1, "email" : email,
                       "refund_time": REFUND_TIME} 
  headers={'Authorization': 'Bearer {}'.format(API_KEY)}
  response = requests.post(SPLIT_KEY_API, data=post_request_data,
                           headers=headers)
  result = response.json()
  btc_address = result.get("bitcoin_address")

  if btc_address:
    email_redeem_code(btc_address)
    redeem_url="{}?key1={}&bitcoin_address={}".format(REDEEM_ENDPOINT,
                                                      private_key, btc_address)
    return dict(redeem_url = redeem_url, 
                bitcoin_address = btc_address)
  else:
    raise RuntimeError(result['message'])


def email_redeem_code(address):
  payload = {"bitcoin_address" : address}
  headers={'Authorization': 'Bearer {}'.format(API_KEY)}
  response = requests.post(SEND_MAIL_API, data=payload, headers=headers)
  if (not response.ok):
    raise Exception("Server ERROR: Could not email redeem code")


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-i", "--infile", type=argparse.FileType("r"), 
                      help="Input CSV file containing email addresses")
  parser.add_argument("-o", "--outfile", type=argparse.FileType("w"), 
                      default=sys.stdout, help="Outfile CSV file (default stdout)")

  args = parser.parse_args()
  email_type = EmailType('RFC5322')

  if (args.infile):
    reader = csv.reader(args.infile)
    writer = csv.writer(args.outfile, delimiter=',')
    for row in reader:
      try:
        if not len(row):
          continue
        email_type(row[0])
        result = generate_redeem_link(row[0])
        #Don't do very fast, wait a second before next request
        time.sleep(1)
        result['emailid']=row[0]
        writer.writerow(result.values())
      except (argparse.ArgumentTypeError, RuntimeError) as e:
        print "Error", e
        continue
  else:  
    parser.print_help()
