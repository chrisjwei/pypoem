import nltk, sqlite3, re, random
from nltk.corpus import cmudict

class ResourceError(Exception):
    pass

class Line(object):
    '''
        content: string - The source content for this line
        is_valid: bool - Whether this line is valid
        words: List<string> - The words found in the content
        parsed: List<List<string>> - The parsed pronuncation of this line
        diagnostics: string - Why the line failed to parse ("Success" otherwise)
    '''
    
    regex = re.compile("[a-z]+(?:'[a-z]+)?")
    pdict = cmudict.dict()
    
    @staticmethod
    def verify_and_parse(content):
        '''
            Given a string, finds all the words in the string and verifies each word has a pronunciation in CMUDICT
            args:
                content: string
            returns:
                (is_valid: bool, words: List<string>, pronunciations: List<List<string>>, status: string) 
        '''
        # find all words in content
        words = Line.regex.findall(content.lower())
        if (len(words) == 0):
            return (False, [], None, "No words found")
        for word in words:
            if not(word in Line.pdict):
                return (False, words, None, "No pronunciation found for word '" + word + "'")
        return (True, words, [Line.pdict[word][0] for word in words], "Valid")
    
    @staticmethod
    def extract_rhyme_phoneme(pron):
        '''
            Given a pronuncation, returns a unique key that maps to all pronunciations that rhyme with the given
            pronuncation.
            args:
                pron: List<string>
            returns:
                key: string
        '''
        # find all the vowels and their indices
        vowels = [(i,vow) for (i,vow) in enumerate(pron) if vow[-1].isnumeric()]
        # if no vowels present, take the whole pronuncation
        if (len(vowels) == 0):
            return reduce(lambda x,y: x+y, pron)
        # take the last vowel and return the concatenation of the vowel
        # and all phonemes occuring after it seperated by spaces
        # removing the stress indicator on the vowel
        (i,_) = max(vowels, key=lambda x: x[0])
        return reduce(lambda x,y: x + " " + y, [pron[i][:-1]] + pron[i+1:])
        
    
    def __init__(self, content):
        self.content = content.strip().replace('\n', ' ')
        (self.is_valid, self.words, self.parsed, self.diagnostics) = Line.verify_and_parse(self.content)
        if (self.is_valid):
            self.syllable_count = sum([len([syl for syl in pron if syl[-1].isnumeric()]) for pron in self.parsed])
            last_pron = self.parsed[-1]
            self.rhyme = Line.extract_rhyme_phoneme(last_pron)
    
    def to_sql_params(self):
        return (self.content, self.syllable_count, self.rhyme,)        

class Poem(object):
    
    def __init__(self, lines, title, author):
        '''
            Creates a new poem
            args:
                lines: list<Line>
                title: string
                author: string
        '''
        self.title = title
        self.lines = lines
        self.author = author
    
    def __str__(self):
        '''
            Override default string converter
        '''
        line_string = reduce(lambda x,y: x + y, map(lambda line: line.content + "\n", self.lines))
        author_string = "-- " + self.author
        title_string = self.title + '\n'
        sep_string = len(self.title)*"_" + '\n\n'
        return title_string + sep_string + line_string + sep_string + author_string

class PoemFactory(object):
    def __init__(self, database_path, new=False):
        '''
            Initializes a new PoemFactory
            args:
                database_path: string
                new: bool
        '''
        self.conn = sqlite3.connect(database_path)
        if (new):
            self.reset_database()
        
    def reset_database(self):
        '''
            Resets the current database
        '''
        c = self.conn.cursor()
        c.execute('''DROP TABLE IF EXISTS line;''')
        c.execute('''CREATE TABLE line (id INTEGER PRIMARY KEY,
                                        raw_text TEXT NOT NULL,
                                        syllable_count INTEGER NOT NULL,
                                        rhyme TEXT);''')
        self.conn.commit()
    
    def insert_many(self, resources):
        '''
            Updates the current database with new resources
            args:
                resources: list<string>
            returns:
                num_failed: int
        '''
        n = 0
        new_lines = []
        unsuccessful_lines= []
        for resource in resources:
            line = Line(resource)
            if not(line.is_valid):
                unsuccessful_lines.append(line)
            else:
                new_lines.append(line)
        # insert many into our database
        c = self.conn.cursor()
        c.executemany('''INSERT INTO line (raw_text, syllable_count, rhyme) VALUES (?,?,?)''',
                      [line.to_sql_params() for line in new_lines])
        self.conn.commit()
        return unsuccessful_lines
    
    def new_poem(self, pattern, syllable_ranges, title="Untitled", author="Anonymous"):
        '''
            Creates a new poem using the current database following certain constraints
            args:
                pattern: string
                syllable_ranges: dict<string,list<int>>
            returns:
                poem: Poem
        '''
        # Check for invalid inputs
        if (len(pattern) == 0):
            raise ValueError("Empty pattern")
            
        # Check for valid syllable ranges
        pattern_domain = set(pattern)
        for p in pattern_domain:
            if not(p in syllable_ranges):
                raise ValueError("Pattern " + p + " does not exist in syllable_ranges")
            if len(syllable_ranges[p]) == 0:
                raise ValueError("Empty syllable_ranges entry for " + p)
        
        # Count the number of lines per pattern category
        pattern_counts = dict.fromkeys(pattern_domain, 0)
        for p in pattern:
            pattern_counts[p] += 1
        
        # Attempt to find lines for each pattern category
        c = self.conn.cursor()
        
        # Assign possible resources for each pattern group
        possible_resources = {}
        for p in pattern_domain:
            requested_count = pattern_counts[p]
            requested_syllable_range = syllable_ranges[p]
            # group 
            c.execute('''
                SELECT rhyme FROM
                    (SELECT l.rhyme, count(id) as num_resources
                     FROM line l
                     WHERE l.syllable_count in (%s)
                     GROUP BY l.rhyme)
                WHERE num_resources >= (?)
                ''' % ','.join('?'*len(requested_syllable_range)),
                      list(requested_syllable_range) + [requested_count])
            results = c.fetchall() # results: list[(string)]
            if not(results):
                raise ResourceError(p)
            possible_resources[p] = [result[0] for result in results]

        # Now that each pattern group has a set of resources that can fill its requirements
        # we need to assign each resource to each pattern. If we want to eliminate collisions
        # we will have to do some smart assigning here, but since this is just a tutorial
        # and I'm lazy AF lets just assume our db is large enough that collisions are very unlikely
        assigned_resources = {}
        for p in pattern_domain:
            # we will introduce randomness here so we don't get same poem over and over again
            resource_group = random.choice(possible_resources[p])
            requested_count = pattern_counts[p]
            requested_syllable_range = syllable_ranges[p]
            c.execute('''
                SELECT raw_text
                FROM line l
                WHERE l.syllable_count in (%s) AND l.rhyme = (?)
                ORDER BY RANDOM()
                LIMIT (?)
            ''' % ','.join('?'*len(requested_syllable_range)),
                      list(requested_syllable_range) + [resource_group, requested_count])
            assigned_resources[p] = [line[0] for line in c.fetchall()]
        
        lines = []
        for p in pattern:
            lines.append(Line(assigned_resources[p].pop()))
        
        return Poem(lines, title, author)