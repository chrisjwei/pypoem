import pysrt, glob, pypoem

marvel_poem_factory = pypoem.PoemFactory("marvel.db", True)
# load all the srt files
lines = []
for filename in glob.glob('marvel_subtitles/*.srt'):
    subs = pysrt.open(filename, encoding='iso-8859-1')
    lines += [sub.text for sub in subs]
unsuccessful = marvel_poem_factory.insert_many(lines)
print str(len(unsuccessful)) + "/" + str(len(lines)) + " failed to parse"


# Since rhyming a word with itself is a lame excuse for a poem, we will do a
# simple cute hack to increase the number of nice poems we have checking for
# repeated words.

def good_poem(factory, pattern, syllables, title, author, retry=5):
    poem = None
    for i in xrange(retry):
        poem = factory.new_poem(pattern, syllables, title, author)
        last_words = [line.words[-1] for line in poem.lines]
        if len(last_words) == len(set(last_words)):
            return poem
    return poem

print good_poem(marvel_poem_factory, "AABBA", {"A":[7,8], "B":[7,8]}, "A Marvel Limmerick", "Chris")