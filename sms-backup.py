#!/usr/bin/env python

# Copyright (c) 2011 Tom Offermann
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the 'Software'), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import csv
import cStringIO
import fnmatch
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile

from datetime import datetime

# argparse isn't in standard library until 2.7
try:
    test = argparse.ArgumentParser()
except NameError:
    try:
        import argparse
    except:
        print "argparse required. Try `pip install argparse`."
        sys.exit(1)
        
# silence Python 2.6 buggy warnings about Exception.message
# See: http://code.google.com/p/argparse/issues/detail?id=25
if sys.version_info[:2] == (2, 6):
    import warnings
    warnings.filterwarnings(action='ignore',
                            message="BaseException.message has been "
                                    "deprecated as of Python 2.6",
                            category=DeprecationWarning,
                            module='argparse')

# Global variables
ORIG_DB = 'test.db'
COPY_DB = None

def setup_and_parse(parser):
    """
    Set up ArgumentParser with all options and then parse_args().
    
    Return args.
    """
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("-q", "--quiet", action='store_true', 
            help="Decrease running commentary.")
    log_group.add_argument("-v", "--verbose", action='store_true', 
            help="Increase running commentary.")
    
    # Format Options Group
    format_group = parser.add_argument_group('Format Options')
    format_group.add_argument("-a", "--alias", action="append", 
            dest="aliases", metavar="ADDRESS=NAME",
            help="Key-value pair (.ini style) that maps an address "
                 "(phone number or email) to a name. Name replaces "
                 "address in output. Can be used multiple times. Optional. "
                 "If not present, address is used in output.")
                 
    format_group.add_argument("-d", "--date-format", dest="date_format",
            metavar="FORMAT", default="%Y-%m-%d %H:%M:%S",
            help="Date format string. Optional. Default: '%(default)s'.")
                 
    format_group.add_argument("-f", "--format", dest="format", 
            choices = ['human', 'csv', 'json'], default = 'human', 
            help="How output is formatted. Valid options: 'human' "
                 "(fields separated by pipe), 'csv', or 'json'. "
                 "Optional. Default: '%(default)s'.")
                 
    format_group.add_argument("-m", "--myname", dest="identity", 
            metavar="NAME", default = 'Me',
            help="Name of iPhone owner in output. Optional. "
                 "Default name: '%(default)s'.")
    
    # Output Options Group
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument("-o", "--output", dest="output", metavar="FILE",
            help="Name of output file. Optional. Default "
                 "(if not present): Output to STDOUT.")
                 
    output_group.add_argument("-e", "--email", action="append",
            dest="emails", metavar="EMAIL",
            help="Limit output to iMessage messages to/from this email "
                 "address. Can be used multiple times. Optional. Default (if "
                 "not present): All iMessages included.")
    
    output_group.add_argument("-p", "--phone", action="append",
            dest="numbers", metavar="PHONE",
            help="Limit output to sms messages to/from this phone number. "
                 "Can be used multiple times. Optional. Default (if "
                 "not present): All messages from all numbers included.")
    
    output_group.add_argument("--no-header", dest="header", 
            action="store_false", default=True, help="Don't print header "
            "row for 'human' or 'csv' formats. Optional. Default (if not "
            "present): Print header row.")
            
    # Input Options Group
    input_group = parser.add_argument_group('Input Options')
    input_group.add_argument("-i", "--input", dest="db_file", metavar="FILE",
            help="Name of SMS db file. Optional. Default: Script will find "
                 "and use db in standard backup location.")
            
    args = parser.parse_args()
    return args

def strip(phone):
    """Remove all non-numeric digits in phone string."""
    if phone:
        return re.sub('[^\d]', '', phone)

def trunc(phone):
    """Strip phone, then truncate it.  Return last 10 digits"""
    if phone:
        ph = strip(phone)
        return ph[-10:]

def format_phone(phone):
    """
    Return consistently formatted phone number for output.
    
    Note: US-centric formatting.
    
    If phone < 10 digits, return stripped phone.
    If phone = 10 digits, return '(555) 555-1212'.
    If phone = 11 digits and 1st digit = '1', return '(555) 555-1212'.
    Otherwise, leave as is.
    """
    ph = strip(phone)
    if len(ph) < 10:
        phone = ph
    elif len(ph) == 10:
        phone = "(%s) %s-%s" % (ph[-10:-7], ph[-7:-4], ph[-4:])
    elif len(ph) == 11 and ph[0] =='1':
        phone = "(%s) %s-%s" % (ph[-10:-7], ph[-7:-4], ph[-4:])
    return phone.decode('utf-8')

def format_address(address):
    """If address is email, leave alone.  Otherwise, call format_phone()."""
    m = re.search('@', address)     # No @ sign?  Must be phone number!
    if not m:
        address = format_phone(address)
    return address

def valid_phone(phone):
    """
    Simple validation of phone number. 
    
    It is considered a valid phone number if: 
        * It does not contain any letters
        * It does not contain the '@' sign
        * It has at least 3 digits, after stripping all non-numeric digits.
    
    Returns True if valid, False if not.
    """
    ret_val = False
    phone_match = re.search('^[^a-zA-Z@]+$', phone)
    if phone_match:
        stripped = strip(phone)
        if len(stripped) >= 3:
            ret_val = True
    return ret_val

def validate_aliases(aliases):
    """Raise exception if any alias is not in 'address = name' format."""
    if aliases:
        for a in aliases:
            # Only one equal sign allowed!
            m = re.search('^([^=]+)=[^=]+$', a)
            if not m:
                raise ValueError("OPTION ERROR: Invalid --alias format. "
                                 "Should be 'address = name'.")
            key = m.group(1)
            phone_match = re.search('^[^@]+$', key)     # No @ sign = phone!
            if phone_match:
                if not valid_phone(key):
                    raise ValueError("OPTION ERROR: Invalid phone number "
                                     "in --alias.")

def validate_numbers(numbers):
    """Raise exception if invalid phone number found."""
    if numbers:
        for n in numbers:
            if not valid_phone(n):
                raise ValueError("OPTION ERROR: Invalid number in --number.")

def validate(args):
    """
    Make sure aliases and numbers are valid.
    
    If invalid arg found, print error msg and raise exception.
    """
    try:
        validate_aliases(args.aliases)
        validate_numbers(args.numbers)
    except ValueError as err:
        print err, '\n'
        raise

def most_recent(paths):
    """Return path of most recently modified file."""
    paths.sort(key=lambda x: os.path.getmtime(x))
    return paths[-1]

def find_sms_db():
    """Find sms db and return its filename."""
    db_name = '3d0d7e5fb2ce288813306e4d4636395e047a3d28'
    mac_dir = '%s/Library/Application Support/MobileSync' % os.path.expanduser('~')
    paths = []
    for root, dirs, files in os.walk(mac_dir):
        for basename in files:
            if fnmatch.fnmatch(basename, db_name):
                path = os.path.join(root, basename)
                paths.append(path)
    if len(paths) == 0:
        logging.warning("No SMS db found.") 
        path = None
    elif len(paths) == 1:
        path = paths[0]
    else:
        logging.warning("Multiple SMS dbs found. Using most recent db.")
        path = most_recent(paths)
    return path

def copy_sms_db(db):
    """Copy db to a tmp file, and return filename of copy."""
    try:
        orig = open(db, 'rb')
    except:
        logging.error("Unable to open DB file: %s" % db)
        sys.exit(1)
    
    try:
        copy = tempfile.NamedTemporaryFile(delete=False)
    except:
        logging.error("Unable to make tmp file.")
        orig.close()
        sys.exit(1)
        
    try:
        shutil.copyfileobj(orig, copy)
    except:
        logging.error("Unable to copy DB.")
        sys.exit(1)
    finally:
        orig.close()
        copy.close()
    return copy.name

def alias_map(aliases):
    """
    Convert .ini-style aliases to dict.
    
    Key: phone number or email address.  (We truncate phone numbers for 
         consistent formatting.)
    Value: Alias
    """
    amap = {}
    if aliases:
        for a in aliases:
            m = re.search('^([^=]+)=([^=]+)$', a)
            key = m.group(1)
            alias = m.group(2)
            # Is key an email address?
            m2 = re.search('@', key)
            if not m2:
                key = trunc(key) 
            amap[key] = alias.decode('utf-8')
    return amap

def which_db_version(cursor):
    """
    Return version of DB schema as string.

    Return '5', if iOS 5.
    Return '6', if iOS 6 or iOS 7.

    """
    query = "select count(*) from sqlite_master where name = 'handle'"
    cursor.execute(query)
    count = cursor.fetchone()[0]
    if count == 1:
        db_version = '6'
    else:
        db_version = '5'
    return db_version

def build_msg_query(numbers, emails):
    """
    Build the query for SMS and iMessage messages.
    
    If `numbers` or `emails` is not None, that means we're querying for a
    subset of messages. Phone number is in `address` field for SMS messages,
    and in `madrid_handle` for iMessage. Email is only in `madrid_handle`.
    
    Because of inconsistently formatted phone numbers, we run both passed-in
    numbers and numbers in DB through trunc() before comparing them.
    
    If `numbers` is None, then we select all messages.
    
    Returns: query (string), params (tuple)
    """
    query = """
SELECT 
    rowid, 
    date, 
    address, 
    text, 
    flags, 
    group_id, 
    madrid_handle, 
    madrid_flags,
    madrid_error,
    is_madrid, 
    madrid_date_read,
    madrid_date_delivered
FROM message """
    # Build up the where clause, if limiting query by phone.
    params = []
    or_clauses = []
    if numbers:
        for n in numbers:
            or_clauses.append("TRUNC(address) = ?")
            or_clauses.append("TRUNC(madrid_handle) = ?")
            params.extend([trunc(n), trunc(n)])
    if emails:
        for e in emails:
            or_clauses.append("madrid_handle = ?")
            params.append(e)
    if or_clauses:
        where = "\nWHERE " + "\nOR ".join(or_clauses)
        query = query + where
    query = query + "\nORDER by rowid"
    return query, tuple(params)

def build_msg_query_ios6(numbers, emails):
    """
    Build the query for SMS and iMessage messages for iOS6 DB.

    If `numbers` or `emails` is not None, that means we're querying for a
    subset of messages. Both phone number and email is stored in the `id`
    field of the handle table.

    If `numbers` is None, then we select all messages.

    Returns: query (string), params (tuple)
    """
    query = """
SELECT
    m.rowid,
    m.date,
    m.is_from_me,
    h.id,
    m.text
FROM
    message m,
    handle h
WHERE
    m.handle_id = h.rowid"""
    # Build up the where clause, if limiting query by phone and/or email.
    params = []
    or_clauses = []
    if numbers:
        for n in numbers:
            or_clauses.append("TRUNC(h.id) = ?")
            params.append(trunc(n))
    if emails:
        for e in emails:
            or_clauses.append("h.id = ?")
            params.append(e)
    if or_clauses:
        where = "\nAND\n(" + "\nOR ".join(or_clauses) + ")"
        query = query + where
    query = query + "\nORDER by m.rowid"
    return query, tuple(params)

def fix_imessage_date(seconds):
    """
    Convert seconds to unix epoch time.
    
    iMessage dates are not standard unix time.  They begin at midnight on 
    2001-01-01, instead of the usual 1970-01-01.
    
    To convert to unix time, add 978,307,200 seconds!
    
    Source: http://d.hatena.ne.jp/sak_65536/20111017/1318829688
    (Thanks, Google Translate!)
    """
    return seconds + 978307200

def imessage_date(row):
    """
    Return date for iMessage.
    
    iMessage messages have 2 dates: madrid_date_read and
    madrid_date_delivered. Only one is set for each message, so find the
    non-zero one, fix it so it is standard unix time, and return it.
    """
    if row['madrid_date_read'] == 0:
        im_date = row['madrid_date_delivered']
    else:
        im_date = row['madrid_date_read']
    return fix_imessage_date(im_date)

def convert_date(unix_date, format):
    """Convert unix epoch time string to formatted date string."""
    dt = datetime.fromtimestamp(int(unix_date))
    ds = dt.strftime(format)
    return ds.decode('utf-8')

def convert_date_ios6(unix_date, format):
    date = fix_imessage_date(unix_date)
    return convert_date(date, format)

def convert_address_imessage(row, me, alias_map):
    """
    Find the iMessage address in row (a sqlite3.Row) and return a tuple of
    address strings: (from_addr, to_addr).
    
    In an iMessage message, the address could be an email or a phone number,
    and is found in the `madrid_handle` field.
    
    Next, look for alias in alias_map.  Otherwise, use formatted address.
    
    Use `madrid_flags` to determine direction of the message.  (See wiki
    page for Meaning of FLAGS fields discussion.)
        
    """
    incoming_flags = (12289, 77825)
    outgoing_flags = (36869, 102405)
    
    if isinstance(me, str): 
        me = me.decode('utf-8')
        
    # If madrid_handle is phone number, have to truncate it.
    email_match = re.search('@', row['madrid_handle'])
    if email_match:
        handle = row['madrid_handle']
    else:
        handle = trunc(row['madrid_handle'])
    
    if handle in alias_map:
        other = alias_map[handle]
    else:
        other = format_address(row['madrid_handle'])
        
    if row['madrid_flags'] in incoming_flags:
        from_addr = other
        to_addr = me
    elif row['madrid_flags'] in outgoing_flags:
        from_addr = me
        to_addr = other
        
    return (from_addr, to_addr)

def convert_address_sms(row, me, alias_map):
    """
    Find the sms address in row (a sqlite3.Row) and return a tuple of address
    strings: (from_addr, to_addr). 
    
    In an SMS message, the address is always a phone number and is found in
    the `address` field.
    
    Next, look for alias in alias_map.  Otherwise, use formatted address.
    
    Use `flags` to determine direction of the message:
        2 = 'incoming'
        3 = 'outgoing'
    """
    if isinstance(me, str): 
        me = me.decode('utf-8')
    
    tr_address = trunc(row['address'])
    if tr_address in alias_map:
        other = alias_map[tr_address]
    else:
        other = format_phone(row['address'])
        
    if row['flags'] == 2:
        from_addr = other
        to_addr = me
    elif row['flags'] == 3:
        from_addr = me
        to_addr = other
        
    return (from_addr, to_addr)

def convert_address_ios6(row, me, alias_map):
    if isinstance(me, str):
        me = me.decode('utf-8')

    address = row['id']

    # Truncate phone numbers, not email addresses.
    m = re.search('@', address)
    if not m:
        address = trunc(address)

    if address in alias_map:
        other = alias_map[address]
    else:
        other = address

    if row['is_from_me']:
        from_addr = me
        to_addr = other
    else:
        from_addr = other
        to_addr = me

    return (from_addr, to_addr)

def clean_text_msg(txt):
    """
    Return cleaned-up text message.

        1. Replace None with ''.
        2. Replace carriage returns (sent by some phones) with '\n'.

    """
    txt = txt or ''
    return txt.replace("\015","\n")

def skip_sms(row):
    """Return True, if sms row should be skipped."""
    retval = False
    if row['flags'] not in (2, 3):
        logging.info("Skipping msg (%s) not sent. Address: %s. Text: %s." % \
                        (row['rowid'], row['address'], row['text']))
        retval = True
    elif not row['address']:
        logging.info("Skipping msg (%s) without address. "
                        "Text: %s" % (row['rowid'], row['text']))
        retval = True
    elif not row['text']:
        logging.info("Skipping msg (%s) without text. Address: %s" % \
                        (row['rowid'], row['address']))
        retval = True
    return retval

def skip_imessage(row):
    """
    Return True, if iMessage row should be skipped.
    
    I whitelist madrid_flags values that I understand:
    
         36869   Sent from iPhone to SINGLE PERSON (address)
        102405   Sent to SINGLE PERSON (text contains email, phone, or url)
         12289   Received by iPhone
         77825   Received (text contains email, phone, or url)
    
    Don't handle iMessage Group chats:
        
         32773   Sent from iPhone to GROUP
         98309   Sent to GROUP (text contains email, phone or url)
     
    See wiki page on FLAGS fields for more details:
        
    """
    flags_group_msgs = (32773, 98309)
    flags_whitelist = (36869, 102405, 12289, 77825)
    retval = False
    if row['madrid_error'] != 0:
        logging.info("Skipping msg (%s) with error code %s. Address: %s. "
                        "Text: %s" % (row['rowid'], row['madrid_error'], 
                        row['address'], row['text']))
        retval = True
    elif row['madrid_flags'] in flags_group_msgs:
        logging.info("Skipping msg (%s). Don't handle iMessage group chat. " 
                     "Text: %s" % (row['rowid'], row['text']))
        retval = True
    elif row['madrid_flags'] not in flags_whitelist:
        logging.info("Skipping msg (%s). Don't understand madrid_flags: %s. " 
                        "Text: %s" % (row['rowid'], row['madrid_flags'], 
                        row['text']))
        retval = True
    elif not row['madrid_handle']:
        logging.info("Skipping msg (%s) without address. "
                        "(Probably iMessage group chat.) "
                        "Text: %s" % (row['rowid'], row['text']))
        retval = True
    elif not row['text']:
        logging.info("Skipping msg (%s) without text. Address: %s" % \
                        (row['rowid'], row['address']))
        retval = True
    return retval

def get_messages(cursor, query, params, aliases, cmd_args):
    cursor.execute(query, params)
    logging.debug("Run query: %s" % (query))
    logging.debug("With query params: %s" % (params,))

    messages = []
    for row in cursor:
        if row['is_madrid'] == 1:
            if skip_imessage(row): continue
            im_date = imessage_date(row)
            fmt_date = convert_date(im_date, cmd_args.date_format)
            fmt_from, fmt_to = convert_address_imessage(row, cmd_args.identity, aliases)
        else:
            if skip_sms(row): continue
            fmt_date = convert_date(row['date'], cmd_args.date_format)
            fmt_from, fmt_to = convert_address_sms(row, cmd_args.identity, aliases)
        msg = {'date': fmt_date,
               'from': fmt_from,
               'to': fmt_to,
               'text': clean_text_msg(row['text'])}
        messages.append(msg)
    return messages

def get_messages_ios6(cursor, query, params, aliases, cmd_args):
    cursor.execute(query, params)
    logging.debug("Run query: %s" % (query))
    logging.debug("With query params: %s" % (params,))

    messages = []
    for row in cursor:
        fmt_date = convert_date_ios6(row['date'], cmd_args.date_format)
        fmt_from, fmt_to = convert_address_ios6(row, cmd_args.identity, aliases)
        msg = {'date': fmt_date,
               'from': fmt_from,
               'to': fmt_to,
               'text': clean_text_msg(row['text'])}
        messages.append(msg)
    return messages

def msgs_human(messages, header):
    """
    Return messages, with optional header row. 
    
    One pipe-delimited message per line in format:
    
    date | from | to | text
    
    Width of 'from' and 'to' columns is determined by widest column value
    in messages, so columns align.
    """
    output = ""
    if messages:
        # Figure out column widths 
        max_from = max([len(x['from']) for x in messages])
        max_to = max([len(x['to']) for x in messages])
        max_date = max([len(x['date']) for x in messages])
    
        from_width = max(max_from, len('From'))
        to_width = max(max_to, len('To'))
        date_width = max(max_date, len('Date'))

        headers_width = from_width + to_width + date_width + 9
    
        msgs = []
        if header:
            htemplate = u"{0:{1}} | {2:{3}} | {4:{5}} | {6}"
            hrow = htemplate.format('Date', date_width, 'From', from_width, 
                                   'To', to_width, 'Text')
            msgs.append(hrow)
        for m in messages:
            text = m['text'].replace("\n","\n" + " " * headers_width)
            template = u"{0:{1}} | {2:>{3}} | {4:>{5}} | {6}"
            msg = template.format(m['date'], date_width, m['from'], from_width, 
                                  m['to'], to_width, text)
            msgs.append(msg)
        msgs.append('')
        output = '\n'.join(msgs).encode('utf-8')
    return output

def msgs_csv(messages, header):
    """Return messages in .csv format."""
    queue = cStringIO.StringIO()
    writer = csv.writer(queue, dialect=csv.excel, quoting=csv.QUOTE_ALL)
    if header:
        writer.writerow(['Date', 'From', 'To', 'Text'])
    for m in messages:
        writer.writerow([m['date'].encode('utf-8'),
                         m['from'].encode('utf-8'),
                         m['to'].encode('utf-8'),
                         m['text'].encode('utf-8')])
    output = queue.getvalue()
    queue.close()
    return output

def msgs_json(messages, header=False):
    """Return messages in JSON format"""
    output = json.dumps(messages, sort_keys=True, indent=2, ensure_ascii=False)
    return output.encode('utf-8')

def output(messages, out_file, format, header):
    """Output messages to out_file in format."""
    if out_file:
        fh = open(out_file, 'w')
    else:
        fh = sys.stdout
        
    if format == 'human': fmt_msgs = msgs_human
    elif format == 'csv': fmt_msgs = msgs_csv
    elif format == 'json': fmt_msgs = msgs_json
    
    try:
        fh.write(fmt_msgs(messages, header))
    except:
        raise
        
    fh.close()

def main():
        parser = argparse.ArgumentParser()
        args = setup_and_parse(parser)
        try:
            validate(args)
        except:
            parser.print_help()
            sys.exit(2)     # bash builtins return 2 for incorrect usage.
    
        if args.quiet:
            logging.basicConfig(level=logging.WARNING)
        elif args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        global ORIG_DB, COPY_DB 
        ORIG_DB = args.db_file or find_sms_db()
        COPY_DB = copy_sms_db(ORIG_DB)
        aliases = alias_map(args.aliases)

        conn = None

        try:
            conn = sqlite3.connect(COPY_DB)
            conn.row_factory = sqlite3.Row
            conn.create_function("TRUNC", 1, trunc)
            cur = conn.cursor()

            ios_db_version = which_db_version(cur)
            if ios_db_version == '5':
                query, params = build_msg_query(args.numbers, args.emails)
                messages = get_messages(cur, query, params, aliases, args)
            elif ios_db_version == '6':
                query, params = build_msg_query_ios6(args.numbers, args.emails)
                messages = get_messages_ios6(cur, query, params, aliases, args)

            output(messages, args.output, args.format, args.header)

        except sqlite3.Error as e:
            logging.error("Unable to access %s: %s" % (COPY_DB, e))
            sys.exit(1)
        finally:
            if conn:
                conn.close()
            if COPY_DB:
                os.remove(COPY_DB)
                logging.debug("Deleted COPY_DB: %s" % COPY_DB)

    
if __name__ == '__main__':
    main()
