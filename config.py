# this specifies the base eprints URL and the user page
eprints = {
    'repo': 'eprints.bbk.ac.uk',
    'user': 'Eve=3AMartin_Paul=3A=3A'}

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
                        'screen -S serve -d -m bash -c "python3 -m http.server 8001"',
                        'sleep 2',
                        'nodejs ./print.js',
                        'screen -S serve -X quit',
                        ]}

# define the section template
section_template = {'pdf': '<div id="{0}">{1}</div>',
                    'html': '<div id="{0}">{1}</div>'}

# define the header template
header_template = {'pdf': '<h2 class="sectionheader">{0} ({1})</h2>',
                   'html': '<h3 class="sectionheader">{0} ({1})</h3>'}

# whether to replace repository links to gold OA titles with the official URL
gold_oa_direct_link = {'pdf': True,
                       'html': True}

# the email address for OA status display
email = "martin.eve@bbk.ac.uk"

# basic OA availability
# note: [[doc]] will insert a space if required
oa_status = {'html': ' [<a href="[[oa_uri]]" style="color:[[oa_color]]">Download[[doc]]</a>]'}

# basic OA nonavailability
non_oa_status = {'html': ''}

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

# citeproc support
citeproc_js_server_directory = '/home/martin/Documents/Programming/citeproc-js-server'

# define the item templates in citeproc mode
citeproc_item_templates = {'pdf': {
    'all_books': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'unedited_books': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'edited_books': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'all_peer_reviewed_articles': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'peer_reviewed_articles': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'other_articles': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'reviews': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'book_chapters': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>',
    'conference_items': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]]</span></p>'},

    'html': {
        'all_books': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'unedited_books': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'edited_books': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'all_peer_reviewed_articles': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'peer_reviewed_articles': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'other_articles': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'reviews': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'book_chapters': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'conference_items': '<p class="anitem genericitem"><span class="prefix">&nbsp;</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>'}
}

# define the item templates for new date lines in citeproc mode
citeproc_item_templates_new_date = {'pdf': {
    'all_books': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'unedited_books': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'edited_books': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'all_peer_reviewed_articles': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'peer_reviewed_articles': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'other_articles': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'reviews': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'book_chapters': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>',
    'conference_items': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]]</span></p>'},

    'html': {
        'all_books': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'unedited_books': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'edited_books': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'all_peer_reviewed_articles': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'peer_reviewed_articles': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'other_articles': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'reviews': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'book_chapters': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>',
        'conference_items': '<p class="anitemnewdate genericitem"><span class="prefix bold">[[year]]</span><span class="bibitem">[[citeproc]] [[oa_status]]</span></p>'}
}

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

# the fire-up address of the citeproc server
citeproc_server = 'http://127.0.0.1:{0}'

# citeproc startup delay
citeproc_delay = 7

# citeproc ports
citeproc_ports = ['8085', '8086', '8087', '8088', '8089', '8090', '8091', '8092', '8093', '8094', '8095', '8096']
