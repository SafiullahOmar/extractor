from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from db_setup import get_connection
from fair_extractor import log_provenance
import json
import os
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
    temperature=0,
    api_key=os.getenv('OPENAI_API_KEY')
)

def validate_metadata(fair_data):
    print(f"[CURATION] validate_metadata called", flush=True)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Validate FAIR metadata for completeness and correctness. Return JSON with:
- is_valid: boolean
- missing_fields: list of required missing fields
- errors: list of validation errors
- warnings: list of warnings
- completeness_score: float 0-1"""),
        ("human", "Validate metadata:\n\n{metadata}")
    ])
    
    messages = prompt.format_messages(metadata=json.dumps(fair_data, indent=2))
    response = llm.invoke(messages)
    
    try:
        return json.loads(response.content)
    except:
        return {"is_valid": False, "errors": ["Validation failed"]}

def enrich_metadata(fair_data, pdf_text):
    print(f"[CURATION] enrich_metadata called text_len={len(pdf_text)}", flush=True)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Enrich FAIR metadata by extracting additional information. Return JSON with enriched fields:
- Add missing PACS codes if physics paper
- Add missing MeSH terms if applicable
- Enhance abstract if incomplete
- Add related identifiers
- Suggest improvements"""),
        ("human", "Enrich metadata:\n\n{metadata}\n\nFrom text:\n\n{text}")
    ])
    
    messages = prompt.format_messages(
        metadata=json.dumps(fair_data, indent=2),
        text=pdf_text[:4000]
    )
    response = llm.invoke(messages)
    
    try:
        enriched = json.loads(response.content)
        return {**fair_data, **enriched}
    except:
        return fair_data

def assess_quality(fair_data):
    print(f"[CURATION] assess_quality called", flush=True)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Assess quality of FAIR metadata. Return JSON with:
- quality_score: float 0-1
- fair_compliance: object with findable, accessible, interoperable, reusable scores
- recommendations: list of improvement recommendations"""),
        ("human", "Assess quality:\n\n{metadata}")
    ])
    
    messages = prompt.format_messages(metadata=json.dumps(fair_data, indent=2))
    response = llm.invoke(messages)
    
    try:
        return json.loads(response.content)
    except:
        return {"quality_score": 0.5, "fair_compliance": {}}

def resolve_conflicts(fair_data, existing_data):
    print(f"[CURATION] resolve_conflicts called", flush=True)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Resolve conflicts between new and existing metadata. Return JSON with:
- resolved_data: merged and resolved metadata
- conflicts: list of conflicts found
- resolution_strategy: how conflicts were resolved"""),
        ("human", "Resolve conflicts:\n\nNew: {new}\n\nExisting: {existing}")
    ])
    
    messages = prompt.format_messages(
        new=json.dumps(fair_data, indent=2),
        existing=json.dumps(existing_data, indent=2)
    )
    response = llm.invoke(messages)
    
    try:
        return json.loads(response.content)
    except:
        return {"resolved_data": fair_data, "conflicts": []}

def update_curation_status(filename, status, quality_score=None, validation_status=None):
    print(f"[CURATION] update_curation_status file={filename} status={status} quality_score={quality_score} validation_status={validation_status}", flush=True)
    conn = get_connection()
    cur = conn.cursor()

    update_fields = ["curation_status = %s"]
    values = [status]
    
    if quality_score is not None:
        update_fields.append("quality_score = %s")
        values.append(quality_score)
    
    if validation_status:
        update_fields.append("validation_status = %s")
        values.append(validation_status)
    
    values.append(filename)
    
    cur.execute(f"""
        UPDATE fair_metadata 
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE filename = %s
    """, values)
    
    conn.commit()
    conn.close()
