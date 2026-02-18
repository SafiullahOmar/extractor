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
        ("system", """Extract full DataCite-compliant FAIR metadata from physics research paper. Return JSON with:
- doi: Digital Object Identifier (if present)
- handle: Handle identifier (if present)
- ark: ARK identifier (if present)
- title: Paper title
- authors: List of author objects with name, affiliation, orcid
- abstract: Abstract text
- keywords: List of keywords
- publication_date: Publication date (YYYY-MM-DD)
- journal: Journal name with ISSN
- license: License type (CC-BY, etc.)
- repository_url: Data/code repository URL
- data_availability: Data availability statement
- methodology: Brief methodology description
- citation_info: Citation format
- pacs_codes: Physics and Astronomy Classification Scheme codes
- mesh_terms: Medical Subject Headings terms (if applicable)
- subject_classifications: Subject area classifications
- datacite_schema: Full DataCite 4.4 schema fields (resourceType, publisher, language, etc.)
- metadata_schema: Schema used (DataCite)"""),
        ("human", "Extract comprehensive metadata from:\n\n{pdf_text}")
    ])
    
    messages = prompt.format_messages(pdf_text=pdf_text[:8000])
    response = llm.invoke(messages)
    
    try:
        return json.loads(response.content)
    except:
        return {}

def log_provenance(filename, action, agent, input_data=None, output_data=None, metadata=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO provenance (filename, action, agent, input_data, output_data, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (filename, action, agent, json.dumps(input_data), json.dumps(output_data), json.dumps(metadata)))
    conn.commit()
    conn.close()

def store_fair_metadata(filename, fair_data, provenance_info=None):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO fair_metadata (
            filename, doi, handle, ark, title, authors, abstract, keywords, publication_date,
            journal, license, repository_url, data_availability, methodology,
            citation_info, pacs_codes, mesh_terms, subject_classifications,
            metadata_schema, datacite_schema, provenance_chain
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (filename) 
        DO UPDATE SET
            doi = EXCLUDED.doi,
            handle = EXCLUDED.handle,
            ark = EXCLUDED.ark,
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
            pacs_codes = EXCLUDED.pacs_codes,
            mesh_terms = EXCLUDED.mesh_terms,
            subject_classifications = EXCLUDED.subject_classifications,
            datacite_schema = EXCLUDED.datacite_schema,
            provenance_chain = EXCLUDED.provenance_chain,
            updated_at = CURRENT_TIMESTAMP
    """, (
        filename,
        fair_data.get('doi'),
        fair_data.get('handle'),
        fair_data.get('ark'),
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
        fair_data.get('pacs_codes', []),
        fair_data.get('mesh_terms', []),
        json.dumps(fair_data.get('subject_classifications', {})),
        fair_data.get('metadata_schema', 'DataCite'),
        json.dumps(fair_data.get('datacite_schema', {})),
        json.dumps(provenance_info or [])
    ))
    
    conn.commit()
    conn.close()
    
    if provenance_info:
        log_provenance(filename, "store_metadata", "fair_extractor", 
                      input_data=fair_data, output_data={"status": "stored"})