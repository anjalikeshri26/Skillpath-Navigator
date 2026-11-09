# Design decisions

Short records of choices that are not obvious from the code, with the alternative that was rejected.

## Quiz sessions live on the server
A test is a stored session listing which questions were served and in what option order. Grading maps the selected
position back to the original option on the server. The first version let the client send question ids and option
indexes, which allowed duplicate answers, answers to questions never served, and a client-controlled timer.
*Cost:* two extra tables and one extra request per test.

## Mastery is a Beta belief per topic
Each answer updates Beta(α, β); hard-correct and easy-wrong carry more weight; evidence decays with a ~46 day half-life.
A running percentage correct treats an easy question like a hard one and never forgets. *Rejected:* full item-response
theory, which needs calibrated item parameters we do not have yet. `times_correct / times_answered` is stored per
question so calibration is possible later.

## AI questions need an independent second opinion
Generation, near-duplicate rejection, then a separate call that solves the question without seeing the key. Only
agreement is stored. This costs roughly twice the tokens and discards some good questions; a wrong answer key shown to a
learner costs more.

## Retrieval is TF-IDF
Groq has no embeddings endpoint and the catalogue is ~35 documents. `TfidfIndex` exposes `search` and `nearest` only,
so a sentence-embedding model with pgvector can replace it later. Recall on the starter cases is not evidence of quality
(see README).

## Notes use optimistic concurrency
Every note has a `revision`; an update must send the revision it loaded, and a mismatch returns 409. Without this, two
open tabs silently overwrite each other. Title uniqueness is enforced per user by a database constraint on a case-folded
key, not only by a pre-check, so a race cannot create duplicates. `excerpt` and `word_count` are stored on write so the
list view never loads note bodies.

## Study generation is a draft, not a record
`/api/study/generate` stores nothing. The learner reviews and edits the text, then saves it as a note, so the library
holds only notes someone chose to keep. Generation is limited to 8 per 10 minutes per user because it is the most
expensive call. A response cut off by the token limit is flagged to the learner rather than saved silently.

## Markdown is rendered by a small in-repo module
Notes are rendered by `frontend/js/core/markdown.js`: input is HTML-escaped first, markup is generated only by that
file, links are limited to http(s), and images and raw HTML are shown as text. A library would support more syntax, but it
would add a dependency (or a CDN script) to code that handles user-written text. The renderer has tests for
script/attribute injection. *Gaps:* no images, footnotes or nested blockquotes.
