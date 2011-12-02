Description
===========
Backup your iPhone SMS text messages.

Why? 
---- 
Your iPhone stores a copy of all your SMS text messages in a sqlite database.
But, if you want to view them all on your iPhone, it's not so easy. Be
prepared to do a lot of scrolling.

Or, you can you use `sms-backup.py` to backup all your SMS messages in text
format, CSV format, or JSON, and then view them in the data viewer of your
choice.

Plus, `sms-backup.py` cleans up and allows you to transform your data, in
order to make your text messages easier to read.

Transformations possible with `sms-backup.py`:

  * Better date formatting.
  
  * Consistent formatting of phone numbers.
  
  * Replacement of phone numbers with names.

How?
----
Each time you sync/backup your iPhone, the SMS sqlite db file is copied to
your computer. 

When you run `sms-backup.py`, it finds the backup db file, makes a temporary
copy of it, selects the text messages you want from the temporary copy, and
then exports them.

Examples
========
    $ sms-backup.py
    
    2010-01-01 15:31:44 |             Me | (555) 555-1212 | I love donuts!!
    2010-01-02 16:17:58 | (555) 555-1212 |             Me | I love a man who loves donuts!!!
    2010-01-02 17:01:19 |             Me | (999) 999-1212 | I don't feel so good...
    ...
    
    $ sms-backup.py --myname Tom \
                    --alias "555-555-1212=Michele" \
                    --phone "5555551212" \
                    --phone "1112223333" \
                    --date-format "%b %d, %Y at %I:%M %p" \
                    --format json
    
    [
      {
        "date": "Jan 01, 2010 at 03:31 PM",
        "from": "Tom", 
        "text": "I love donuts!!", 
        "to": "Michele"
      }, 
      {
        "date": "Jan 02, 2010 at 04:17 PM",
        "from": "Michele", 
        "text": "I love a man who loves donuts!!!", 
        "to": "Tom"
      }, 
      {
        "date": "Jan 02, 2010 at 06:00 PM",
        "from": "Tom", 
        "text": "Just checking in...where are you?", 
        "to": "(111) 222-3333"
      }, 
      ...

Usage
=====
    usage: sms-backup.py [-h] [-q] [-a PHONE=NAME] [-d FORMAT]
                         [-f {human,csv,json}] [-m NAME] [-o FILE] [-p PHONE]
                         [--no-header] [-i FILE]

    optional arguments:
      -h, --help            show this help message and exit
      -q, --quiet           Reduce running commentary.

    Format Options:
      -a PHONE=NAME, --alias PHONE=NAME
                            Key-value pair (.ini style) that maps a phone number
                            to a name. Name replaces phone number in output. Can
                            be used multiple times. Optional. If not present,
                            phone number is used in output.
      -d FORMAT, --date-format FORMAT
                            Date format string. Optional. Default: '%Y-%m-%d
                            %H:%M:%S'.
      -f {human,csv,json}, --format {human,csv,json}
                            How output is formatted. Valid options: 'human'
                            (fields separated by pipe), 'csv', or 'json'.
                            Optional. Default: 'human'.
      -m NAME, --myname NAME
                            Name of iPhone owner in output. Optional. Default
                            name: 'Me'.

    Output Options:
      -o FILE, --output FILE
                            Name of output file. Optional. Default (if not
                            present): Output to STDOUT.
      -p PHONE, --phone PHONE
                            Limit output to sms messages to/from this phone
                            number. Can be used multiple times. Optional. Default
                            (if not present): All messages from all numbers
                            included.
      --no-header           Don't print header row for 'human' or 'csv' formats.
                            Optional. Default (if not present): Print header row.

    Input Options:
      -i FILE, --input FILE
                            Name of SMS db file. Optional. Default: Script will
                            find and use db in standard backup location.

Notes on the SMS Database
=========================
The backup sqlite db file is located

    ~/Library/Application Support/MobileSync/Backup/<phone ID>
    
and is named `3d0d7e5fb2ce288813306e4d4636395e047a3d28`.

It's name is an SHA1 hash of the full path of the file on the phone, plus its
Domain.

    $ printf 'HomeDomain-Library/SMS/sms.db' | openssl sha1
    3d0d7e5fb2ce288813306e4d4636395e047a3d28

The schema of the two key tables: `message` and `group_member`:

    CREATE TABLE message 
        (ROWID INTEGER PRIMARY KEY AUTOINCREMENT, 
         address TEXT, 
         date INTEGER, 
         text TEXT, 
         flags INTEGER, 
         replace INTEGER, 
         svc_center TEXT, 
         group_id INTEGER, 
         association_id INTEGER, 
         height INTEGER, 
         UIFlags INTEGER, 
         version INTEGER, 
         subject TEXT, 
         country TEXT, 
         headers BLOB, 
         recipients BLOB, 
         read INTEGER);

     CREATE TABLE group_member 
         (ROWID INTEGER PRIMARY KEY AUTOINCREMENT, 
          group_id INTEGER, 
          address TEXT, 
          country TEXT);

The `address` (phone number) in `message` is inconsistently formatted. Numbers
can appear as (555) 555-1212, or 15555551212, or +15555551212. That's one
reason why I decided to query on `group_id`.

The `flags` field shows whether a message was sent or received by the iPhone:

    2 - Message received by iPhone from address
    3 - Message sent from iPhone to address

More Reading
------------
  * http://www.slideshare.net/hrgeeks/iphone-forensics-without-the-iphone
  * http://damon.durandfamily.org/archives/000487.html
  * http://linuxsleuthing.blogspot.com/2011/02/parsing-iphone-sms-database.html
 
Known Limitations
=================

  * Won't find the backup sqlite db on Windows, but it *should* run if you pass
    in the db name with --input.  (I haven't tested it, though...)

  * Assumes encoding of texts is 'utf-8'...and there's no way to change it.
    
  * Does not try to recover texts with photos.  Just skips past them.

License
=======
MIT License.  Copyright 2011 Tom Offermann.
