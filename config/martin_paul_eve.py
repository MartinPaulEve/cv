user = "Martin Paul Eve"

# email addresses that repositories may hold for this user
emails = ["martin.eve@bbk.ac.uk", "eve@msu.edu", "martin@eve.gd"]

# ORCID identifier, for repository sources that can search by identifier
orcid = "0000-0002-5589-8511"

# this specifies the base eprints URL; the person identifier is derived
# automatically from the plaintext user variable above. Both `eprints`
# and `invenio` also accept a list of entries for fetching from several
# repositories of the same type, merged in declaration order (eprints
# entries first); each entry takes an optional human-readable 'name',
# defaulting to the hostname
eprints = {'repo': 'eprints.bbk.ac.uk'}

# an InvenioRDM repository (KC Works) whose records are merged with the
# eprints data on fetch; items sharing a DOI with an earlier deposit are
# deduplicated, with the earlier record preferred and its gaps filled
# from the InvenioRDM copy
invenio = {'api': 'https://works.hcommons.org/api/records'}

# this controls the output headings in the template
section_headings = {'pdf': {'all_books': "BOOKS",
                    'unedited_books': "BOOKS",
                    'edited_books': "EDITED VOLUMES",
                    'all_peer_reviewed_articles': "PEER-REVIEWED ARTICLES",
                    'peer_reviewed_articles': "PEER-REVIEWED ARTICLES",
                    'other_articles': "OTHER ARTICLES / MEDIA / INTERVIEWS",
                    'reviews': "REVIEWS",
                    'book_chapters': "BOOK CHAPTERS",
                    'conference_items': "CONFERENCE PAPERS/EVENTS"},

                    'html': {'all_books': "Books",
                    'unedited_books': "Books",
                    'edited_books': "Edited Volumes",
                    'all_peer_reviewed_articles': "Peer-Reviewed Articles",
                    'peer_reviewed_articles': "Peer-Reviewed Articles",
                    'other_articles': "Other Articles / Media/ Interviews",
                    'reviews': "Reviews",
                    'book_chapters': "Book Chapters",
                    'conference_items': "Conference Papers/Events"}
                    }

# this determines the peer review conditions for each input type
peer_reviewed = {'all_books': "ANY",
                 'unedited_books': True,
                 'edited_books': True,
                 'all_peer_reviewed_articles': True,
                 'peer_reviewed_articles': True,
                 'other_articles': False,
                 'reviews': "ANY",
                 'book_chapters': "ANY",
                 'conference_items': "ANY"}

# this determines the editorial conditions for each input type
editorial = {'all_books': "ANY",
             'unedited_books': False,
             'edited_books': True,
             'all_peer_reviewed_articles': "ANY",
             'peer_reviewed_articles': "ANY",
             'other_articles': "ANY",
             'reviews': "ANY",
             'book_chapters': "ANY",
             'conference_items': "ANY"}

# the text that starts a review
review_of = "Review of"

# this determines the book review conditions for each input type (if the text starts with the value of config.review_of)
book_review = {'all_books': False,
               'unedited_books': False,
               'edited_books': False,
               'all_peer_reviewed_articles': False,
               'peer_reviewed_articles': False,
               'other_articles': False,
               'reviews': True,
               'book_chapters': False,
               'conference_items': False}

# this determines the underlying database type in eprints
eprints_db = {'all_books': "book",
              'unedited_books': "book",
              'edited_books': "book",
              'all_peer_reviewed_articles': "article",
              'peer_reviewed_articles': "article",
              'other_articles': "article",
              'reviews': "article",
              'book_chapters': "book_section",
              'conference_items': "conference_item"}

# this section determines data storage locations
storage = {'json': 'data/eprints.json',
           'all_books': "data/all_books.json",
           'unedited_books': "data/unedited_books.json",
           'edited_books': "data/edited_books.json",
           'all_peer_reviewed_articles': "data/all_peer_reviewed_articles.json",
           'peer_reviewed_articles': "data/peer_reviewed_articles.json",
           'other_articles': "data/other_articles.json",
           'reviews': "data/reviews.json",
           'book_chapters': "data/book_sections.json",
           'conference_items': "data/conference_items.json"
           }

# this controls the default types to parse if nothing is given on the command line
default_types = ['unedited_books', 'edited_books', 'peer_reviewed_articles']

# this controls output documents
# a dictionary of lists, the first entry in each list should be a template, the second a file destination, then a series
# of operations required to create the output (the latter optional)
output_rules = {'html': ['templates/HTML',
                         'output/Eve-CV.html'],

                'pdf': ['templates/PDF',
                        'output/Eve-CV-PDF.html',
                        'uv run cv-print output/Eve-CV-PDF.html output/Eve-CV.pdf',
                        ]}

# define the section template
# sections are semantic <section> landmarks so that assistive technology can
# navigate between them
section_template = {
    'pdf': '<section id="{0}" aria-labelledby="{2}">{1}</section>',
    'html': '<section id="{0}" aria-labelledby="{2}">{1}</section>'}

# define the header template
header_template = {'pdf': '<h2 id="{2}" class="sectionheader">{0} ({1})</h2>',
                   'html': '<h3 id="{2}" class="sectionheader">{0} ({1})</h3>'}

# define the list wrapper placed around the items of each publication section
# (real lists are announced item-by-item by screen readers; the inline style
# keeps the HTML fragment self-contained when transcluded into other sites)
# line-height 1.6 keeps every link's touch target at or above 24 CSS pixels
# (WCAG 2.5.8) even when the fragment is embedded in a page with tight styles
list_template = {'pdf': '<ul class="publist">{0}</ul>',
                 'html': '<ul class="publist" style="list-style:none;margin:0;'
                         'padding:0;line-height:1.6">{0}</ul>'}

# whether to replace repository links to gold OA titles with the official URL
gold_oa_direct_link = {'pdf': True,
                       'html': True}

# the email address for OA status display
email = emails[0]

# basic OA availability
# note: [[doc]] will insert a space if required
# the aria-label names the link target (WCAG 2.4.9) and states the OA route
# in text so that gold versus green is not conveyed by colour alone (1.4.1)
oa_status = {'html': ' [<a href="[[oa_uri]]" style="color:[[oa_color]]" '
                     'aria-label="Download the [[oa_route]] open access '
                     'version of [[title]]">Download[[doc]]</a>]'}

# basic OA nonavailability
non_oa_status = {'html': ''}

# the colours used for open access download links; both values meet the
# WCAG 2.2 AAA enhanced contrast ratio of 7:1 against a white background
oa_colors = {'gold': '#6B5300',
             'green': '#175117'}

# list of venues to exclude from a list
exclude_venues = {'pdf': {
    'other_articles': 'eve.gd',
    },

    'html': {
        'other_articles': 'eve.gd',
    }}

# whether to italicize titles within specific rules
italicize_titles = {'pdf': True,
                    'html': True}

# a list of titles to italicize
# NB for this to work your CSS in any HTML must include:
# i i {
#   font-style: normal;
# }
# Ordering does matter and replacements take place in the order specified
titles_to_italicize = ['Cloud Atlas', 'Abortion Eve', 'I’m Jack', 'Station Eleven', 'Point Omega',
                       'Affinity', 'C', 'Saint Antony in His Desert', 'Enumerations: Data and Literary Study',
                       'Making Literature Now', 'Mere Reading: The Poetics of Wonder in Modern American Novels',
                       'Anti-Book: On the Art and Politics of Radical Publishing',
                       'The Cruft of Fiction: Mega-Novels and the Science of Paying Attention',
                       'Digital Humanities: Knowledge and Critique in a Digital Age',
                       'Composition, Creative Writing Studies and the Digital Humanities',
                       'The Maximalist Novel: From Thomas Pynchon\'s Gravity\'s Rainbow to Roberto Bolaño\'s 2666',
                       'Gravity\'s Rainbow', '2666', 'Literature and the Public Good',
                       'Foucault on the Politics of Parrhesia',
                       'A New Republic of Letters: Memory and Scholarship in the Age of Digital Reproduction',
                       'Laruelle Against the Digital',
                       'The Open-Source Everything Manifesto: Transparency, Truth, and Trust',
                       'Althusser and His Contemporaries: Philosophy\'s Perpetual War',
                       'Thomas Pynchon and the American Counterculture',
                       'Humanities In the Twenty-First Century: Beyond Utility and Markets',
                       'Terrorism and Temporality In The Works of Thomas Pynchon and Don DeLillo',
                       'American Postmodernist Fiction and the Past',
                       'Thomas Pynchon & the Dark Passages of History', 'Pynchon and Relativity',
                       'The Cambridge Companion to Thomas Pynchon', 'Interdisciplinarity',
                       'Local Transcendence: Postmodern Historiography and the Database', 'The Time That Remains',
                       'The Ferryman', 'The Third Policeman', 'The White Devil', 'The Goat, or Who is Sylvia',
                       'Nice Fish', 'The Man Who Knew Infinity', 'No’s Knife', 'The Alchemist', 'JR',
                       'The Glass Bead Game', 'Pynchon Notes', 'Cow Country', 'Twenty-First-Century Drama',
                       'A Visit from the Goon Squad', 'Mason & Dixon', 'Against the Day', 'Underworld', '1Q84',
                       'Emerald City', 'Telephone', 'Binding Media'
                       ]

# specify the names of the special fields
creators_item_name = 'creators'
creator_field_top_level = 'name'
creator_field_given_name = 'given'
creator_field_last_name = 'family'

editors_item_name = 'editors'
editor_field_top_level = 'name'
editor_field_given_name = 'given'
editor_field_last_name = 'family'

# the directory holding vendored CSL styles and locales
csl_directory = 'static/csl'

# the CSL locale used for citation rendering
citeproc_locale = 'en-GB'

# define the item templates in citeproc mode
# each item is a list entry; the prefix column is aria-hidden because it is a
# purely visual navigation aid (the year is already part of every citation)
_types = ['all_books', 'unedited_books', 'edited_books',
          'all_peer_reviewed_articles', 'peer_reviewed_articles',
          'other_articles', 'reviews', 'book_chapters', 'conference_items']

_pdf_item = ('<li class="anitem genericitem"><span class="prefix" '
             'aria-hidden="true">&nbsp;</span><span class="bibitem">'
             '[[citeproc]]</span></li>')

_html_item = ('<li class="anitem genericitem"><span class="prefix" '
              'aria-hidden="true">&nbsp;</span><span class="bibitem">'
              '[[citeproc]] [[oa_status]]</span></li>')

citeproc_item_templates = {'pdf': {t: _pdf_item for t in _types},
                           'html': {t: _html_item for t in _types}}

# define the item templates for new date lines in citeproc mode
_pdf_item_new_date = ('<li class="anitemnewdate genericitem"><span '
                      'class="prefix bold" aria-hidden="true">[[year]]</span>'
                      '<span class="bibitem">[[citeproc]]</span></li>')

_html_item_new_date = ('<li class="anitemnewdate genericitem"><span '
                       'class="prefix bold" aria-hidden="true">[[year]]</span>'
                       '<span class="bibitem">[[citeproc]] [[oa_status]]'
                       '</span></li>')

citeproc_item_templates_new_date = {
    'pdf': {t: _pdf_item_new_date for t in _types},
    'html': {t: _html_item_new_date for t in _types}}

# this determines the underlying database type in eprints
citeproc_type_mapper = {'all_books': "book",
                        'unedited_books': "book",
                        'edited_books': "book",
                        'all_peer_reviewed_articles': "article-journal",
                        'peer_reviewed_articles': "article-journal",
                        'other_articles': "article-journal",
                        'reviews': "article-journal",
                        'book_chapters': "chapter",
                        'conference_items': "paper-conference"}

# the citeproc style to use
citeproc_style = {'pdf': 'modern-humanities-research-association',
                  'html': 'modern-humanities-research-association'}
