Description
===========
Backup your iPhone SMS and iMessage text messages.

Works with iOS6 and iOS7.

(And, it continues to work with iOS5, if anyone still finds that useful...)

Why? 
---- 
Your iPhone stores a copy of all your SMS and iMessage text messages in a
sqlite database. But, if you want to view them all on your iPhone, it's not so
easy. Be prepared to do a lot of scrolling.

Or, you can you use `sms-backup.py` to backup all your messages in text
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
Before running this script, you need to backup up your iPhone to your local
computer. Connect it with a USB cable and launch a backup through iTunes.

Even if your iPhone is set to automatically backup to iCloud, you can
still choose to "Manually Backup Up" within iTunes, which will do a one-time
backup to your computer, and then resume the automatic iCloud backups.

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
    usage: sms-backup.py [-h] [-q | -v] [-a ADDRESS=NAME] [-d FORMAT]
                         [-f {human,csv,json}] [-m NAME] [-o FILE] [-e EMAIL]
                         [-p PHONE] [--no-header] [-i FILE]

    optional arguments:
      -h, --help            show this help message and exit
      -q, --quiet           Decrease running commentary.
      -v, --verbose         Increase running commentary.

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
      -e EMAIL, --email EMAIL
                            Limit output to iMessage messages to/from this email
                            address. Can be used multiple times. Optional. Default
                            (if not present): All iMessages included.
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

Notes on the Database
=====================
The discussion about the SMS/iMessage database has been moved to the project wiki:

  * https://github.com/toffer/iphone-sms-backup/wiki

Known Limitations
=================
  * Won't find the backup sqlite db on Windows, but it *should* run if you pass
    in the db name with --input.  (I haven't tested it, though...)

  * Assumes encoding of texts is 'utf-8'...and there's no way to change it.
    
  * Does not try to recover texts with photos.  Just skips past them.
  
  * Does not handle group chats.

License
=======
MIT License.  Copyright 2011 Tom Offermann.
