from flask import Flask, request, jsonify
import pdfplumber
import spacy
import re
from spacy.lang.en.stop_words import STOP_WORDS
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains on all routes

nlp = spacy.load("en_core_web_md")  # Load spaCy language model

def download_file(url):
    local_filename = "temp.pdf"
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

def load_pdf_text(url):
    filename = download_file(url)
    text = ''
    with pdfplumber.open(filename) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'
    os.remove(filename)  # Clean up the downloaded file
    return text


# Usage
pdf_url = "https://drive.google.com/uc?export=download&id=1Bj1ncGyE_G5C_tukXrrShWEVVyInoMgP"
pdf_text = load_pdf_text(pdf_url)

def extract_keywords(query):
    doc = nlp(query)
    keywords = set()

    # Extract named entities, prioritize PROPN if it's part of a longer noun chunk
    for ent in doc.ents:
        keywords.add(ent.text)

    # Extract noun chunks and filter out stop words and common query terms
    for chunk in doc.noun_chunks:
        # Exclude chunks that are likely common phrases in queries
        if not any(token.lemma_ in ['who', 'where', 'which', 'what', 'when'] for token in chunk):
            keywords.add(chunk.text)

    return ' '.join(keywords)


def search_text(query):
    keywords = query.split()
    results = []
    for line in pdf_text.split('\n'):
        if all(keyword.lower() in line.lower() for keyword in keywords):
            results.append(line)
    return results


def extract_query_intent(doc):
    # Example of rule-based approach to identify common query intents
    root = [token for token in doc if token.head == token][0]
    subj = [w for w in root.lefts if w.dep_ in ("nsubj", "nsubjpass")]  # subject
    dobj = [w for w in root.rights if w.dep_ == "dobj"]  # direct object

    person = next((w for w in doc if w.ent_type_ == "PERSON"), None)
    location = next((w for w in doc if w.ent_type_ == "GPE"), None)

    # Use these to determine the focus of the query
    if person:
        return str(person)
    elif subj or dobj:
        return ' '.join([w.text for w in subj + dobj])
    return None


@app.route('/search', methods=['POST'])
def handle_query():
    query = request.json.get('query')
    print(f"Received query: {query}")  # Check what query is received

    keywords = extract_keywords(query)
    print(f"Extracted keywords: {keywords}")  # Verify what keywords are extracted

    results = search_text(keywords)
    print(f"Search results: {len(results)} results found.")  # Check how many results are returned
    """ Handle search queries, extract keywords, and search the PDF text. """

    query = request.json.get('query')
    keywords = extract_keywords(query)
    if not keywords:  # Handle the case where no significant keywords are extracted
        return jsonify(
            {"results": [], "disclaimer": "No significant terms found in your query. Please refine your query."})

    results = search_text(keywords)
    if len(results) == 0:
        disclaimer = f"No results found based on your query: '{query}'. It does not exist."
    elif len(results) == 1:
        disclaimer = "This is the current updated posting of the officer as on 22nd April 2024."
    else:
        disclaimer = "These are the current updated postings of officers as on 22nd April 2024."

    return jsonify({"results": results, "disclaimer": disclaimer})


@app.route('/')
def home():
    """ Default home route to check if the app is running. """
    return "Hello, Welcome to IAS directory Search!"


if __name__ == '__main__':
    from waitress import serve

    serve(app, host='0.0.0.0', port=8080)
