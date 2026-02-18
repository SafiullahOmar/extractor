from langgraph.graph import StateGraph, END
from typing import TypedDict
from pdf_extractor import extract_text
from fair_extractor import extract_fair_metadata, store_fair_metadata, log_provenance
from curation_agents import update_curation_status
from react_agents import create_metadata_extraction_agent, create_curation_agent, create_quality_agent
from process_pdf import process_pdf
from db_setup import get_connection
from datetime import datetime
import os
import json

def extract_metadata_from_result(result, default=None):
    """Helper to extract metadata from agent result consistently"""
    if default is None:
        default = {}
    
    if "metadata" in result and isinstance(result["metadata"], dict):
        return result["metadata"]
    
    if "last_result" in result:
        last_result = result["last_result"]
        if isinstance(last_result, dict):
            if "metadata" in last_result:
                return last_result["metadata"]
            if "conflict_resolution" in last_result:
                return last_result["conflict_resolution"].get("resolved_data", default)
            return last_result
    
    return default

def extract_quality_from_result(result, default=None):
    """Helper to extract quality assessment from agent result"""
    if default is None:
        default = {}
    
    if "quality_assessment" in result:
        return result["quality_assessment"]
    
    if "last_result" in result:
        last_result = result["last_result"]
        if isinstance(last_result, dict):
            if "quality_assessment" in last_result:
                return last_result["quality_assessment"]
            return last_result
    
    return default

def extract_validation_from_result(result, default=None):
    """Helper to extract validation result from agent result"""
    if default is None:
        default = {}
    
    if "validation_result" in result:
        return result["validation_result"]
    
    if "last_result" in result:
        last_result = result["last_result"]
        if isinstance(last_result, dict):
            if "validation_result" in last_result:
                return last_result["validation_result"]
    
    return default

def chunk_text(text, max_chunk=8000, overlap=200):
    """Split text into chunks with overlap for better context"""
    if len(text) <= max_chunk:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    
    return chunks

class WorkflowState(TypedDict):
    pdf_path: str
    filename: str
    extracted_text: str
    fair_metadata: dict
    validation_result: dict
    enrichment_result: dict
    quality_assessment: dict
    conflict_resolution: dict
    provenance_chain: list
    processing_status: str

def _log(step: str, msg: str, **kwargs):
    """Print workflow/agent output to terminal for live logs."""
    extra = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    print(f"[WORKFLOW] {step} | {msg} {extra}".strip(), flush=True)

def extract_pdf_text(state: WorkflowState) -> WorkflowState:
    _log("extract_text", "Starting PDF text extraction", file=state["filename"])
    try:
        texts = extract_text(state["pdf_path"])
        full_text = "\n\n".join([item['text'] for item in texts])
        state["extracted_text"] = full_text
        state["provenance_chain"] = state.get("provenance_chain", [])
        state["provenance_chain"].append({
            "action": "extract_text",
            "agent": "pdf_extractor",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "success"
        })
        log_provenance(state["filename"], "extract_text", "pdf_extractor", 
                      output_data={"text_length": len(full_text)})
        _log("extract_text", "Done", chars=len(full_text), items=len(texts))
    except Exception as e:
        _log("extract_text", "Error", error=str(e))
        state["provenance_chain"].append({
            "action": "extract_text",
            "agent": "pdf_extractor",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(e)
        })
        log_provenance(state["filename"], "extract_text_error", "pdf_extractor",
                      input_data={"error": str(e)})
        raise
    return state

def extract_fair_react(state: WorkflowState) -> WorkflowState:
    _log("extract_fair_react", "Starting metadata extraction agent", file=state["filename"])
    try:
        agent = create_metadata_extraction_agent()
        
        text_chunks = chunk_text(state["extracted_text"], max_chunk=8000)
        primary_text = text_chunks[0]
        if len(text_chunks) > 1:
            primary_text += "\n\n[Additional pages available but truncated for initial extraction]"
        
        observation = {
            "text": primary_text,
            "metadata": {}
        }
        
        result = agent.run(observation, max_iterations=6)
        
        state["fair_metadata"] = extract_metadata_from_result(result, {})
        _log("extract_fair_react", "Done", iterations=len(result.get("iterations", [])), keys=list(state["fair_metadata"].keys())[:8])
        state["provenance_chain"].append({
            "action": "extract_fair_react",
            "agent": "metadata_extraction_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "iterations": result.get("iterations", []),
            "final_thought": result.get("final_thought", ""),
            "status": "success"
        })
        log_provenance(state["filename"], "extract_fair_react", "metadata_extraction_agent",
                      input_data={"text_length": len(state["extracted_text"]), "chunks": len(text_chunks)},
                      output_data=state["fair_metadata"])
    except Exception as e:
        _log("extract_fair_react", "Error, using fallback", error=str(e))
        state["provenance_chain"].append({
            "action": "extract_fair_react",
            "agent": "metadata_extraction_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(e)
        })
        log_provenance(state["filename"], "extract_fair_react_error", "metadata_extraction_agent",
                      input_data={"error": str(e)})
        state["fair_metadata"] = extract_fair_metadata(state["extracted_text"][:8000])
        log_provenance(state["filename"], "extract_fair_fallback", "fair_extractor",
                      output_data=state["fair_metadata"])
    return state

def curate_react(state: WorkflowState) -> WorkflowState:
    _log("curate_react", "Starting curation agent", file=state["filename"])
    try:
        agent = create_curation_agent()
        
        text_chunks = chunk_text(state["extracted_text"], max_chunk=4000)
        observation = {
            "metadata": state["fair_metadata"],
            "text": text_chunks[0] if text_chunks else "",
            "quality_score": 0
        }
        
        result = agent.run(observation, max_iterations=10)
        
        extracted_metadata = extract_metadata_from_result(result, state["fair_metadata"])
        if extracted_metadata:
            state["fair_metadata"].update(extracted_metadata)
        
        state["quality_assessment"] = extract_quality_from_result(result, {})
        state["validation_result"] = extract_validation_from_result(result, {})
        
        state["provenance_chain"].append({
            "action": "curate_react",
            "agent": "curation_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "iterations": result.get("iterations", []),
            "final_thought": result.get("final_thought", ""),
            "final_quality": state["quality_assessment"].get("quality_score", 0) if isinstance(state.get("quality_assessment"), dict) else 0,
            "status": "success"
        })
        
        quality_score = state["quality_assessment"].get("quality_score", 0) if isinstance(state.get("quality_assessment"), dict) else 0
        update_curation_status(state["filename"], "curated",
                              quality_score=quality_score)
        _log("curate_react", "Done", iterations=len(result.get("iterations", [])), quality_score=quality_score)
        log_provenance(state["filename"], "curate_react", "curation_agent",
                      input_data=observation,
                      output_data=result)
    except Exception as e:
        _log("curate_react", "Error", error=str(e))
        state["provenance_chain"].append({
            "action": "curate_react",
            "agent": "curation_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(e)
        })
        log_provenance(state["filename"], "curate_react_error", "curation_agent",
                      input_data={"error": str(e)})
        state["quality_assessment"] = state.get("quality_assessment", {})
    return state

def quality_assurance_react(state: WorkflowState) -> WorkflowState:
    _log("quality_assurance_react", "Starting quality assurance agent", file=state["filename"])
    try:
        agent = create_quality_agent()
        
        text_chunks = chunk_text(state["extracted_text"], max_chunk=4000)
        observation = {
            "metadata": state["fair_metadata"],
            "text": text_chunks[0] if text_chunks else "",
            "current_quality": state.get("quality_assessment", {}).get("quality_score", 0) if isinstance(state.get("quality_assessment"), dict) else 0
        }
        
        result = agent.run(observation, max_iterations=8)
        
        extracted_quality = extract_quality_from_result(result, state.get("quality_assessment", {}))
        if extracted_quality:
            state["quality_assessment"] = extracted_quality
        
        extracted_metadata = extract_metadata_from_result(result, {})
        if extracted_metadata:
            state["fair_metadata"].update(extracted_metadata)
        
        state["provenance_chain"].append({
            "action": "quality_assurance_react",
            "agent": "quality_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "iterations": result.get("iterations", []),
            "final_thought": result.get("final_thought", ""),
            "final_quality": state["quality_assessment"].get("quality_score", 0) if isinstance(state.get("quality_assessment"), dict) else 0,
            "status": "success"
        })
        
        quality_score = state["quality_assessment"].get("quality_score", 0) if isinstance(state.get("quality_assessment"), dict) else 0
        update_curation_status(state["filename"], "quality_assured",
                              quality_score=quality_score)
        _log("quality_assurance_react", "Done", iterations=len(result.get("iterations", [])), quality_score=quality_score)
        log_provenance(state["filename"], "quality_assurance_react", "quality_agent",
                      input_data=observation,
                      output_data=result)
    except Exception as e:
        _log("quality_assurance_react", "Error", error=str(e))
        state["provenance_chain"].append({
            "action": "quality_assurance_react",
            "agent": "quality_agent",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(e)
        })
        log_provenance(state["filename"], "quality_assurance_react_error", "quality_agent",
                      input_data={"error": str(e)})
        state["quality_assessment"] = state.get("quality_assessment", {})
    return state

def store_content(state: WorkflowState) -> WorkflowState:
    _log("store_content", "Storing content and vectors", file=state["filename"])
    try:
        process_pdf(state["pdf_path"], skip_fair=True, fair_metadata=state["fair_metadata"])
        _log("store_content", "Done")
        state["provenance_chain"].append({
            "action": "store_content",
            "agent": "content_storage",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "success"
        })
        log_provenance(state["filename"], "store_content", "content_storage",
                      output_data={"status": "stored"})
    except Exception as e:
        _log("store_content", "Error", error=str(e))
        state["provenance_chain"].append({
            "action": "store_content",
            "agent": "content_storage",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(e)
        })
        log_provenance(state["filename"], "store_content_error", "content_storage",
                      input_data={"error": str(e)})
        raise
    return state

def store_fair(state: WorkflowState) -> WorkflowState:
    _log("store_fair", "Storing FAIR metadata and finalizing", file=state["filename"])
    store_fair_metadata(state["filename"], state["fair_metadata"], state["provenance_chain"])
    state["processing_status"] = "completed"
    update_curation_status(state["filename"], "completed",
                          quality_score=state["quality_assessment"].get("quality_score"))
    _log("store_fair", "Workflow completed", file=state["filename"])
    return state


workflow = StateGraph(WorkflowState)

workflow.add_node("extract_text", extract_pdf_text)
workflow.add_node("extract_fair_react", extract_fair_react)
workflow.add_node("curate_react", curate_react)
workflow.add_node("quality_assurance_react", quality_assurance_react)
workflow.add_node("store_content", store_content)
workflow.add_node("store_fair", store_fair)

workflow.set_entry_point("extract_text")
workflow.add_edge("extract_text", "extract_fair_react")
workflow.add_edge("extract_fair_react", "curate_react")
workflow.add_edge("curate_react", "quality_assurance_react")
workflow.add_edge("quality_assurance_react", "store_content")
workflow.add_edge("store_content", "store_fair")
workflow.add_edge("store_fair", END)

app = workflow.compile()

def process_paper(pdf_path):
    filename = os.path.basename(pdf_path)
    _log("process_paper", "Starting agent workflow", file=filename)
    initial_state = {
        "pdf_path": pdf_path,
        "filename": filename,
        "extracted_text": "",
        "fair_metadata": {},
        "validation_result": {},
        "enrichment_result": {},
        "quality_assessment": {},
        "conflict_resolution": {},
        "provenance_chain": [],
        "processing_status": "processing"
    }
    result = app.invoke(initial_state)
    return result
