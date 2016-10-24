
# Writing Crowdsourced Poetry Using NLTK

Poetry is the art of putting words together to form thoughtful and provoking imagery. In the modern age, nobody has time for creative thought anymore -- so lets use technology to create poetry for us.

This tutorial will consist of three parts  

1. Prerequisites: We will walk through how to install the CMUDICT corpus from NLTK and go through some examples to familarize you with how to use the dictionary.
2. Poetry Library: We will build from scratch a poetry library that will interface a database to computationally build poetry base on rhyming schemes and syllable counts.
3. Application of Library: We will build a quick example to generate poetry from the subtitle files from a bunch of Marvel films

## Prerequisites

#### NLTK

We will be using NLTK, a python natural language processing tool kit. Specifically, we will be using one of NLTK's many
corpuses: CMU Pronunciation dictionary, a giant python-like dictionary that provides pronunciations of over 100,000 words developed here at CMU!

First, we will need to install the nltk python library, which you should already have if you have anaconda. From here, we will also need to download the CMU Dictionary corpus, which does not come preinstalled with NLTK. The NLTK downloader can be run through any python command line and will appear as a GUI for some operating systems, or some text-based GUI for others.


```python
import nltk, sqlite3, re, random
try:
    from nltk.corpus import cmudict
except:
    nltk.download("cmudict")
    from nltk.corpus import cmudict
```

Now, we can create a python dictionary and we can index into it with any particular word. We can see that typical english words including proper nouns exist in our dictionary, but capitalized words do not.

Our pronunciation dictionary maps words to an array of different possible pronunciations of the key word, where each pronunciation is an array of phonemes
represented by alphabetical characters and optionally a number from 0-2 to denote primary, secondary, or no stress for vowels. You can find more information about phonemes here: http://www.speech.cs.cmu.edu/cgi-bin/cmudict


```python
d = cmudict.dict()
words = ["hello", "world", "chris", "aint", "ain't", "pittsburgh", "Chris", "Hello", "0"]
for word in words:
    try:
        print "'" + word + "': " + str(d[word])
    except KeyError:
        print "'" + word + "'" + " does not exist"

```

    'hello': [[u'HH', u'AH0', u'L', u'OW1'], [u'HH', u'EH0', u'L', u'OW1']]
    'world': [[u'W', u'ER1', u'L', u'D']]
    'chris': [[u'K', u'R', u'IH1', u'S']]
    'aint' does not exist
    'ain't': [[u'EY1', u'N', u'T']]
    'pittsburgh': [[u'P', u'IH1', u'T', u'S', u'B', u'ER0', u'G']]
    'Chris' does not exist
    'Hello' does not exist
    '0' does not exist
    

#### Sqlite3
Typically, we would want to load data into memory so we have more freedom in manipulating it. However, in our case, for us quality will be achieved by quantity. With more data points we will get poems with more variety. Therefore, it is important to offload data because we cannot reasonably load large amounts of data to memory and expect to be able to parse it through it efficiently (especially in python \*rolls eyes\*). So in order to efficiently parse through our data, we need to take advantage of the many years of SQL optimizations and effectively transform our problem into a bunch of SQL queries.

In this library, we will be using SQLite3 due to its ease of entry. We can create databases represented as files, access those databases, insert, update, select etc. Here is a quick example of how to use the python sqlite3 library.


```python
conn = sqlite3.connect("tutorial.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT)")
cursor.execute('INSERT INTO users (firstName, lastName) VALUES (?,?)',["Chris","Wei"])
cursor.execute("SELECT * FROM users")
results = cursor.fetchall()
cursor.execute("DROP TABLE users")
conn.commit()

results
```




    [(1, u'Chris', u'Wei')]



## Poetry library

With NLTK's CMU Dictionary, we have all that we need to create a pretty decent poetry library that will let us create interesting poetry. Let us define a class called Line, which will represent a single line of text, Poem, that will represent a poem (a collection of lines), and a class called PoemFactory that will load/store the lines in a database, and create Poem instances given its resources.

### Line

Lets define the basis of our poems, the Line class. We will initialize an instance of Line by providing it some raw content that we will, for now, provide through an array of strings. The raw content will be parsed and verified through the static method verify_and_parse(), providing some diagnostic which will tell us what went wrong for each invalid line. If all is well, our verify_and_parse function will return a list of pronunciations for each word that it found in the input content.

From here, we need to collect two more pieces of information: the total syllable count, and the rhyme of that particular line. 

For syllable count, we simply count the number of phonemes that end with a numeric character.

For our rhyme, we need to generate a unique key that classifies the line into a particular rhyme catagory. If our key is too generic, we will get more matches but lower quality rhymes; if our key is too specific we won't get enough matches to make a poem.

For this implementation, we will be taking the last vowel and all proceding phonemes and concatenating them as a key.


```python
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
```

#### A) init function
To create a line, we must first pass it a variable `content` which is the raw string contents of that particular line. In this implementation, we first strip all `\n` characters so that we don't get any unsightly newlines in our poems. We then call `verify_and_parse` which will tell us if this line can be parsed in a meaningful way given our implementation. The return value of `verify_and_parse = (is_valid, parsed, diagnostics)` which tells us whether the Line is a valid line, the pronunciation of the line given as an array of array of phonemes (we arbitrarily take the first pronunciation from the dictionary), and the reason why the Line failed to be created.

Provided all went well in parsing the line, we need to count the number of syllables in our line. This is done by going through each of the phonemes and counting the number of phonemes that end with a integer, indicating a stress vowel.

`cmud["misdemeanor"] = [u'M', u'IH2', u'S', u'D', u'AH0', u'M', u'IY1', u'N', u'ER0', u'Z']
vowels = [u'IH2', u'AH0', u'IY1', u'ER0']
num_syllables = 4
`

Next, we need to extract some sort of rhyming information from the last word. We will go into more depth later on about this.

#### B) verify_and_parse
For each input, we should verify that each word in the input is a valid word (has an entry in our dictionary) and should then parse each word by converting each word into an arbitrary pronunciation of said word (this implementation simply chooses the first pronunciation)

#### C) extract_rhyme_phoneme
Given a pronunciation, this function will return a string that represents groupings a particular word. For example, ["word", "curd", "bird"] all belong in the same grouping since the last vowel to occur to the end of the word is "ER D". We will use this function to group rows in our sql table together when searching for rhymes.

### Poem

Now, we can create a simple Poem class that represents a poem, which intuitively is an ordered collection of Line instances, along with some metadata like author or title.


```python
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
```

### PoemFactory and populating our database

Now, lets create a PoemFactory that will create poems for us. All we need to do is feed the PoemFactory resources and tell it to spit out new poems for us. 


```python
class ResourceError(Exception):
    pass

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
        
    
```

### Initializing PoemFactory and populating with resources
#### A) init function & reset_database
Our init function simply creates or selects an existing database to store our instances of the Line class in. If the new flag is raised, we create a new database and call `reset_database` which essentially recreates the line table.
#### B) insert_many
This function simply takes in a list of strings that represent the raw data we want to convert into lines. For each line of raw data, we attempt to create an instance of Line to represent our raw data, and for each successful instance of Line created, we insert a SQL representation into our database.


```python
factory = PoemFactory("foo.db", True)
resources = ["Borgleborgleborgle!!!",
             "I drank Moet with Medusa, gave her shotguns in hell.",
             "  hello world",
             "From the split that I lift and inhale, it ain't hard to tell.",
             "<><>< !!!> <! hello !!!!!goodbye",
             "<<<<>>><<><>><{}{}{}{}"]
unsuccessful = factory.insert_many(resources)
for line in unsuccessful:
    print line.diagnostics
```

    No pronunciation found for word 'borgleborgleborgle'
    No words found
    


```python
c = factory.conn.cursor()
c.execute("SELECT * FROM line LIMIT 20")
c.fetchall()
```




    [(1, u'I drank Moet with Medusa, gave her shotguns in hell.', 14, u'EH L'),
     (2, u'hello world', 3, u'ER L D'),
     (3,
      u"From the split that I lift and inhale, it ain't hard to tell.",
      14,
      u'EH L'),
     (4, u'<><>< !!!> <! hello !!!!!goodbye', 4, u'AY')]



### Creating a poem

Now that we have populated our database with a couple dummy lines, we can try to create a poem.
#### C) new_poem
This part might be a bit confusing and rightly so since most of the logic is caked into this function. Up until this point, we have created classes to represent poem lines and poems and we've gone through and created a method of storing and accessing these lines. We have also done a little bit of analysis by extracting out rhyme phonemes that simplifies the process of generating a new poem.

First we need to understand the two inputs `pattern` and `syllable_ranges`. `pattern` is a string that represents the rhyme structure of our poem. For example, `"AABBAA"` corresponds to a poem with six lines, where line 1,2,5,6 rhyme and 3,4 rhyme. `syllable_ranges` provides a range of desired syllable counts for each rhyme group. Continuing our example, `syllable_ranges={"A":range(5,10),"B":[6,8]}` declares that every entry into group `"A"` must have 5-9 syllables and every entry into `"B"` must have either 6 or 8 syllables. This design is obviously fairly generalized and is slightly limited, you can redesign this function if you need line by line syllable granularity.

After calling `new_poem`, the input `pattern` and `syllable_ranges` are checked for consistency. We the count the number of lines we need per pattern domain. We now have two dictionaries that tell us for each pattern group the `requested_count` and `requested_syllable_range`.

Now, for each pattern group we query into our database to populate a mapping between each pattern group to a pool of resource groups. We do this by filtering out all lines that do not fall in the `requested_syllable_range` and then grouping the remaining lines by its rhyme column, so all words that rhyme with eachother are grouped together. We then filter out all the groups that do not have a count that satisfies `requested_count`; all the remaining groups are valid candidates for this particular pattern group and we simply select out the rhyme column and save it for later use. If a pattern group's resources cannot be fulfilled, a `ResourceError` will be raised, which the user of our library can handle themselves.

From here, we randomly select a rhyme group for each pattern group, and for each line within a pattern group, we randomly select a unique line from the assigned rhyme group. We then populate a Poem instance with the selected lines and we have ourselves a poem!


```python
try:
    poem = factory.new_poem(pattern="AA", syllable_ranges={"A": xrange(13,15)})
    print poem
except ValueError as e:
    print "Error: " + str(e)
except ResourceError as e:
    print "Not enough resources: " + str(e)
```

    Untitled
    ________
    
    I drank Moet with Medusa, gave her shotguns in hell.
    From the split that I lift and inhale, it ain't hard to tell.
    ________
    
    -- Anonymous
    

## Using our poetry library

Now that we have established our poetry library, we can now use our PoemFactory to save text from various sources and generate poetry! But first, lets look at some common poem structures and see how we can express them as a call to PoemFactory.new_poem().

#### Triplet 
`PoemFactory.new_poem("AAA", {"A":[7,8,9]})`  
*Shall we go dance the hay, the hay?  
Never pipe could ever play  
Better shepherd’s roundelay.*
#### Limmerick
`PoemFactory.new_poem("AABBA", {"A":[7,8], "B":[7,8]})`  
*There was an Old Man with a beard  
Who said, 'It is just as I feared!  
Two Owls and a Hen,  
Four Larks and a Wren,  
Have all built their nests in my beard!'*
#### Haiku
`PoemFactory.new_poem("ABC", {"A":[5], "B":[7], "C":[5]})`  
*Light of the moon  
Moves west, flowers' shadows  
Creep eastward.*

### Example: Limmericks from Marvel Movies

As an example, we will be using the scripts from all Marvel Movies as our datasource, and we will use our poem library to automatically generate limmericks.

This example requires `pysrt` which can be easily installed through `pip install pysrt` as we will be using .SRT subtitle files which will naturally split the scripts from the movies into reasonable chunks.


```python
import pysrt, glob
```


```python
marvel_poem_factory = PoemFactory("marvel.db", True)
# load all the srt files
lines = []
for filename in glob.glob('marvel_subtitles/*.srt'):
    subs = pysrt.open(filename, encoding='iso-8859-1')
    lines += [sub.text for sub in subs]
unsuccessful = marvel_poem_factory.insert_many(lines)
print str(len(unsuccessful)) + "/" + str(len(lines)) + " failed to parse"
```

    2708/37935 failed to parse
    

Since rhyming a word with itself is a lame excuse for a poem, we will do a simple cute hack to increase the number of nice poems we have checking for repeated words.


```python
def good_poem(factory, pattern, syllables, title, author, retry=5):
    poem = None
    for i in xrange(retry):
        poem = factory.new_poem(pattern, syllables, title, author)
        last_words = [line.words[-1] for line in poem.lines]
        if len(last_words) == len(set(last_words)):
            return poem
    return poem 
```


```python
print good_poem(marvel_poem_factory, "AABBA", {"A":[7,8], "B":[7,8]}, "A Marvel Limmerick", "Chris")
```

    A Marvel Limmerick
    __________________
    
    Should've brought my roller blades.
    He wants flowers, he wants parades.
    - Hubble. - Hubble Telescope.
    - You don't give up, do you? - Nope!
    Keep moving! Grab those grenades!
    __________________
    
    -- Chris
    

### Remarks

Something that you can see happening is that a lot of times you'll get the same word rhyming to the same word, which in my honest opinion is just bad poetry. Some improvements we can make to this library is upgrading the resource management so we don't see the same word over and over again. The rhyming scheme is not super accurate but works for most cases. We should also make bookkeeping easier so that you can store other metadata about each line you insert into so you can do stuff like this: https://vimeo.com/165395316 you can check out the code for this here https://github.com/chrisjwei/iacd-final which does not support poem structures, but has a much more developed rhyming algorithm and does everything in memory (SHAMELESS PLUG).

Here is a really nice one that really capture the essence of marvel movies

*It's just a metaphor, dude.  
Big and green and buck-ass nude.  
It's very hard to get hold of.  
Even from the people they love.  
I thought you'd be in a good mood.*


```python

```
