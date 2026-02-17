from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage
from db_setup import get_connection
import json
import os
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
    temperature=0,
    api_key=os.getenv('OPENAI_API_KEY')
)

def extract_fair_metadata(pdf_text):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Extract FAIR-compliant metadata from physics research paper. Return JSON with:
- doi: Digital Object Identifier
- title: Paper title
- authors: List of author names with affiliations
- abstract: Abstract text
- keywords: List of keywords
- publication_date: Publication date (YYYY-MM-DD)
- journal: Journal name
- license: License type
- repository_url: Data/code repository URL if mentioned
- data_availability: Data availability statement
- methodology: Brief methodology description
- citation_info: Citation format
- controlled_vocabularies: Subject classifications, PACS codes
- metadata_schema: Schema used (e.g., Dublin Core, DataCite)"""),
        ("human", "Extract metadata from:\n\n{pdf_text}")
    ])
    
    messages = prompt.format_messages(pdf_text=pdf_text[:8000])
    response = llm.invoke(messages)
    
    try:
        return json.loads(response.content)
    except:
        return {}

def store_fair_metadata(filename, fair_data):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO fair_metadata (
            filename, doi, title, authors, abstract, keywords, publication_date,
            journal, license, repository_url, data_availability, methodology,
            citation_info, controlled_vocabularies, metadata_schema
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (filename) 
        DO UPDATE SET
            doi = EXCLUDED.doi,
            title = EXCLUDED.title,
            authors = EXCLUDED.authors,
            abstract = EXCLUDED.abstract,
            keywords = EXCLUDED.keywords,
            publication_date = EXCLUDED.publication_date,
            journal = EXCLUDED.journal,
            license = EXCLUDED.license,
            repository_url = EXCLUDED.repository_url,
            data_availability = EXCLUDED.data_availability,
            methodology = EXCLUDED.methodology,
            citation_info = EXCLUDED.citation_info,
            controlled_vocabularies = EXCLUDED.controlled_vocabularies,
            metadata_schema = EXCLUDED.metadata_schema,
            updated_at = CURRENT_TIMESTAMP
    """, (
        filename,
        fair_data.get('doi'),
        fair_data.get('title'),
        json.dumps(fair_data.get('authors', [])),
        fair_data.get('abstract'),
        fair_data.get('keywords', []),
        fair_data.get('publication_date'),
        fair_data.get('journal'),
        fair_data.get('license'),
        fair_data.get('repository_url'),
        fair_data.get('data_availability'),
        fair_data.get('methodology'),
        json.dumps(fair_data.get('citation_info', {})),
        json.dumps(fair_data.get('controlled_vocabularies', {})),
        fair_data.get('metadata_schema', 'DataCite')
    ))
    
    conn.commit()
    conn.close()
